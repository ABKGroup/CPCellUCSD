"""
Signoff checks for generated FinFET standard-cell library GDS files (one GDS
per LIBNAME, one top cell per standard cell, e.g.
output/<LIBNAME>/SH/gds/<LIBNAME>.gds -- see the smtcell_gds Makefile target
and src/gds/gds_FinFET_SH.py). Four independent checks:

  - gate-cut: consecutive (multi-CPP) gate cuts on layer 10/0
  - eol:      End-of-Line metal spacing on M0/M1/M2
  - mar:      Minimum Area Rule (minimum wire length) on M0/M1/M2
  - abutment: EOL violations introduced by placing two cells side by side

=== gate-cut ===

`FinFETLayout.__gate_cut_boundary__`/`__gate_cut__` in src/gds/gds_FinFET_SH.py
draw three different kinds of box onto GateCut layer 10/0:
  - a per-track cut wherever a PMOS/NMOS pair on the same gate track needs
    different signals (the real "gate cut" markers we care about here)
  - a fixed leftmost/rightmost diffusion-break box at the cell's edges
  - full-width VDD/VSS power-rail boxes at the top/bottom of the cell

Only the first kind is subject to the solver's `minimum_gate_cut_length`
config (src/utility/config.py, enforced in src/core/routing.py's
gate_cut_window()): "gate cut is continuous and is at least X CPP long".
Two adjacent per-track cuts, one CPP pitch apart center-to-center, is how a
merged/continuous 2-CPP gate cut shows up in the GDS (there is no single
polygon spanning both tracks -- the per-track boxes are narrower than CPP
and don't touch). This script re-derives that from the GDS directly, so it
independently verifies what the solver's model claims to have enforced.

=== eol / mar ===

For each metal layer (M0/M1/M2, direction/pitch/width/GDS layer number read
from a .layer JSON config), shapes are grouped onto the same track (row for
horizontal layers, column for vertical) and checked against a real,
physical nm threshold supplied directly by the caller (`--eol-nm`/
`--mar-nm`, e.g. an actual foundry DRC value) -- NOT derived from this
repo's own solver config (`eol_c2c_rule`/`mar_c2c_rule` in
src/utility/config.py, enforced during solving by src/core/metal_rule.py on
a 2x-rescaled internal grid, see SOLVER_RESCALE in src/gds/gds_FinFET_SH.py).
EOL measures the literal edge-to-edge gap between the facing ends of two
distinct same-track polygons; MAR measures the literal length of each
polygon along its layer's routing direction. This is a real signoff check
on final geometry against real DRC numbers, independent of the solver's own
internal bookkeeping.

=== abutment ===

Places two cells (by GDS top-cell name) side by side -- translating the
right-hand cell by the left-hand cell's width, matching ordinary same-row
standard-cell abutment (no flip) -- and looks for new EOL violations that
only appear because of that translation (an existing violation entirely
inside one cell should already have been caught by the plain `eol` check).
Every M0/M1/M2 shape is used, since in the generated LEF
(src/utility/genLEF.py) every metal shape is classified as exactly one of
PIN (has an overlapping net label) or OBS (does not) -- OBS+PIN together is
the complete physical metal footprint of the cell. Like `eol`, its
threshold is a real, physical nm value supplied directly by the caller
(`--eol-nm`), not derived from this repo's own solver config.

Usage:
    python -m src.utility.signoff gate-cut --gds output/<LIBNAME>/SH/gds/<LIBNAME>.gds
    python -m src.utility.signoff gate-cut --gds <path> --min-cpp 2 --csv report.csv
    python -m src.utility.signoff eol --gds <path> --layer-config <path>.layer --eol-nm M0=10 M1=24 M2=22.5
    python -m src.utility.signoff mar --gds <path> --layer-config <path>.layer --mar-nm M0=10 M1=72 M2=45
    python -m src.utility.signoff abutment --gds <path> --layer-config <path>.layer --eol-nm M0=10 M1=24 M2=22.5 \\
        --cell-a INV_X1 NAND2_X1 --cell-b INV_X1 NAND2_X1
"""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict

import klayout.db as pya

GATE_CUT_LAYER = (10, 0)
BOUNDARY_LAYER = (100, 0)

# Boundary/rail boxes span nearly the full cell height or width; a real
# per-track cut is short in both directions. See module docstring.
SPAN_RATIO_THRESHOLD = 0.5

DEFAULT_CPP_PITCH_NM = 45.0
DEFAULT_TOLERANCE_NM = 1.0

METAL_LAYER_NAMES = ("M0", "M1", "M2")

