"""Small geometric counterexamples using the production graph and constraints."""
from types import SimpleNamespace

import pytest
from ortools.sat.python import cp_model

from src.core import metal_rule, via_rule
from src.solve.graph import LayeredGridGraph


def grid_model(direction, rows, cols):
    """Three-layer grid whose middle layer M0 runs in ``direction``."""
    layers = {0: "PC", 1: "M0", 2: "M1"}
    graph = LayeredGridGraph(
        {name: rows for name in layers.values()},
        {name: cols for name in layers.values()}, layers,
        {"PC": "V" if direction == "H" else "H", "M0": direction,
         "M1": "V" if direction == "H" else "H"},
    )
    model = cp_model.CpModel()
    model.log_comment = lambda *_: None
    cell = SimpleNamespace(opt=model, lgg=graph, geometric_vars={},
                           edge_vars={edge: model.NewBoolVar(str(edge)) for edge in graph.edges()})
    return cell


def track_model(direction, coordinates):
    rows, cols = ([0], coordinates) if direction == "H" else (coordinates, [0])
    return grid_model(direction, rows, cols)


def solve(cell):
    return cp_model.CpSolver().Solve(cell.opt)


def set_geometry(cell, direction, wires, vias=()):
    """Select metal intervals and (position, lower layer) vias on the test track."""
    axis = 2 if direction == "H" else 1
    for (u, v), var in cell.edge_vars.items():
        if u[0] == v[0]:
            on = u[0] == 1 and (u[axis], v[axis]) in wires
        else:
            on = (u[axis], min(u[0], v[0])) in vias
        cell.opt.Add(var == int(on))


@pytest.mark.parametrize("direction", ["H", "V"])
@pytest.mark.parametrize("positions,minimum,feasible", [
    ((0, 20), 15, True),  # unused midpoint must not exclude both ends
    ((0, 10), 15, False),
    ((0, 20), 20, True),  # equality is legal
    ((0, 20), 21, False),
    ((0, 10), 0, True),
])
def test_via_spacing(direction, positions, minimum, feasible):
    cell = track_model(direction, [0, 10, 20])
    set_geometry(cell, direction, [], [(p, 0) for p in positions])
    via_rule.via_separation_rules(cell, {("PC", "M0"): minimum})
    assert solve(cell) == (cp_model.OPTIMAL if feasible else cp_model.INFEASIBLE)


@pytest.mark.parametrize("minimum,feasible", [
    (15, True),  # Manhattan distance is 20; Chebyshev or single-axis distance would be 10
    (20, True),
    (21, False),
])
def test_via_spacing_is_manhattan(minimum, feasible):
    cell = grid_model("H", [0, 10], [0, 10])
    vias = {(0, 0), (10, 10)}
    for (u, v), var in cell.edge_vars.items():
        if u[0] != v[0]:
            cell.opt.Add(var == int(min(u[0], v[0]) == 0 and (u[1], u[2]) in vias))
    via_rule.via_separation_rules(cell, {("PC", "M0"): minimum})
    assert solve(cell) == (cp_model.OPTIMAL if feasible else cp_model.INFEASIBLE)


def test_via_spacing_rejects_layer_pair_without_candidates():
    cell = track_model("H", [0, 10])
    with pytest.raises(ValueError, match="no via candidates"):
        via_rule.via_separation_rules(cell, {("PC", "M1"): 15})  # not adjacent


@pytest.mark.parametrize("direction", ["H", "V"])
@pytest.mark.parametrize("minimum,feasible", [(0, True), (15, True), (20, True), (21, False)])
def test_end_of_line_spacing(direction, minimum, feasible):
    cell = track_model(direction, [0, 10, 20, 30, 40])
    set_geometry(cell, direction, [(0, 10), (30, 40)])
    metal_rule.geometric_vars_in_horizontal_layers(cell)
    metal_rule.geometric_vars_in_vertical_layers(cell)
    rules = {"M0": minimum, "M1": 0}
    metal_rule.eol_rules_in_horizontal_layers(cell, rules)
    metal_rule.eol_rules_in_vertical_layers(cell, rules)
    assert solve(cell) == (cp_model.OPTIMAL if feasible else cp_model.INFEASIBLE)


@pytest.mark.parametrize("direction", ["H", "V"])
@pytest.mark.parametrize("vias,feasible", [
    ([], False),
    ([(0, 0)], True), ([(10, 0)], True), ([(20, 0)], True),
    ([(10, 1)], True),  # via above the layer is also a connection
    ([(30, 0)], False),  # cannot borrow a via across a gap
])
def test_each_metal_segment_requires_a_via(direction, vias, feasible):
    cell = track_model(direction, [0, 10, 20, 30])
    set_geometry(cell, direction, [(0, 10), (10, 20)], vias)
    via_rule.horizontal_metal_must_be_connected_to_via(cell)
    via_rule.vertical_metal_must_be_connected_to_via(cell)
    assert solve(cell) == (cp_model.OPTIMAL if feasible else cp_model.INFEASIBLE)


@pytest.mark.parametrize("direction", ["H", "V"])
@pytest.mark.parametrize("both", [False, True])
def test_separate_segments_need_separate_connections(direction, both):
    cell = track_model(direction, [0, 10, 20, 30])
    vias = [(0, 0)] + ([(30, 1)] if both else [])
    set_geometry(cell, direction, [(0, 10), (20, 30)], vias)
    via_rule.horizontal_metal_must_be_connected_to_via(cell)
    via_rule.vertical_metal_must_be_connected_to_via(cell)
    assert solve(cell) == (cp_model.OPTIMAL if both else cp_model.INFEASIBLE)