# M0/M2 route horizontally and M1 routes vertically in every tech variant
# this repo generates (src/gds/gds_FinFET_SH.py, evaluation/libgen/*/scripts/
# genGdsLef.py); a Cadence .tf tech file doesn't record direction itself
# (unlike the .layer JSON configs), so it's fixed here instead of guessed.
TF_LAYER_DIRECTION = {"M0": "H", "M1": "V", "M2": "H"}

# Tolerance, in nm, used only to cluster boxes onto the same track (row/col)
# when comparing float y-/x-centers -- not a DRC tolerance.
DEFAULT_TRACK_TOLERANCE_NM = 0.5


def load_cpp_pitch_nm(layer_config_path):
    """Read the PC (poly/CPP) pitch, in nm, out of a .layer JSON config."""
    with open(layer_config_path) as f:
        data = json.load(f)
    return float(data["PC"]["pitch"])


def load_layer_geometry(layer_config_path):
    """
    Read M0/M1/M2's GDS layer number, routing direction, pitch and width out
    of a .layer JSON config. Returns {layer_name: {gds_layer, direction,
    pitch, width}}.
    """
    with open(layer_config_path) as f:
        data = json.load(f)
    geometry = {}
    for layer_name in METAL_LAYER_NAMES:
        entry = data[layer_name]
        geometry[layer_name] = {
            "gds_layer": int(entry["layer_number"]),
            "direction": entry["direction"],
            "pitch": float(entry["pitch"]),
            "width": float(entry["width"]),
        }
    return geometry


def _tf_layer_block(text, layer_name):
    m = re.search(rf'Layer\s+"{layer_name}"\s*\{{(.*?)\n\}}', text, re.DOTALL)
    return m.group(1) if m else None


def _tf_field(block, field_name):
    m = re.search(rf'{field_name}\s*=\s*"?([\w.]+)"?', block)
    return float(m.group(1)) if m else None


def load_tf_layer_geometry(tf_path):
    """
    Read M0/M1/M2's GDS layer number, pitch and width directly out of a real
    Cadence .tf tech file (as generated by evaluation/libgen/*/scripts/
    genTechFile.tcl) -- the actual DRC input each library variant is
    generated for, as opposed to the .layer JSON configs, which are a
    separate (and not always matching) source of the same information.
    Direction isn't recorded in a .tf file, so it comes from
    TF_LAYER_DIRECTION. Returns {layer_name: {gds_layer, direction, pitch, width}},
    same shape as load_layer_geometry, skipping any layer not present.
    """
    with open(tf_path) as f:
        text = f.read()
    geometry = {}
    for layer_name in METAL_LAYER_NAMES:
        block = _tf_layer_block(text, layer_name)
        if block is None:
            continue
        geometry[layer_name] = {
            "gds_layer": int(_tf_field(block, "layerNumber")),
            "direction": TF_LAYER_DIRECTION[layer_name],
            "pitch": _tf_field(block, "pitch") * 1000.0,
            "width": _tf_field(block, "defaultWidth") * 1000.0,
        }
    return geometry


def load_tf_eol_mar_nm(tf_path):
    """
    Read M0/M1/M2's real EOL and MAR thresholds, in nm, directly out of a
    Cadence .tf tech file. EOL is `endOfLine1NeighborEndToEndMinSpacing`;
    MAR is a minimum wire length derived from `minArea / defaultWidth`,
    omitted for a layer whose `minArea` is 0 (no constraint -- see
    mar_signoff, which already treats an absent layer as exempt). Returns
    (eol_nm, mar_nm), each {layer_name: threshold_nm}.
    """
    with open(tf_path) as f:
        text = f.read()
    eol_nm, mar_nm = {}, {}
    for layer_name in METAL_LAYER_NAMES:
        block = _tf_layer_block(text, layer_name)
        if block is None:
            continue
        eol_um = _tf_field(block, "endOfLine1NeighborEndToEndMinSpacing")
        if eol_um is not None:
            eol_nm[layer_name] = eol_um * 1000.0
        min_area_um2 = _tf_field(block, "minArea")
        default_width_um = _tf_field(block, "defaultWidth")
        if min_area_um2 and default_width_um:
            mar_nm[layer_name] = min_area_um2 / default_width_um * 1000.0
    return eol_nm, mar_nm


def classify_gate_cut_shapes(boxes):
    """
    Split raw layer 10/0 boxes for one cell into (internal, boundary_or_rail).

    `boxes` is a list of (left, bottom, right, top) tuples in dbu. Classification
    is relative to the combined span of every box in the cell, since boundary
    and rail markers are always present alongside zero or more internal cuts
    (see __gate_cut_boundary__, always called from FinFETLayout.draw()).
    """
    if not boxes:
        return [], []

    min_x = min(b[0] for b in boxes)
    max_x = max(b[2] for b in boxes)
    min_y = min(b[1] for b in boxes)
    max_y = max(b[3] for b in boxes)
    span_w = max_x - min_x
    span_h = max_y - min_y

    internal, boundary_or_rail = [], []
    for b in boxes:
        w = b[2] - b[0]
        h = b[3] - b[1]
        is_rail = span_w > 0 and w >= SPAN_RATIO_THRESHOLD * span_w
        is_boundary = span_h > 0 and h >= SPAN_RATIO_THRESHOLD * span_h
        (boundary_or_rail if (is_rail or is_boundary) else internal).append(b)
    return internal, boundary_or_rail


def group_consecutive_cuts(internal_boxes, cpp_pitch_dbu, tolerance_dbu):
    """
    Group per-track gate-cut boxes into runs of consecutive CPP tracks.

    Boxes are clustered by y-center (gate cuts on different rows never merge),
    then within each row sorted by x-center and chained whenever two
    neighbors are exactly one CPP pitch apart (within tolerance). Returns a
    list of runs, each a list of boxes ordered by x; a run of length 2 is a
    "2-CPP gate cut".
    """
    rows = defaultdict(list)
    for b in internal_boxes:
        yc = (b[1] + b[3]) // 2
        row_key = yc
        for key in rows:
            if abs(key - yc) <= tolerance_dbu:
                row_key = key
                break
        rows[row_key].append(b)

    runs = []
    for row_boxes in rows.values():
        row_boxes = sorted(row_boxes, key=lambda b: (b[0] + b[2]) // 2)
        run = [row_boxes[0]]
        for prev, cur in zip(row_boxes, row_boxes[1:]):
            prev_xc = (prev[0] + prev[2]) // 2
            cur_xc = (cur[0] + cur[2]) // 2
            if abs((cur_xc - prev_xc) - cpp_pitch_dbu) <= tolerance_dbu:
                run.append(cur)
            else:
                runs.append(run)
                run = [cur]
        runs.append(run)
    return runs


def scan_cell_gate_cuts(cell, gate_cut_layer_idx, cpp_pitch_dbu, tolerance_dbu):
    """Return the consecutive-cut runs found on layer 10/0 in one top cell."""
    region = pya.Region(cell.begin_shapes_rec(gate_cut_layer_idx))
    boxes = [(p.bbox().left, p.bbox().bottom, p.bbox().right, p.bbox().top) for p in region.each()]
    internal, _ = classify_gate_cut_shapes(boxes)
    return group_consecutive_cuts(internal, cpp_pitch_dbu, tolerance_dbu)


def gate_cut_signoff(gds_path, cell_names=None, cpp_pitch_nm=DEFAULT_CPP_PITCH_NM,
                      tolerance_nm=DEFAULT_TOLERANCE_NM, min_cpp=None):
    """
    Scan `gds_path` and return one result dict per gate-cut run found:
    {cell, length_cpp, x_start_um, x_end_um, y_center_um, violation}.

    `violation` is only meaningful when `min_cpp` is given (flags runs
    shorter than that as failing signoff).
    """
    layout = pya.Layout()
    layout.read(gds_path)
    dbu = layout.dbu
    gate_cut_layer_idx = layout.layer(*GATE_CUT_LAYER)
    cpp_pitch_dbu = round(cpp_pitch_nm / 1000.0 / dbu)
    tolerance_dbu = max(1, round(tolerance_nm / 1000.0 / dbu))

    results = []
    for cell in layout.top_cells():
        if cell_names and cell.name not in cell_names:
            continue
        runs = scan_cell_gate_cuts(cell, gate_cut_layer_idx, cpp_pitch_dbu, tolerance_dbu)
        for run in runs:
            length = len(run)
            violation = min_cpp is not None and length < min_cpp
            results.append({
                "cell": cell.name,
                "length_cpp": length,
                "x_start_um": round(min(b[0] for b in run) * dbu, 4),
                "x_end_um": round(max(b[2] for b in run) * dbu, 4),
                "y_center_um": round(((run[0][1] + run[0][3]) / 2) * dbu, 4),
                "violation": violation,
            })
    return results


def print_report(results, min_cpp):
    if not results:
        print("[INFO] No internal gate-cut markers found.")
        return

    isolated = [r for r in results if r["length_cpp"] == 1]
    two_cpp = [r for r in results if r["length_cpp"] == 2]
    longer = [r for r in results if r["length_cpp"] > 2]
    threshold_note = f" (signoff requires >= {min_cpp} CPP)" if min_cpp is not None else ""
    print(f"[INFO] Found {len(results)} gate-cut run(s){threshold_note}: "
          f"{len(isolated)} isolated (1-CPP), {len(two_cpp)} 2-CPP, {len(longer)} longer merged run(s).")

    for r in sorted(results, key=lambda r: (r["cell"], r["x_start_um"])):
        tag = "VIOLATION" if r["violation"] else f"{r['length_cpp']}-CPP"
        print(f"  [{tag}] cell={r['cell']} x=[{r['x_start_um']}, {r['x_end_um']}] um "
              f"y_center={r['y_center_um']} um")


def write_csv(results, csv_path):
    if not results:
        print(f"[INFO] No rows to write to {csv_path}.")
        return
    fieldnames = list(results[0].keys())
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"[INFO] Wrote {len(results)} row(s) to {csv_path}")


# =====================================================================
# EOL / MAR (shared geometry helpers)
# =====================================================================

def get_layer_boxes(cell, gds_layer_idx, tag=None):
    """Return every polygon's bbox on `gds_layer_idx` in `cell` as (left, bottom, right, top, tag)."""
    region = pya.Region(cell.begin_shapes_rec(gds_layer_idx))
    return [(p.bbox().left, p.bbox().bottom, p.bbox().right, p.bbox().top, tag) for p in region.each()]


def get_cell_width_dbu(layout, cell):
    """Read a cell's width (in dbu) off its single Boundary layer (100/0) box."""
    boundary_layer_idx = layout.layer(*BOUNDARY_LAYER)
    boxes = get_layer_boxes(cell, boundary_layer_idx)
    if not boxes:
        raise ValueError(f"Cell '{cell.name}' has no shape on the boundary layer {BOUNDARY_LAYER}.")
    return max(b[2] for b in boxes)


def group_by_track(boxes, direction, tolerance_dbu):
    """
    Cluster (left, bottom, right, top, tag) boxes into same-track groups --
    rows (by y-center) for horizontal-direction layers, columns (by x-center)
    for vertical-direction layers -- each sorted along its routing axis.
    Returns a list of (track_center, [boxes]).
    """
    groups = defaultdict(list)
    for b in boxes:
        key = ((b[1] + b[3]) // 2) if direction == "H" else ((b[0] + b[2]) // 2)
        track_key = key
        for existing in groups:
            if abs(existing - key) <= tolerance_dbu:
                track_key = existing
                break
        groups[track_key].append(b)

    tracks = []
    for track_key, group_boxes in groups.items():
        sort_key = (lambda b: b[0]) if direction == "H" else (lambda b: b[1])
        tracks.append((track_key, sorted(group_boxes, key=sort_key)))
    return tracks


def scan_eol_gaps(boxes, direction, threshold_dbu, tolerance_dbu, cross_only=False):
    """
    Group `boxes` onto tracks and yield (prev, cur, gap_dbu) for every
    adjacent pair whose facing-end gap is a nonzero EOL violation
    (0 < gap < threshold). Touching/overlapping boxes (gap <= 0) are treated
    as merged, not a violation. If `cross_only`, only pairs whose tag differs
    are considered (used by the abutment check to ignore purely-internal
    gaps already covered by the plain per-cell EOL check).
    """
    violations = []
    for _, ordered in group_by_track(boxes, direction, tolerance_dbu):
        for prev, cur in zip(ordered, ordered[1:]):
            if cross_only and prev[4] == cur[4]:
                continue
            gap_dbu = (cur[0] - prev[2]) if direction == "H" else (cur[1] - prev[3])
            if 0 < gap_dbu < threshold_dbu:
                violations.append((prev, cur, gap_dbu))
    return violations


def _gap_location_um(prev, cur, direction, dbu):
    """Midpoint of a flagged EOL gap, for reporting."""
    if direction == "H":
        return round((prev[2] + cur[0]) / 2 * dbu, 4), round((prev[1] + prev[3]) / 2 * dbu, 4)
    return round((prev[0] + prev[2]) / 2 * dbu, 4), round((prev[3] + cur[1]) / 2 * dbu, 4)


# =====================================================================
# EOL signoff
# =====================================================================

def eol_signoff(gds_path, layer_geometry, eol_nm, cell_names=None,
                 track_tolerance_nm=DEFAULT_TRACK_TOLERANCE_NM):
    """
    Scan `gds_path` for End-of-Line spacing violations on the layers named in
    `eol_nm` -- a real, physical spacing threshold in nm per layer name
    (e.g. {"M0": 10.0, "M1": 24.0, "M2": 22.5}) supplied directly by the
    caller, not derived from this repo's own solver config. `layer_geometry`
    is {layer_name: {gds_layer, direction, pitch, width}}, from either
    load_layer_geometry (.layer JSON) or load_tf_layer_geometry (.tf tech
    file). Returns one result dict per violation: {cell, layer, gap_nm,
    threshold_nm, x_um, y_um}.
    """
    layout = pya.Layout()
    layout.read(gds_path)
    dbu = layout.dbu
    tolerance_dbu = max(1, round(track_tolerance_nm / 1000.0 / dbu))

    layers_to_check = []
    for layer_name, threshold_nm in eol_nm.items():
        geo = layer_geometry.get(layer_name)
        if geo is None:
            print(f"[WARNING] Unknown layer '{layer_name}' in --eol-nm; not in {list(layer_geometry)}. Skipping.")
            continue
        layers_to_check.append((layer_name, geo, threshold_nm, threshold_nm / 1000.0 / dbu))

    results = []
    for cell in layout.top_cells():
        if cell_names and cell.name not in cell_names:
            continue
        for layer_name, geo, threshold_nm, threshold_dbu in layers_to_check:
            gds_layer_idx = layout.layer(geo["gds_layer"], 0)
            boxes = get_layer_boxes(cell, gds_layer_idx)
            for prev, cur, gap_dbu in scan_eol_gaps(boxes, geo["direction"], threshold_dbu, tolerance_dbu):
                x_um, y_um = _gap_location_um(prev, cur, geo["direction"], dbu)
                results.append({
                    "cell": cell.name,
                    "layer": layer_name,
                    "gap_nm": round(gap_dbu * dbu * 1000.0, 2),
                    "threshold_nm": round(threshold_nm, 2),
                    "x_um": x_um,
                    "y_um": y_um,
                })
    return results


def print_eol_report(results):
    if not results:
        print("[INFO] No EOL violations found.")
        return
    print(f"[INFO] Found {len(results)} EOL violation(s).")
    for r in sorted(results, key=lambda r: (r["cell"], r["layer"], r["x_um"])):
        print(f"  [VIOLATION] cell={r['cell']} layer={r['layer']} gap={r['gap_nm']}nm "
              f"(< {r['threshold_nm']}nm) at ({r['x_um']}, {r['y_um']}) um")


# =====================================================================
# MAR signoff
# =====================================================================

def mar_signoff(gds_path, layer_geometry, mar_nm, cell_names=None):
    """
    Scan `gds_path` for Minimum Area Rule (minimum wire length) violations on
    the layers named in `mar_nm` -- a real, physical minimum-length
    threshold in nm per layer name (e.g. {"M0": 10.0, "M1": 72.0, "M2": 45.0})
    supplied directly by the caller, not derived from this repo's own solver
    config. `layer_geometry` is {layer_name: {gds_layer, direction, pitch,
    width}}, from either load_layer_geometry (.layer JSON) or
    load_tf_layer_geometry (.tf tech file). A layer this repo would
    otherwise exempt as a supervia is exempted simply by leaving it out of
    `mar_nm`. Returns one result dict per violation: {cell, layer,
    length_nm, threshold_nm, x_um, y_um}.
    """
    layout = pya.Layout()
    layout.read(gds_path)
    dbu = layout.dbu

    layers_to_check = []
    for layer_name, threshold_nm in mar_nm.items():
        geo = layer_geometry.get(layer_name)
        if geo is None:
            print(f"[WARNING] Unknown layer '{layer_name}' in --mar-nm; not in {list(layer_geometry)}. Skipping.")
            continue
        layers_to_check.append((layer_name, geo, threshold_nm, threshold_nm / 1000.0 / dbu))

    results = []
    for cell in layout.top_cells():
        if cell_names and cell.name not in cell_names:
            continue
        for layer_name, geo, threshold_nm, threshold_dbu in layers_to_check:
            gds_layer_idx = layout.layer(geo["gds_layer"], 0)
            boxes = get_layer_boxes(cell, gds_layer_idx)
            for b in boxes:
                length_dbu = (b[2] - b[0]) if geo["direction"] == "H" else (b[3] - b[1])
                if length_dbu < threshold_dbu:
                    results.append({
                        "cell": cell.name,
                        "layer": layer_name,
                        "length_nm": round(length_dbu * dbu * 1000.0, 2),
                        "threshold_nm": round(threshold_nm, 2),
                        "x_um": round(b[0] * dbu, 4),
                        "y_um": round(b[1] * dbu, 4),
                    })
    return results


def print_mar_report(results):
    if not results:
        print("[INFO] No MAR violations found.")
        return
    print(f"[INFO] Found {len(results)} MAR violation(s).")
    for r in sorted(results, key=lambda r: (r["cell"], r["layer"], r["x_um"])):
        print(f"  [VIOLATION] cell={r['cell']} layer={r['layer']} length={r['length_nm']}nm "
              f"(< {r['threshold_nm']}nm) at ({r['x_um']}, {r['y_um']}) um")


# =====================================================================
# Abutment EOL signoff
# =====================================================================

def abutment_eol_signoff(gds_path, cell_a_names, cell_b_names, layer_geometry, eol_nm,
                          gds_path_b=None, track_tolerance_nm=DEFAULT_TRACK_TOLERANCE_NM):
    """
    For every (a, b) pair in cell_a_names x cell_b_names, place `b`
    immediately to the right of `a` (translate `b` by `a`'s cell width --
    same orientation, no flip, matching ordinary same-row abutment) and
    report every M0/M1/M2 EOL violation that straddles the two cells, using a
    real, physical EOL threshold in nm per layer (e.g.
    {"M0": 10.0, "M1": 24.0, "M2": 22.5}) supplied directly by the caller.
    `layer_geometry` is {layer_name: {gds_layer, direction, pitch, width}},
    from either load_layer_geometry (.layer JSON) or load_tf_layer_geometry
    (.tf tech file). Assumes `a` and `b` share the same row height/track
    grid, as any two cells in the same generated library do. Returns one
    result dict per violation: {cell_left, cell_right, layer, gap_nm,
    threshold_nm, x_um, y_um}.
    """
    layout_a = pya.Layout()
    layout_a.read(gds_path)
    layout_b = layout_a
    if gds_path_b is not None:
        layout_b = pya.Layout()
        layout_b.read(gds_path_b)
    dbu = layout_a.dbu

    tolerance_dbu = max(1, round(track_tolerance_nm / 1000.0 / dbu))

    results = []
    for cell_a_name in cell_a_names:
        cell_a = layout_a.cell(layout_a.cell_by_name(cell_a_name))
        width_a_dbu = get_cell_width_dbu(layout_a, cell_a)
        for cell_b_name in cell_b_names:
            cell_b = layout_b.cell(layout_b.cell_by_name(cell_b_name))
            for layer_name, threshold_nm in eol_nm.items():
                geo = layer_geometry.get(layer_name)
                if geo is None:
                    continue
                threshold_dbu = threshold_nm / 1000.0 / dbu
                boxes_a = get_layer_boxes(cell_a, layout_a.layer(geo["gds_layer"], 0), tag="A")
                boxes_b_raw = get_layer_boxes(cell_b, layout_b.layer(geo["gds_layer"], 0), tag="B")
                boxes_b = [(l + width_a_dbu, bo, r + width_a_dbu, t, tag) for (l, bo, r, t, tag) in boxes_b_raw]
                combined = boxes_a + boxes_b
                for prev, cur, gap_dbu in scan_eol_gaps(combined, geo["direction"], threshold_dbu,
                                                         tolerance_dbu, cross_only=True):
                    x_um, y_um = _gap_location_um(prev, cur, geo["direction"], dbu)
                    results.append({
                        "cell_left": cell_a_name,
                        "cell_right": cell_b_name,
                        "layer": layer_name,
                        "gap_nm": round(gap_dbu * dbu * 1000.0, 2),
                        "threshold_nm": round(threshold_nm, 2),
                        "x_um": x_um,
                        "y_um": y_um,
                    })
    return results


def print_abutment_report(results):
    if not results:
        print("[INFO] No abutment EOL violations found.")
        return
    print(f"[INFO] Found {len(results)} abutment EOL violation(s).")
    for r in sorted(results, key=lambda r: (r["cell_left"], r["cell_right"], r["layer"])):
        print(f"  [VIOLATION] {r['cell_left']} | {r['cell_right']} layer={r['layer']} "
              f"gap={r['gap_nm']}nm (< {r['threshold_nm']}nm) at ({r['x_um']}, {r['y_um']}) um")


def parse_layer_value_args(values):
    """Parse ["M0=10", "M1=24.0", "M2=22.5"] into {"M0": 10.0, "M1": 24.0, "M2": 22.5}."""
    parsed = {}
    for item in values:
        layer, sep, value = item.partition("=")
        if not sep:
            raise ValueError(f"Expected LAYER=NM (e.g. M0=10), got '{item}'")
        parsed[layer] = float(value)
    return parsed


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Signoff checks for generated FinFET standard-cell GDS files."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gate_cut_p = sub.add_parser("gate-cut", help="Detect consecutive (multi-CPP) gate cuts on layer 10/0.")
    gate_cut_p.add_argument("--gds", required=True, help="Path to the GDS file to scan.")
    gate_cut_p.add_argument("--cell", nargs="*", default=None, help="Restrict to these top-cell names (default: all).")
    gate_cut_p.add_argument("--cpp-pitch-nm", type=float, default=None,
                             help=f"CPP (gate) pitch in nm, used to detect adjacency (default: {DEFAULT_CPP_PITCH_NM}).")
    gate_cut_p.add_argument("--layer-config", default=None,
                             help="Path to a .layer JSON config to read the PC pitch from, instead of --cpp-pitch-nm.")
    gate_cut_p.add_argument("--tolerance-nm", type=float, default=DEFAULT_TOLERANCE_NM,
                             help="Tolerance, in nm, for the adjacency spacing check.")
    gate_cut_p.add_argument("--min-cpp", type=int, default=None,
                             help="If set, flag any gate-cut run shorter than this as a signoff violation "
                                  "(e.g. 2 to require every gate cut span at least 2 CPP) and set the exit code.")
    gate_cut_p.add_argument("--csv", default=None, help="Optional path to write results as CSV.")

    eol_p = sub.add_parser("eol", help="Detect End-of-Line metal spacing violations on real geometry.")
    eol_p.add_argument("--gds", required=True, help="Path to the GDS file to scan.")
    eol_p.add_argument("--cell", nargs="*", default=None, help="Restrict to these top-cell names (default: all).")
    eol_p.add_argument("--layer-config", default=None,
                        help="Path to the .layer JSON config (M0/M1/M2 direction/pitch/width/layer number). "
                             "Not needed if --tf is given.")
    eol_p.add_argument("--eol-nm", nargs="+", default=None, metavar="LAYER=NM",
                        help="Real EOL spacing threshold in nm per layer, e.g. --eol-nm M0=10 M1=24 M2=22.5 "
                             "(an actual DRC value you supply -- not derived from this repo's eol_c2c_rule config). "
                             "Not needed if --tf is given.")
    eol_p.add_argument("--tf", default=None,
                        help="Path to a real Cadence .tf tech file (evaluation/libgen/*/scripts/genTechFile.tcl "
                             "output) to read layer geometry and/or the EOL threshold from directly, in place of "
                             "--layer-config/--eol-nm. An explicit --layer-config or --eol-nm still takes "
                             "precedence over --tf for that piece if both are given.")
    eol_p.add_argument("--track-tolerance-nm", type=float, default=DEFAULT_TRACK_TOLERANCE_NM,
                        help="Tolerance, in nm, used to cluster boxes onto the same track.")
    eol_p.add_argument("--csv", default=None, help="Optional path to write results as CSV.")

    mar_p = sub.add_parser("mar", help="Detect Minimum Area Rule (minimum wire length) violations on real geometry.")
    mar_p.add_argument("--gds", required=True, help="Path to the GDS file to scan.")
    mar_p.add_argument("--cell", nargs="*", default=None, help="Restrict to these top-cell names (default: all).")
    mar_p.add_argument("--layer-config", default=None,
                        help="Path to the .layer JSON config (M0/M1/M2 direction/pitch/width/layer number). "
                             "Not needed if --tf is given.")
    mar_p.add_argument("--mar-nm", nargs="+", default=None, metavar="LAYER=NM",
                        help="Real minimum wire length threshold in nm per layer, e.g. --mar-nm M0=10 M1=72 M2=45 "
                             "(an actual DRC value you supply -- not derived from this repo's mar_c2c_rule config). "
                             "Omit a layer to exempt it (e.g. a supervia layer). Not needed if --tf is given.")
    mar_p.add_argument("--tf", default=None,
                        help="Path to a real Cadence .tf tech file to read layer geometry and/or the MAR "
                             "threshold from directly, in place of --layer-config/--mar-nm. An explicit "
                             "--layer-config or --mar-nm still takes precedence over --tf for that piece if "
                             "both are given.")
    mar_p.add_argument("--csv", default=None, help="Optional path to write results as CSV.")

    abut_p = sub.add_parser("abutment", help="Detect EOL violations introduced by placing two cells side by side.")
    abut_p.add_argument("--gds", required=True, help="GDS containing --cell-a (and --cell-b, unless --gds-b is given).")
    abut_p.add_argument("--gds-b", default=None, help="GDS containing --cell-b, if different from --gds.")
    abut_p.add_argument("--cell-a", nargs="+", required=True, help="Cell(s) placed on the left.")
    abut_p.add_argument("--cell-b", nargs="+", required=True,
                         help="Cell(s) placed on the right (checked as the Cartesian product with --cell-a).")
    abut_p.add_argument("--layer-config", default=None,
                         help="Path to the .layer JSON config (M0/M1/M2 direction/pitch/width/layer number). "
                              "Not needed if --tf is given.")
    abut_p.add_argument("--eol-nm", nargs="+", default=None, metavar="LAYER=NM",
                         help="Real EOL spacing threshold in nm per layer, e.g. --eol-nm M0=10 M1=24 M2=22.5 "
                              "(an actual DRC value you supply -- not derived from this repo's eol_c2c_rule config). "
                              "Not needed if --tf is given.")
    abut_p.add_argument("--tf", default=None,
                         help="Path to a real Cadence .tf tech file to read layer geometry and/or the EOL "
                              "threshold from directly, in place of --layer-config/--eol-nm. An explicit "
                              "--layer-config or --eol-nm still takes precedence over --tf for that piece if "
                              "both are given.")
    abut_p.add_argument("--track-tolerance-nm", type=float, default=DEFAULT_TRACK_TOLERANCE_NM,
                         help="Tolerance, in nm, used to cluster boxes onto the same track.")
    abut_p.add_argument("--csv", default=None, help="Optional path to write results as CSV.")

    return parser


def resolve_layer_geometry(args):
    if args.layer_config:
        return load_layer_geometry(args.layer_config)
    if args.tf:
        return load_tf_layer_geometry(args.tf)
    raise ValueError("Need --layer-config or --tf to determine M0/M1/M2 layer geometry.")


def resolve_eol_nm(args):
    if args.eol_nm:
        return parse_layer_value_args(args.eol_nm)
    if args.tf:
        eol_nm, _ = load_tf_eol_mar_nm(args.tf)
        return eol_nm
    raise ValueError("Need --eol-nm or --tf to determine the EOL threshold.")


def resolve_mar_nm(args):
    if args.mar_nm:
        return parse_layer_value_args(args.mar_nm)
    if args.tf:
        _, mar_nm = load_tf_eol_mar_nm(args.tf)
        return mar_nm
    raise ValueError("Need --mar-nm or --tf to determine the MAR threshold.")


def main():
    args = build_arg_parser().parse_args()

    try:
        if args.command == "gate-cut":
            if args.cpp_pitch_nm is not None:
                cpp_pitch_nm = args.cpp_pitch_nm
            elif args.layer_config is not None:
                cpp_pitch_nm = load_cpp_pitch_nm(args.layer_config)
            else:
                cpp_pitch_nm = DEFAULT_CPP_PITCH_NM

            results = gate_cut_signoff(
                gds_path=args.gds,
                cell_names=set(args.cell) if args.cell else None,
                cpp_pitch_nm=cpp_pitch_nm,
                tolerance_nm=args.tolerance_nm,
                min_cpp=args.min_cpp,
            )
            print_report(results, args.min_cpp)
            if args.csv:
                write_csv(results, args.csv)
            if args.min_cpp is not None:
                violations = [r for r in results if r["violation"]]
                if violations:
                    print(f"[FAIL] {len(violations)} gate-cut run(s) shorter than {args.min_cpp} CPP.")
                    sys.exit(1)
                print(f"[PASS] All gate-cut runs are at least {args.min_cpp} CPP long.")

        elif args.command == "eol":
            results = eol_signoff(
                gds_path=args.gds,
                layer_geometry=resolve_layer_geometry(args),
                eol_nm=resolve_eol_nm(args),
                cell_names=set(args.cell) if args.cell else None,
                track_tolerance_nm=args.track_tolerance_nm,
            )
            print_eol_report(results)
            if args.csv:
                write_csv(results, args.csv)
            if results:
                print(f"[FAIL] {len(results)} EOL violation(s).")
                sys.exit(1)
            print("[PASS] No EOL violations found.")

        elif args.command == "mar":
            results = mar_signoff(
                gds_path=args.gds,
                layer_geometry=resolve_layer_geometry(args),
                mar_nm=resolve_mar_nm(args),
                cell_names=set(args.cell) if args.cell else None,
            )
            print_mar_report(results)
            if args.csv:
                write_csv(results, args.csv)
            if results:
                print(f"[FAIL] {len(results)} MAR violation(s).")
                sys.exit(1)
            print("[PASS] No MAR violations found.")

        elif args.command == "abutment":
            results = abutment_eol_signoff(
                gds_path=args.gds,
                cell_a_names=args.cell_a,
                cell_b_names=args.cell_b,
                layer_geometry=resolve_layer_geometry(args),
                eol_nm=resolve_eol_nm(args),
                gds_path_b=args.gds_b,
                track_tolerance_nm=args.track_tolerance_nm,
            )
            print_abutment_report(results)
            if args.csv:
                write_csv(results, args.csv)
            if results:
                print(f"[FAIL] {len(results)} abutment EOL violation(s).")
                sys.exit(1)
            print("[PASS] No abutment EOL violations found.")

    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
