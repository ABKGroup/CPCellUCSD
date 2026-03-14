"""
Routing-related constraints for FinFET layout optimization.
This module contains all routing constraint implementations.
"""

import math
import re
from absl import logging as absl_logging
from ortools.sat.python import cp_model
from src.utility.entity import Model
from src.utility.util import sliding_windows

_NUM_COL_SDG_ = 3  # number of columns needed for source/drain/gate


def prohibit_routing_to_left_cell_boundaries(finfet):
    """
    Prohibit routing to left cell boundaries.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Prohibiting routing to left cell boundaries ...")
    absl_logging.info(f"\t==\tProhibiting routing to left cell boundaries ...")
    # NOTE: this is a hack to prevent routing to the left cell boundaries
    left_bound_col = 0
    # gather all edge vars in the column
    gathered_edge_vars = []
    for u_edge, v_edge in finfet.lgg.edges():
        if u_edge[2] == left_bound_col or v_edge[2] == left_bound_col:
            gathered_edge_vars.append(finfet.edge_vars[(u_edge, v_edge)])
    # gather all net arc vars in the column
    gathered_net_arc_vars = []
    for net in finfet.circuit.get_nets(with_power_ground=False):
        for u_arc, v_arc in finfet.lgg.arcs():
            if u_arc[2] == left_bound_col or v_arc[2] == left_bound_col:
                gathered_net_arc_vars.append(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
    # gather all net flow vars in the column
    gathered_net_flow_vars = []
    for net in finfet.circuit.get_nets(with_power_ground=False):
        for k in range(net.num_terminals()):
            for u_arc, v_arc in finfet.lgg.arcs():
                if u_arc[2] == left_bound_col or v_arc[2] == left_bound_col:
                    gathered_net_flow_vars.append(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
    # if any edge or net arc or net flow var is used, then it must be 0
    finfet.opt.Add(sum(gathered_edge_vars) == 0)
    finfet.opt.Add(sum(gathered_net_arc_vars) == 0)
    finfet.opt.Add(sum(gathered_net_flow_vars) == 0)


def prohibit_routing_to_right_cell_boundaries(finfet):
    """
    Prohibit routing to right cell boundaries.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Prohibiting routing to right cell boundaries ...")
    absl_logging.info(f"\t==\tProhibiting routing to right cell boundaries ...")
    # NOTE: this is a hack to prevent routing to the right cell boundaries
    for possible_cpp in finfet.plc_ci:
        right_bound_col = (possible_cpp + (_NUM_COL_SDG_ - 1)) * math.ceil(finfet.fin_tech.get_pitch("PC"))
        finfet.opt.log_comment(f"Prohibiting right bound {right_bound_col} at possible_cpp {possible_cpp}...")
        # gather all edge vars in the column
        gathered_edge_vars = []
        for u_edge, v_edge in finfet.lgg.edges():
            if u_edge[2] > right_bound_col or v_edge[2] > right_bound_col:
                gathered_edge_vars.append(finfet.edge_vars[(u_edge, v_edge)])
        # gather all net arc vars in the column
        gathered_net_arc_vars = []
        for net in finfet.circuit.get_nets(with_power_ground=False):
            for u_arc, v_arc in finfet.lgg.arcs():
                if u_arc[2] > right_bound_col or v_arc[2] > right_bound_col:
                    gathered_net_arc_vars.append(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
        # gather all net flow vars in the column
        gathered_net_flow_vars = []
        for net in finfet.circuit.get_nets(with_power_ground=False):
            for k in range(net.num_terminals()):
                for u_arc, v_arc in finfet.lgg.arcs():
                    if u_arc[2] > right_bound_col or v_arc[2] > right_bound_col:
                        gathered_net_flow_vars.append(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
        # if any edge or net arc or net flow var is used, then it must be 0
        cpp_bool = finfet.opt.NewBoolVar(f"cpp_is_{possible_cpp}")
        finfet.opt.Add(finfet.cpp_cost == possible_cpp).OnlyEnforceIf(cpp_bool)
        finfet.opt.Add(finfet.cpp_cost != possible_cpp).OnlyEnforceIf(cpp_bool.Not())
        finfet.opt.Add(sum(gathered_edge_vars) == 0).OnlyEnforceIf(cpp_bool)
        finfet.opt.Add(sum(gathered_net_arc_vars) == 0).OnlyEnforceIf(cpp_bool)
        finfet.opt.Add(sum(gathered_net_flow_vars) == 0).OnlyEnforceIf(cpp_bool)


def bind_gate_sharing_to_columns(finfet, db_as_gs=True):
    """
    Bind gate sharing at column.

    Args:
        finfet: The FinFET instance
        db_as_gs: Whether to treat diffusion break as gate sharing (default True)
    """
    finfet.opt.log_comment(f"Binding gate sharing at column ...")
    for ci in finfet.plc_ci:
        col_r = finfet.lgg.col_in_layer("PC", ci + 1)
        finfet.gate_share_at_col_vars[col_r] = finfet.opt.NewBoolVar(f"gate_share_at_col_{col_r}")
        gate_share = finfet.gate_share_at_col_vars[col_r]

        has_tran = finfet.has_tran_at_ci_vars[ci]

        # 3) Build existing per-pair "tran_gate_share_at_col" list
        tmp_gate_share_vars_at_col = []
        for key, gs_var in finfet.gate_share_pair_vars.items():
            m = re.match(r"gate_share_(M\w+)_(M\w+)_(\w+)", key)
            if not m:
                continue
            t1, t2, net = m.group(1), m.group(2), m.group(3)
            p1 = finfet.placed_tran_ci_vars[(t1, ci)]
            p2 = finfet.placed_tran_ci_vars[(t2, ci)]
            tv = finfet.opt.NewBoolVar(f"tran_gate_share_at_col_{t1}_{t2}_{net}_{col_r}")
            # tv is true if and only if ...
            finfet.opt.Add(tv == 1).OnlyEnforceIf([gs_var, p1, p2])
            finfet.opt.Add(gs_var == 1).OnlyEnforceIf(tv)
            finfet.opt.Add(p1 == 1).OnlyEnforceIf(tv)
            finfet.opt.Add(p2 == 1).OnlyEnforceIf(tv)
            tmp_gate_share_vars_at_col.append(tv)

        # 4) Now: gate_share should be true iff (some tv is true) OR (no transistor at ci)
        # 4a) If gate_share then enforce OR(tmp_vars) OR (not has_tran)
        if db_as_gs:
            finfet.opt.AddBoolOr(tmp_gate_share_vars_at_col + [has_tran.Not()]).OnlyEnforceIf(gate_share)
        else:
            finfet.opt.AddBoolOr(tmp_gate_share_vars_at_col).OnlyEnforceIf(gate_share)
        # 4b) If any tv is true, force gate_share
        for tv in tmp_gate_share_vars_at_col:
            finfet.opt.AddImplication(tv, gate_share)
        # 4c) If no transistor, force gate_share (NOTE: not counting diffusion break as gate cut)
        finfet.opt.AddImplication(has_tran.Not(), gate_share)

        # 5) Finally: if gate_share is false => no tv is true AND at least one transistor is placed
        finfet.opt.Add(sum(tmp_gate_share_vars_at_col) == 0).OnlyEnforceIf(gate_share.Not())
        finfet.opt.AddBoolOr(has_tran).OnlyEnforceIf(gate_share.Not())
    # ^ always let the first gate col be shared
    finfet.opt.log_comment(f"Allowing gate sharing at the first column ...")
    finfet.opt.Add(finfet.gate_share_at_col_vars[finfet.lgg.col_in_layer("PC", 2)] == 1)


def gate_cut_window(finfet):
    """
    Define gate cut windows.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Defining gate cut windows ...")
    gate_cut_windows = sliding_windows(list(finfet.gate_share_at_col_vars.keys()), finfet.min_gate_cut_len)
    finfet.gate_cut_window_vars = {windows: finfet.opt.NewBoolVar(f"gate_cut_window_{windows}") for windows in gate_cut_windows}
    # ^ Boundary condition for gate cut and diffusion break
    finfet.opt.log_comment(f"Enforcing gate cut boundary condition and diffusion break ...")
    absl_logging.info(f"\t==\tEnforcing gate cut boundary condition to {finfet.min_boundary_col} and {finfet.max_boundary_col} ...")
    for gcw in gate_cut_windows:
        can_be_oob = False
        for gc in gcw:
            if gc > finfet.min_boundary_col:
                can_be_oob = True
                break
        if can_be_oob:
            # this gate cut is only valid if the cpp_cost is actually greater than it
            max_col_in_gcw = max(gcw)
            max_ci_in_gcw = finfet.lgg.col_index_in_layer("PC", max_col_in_gcw)
            # seek for the immediate placeable column to the left
            plc_ci_in_gcw = max_ci_in_gcw - 1
            # if this windows is valid, then the cpp_cost must be greater than the max plc col in the window
            finfet.opt.Add(finfet.cpp_cost >= plc_ci_in_gcw).OnlyEnforceIf(finfet.gate_cut_window_vars[gcw])
    # ^ Binding gate cut windows to gate cut
    finfet.opt.log_comment(f"Binding gate cut windows to gate cut ...")
    for gcw in gate_cut_windows:
        gs_vars = [finfet.gate_share_at_col_vars[col] for col in gcw]
        gs_vars_negated = [var.Not() for var in gs_vars]
        gcw_var = finfet.gate_cut_window_vars[gcw]
        # if the gate cut window is valid, then the gate share vars must be 0
        finfet.opt.Add(gcw_var == 1).OnlyEnforceIf(gs_vars_negated)
        for gs_var in gs_vars:
            # if the gate share vars are 0, then the gate cut window must be valid
            finfet.opt.Add(gcw_var == 0).OnlyEnforceIf(gs_var)

    # ^ enforce that gate cut is continous and is at least X CPP long
    finfet.opt.log_comment(f"Enforcing gate cut continuity ...")
    for gcol in finfet.gate_share_at_col_vars.keys():
        possible_gate_cuts = []
        for gcw in gate_cut_windows:
            if gcol in gcw:
                possible_gate_cuts.append(finfet.gate_cut_window_vars[gcw])
        # if gate cut at gcol, then exactly one of the gate cut windows must be true
        # NOTE: if you want gate cut beyond the given limit, set to at least 1
        finfet.opt.Add(sum(possible_gate_cuts) == 1).OnlyEnforceIf(finfet.gate_share_at_col_vars[gcol].Not())


def prohibit_pc_routing_in_diffusion_break_cols(finfet):
    """
    Enforce if a db is placed at col, then no net arc and no net edge can use the immediate right gate col.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing if a db is placed at col, then no net arc and no net edge can use the immediate right gate col ...")
    # NOTE diffusion break should only be inserted in plc columns
    for ci in finfet.plc_ci:
        pdb_var = finfet.db_pmos_cols_vars[ci]
        ndb_var = finfet.db_nmos_cols_vars[ci]
        c = finfet.lgg.col_in_layer("PC", ci)
        try:
            cr = finfet.lgg.col_in_layer("PC", ci + 1)
        except IndexError:
            continue
        # NOTE: do not disable crr as it be used by the transistor immediately to the right
        # PMOS
        gathered_pmos_edge_vars = []
        gathered_pmos_net_arc_vars = []
        gathered_pmos_net_flow_vars = []
        pmos_row = []
        for ri in finfet.pmos_pin_access_ri:
            pmos_row.append(finfet.lgg.row_in_layer("PC", ri))
        for u_edge, v_edge in finfet.lgg.edges():
            if u_edge[0] == 0 and u_edge[1] in pmos_row and u_edge[2] == cr:
                gathered_pmos_edge_vars.append(finfet.edge_vars[(u_edge, v_edge)])
            elif v_edge[0] == 0 and v_edge[1] in pmos_row and v_edge[2] == cr:
                gathered_pmos_edge_vars.append(finfet.edge_vars[(u_edge, v_edge)])
        for net in finfet.circuit.get_nets(with_power_ground=False):
            for u_arc, v_arc in finfet.lgg.arcs():
                if u_arc[0] == 0 and u_arc[1] in pmos_row and u_arc[2] == cr:
                    gathered_pmos_net_arc_vars.append(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                elif v_arc[0] == 0 and v_arc[1] in pmos_row and v_arc[2] == cr:
                    gathered_pmos_net_arc_vars.append(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
        for net in finfet.circuit.get_nets(with_power_ground=False):
            for k in range(net.num_terminals()):
                for u_arc, v_arc in finfet.lgg.arcs():
                    if u_arc[0] == 0 and u_arc[1] in pmos_row and u_arc[2] == cr:
                        gathered_pmos_net_flow_vars.append(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    elif v_arc[0] == 0 and v_arc[1] in pmos_row and v_arc[2] == cr:
                        gathered_pmos_net_flow_vars.append(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])

        # if a db is set, then no net arc and no net edge can use col
        finfet.opt.Add(sum(gathered_pmos_edge_vars) == 0).OnlyEnforceIf(pdb_var)
        finfet.opt.Add(sum(gathered_pmos_net_arc_vars) == 0).OnlyEnforceIf(pdb_var)
        finfet.opt.Add(sum(gathered_pmos_net_flow_vars) == 0).OnlyEnforceIf(pdb_var)
        # NMOS
        gathered_nmos_edge_vars = []
        gathered_nmos_net_arc_vars = []
        gathered_nmos_net_flow_vars = []
        nmos_row = []
        for ri in finfet.nmos_pin_access_ri:
            nmos_row.append(finfet.lgg.row_in_layer("PC", ri))
        for u_edge, v_edge in finfet.lgg.edges():
            if u_edge[0] == 0 and u_edge[1] in nmos_row and u_edge[2] == cr:
                gathered_nmos_edge_vars.append(finfet.edge_vars[(u_edge, v_edge)])
            elif v_edge[0] == 0 and v_edge[1] in nmos_row and v_edge[2] == cr:
                gathered_nmos_edge_vars.append(finfet.edge_vars[(u_edge, v_edge)])
        for net in finfet.circuit.get_nets(with_power_ground=False):
            for u_arc, v_arc in finfet.lgg.arcs():
                if u_arc[0] == 0 and u_arc[1] in nmos_row and u_arc[2] == cr:
                    gathered_nmos_net_arc_vars.append(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                elif v_arc[0] == 0 and v_arc[1] in nmos_row and v_arc[2] == cr:
                    gathered_nmos_net_arc_vars.append(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
        for net in finfet.circuit.get_nets(with_power_ground=False):
            for k in range(net.num_terminals()):
                for u_arc, v_arc in finfet.lgg.arcs():
                    if u_arc[0] == 0 and u_arc[1] in nmos_row and u_arc[2] == cr:
                        gathered_nmos_net_flow_vars.append(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    elif v_arc[0] == 0 and v_arc[1] in nmos_row and v_arc[2] == cr:
                        gathered_nmos_net_flow_vars.append(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
        # if a db is set, then no net arc and no net edge can use col
        finfet.opt.Add(sum(gathered_nmos_edge_vars) == 0).OnlyEnforceIf(ndb_var)
        finfet.opt.Add(sum(gathered_nmos_net_arc_vars) == 0).OnlyEnforceIf(ndb_var)
        finfet.opt.Add(sum(gathered_nmos_net_flow_vars) == 0).OnlyEnforceIf(ndb_var)


def enforce_CA_pickup_for_gate_cut(finfet):
    """
    Enforce CA pickup for gate cut.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing CA pickup for gate cut ...")
    absl_logging.info(f"\t==\tEnforcing CA pickup for gate cut ...")
    # if there is a gate cut, then the CA must be picked up
    for gcol in finfet.gate_share_at_col_vars.keys():
        gate_share_var = finfet.gate_share_at_col_vars[gcol]
        gathered_edge_vars = []
        # middle row access
        if finfet.fin_tech.height_config == "SH" and finfet.fin_tech.num_rt_track == 4:
            first_ri = 1
            second_ri = 2
            first_row = finfet.lgg.row_in_layer("PC", first_ri)
            second_row = finfet.lgg.row_in_layer("PC", second_ri)
            # gather all edge vars in the column
            for u_edge, v_edge in finfet.lgg.edges():
                if u_edge[0] == 0 and v_edge[0] == 1:
                    if (u_edge[1] == first_row and v_edge[1] == first_row) or (u_edge[1] == second_row and v_edge[1] == second_row):
                        if u_edge[2] == gcol and v_edge[2] == gcol:
                            gathered_edge_vars.append(finfet.edge_vars[(u_edge, v_edge)])
            # gather all net arc vars in the column
            gathered_net_arc_vars = []
            for net in finfet.circuit.get_nets(with_power_ground=False):
                for u_arc, v_arc in finfet.lgg.arcs():
                    if u_arc[0] == 0 and v_arc[0] == 1:
                        if (u_arc[1] == first_row and v_arc[1] == first_row) or (u_arc[1] == second_row and v_arc[1] == second_row):
                            if u_arc[2] == gcol and v_arc[2] == gcol:
                                gathered_net_arc_vars.append(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
            # gather all net flow vars in the column
            gathered_net_flow_vars = []
            for net in finfet.circuit.get_nets(with_power_ground=False):
                for k in range(net.num_terminals()):
                    for u_arc, v_arc in finfet.lgg.arcs():
                        if u_arc[0] == 0 and v_arc[0] == 1:
                            if (u_arc[1] == first_row and v_arc[1] == first_row) or (u_arc[1] == second_row and v_arc[1] == second_row):
                                if u_arc[2] == gcol and v_arc[2] == gcol:
                                    gathered_net_flow_vars.append(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
        elif finfet.fin_tech.height_config == "SH" and finfet.fin_tech.num_rt_track == 3:
            first_ri = 1
            first_row = finfet.lgg.row_in_layer("PC", first_ri)
            # gather all edge vars in the column
            for u_edge, v_edge in finfet.lgg.edges():
                if u_edge[0] == 0 and v_edge[0] == 1:
                    if u_edge[1] == first_row and v_edge[1] == first_row:
                        if u_edge[2] == gcol and v_edge[2] == gcol:
                            gathered_edge_vars.append(finfet.edge_vars[(u_edge, v_edge)])
            # gather all net arc vars in the column
            gathered_net_arc_vars = []
            for net in finfet.circuit.get_nets(with_power_ground=False):
                for u_arc, v_arc in finfet.lgg.arcs():
                    if u_arc[0] == 0 and v_arc[0] == 1:
                        if u_arc[1] == first_row and v_arc[1] == first_row:
                            if u_arc[2] == gcol and v_arc[2] == gcol:
                                gathered_net_arc_vars.append(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
            # gather all net flow vars in the column
            gathered_net_flow_vars = []
            for net in finfet.circuit.get_nets(with_power_ground=False):
                for k in range(net.num_terminals()):
                    for u_arc, v_arc in finfet.lgg.arcs():
                        if u_arc[0] == 0 and v_arc[0] == 1:
                            if u_arc[1] == first_row and v_arc[1] == first_row:
                                if u_arc[2] == gcol and v_arc[2] == gcol:
                                    gathered_net_flow_vars.append(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])

        finfet.opt.Add(sum(gathered_edge_vars) == 0).OnlyEnforceIf(gate_share_var.Not())
        finfet.opt.Add(sum(gathered_net_arc_vars) == 0).OnlyEnforceIf(gate_share_var.Not())
        finfet.opt.Add(sum(gathered_net_flow_vars) == 0).OnlyEnforceIf(gate_share_var.Not())


def limit_gate_contact(finfet, num_contact=1):
    """
    Limit gate contact to specified number.

    Args:
        finfet: The FinFET instance
        num_contact: Maximum number of gate contacts (default 1)
    """
    finfet.opt.log_comment(f"Limiting gate contact to {num_contact} ...")
    for ci in finfet.plc_ci:
        col_r = finfet.lgg.col_in_layer("PC", ci + 1)
        gs_col_var = finfet.gate_share_at_col_vars[col_r]
        # if gs_col_var is true, then we can have at most num_contact gate contacts
        pmos_contact_edge_vars = finfet.gather_via_vars_in_pmos_region(col=col_r)
        nmos_contact_edge_vars = finfet.gather_via_vars_in_nmos_region(col=col_r)
        assert len(pmos_contact_edge_vars) == len(nmos_contact_edge_vars), "PMOS and NMOS contact edge vars must be of the same length"
        # if gate sharing is true, then we can have at most num_contact gate contacts
        finfet.opt.Add(sum(pmos_contact_edge_vars + nmos_contact_edge_vars) <= num_contact).OnlyEnforceIf(gs_col_var)
        # if gate sharing is false, then we can have at most num_contact on each side
        finfet.opt.Add(sum(pmos_contact_edge_vars) <= num_contact).OnlyEnforceIf(gs_col_var.Not())
        finfet.opt.Add(sum(nmos_contact_edge_vars) <= num_contact).OnlyEnforceIf(gs_col_var.Not())


def bind_lisd_sharing_to_columns(finfet):
    """
    Bind LISD sharing at column.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Binding lisd sharing at column ...")

    # First, collect all unique columns that need sharing variables
    all_sharing_cols = set()
    for ci in finfet.plc_ci:
        col = finfet.lgg.col_in_layer("PC", ci)
        col_rr = finfet.lgg.col_in_layer("PC", ci + 2)
        all_sharing_cols.add(col)
        all_sharing_cols.add(col_rr)

    # Create sharing variables for all unique columns
    for col in all_sharing_cols:
        if col not in finfet.lisd_share_at_col_vars:
            finfet.lisd_share_at_col_vars[col] = finfet.opt.NewBoolVar(f"lisd_share_at_col_{col}")

    for ci in finfet.plc_ci:
        col = finfet.lgg.col_in_layer("PC", ci)
        col_rr = finfet.lgg.col_in_layer("PC", ci + 2)

        lisd_share_col = finfet.lisd_share_at_col_vars[col]
        lisd_share_col_rr = finfet.lisd_share_at_col_vars[col_rr]

        has_tran = finfet.has_tran_at_ci_vars[ci]

        # 3) Build per-pair "tran_lisd_share_at_col" lists for both columns
        lisd_share_vars_at_col = []
        lisd_share_vars_at_col_rr = []

        for key, ls_var in finfet.lisd_share_pair_vars.items():
            m = re.match(r"lisd_share_(M\w+)_(M\w+)_(\w+)", key)
            if not m:
                continue

            t1, t2, net = m.group(1), m.group(2), m.group(3)
            p1 = finfet.placed_tran_ci_vars[(t1, ci)]
            p2 = finfet.placed_tran_ci_vars[(t2, ci)]
            f1 = finfet.transistor_vars[t1].flip_var
            f2 = finfet.transistor_vars[t2].flip_var
            sn1 = finfet.circuit.transistors[t1].source
            dn1 = finfet.circuit.transistors[t1].drain
            sn2 = finfet.circuit.transistors[t2].source
            dn2 = finfet.circuit.transistors[t2].drain

            # Create variables for sharing at col and col_rr
            tv = finfet.opt.NewBoolVar(f"tran_lisd_share_at_col_{t1}_{t2}_{net}_{col}")
            tv_rr = finfet.opt.NewBoolVar(f"tran_lisd_share_at_colrr_{t1}_{t2}_{net}_{col_rr}")

            # Add constraints based on which nets are shared
            if sn1 == sn2:  # both source nets
                # For col (not flipped case)
                finfet.opt.AddBoolAnd([ls_var, p1, p2, f1.Not(), f2.Not()]).OnlyEnforceIf(tv)
                finfet.opt.AddBoolOr([ls_var.Not(), p1.Not(), p2.Not(), f1, f2]).OnlyEnforceIf(tv.Not())

                # For col_rr (flipped case)
                finfet.opt.AddBoolAnd([ls_var, p1, p2, f1, f2]).OnlyEnforceIf(tv_rr)
                finfet.opt.AddBoolOr([ls_var.Not(), p1.Not(), p2.Not(), f1.Not(), f2.Not()]).OnlyEnforceIf(tv_rr.Not())

            elif dn1 == dn2:  # both drain nets
                # For col (flipped case)
                finfet.opt.AddBoolAnd([ls_var, p1, p2, f1, f2]).OnlyEnforceIf(tv)
                finfet.opt.AddBoolOr([ls_var.Not(), p1.Not(), p2.Not(), f1.Not(), f2.Not()]).OnlyEnforceIf(tv.Not())

                # For col_rr (not flipped case)
                finfet.opt.AddBoolAnd([ls_var, p1, p2, f1.Not(), f2.Not()]).OnlyEnforceIf(tv_rr)
                finfet.opt.AddBoolOr([ls_var.Not(), p1.Not(), p2.Not(), f1, f2]).OnlyEnforceIf(tv_rr.Not())

            elif sn1 == dn2:  # source of t1 and drain of t2
                # For col (mixed case 1)
                finfet.opt.AddBoolAnd([ls_var, p1, p2, f1.Not(), f2]).OnlyEnforceIf(tv)
                finfet.opt.AddBoolOr([ls_var.Not(), p1.Not(), p2.Not(), f1, f2.Not()]).OnlyEnforceIf(tv.Not())

                # For col_rr (mixed case 2)
                finfet.opt.AddBoolAnd([ls_var, p1, p2, f1, f2.Not()]).OnlyEnforceIf(tv_rr)
                finfet.opt.AddBoolOr([ls_var.Not(), p1.Not(), p2.Not(), f1.Not(), f2]).OnlyEnforceIf(tv_rr.Not())

            elif dn1 == sn2:  # drain of t1 and source of t2
                # For col (mixed case 2)
                finfet.opt.AddBoolAnd([ls_var, p1, p2, f1, f2.Not()]).OnlyEnforceIf(tv)
                finfet.opt.AddBoolOr([ls_var.Not(), p1.Not(), p2.Not(), f1.Not(), f2]).OnlyEnforceIf(tv.Not())

                # For col_rr (mixed case 1)
                finfet.opt.AddBoolAnd([ls_var, p1, p2, f1.Not(), f2]).OnlyEnforceIf(tv_rr)
                finfet.opt.AddBoolOr([ls_var.Not(), p1.Not(), p2.Not(), f1, f2.Not()]).OnlyEnforceIf(tv_rr.Not())

            else:
                raise ValueError(f"Transistor {t1} and {t2} do not share a source or drain net: {sn1}, {dn1} vs {sn2}, {dn2}")

            lisd_share_vars_at_col.append(tv)
            lisd_share_vars_at_col_rr.append(tv_rr)

        # 4) Link column sharing variables to individual pair sharing variables
        # Only process constraints for columns that are actually used in this ci
        if lisd_share_vars_at_col:
            finfet.opt.AddBoolOr(lisd_share_vars_at_col + [has_tran.Not()]).OnlyEnforceIf(lisd_share_col)
            finfet.opt.Add(sum(lisd_share_vars_at_col) == 0).OnlyEnforceIf([lisd_share_col.Not(), has_tran])
        else:
            # If no sharing variables, sharing only depends on transistor presence
            finfet.opt.AddImplication(has_tran.Not(), lisd_share_col)
            finfet.opt.AddImplication(has_tran, lisd_share_col.Not())

        if lisd_share_vars_at_col_rr:
            finfet.opt.AddBoolOr(lisd_share_vars_at_col_rr + [has_tran.Not()]).OnlyEnforceIf(lisd_share_col_rr)
            finfet.opt.Add(sum(lisd_share_vars_at_col_rr) == 0).OnlyEnforceIf([lisd_share_col_rr.Not(), has_tran])
        else:
            # If no sharing variables, sharing only depends on transistor presence
            finfet.opt.AddImplication(has_tran.Not(), lisd_share_col_rr)
            finfet.opt.AddImplication(has_tran, lisd_share_col_rr.Not())


def limit_lisd_contact(finfet, num_contact=1):
    """
    Limit LISD contact to specified number.

    Args:
        finfet: The FinFET instance
        num_contact: Maximum number of LISD contacts (default 1)
    """
    finfet.opt.log_comment(f"Limiting lisd contact to {num_contact} ...")
    for ci in finfet.sd_ci:
        col = finfet.lgg.col_in_layer("PC", ci)
        lisd_share_col_var = finfet.lisd_share_at_col_vars[col]
        # if lisd sharing is true, then we can have at most num_contact lisd contacts
        pmos_contact_edge_vars = finfet.gather_via_vars_in_pmos_region(col=col)
        nmos_contact_edge_vars = finfet.gather_via_vars_in_nmos_region(col=col)
        assert len(pmos_contact_edge_vars) == len(nmos_contact_edge_vars), "PMOS and NMOS contact edge vars must be of the same length"
        # if lisd sharing is true, then we can have at most num_contact lisd contacts
        finfet.opt.Add(sum(pmos_contact_edge_vars + nmos_contact_edge_vars) <= num_contact).OnlyEnforceIf(lisd_share_col_var)
        # if lisd sharing is false, then we can have at most num_contact on each side
        finfet.opt.Add(sum(pmos_contact_edge_vars) <= num_contact).OnlyEnforceIf(lisd_share_col_var.Not())
        finfet.opt.Add(sum(nmos_contact_edge_vars) <= num_contact).OnlyEnforceIf(lisd_share_col_var.Not())


def link_flow_to_arc(finfet):
    """
    Link flow variables to arc usage.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Linking flow variables to arc usage ...")
    # NOTE: flow is the minimum route. arc is on top of the flow and can be extended as needed (satisfy DR). edge is used to abstract the flow
    for net in finfet.circuit.get_nets(with_power_ground=False):
        for u_arc, v_arc in finfet.lgg.arcs():
            for k in range(finfet.net_to_flow_cnt[net.name]):
                # if there is flow, then there must be an arc
                # NOTE: in SMTCell, arc can exist without flow
                finfet.opt.AddImplication(
                    finfet.net_flow_vars[(net.name, k, u_arc, v_arc)],
                    finfet.net_arc_vars[(net.name, u_arc, v_arc)],
                )


def link_arc_to_edge(finfet):
    """
    Link arc variables to edge usage.

    Args:
        finfet: The FinFET instance
    """
    for u, v in finfet.lgg.edges():
        # net arc cannot go in both directions
        finfet.opt.Add(
            sum(
                finfet.net_arc_vars[(net.name, u, v)] + finfet.net_arc_vars[(net.name, v, u)]
                for net in finfet.circuit.get_nets(with_power_ground=False)
                if (net.name, u, v) in finfet.net_arc_vars and (net.name, v, u) in finfet.net_arc_vars
            )
            <= 1
        )
        # Link edge usage to net arc usage
        conditions_for_edge_usage = []
        for net in finfet.circuit.get_nets(with_power_ground=False):
            if (net.name, u, v) in finfet.net_arc_vars and (
                net.name,
                v,
                u,
            ) in finfet.net_arc_vars:
                conditions_for_edge_usage.append(finfet.net_arc_vars[(net.name, u, v)])
                conditions_for_edge_usage.append(finfet.net_arc_vars[(net.name, v, u)])
        finfet.opt.AddBoolOr(conditions_for_edge_usage).OnlyEnforceIf(finfet.edge_vars[(u, v)])
        finfet.opt.Add(sum(conditions_for_edge_usage) == 0).OnlyEnforceIf(finfet.edge_vars[(u, v)].Not())

    # also forbid flow for using the same edge
    for net in finfet.circuit.get_nets(with_power_ground=False):
        for k in range(finfet.net_to_flow_cnt[net.name]):
            for u, v in finfet.lgg.edges():
                # forbid using (u, v) and (v, u) at the same time
                finfet.opt.Add(finfet.net_flow_vars[(net.name, k, u, v)] + finfet.net_flow_vars[(net.name, k, v, u)] <= 1)


def net_has_one_src_and_k_terminals(finfet):
    """
    Enforce net unique edge constraint.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing net unique edge constraint ...")
    for net in finfet.circuit.get_nets(with_power_ground=False):
        # --- Constraint: Each net must have exactly one source node chosen ---
        source_candidates_for_net = [finfet.node_is_src_vars[net.name][node] for node in finfet.node_is_src_vars[net.name]]
        if source_candidates_for_net:
            finfet.opt.Add(sum(source_candidates_for_net) == 1)
        else:
            absl_logging.error(f"Net {net.name} has no potential source locations defined.")

        # --- Constraint: Each net must have exactly one k-th terminal chosen ---
        for k in range(net.num_terminals()):
            # --- Constraint: For each k of a net, exactly one node is chosen as its k-th terminal ---
            kth_terminal_candidates = [finfet.node_is_term_vars[net.name][k][node] for node in finfet.node_is_term_vars[net.name][k].keys()]
            if kth_terminal_candidates:
                finfet.opt.Add(sum(kth_terminal_candidates) == 1)
            else:
                absl_logging.error(f"Net {net.name}, terminal {k} has no potential locations defined.")


def net_src_node_uniqueness(finfet):
    """
    Enforce a node cannot be a source for more than one net.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing a node cannot be a source for more than one net ...")
    for node in finfet.lgg.nodes():
        if finfet.fin_tech.height_config == "SH" and finfet.fin_tech.num_rt_track == 3:
            # skip middle routing
            if node[1] == 48:
                continue
        tmp_node_is_src_vars = []
        for net in finfet.circuit.get_nets(with_power_ground=False):
            if node in finfet.node_is_src_vars[net.name]:
                tmp_node_is_src_vars.append(finfet.node_is_src_vars[net.name][node])
        # At most one source can chosen by a node
        if len(tmp_node_is_src_vars) > 0:
            finfet.opt.Add(sum(tmp_node_is_src_vars) <= 1)


def net_term_node_uniqueness(finfet):
    """
    Enforce a node cannot be a terminal for more than one net.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing a node cannot be a terminal for more than one net ...")
    for node in finfet.lgg.nodes():
        if finfet.fin_tech.height_config == "SH" and finfet.fin_tech.num_rt_track == 3:
            # skip middle routing
            if node[1] == 48:
                continue
        tmp_node_is_term_vars = []
        for net in finfet.circuit.get_nets(with_power_ground=False):
            # NOTE: abstract to above flow level to allow flow overlapping
            tmp_term_placed_var = finfet.opt.NewBoolVar(f"{net.name}_isterm_placed_at_{node}")
            tmp_node_is_term_vars.append(tmp_term_placed_var)
            tmp_net_term_vars = []  # gather var for summation
            for k in range(net.num_terminals()):
                if node in finfet.node_is_term_vars[net.name][k]:
                    # if term is placed at node, then abstract var must be true
                    finfet.opt.AddImplication(finfet.node_is_term_vars[net.name][k][node], tmp_term_placed_var)
                    tmp_net_term_vars.append(finfet.node_is_term_vars[net.name][k][node])
                # if no term is placed at node, then all term node cannot be placed here.
        # TODO: test this!!!
        # at each node, there can only be one terminal node from one of the nets to be placed here
        finfet.opt.Add(sum(tmp_node_is_term_vars) <= 1)

        # At most one terminal can chosen by a node
        if len(tmp_node_is_term_vars) > 0:
            finfet.opt.Add(sum(tmp_node_is_term_vars) <= 1)


def net_SON_node_uniqueness(finfet):
    """
    Enforce an SON terminal cannot be a terminal for more than one net.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing an SON terminal cannot be a terminal for more than one net ...")
    # NOTE pin rule can also be enforced here
    for node in finfet.son_terminal_nodes["M1"]:
        tmp_SON_vars_for_nets = []  # node view
        for net in finfet.circuit.get_nets(with_power_ground=False):
            if not net.is_io_net():
                continue
            for k in range(net.num_terminals(), finfet.net_to_flow_cnt[net.name], 1):
                tmp_SON_vars_for_nets.append(finfet.node_is_SON_vars[net.name][k][node])
        # At most one SON terminal can chosen by a net
        finfet.opt.Add(sum(tmp_SON_vars_for_nets) <= 1)


def prohibit_multiple_SONs_same_column(finfet):
    """
    Enforce an SON cannot be aligned at the same column.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing an SON cannot be aligned at the same column ...")
    tmp_SON_vars_for_at_col = {}
    for col in finfet.lgg.cols_in_layer("M1"):
        tmp_SON_vars_for_at_col[col] = []
        for node in finfet.son_terminal_nodes["M1"]:
            for net in finfet.circuit.get_nets(with_power_ground=False):
                if not net.is_io_net():
                    continue
                for k in range(net.num_terminals(), finfet.net_to_flow_cnt[net.name], 1):
                    if node[2] == col:
                        tmp_SON_vars_for_at_col[col].append(finfet.node_is_SON_vars[net.name][k][node])
    for col in finfet.lgg.cols_in_layer("M1"):
        # At most one SON terminal can chosen by a net
        finfet.opt.Add(sum(tmp_SON_vars_for_at_col[col]) <= 1)


def induce_internal_routing_flow_with_diffusion(finfet):
    """
    Simplified routing: Enforce directed flow-conservation per net, per terminal.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Simplified routing: Enforcing directed flow-conservation per net, per terminal ...")
    for net in finfet.circuit.get_nets(with_power_ground=False):
        src_tran_name, src_pin = net.source()
        for k, (term_tran_name, term_pin) in enumerate(net.terminals()):
            k_shareable_vars = []
            # iterate over src and previous terminals to gather shareable vars
            tmp_ds_share_vars = finfet.gather_ds_shareable_vars(net.name, src_tran_name, term_tran_name, src_pin, term_pin)
            k_shareable_vars.extend(tmp_ds_share_vars)
            tmp_lisd_share_vars = finfet.gather_lisd_shareable_vars(net.name, src_tran_name, term_tran_name, src_pin, term_pin)
            k_shareable_vars.extend(tmp_lisd_share_vars)
            tmp_gate_share_vars = finfet.gather_gate_shareable_vars(net.name, src_tran_name, term_tran_name, src_pin, term_pin)
            k_shareable_vars.extend(tmp_gate_share_vars)
            for k_prev in range(k):
                prev_k_term_tran_name, prev_k_pin = net.terminals()[k_prev]
                tmp_ds_share_vars = finfet.gather_ds_shareable_vars(net.name, prev_k_term_tran_name, term_tran_name, prev_k_pin, term_pin)
                k_shareable_vars.extend(tmp_ds_share_vars)
                tmp_lisd_share_vars = finfet.gather_lisd_shareable_vars(net.name, prev_k_term_tran_name, term_tran_name, prev_k_pin, term_pin)
                k_shareable_vars.extend(tmp_lisd_share_vars)
                tmp_gate_share_vars = finfet.gather_gate_shareable_vars(net.name, prev_k_term_tran_name, term_tran_name, prev_k_pin, term_pin)
                k_shareable_vars.extend(tmp_gate_share_vars)
            is_shared = finfet.opt.NewBoolVar(f"shared_{net.name}_{k}")
            # bind the shareable vars to the is_shared var
            finfet.opt.AddBoolOr(k_shareable_vars).OnlyEnforceIf(is_shared)
            finfet.opt.Add(sum(k_shareable_vars) == 0).OnlyEnforceIf(is_shared.Not())
            for node in finfet.lgg.nodes():
                # incoming to 'node'
                in_flows = sum(
                    finfet.net_flow_vars[(net.name, k, u_arc, v_arc)]
                    for u_arc, v_arc in finfet.adj_in.get(node, [])
                    if (net.name, k, u_arc, v_arc) in finfet.net_flow_vars
                )
                # outgoing from 'node'
                out_flows = sum(
                    finfet.net_flow_vars[(net.name, k, u_arc, v_arc)]
                    for u_arc, v_arc in finfet.adj_out.get(node, [])
                    if (net.name, k, u_arc, v_arc) in finfet.net_flow_vars
                )

                # If node is the CHOSEN source for this 'net':
                can_be_src = finfet.node_is_src_vars[net.name].get(node)
                if can_be_src is not None:
                    finfet.opt.Add(out_flows - in_flows == 1).OnlyEnforceIf([can_be_src, is_shared.Not()])

                # If node is the CHOSEN k-th terminal for this 'net':
                can_be_kth_terminal = finfet.node_is_term_vars[net.name][k].get(node)
                if can_be_kth_terminal is not None:
                    finfet.opt.Add(in_flows - out_flows == 1).OnlyEnforceIf([can_be_kth_terminal, is_shared.Not()])

                # --- Intermediate Node Condition ---
                conditions_for_intermediate = []
                if can_be_src is not None:
                    conditions_for_intermediate.append(can_be_src.Not())

                if can_be_kth_terminal is not None:
                    conditions_for_intermediate.append(can_be_kth_terminal.Not())

                conditions_for_intermediate += [is_shared.Not()]
                if not conditions_for_intermediate:
                    finfet.opt.Add(in_flows == out_flows).OnlyEnforceIf(is_shared.Not())
                else:
                    finfet.opt.Add(in_flows == out_flows).OnlyEnforceIf(conditions_for_intermediate)
                # for every flow, it must be smaller or equal to 1
                finfet.opt.Add(in_flows <= 1).only_enforce_if(is_shared.Not())
                finfet.opt.Add(out_flows <= 1).OnlyEnforceIf(is_shared.Not())
                finfet.opt.Add(in_flows == 0).OnlyEnforceIf(is_shared)
                finfet.opt.Add(out_flows == 0).OnlyEnforceIf(is_shared)


def induce_external_routing_flow(finfet):
    """
    Enforce directed flow-conservation per net, per terminal to I/O pins.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing directed flow-conservation per net, per terminal to I/O pins ...")
    for net in finfet.circuit.get_nets(with_power_ground=False):
        if net.is_io_net():
            absl_logging.info(
                f"Route to I/O pins: {net.name} has {net.num_terminals()} terminals and {finfet.net_to_flow_cnt[net.name]} flow variables"
            )
            for k in range(net.num_terminals(), finfet.net_to_flow_cnt[net.name], 1):
                absl_logging.info(f"Route to I/O pins: {net.name} {k}")
                for node in finfet.lgg.nodes():
                    # incoming to 'node'
                    in_flows = sum(
                        finfet.net_flow_vars[(net.name, k, u_arc, v_arc)]
                        for u_arc, v_arc in finfet.adj_in.get(node, [])
                        if (net.name, k, u_arc, v_arc) in finfet.net_flow_vars
                    )
                    # outgoing from 'node'
                    out_flows = sum(
                        finfet.net_flow_vars[(net.name, k, u_arc, v_arc)]
                        for u_arc, v_arc in finfet.adj_out.get(node, [])
                        if (net.name, k, u_arc, v_arc) in finfet.net_flow_vars
                    )
                    # If node is the CHOSEN source for this 'net':
                    can_be_src = finfet.node_is_src_vars[net.name].get(node)
                    if can_be_src is not None:
                        finfet.opt.Add(out_flows - in_flows == 1).OnlyEnforceIf(can_be_src)

                    # If node is the CHOSEN k-th SON for this 'net':
                    can_be_kth_SON = finfet.node_is_SON_vars[net.name][k].get(node)
                    if can_be_kth_SON is not None:
                        finfet.opt.Add(in_flows - out_flows == 1).OnlyEnforceIf(can_be_kth_SON)

                    # --- Intermediate Node Condition ---
                    conditions_for_intermediate = []
                    if can_be_src is not None:
                        conditions_for_intermediate.append(can_be_src.Not())

                    if can_be_kth_SON is not None:
                        conditions_for_intermediate.append(can_be_kth_SON.Not())
                    if not conditions_for_intermediate:
                        finfet.opt.Add(in_flows == out_flows)
                    else:
                        finfet.opt.Add(in_flows == out_flows).OnlyEnforceIf(conditions_for_intermediate)
                    # for every flow, it must be smaller or equal to 1
                    finfet.opt.Add(in_flows <= 1)
                    finfet.opt.Add(out_flows <= 1)


def node_exclusivity(finfet):
    """
    Enforce a node cannot be propagated flow for more than one net.

    Args:
        finfet: The FinFET instance
    """
    absl_logging.info("\t==\tAdding node exclusivity constraints...")
    finfet.opt.log_comment(f"Enforcing a node cannot be propagated flow for more than one net ...")
    for node in finfet.lgg.nodes():  # node_n is a tuple like (layer_idx, row_coord, col_coord)
        net_touches_node_indicators = []  # if a node conducts flow for a net, then it is exclusive to that net
        for net in finfet.circuit.get_nets(with_power_ground=False):
            net_touches_node_var = finfet.opt.NewBoolVar(f"net_{net.name}_touches_node_L{node[0]}R{node[1]}C{node[2]}")
            net_touches_node_indicators.append(net_touches_node_var)
            # collect all net_arc_vars for current_net that are incident to node
            incident_net_arc_vars_for_node_net = []
            # incoming arcs to node: (u, node)
            for u_arc, __ in finfet.adj_in.get(node, []):
                # arc_tuple is (u_arc, node)
                arc_key = (net.name, u_arc, node)
                if arc_key in finfet.net_arc_vars:  # Should always be true if populated for all arcs
                    incident_net_arc_vars_for_node_net.append(finfet.net_arc_vars[arc_key])
            # outgoing arcs from node: (node, v)
            for __, v_arc in finfet.adj_out.get(node, []):
                # arc_tuple is (node, v_arc)
                arc_key = (net.name, node, v_arc)
                if arc_key in finfet.net_arc_vars:
                    incident_net_arc_vars_for_node_net.append(finfet.net_arc_vars[arc_key])

            # link net_touches_node_var to the collected incident_net_arc_vars_for_node_net
            if incident_net_arc_vars_for_node_net:
                # If net_touches_node_var is true, at least one incident arc must be used by current_net
                finfet.opt.AddBoolOr(incident_net_arc_vars_for_node_net).OnlyEnforceIf(net_touches_node_var)
                # If net_touches_node_var is false, none of the incident arcs can be used by current_net
                finfet.opt.Add(sum(incident_net_arc_vars_for_node_net) == 0).OnlyEnforceIf(net_touches_node_var.Not())
            else:
                # If there are no arcs incident to this node for this net (e.g. isolated node, or graph error),
                # then this net cannot touch this node.
                finfet.opt.Add(net_touches_node_var == 0)
        # At most one net can "touch" this node_n
        if net_touches_node_indicators:
            finfet.opt.Add(sum(net_touches_node_indicators) <= 1)


def routing_localization(finfet):
    """
    Enforce routing localization constraints.

    Args:
        finfet: The FinFET instance
    """
    # TODO unify the domain
    pc_and_m1_cols = finfet.lgg.cols_in_layer("PC") + finfet.lgg.cols_in_layer("M1")
    pc_and_m1_rows = finfet.lgg.rows_in_layer("PC") + finfet.lgg.rows_in_layer("M1")
    # sort and unique the cols
    pc_and_m1_cols = list(sorted(set(pc_and_m1_cols)))
    pc_and_m1_rows = list(sorted(set(pc_and_m1_rows)))

    # NOTE: populate these variables regardless of tolerance
    for net in finfet.circuit.get_nets(with_power_ground=False):
        src_tran_name, src_pin = net.source()
        tran = finfet.circuit.transistors[src_tran_name]
        # eligible src pin x coordinate (based on the pin type)
        if src_pin == "source" or src_pin == "drain":
            finfet.s_coord_x[net.name] = finfet.opt.NewIntVarFromDomain(
                cp_model.Domain.FromValues(finfet.lgg.cols_in_layer("PC")),
                f"s_coord_x_{net.name}",
            )
        elif src_pin == "gate":
            finfet.s_coord_x[net.name] = finfet.opt.NewIntVarFromDomain(
                cp_model.Domain.FromValues(finfet.lgg.cols_in_layer("PC")),
                f"s_coord_x_{net.name}",
            )
        # eligible src pin y coordinate (based on tran type)
        if tran.model == Model.PMOS:
            finfet.s_coord_y[net.name] = finfet.opt.NewIntVarFromDomain(
                cp_model.Domain.FromValues(finfet.lgg.rows_in_layer("PC")),
                f"s_coord_y_{net.name}",
            )
        elif tran.model == Model.NMOS:
            finfet.s_coord_y[net.name] = finfet.opt.NewIntVarFromDomain(
                cp_model.Domain.FromValues(finfet.lgg.rows_in_layer("PC")),
                f"s_coord_y_{net.name}",
            )
        finfet.t_coord_x[net.name] = []
        finfet.t_coord_y[net.name] = []
        # internal terminal pins
        for k in range(net.num_terminals()):
            term_tran_name, term_pin = net.terminals()[k]
            tran = finfet.circuit.transistors[term_tran_name]
            # eligible k-th terminal x coordinate (based on the pin type)
            if term_pin == "source" or term_pin == "drain":
                finfet.t_coord_x[net.name].append(
                    finfet.opt.NewIntVarFromDomain(
                        cp_model.Domain.FromValues(finfet.lgg.cols_in_layer("PC")),
                        f"t_coord_x_{net.name}_{k}",
                    )
                )
            elif term_pin == "gate":
                finfet.t_coord_x[net.name].append(
                    finfet.opt.NewIntVarFromDomain(
                        cp_model.Domain.FromValues(finfet.lgg.cols_in_layer("PC")),
                        f"t_coord_x_{net.name}_{k}",
                    )
                )
            # eligible k-th terminal y coordinate (based on tran type)
            if tran.model == Model.PMOS:
                finfet.t_coord_y[net.name].append(
                    finfet.opt.NewIntVarFromDomain(
                        cp_model.Domain.FromValues(finfet.lgg.rows_in_layer("PC") + finfet.lgg.rows_in_layer("M1")),
                        f"t_coord_y_{net.name}_{k}",
                    )
                )
            elif tran.model == Model.NMOS:
                finfet.t_coord_y[net.name].append(
                    finfet.opt.NewIntVarFromDomain(
                        cp_model.Domain.FromValues(finfet.lgg.rows_in_layer("PC") + finfet.lgg.rows_in_layer("M1")),
                        f"t_coord_y_{net.name}_{k}",
                    )
                )
        # external IO terminal pins
        # ? attempt to bind the external IO terminals to the actual coordinates
        for k in range(net.num_terminals(), finfet.net_to_flow_cnt[net.name], 1):
            # absl_logging.info(f"Adding external IO terminal pins for {net.name} at {k}")
            finfet.t_coord_x[net.name].append(
                finfet.opt.NewIntVarFromDomain(
                    cp_model.Domain.FromValues(finfet.lgg.cols_in_layer("PC") + finfet.lgg.cols_in_layer("M1")),
                    f"t_coord_x_{net.name}_{k}",
                )
            )
            finfet.t_coord_y[net.name].append(
                finfet.opt.NewIntVarFromDomain(
                    cp_model.Domain.FromValues(finfet.lgg.rows_in_layer("PC") + finfet.lgg.rows_in_layer("M1")),
                    f"t_coord_y_{net.name}_{k}",
                )
            )

        # routing window can be at any column and row
        finfet.net_min_x[net.name] = finfet.opt.NewIntVarFromDomain(
            cp_model.Domain.FromValues(finfet.lgg.cols_in_layer("PC") + finfet.lgg.cols_in_layer("M1")),
            f"net_min_x_{net.name}",
        )
        finfet.net_max_x[net.name] = finfet.opt.NewIntVarFromDomain(
            cp_model.Domain.FromValues(finfet.lgg.cols_in_layer("PC") + finfet.lgg.cols_in_layer("M1")),
            f"net_max_x_{net.name}",
        )
        finfet.net_min_y[net.name] = finfet.opt.NewIntVarFromDomain(
            cp_model.Domain.FromValues(finfet.lgg.rows_in_layer("PC") + finfet.lgg.rows_in_layer("M1")),
            f"net_min_y_{net.name}",
        )
        finfet.net_max_y[net.name] = finfet.opt.NewIntVarFromDomain(
            cp_model.Domain.FromValues(finfet.lgg.rows_in_layer("PC") + finfet.lgg.rows_in_layer("M1")),
            f"net_max_y_{net.name}",
        )

        # Domain for finfet.window_xmin_raw: finfet.net_min_x (0 to nx-1) - tol => [-tol, nx-1-tol]
        domain_xmin = cp_model.Domain(
            0,
            finfet.lgg.max_col_in_layer("PC") + finfet.lgg.max_col_in_layer("M1"),
        )
        finfet.window_xmin_raw[net.name] = finfet.opt.NewIntVarFromDomain(
            domain_xmin,
            f"window_xmin_raw_{net.name}",
        )
        # Domain for finfet.window_xmax_raw: finfet.net_max_x (0 to nx-1) + tol => [tol, nx-1+tol]
        domain_xmax = cp_model.Domain(
            0,
            finfet.lgg.max_col_in_layer("PC") + finfet.lgg.max_col_in_layer("M1"),
        )
        finfet.window_xmax_raw[net.name] = finfet.opt.NewIntVarFromDomain(
            domain_xmax,
            f"window_xmax_raw_{net.name}",
        )
        # Domain for finfet.window_ymin_raw: finfet.net_min_y (0 to ny-1) - tol => [-tol, ny-1-tol]
        domain_ymin = cp_model.Domain(
            0,
            finfet.lgg.max_row_in_layer("PC") + finfet.lgg.max_row_in_layer("M1"),
        )
        finfet.window_ymin_raw[net.name] = finfet.opt.NewIntVarFromDomain(
            domain_ymin,
            f"window_ymin_raw_{net.name}",
        )
        # Domain for finfet.window_ymax_raw: finfet.net_max_y (0 to ny-1) + tol => [tol, ny-1+tol]
        domain_ymax = cp_model.Domain(
            0,
            finfet.lgg.max_row_in_layer("PC") + finfet.lgg.max_row_in_layer("M1"),
        )
        finfet.window_ymax_raw[net.name] = finfet.opt.NewIntVarFromDomain(
            domain_ymax,
            f"window_ymax_raw_{net.name}",
        )
        # absl_logging.info(f"\t{len(finfet.s_coord_x)} source coordinates created, {len(finfet.t_coord_x)} terminal coordinates created")
        # absl_logging.info(f"\t{len(finfet.net_min_x)} net min x coordinates created, {len(finfet.net_max_x)} net max x coordinates created")
        # absl_logging.info(f"\t{len(finfet.net_min_y)} net min y coordinates created, {len(finfet.net_max_y)} net max y coordinates created")
        # absl_logging.info(
        #     f"\t{len(finfet.window_xmin_raw)} window x min coordinates created, {len(finfet.window_xmax_raw)} window x max coordinates created"
        # )
        # absl_logging.info(
        #     f"\t{len(finfet.window_ymin_raw)} window y min coordinates created, {len(finfet.window_ymax_raw)} window y max coordinates created"
        # )
        # 1. Link placement variables to actual source/terminal coordinate variables
        # node[2] is the column, node[1] is the row
        finfet.opt.Add(finfet.s_coord_x[net.name] == sum(node[2] * var for node, var in finfet.node_is_src_vars[net.name].items()))
        finfet.opt.Add(finfet.s_coord_y[net.name] == sum(node[1] * var for node, var in finfet.node_is_src_vars[net.name].items()))

        for k in range(net.num_terminals()):
            finfet.opt.Add(finfet.t_coord_x[net.name][k] == sum(node[2] * var for node, var in finfet.node_is_term_vars[net.name][k].items()))
            finfet.opt.Add(finfet.t_coord_y[net.name][k] == sum(node[1] * var for node, var in finfet.node_is_term_vars[net.name][k].items()))
        # ? attempt to bind the external IO terminals to the actual coordinates
        for k in range(net.num_terminals(), finfet.net_to_flow_cnt[net.name], 1):
            finfet.opt.Add(finfet.t_coord_x[net.name][k] == sum(node[2] * var for node, var in finfet.node_is_SON_vars[net.name][k].items()))
            finfet.opt.Add(finfet.t_coord_y[net.name][k] == sum(node[1] * var for node, var in finfet.node_is_SON_vars[net.name][k].items()))

        # 2. Define net's bounding box based on its actual s/t coordinates (X and Y)
        # ? attempt to bind the external IO terminals to the actual coordinates
        all_x_coords_for_net = [finfet.s_coord_x[net.name]] + [
            # finfet.t_coord_x[net.name][k]
            # for k in range(net.num_terminals())
            finfet.t_coord_x[net.name][k]
            for k in range(finfet.net_to_flow_cnt[net.name])
        ]
        # absl_logging.info(f"\t{all_x_coords_for_net} all x coordinates for net {net.name}")
        all_y_coords_for_net = [finfet.s_coord_y[net.name]] + [
            # finfet.t_coord_y[net.name][k]
            # for k in range(net.num_terminals())
            finfet.t_coord_y[net.name][k]
            for k in range(finfet.net_to_flow_cnt[net.name])
        ]
        # absl_logging.info(f"\t{all_y_coords_for_net} all x coordinates for net {net.name}")

        finfet.opt.AddMinEquality(finfet.net_min_x[net.name], all_x_coords_for_net)
        finfet.opt.AddMaxEquality(finfet.net_max_x[net.name], all_x_coords_for_net)
        finfet.opt.AddMinEquality(finfet.net_min_y[net.name], all_y_coords_for_net)
        finfet.opt.AddMaxEquality(finfet.net_max_y[net.name], all_y_coords_for_net)

    # if tolerance is set
    if finfet.routing_tolerance != -1:
        finfet.opt.log_comment(f"Enforcing routing window constraints {finfet.routing_tolerance} ...")
        # NOTE this +2 is the default transistor size, might change later
        max_col = (finfet.cpp_cost + (_NUM_COL_SDG_ - 1)) * int(finfet.fin_tech.get_pitch("PC"))
        max_row = (finfet.fin_tech.num_rt_track - 1) * int(finfet.fin_tech.get_pitch("M0")) * 2
        absl_logging.info(f"\t==\tEnforcing max row and col for routing window to {max_row} and {max_col} ...")
        for net in finfet.circuit.get_nets(with_power_ground=False):
            # 3. Define routing window boundaries using tolerance with proper clamping
            # BUG FIX: Previously, constraints like:
            #   window_xmin_raw == net_min_x - tolerance AND window_xmin_raw >= 0
            # effectively meant net_min_x >= tolerance, which incorrectly constrained placement.
            # The correct approach: window_xmin = max(0, net_min_x - tolerance)

            # Create unclamped intermediate variables for x
            unclamped_xmin = finfet.opt.NewIntVar(
                -finfet.routing_tolerance,
                finfet.lgg.max_col_in_layer("PC") + finfet.lgg.max_col_in_layer("M1"),
                f"unclamped_xmin_{net.name}"
            )
            finfet.opt.Add(unclamped_xmin == finfet.net_min_x[net.name] - finfet.routing_tolerance)
            # window_xmin_raw = max(0, unclamped_xmin)
            finfet.opt.AddMaxEquality(finfet.window_xmin_raw[net.name], [unclamped_xmin, 0])

            unclamped_xmax = finfet.opt.NewIntVar(
                0,
                finfet.lgg.max_col_in_layer("PC") + finfet.lgg.max_col_in_layer("M1") + finfet.routing_tolerance,
                f"unclamped_xmax_{net.name}"
            )
            finfet.opt.Add(unclamped_xmax == finfet.net_max_x[net.name] + finfet.routing_tolerance)
            # window_xmax_raw = min(max_col, unclamped_xmax)
            finfet.opt.AddMinEquality(finfet.window_xmax_raw[net.name], [unclamped_xmax, max_col])

            # Create unclamped intermediate variables for y
            unclamped_ymin = finfet.opt.NewIntVar(
                -finfet.routing_tolerance,
                finfet.lgg.max_row_in_layer("PC") + finfet.lgg.max_row_in_layer("M1"),
                f"unclamped_ymin_{net.name}"
            )
            finfet.opt.Add(unclamped_ymin == finfet.net_min_y[net.name] - finfet.routing_tolerance)
            # window_ymin_raw = max(0, unclamped_ymin)
            finfet.opt.AddMaxEquality(finfet.window_ymin_raw[net.name], [unclamped_ymin, 0])

            unclamped_ymax = finfet.opt.NewIntVar(
                0,
                finfet.lgg.max_row_in_layer("PC") + finfet.lgg.max_row_in_layer("M1") + finfet.routing_tolerance,
                f"unclamped_ymax_{net.name}"
            )
            finfet.opt.Add(unclamped_ymax == finfet.net_max_y[net.name] + finfet.routing_tolerance)
            # window_ymax_raw = min(max_row, unclamped_ymax)
            finfet.opt.AddMinEquality(finfet.window_ymax_raw[net.name], [unclamped_ymax, max_row])

            # 4. Constrain used arcs for this net to be within the calculated window (X and Y)
            # Arc (u,v) is used by 'net' if net_arc[net][(u,v)] is true.
            for u_arc, v_arc in finfet.lgg.arcs():
                u_node_x = u_arc[2]
                u_node_y = u_arc[1]
                v_node_x = v_arc[2]
                v_node_y = v_arc[1]
                # If arc (u_node, v_node) is used by this net, then node u_node must be in window (x,y)
                # For net arc, only constrain to canvas size
                finfet.opt.Add(u_node_x >= 0).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                # finfet.opt.Add(u_node_x <= finfet.window_xmax_raw[net.name]).OnlyEnforceIf(
                finfet.opt.Add(u_node_x <= max_col).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                # finfet.opt.Add(u_node_y >= finfet.window_ymin_raw[net.name]).OnlyEnforceIf(
                finfet.opt.Add(u_node_y >= 0).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                # finfet.opt.Add(u_node_y <= finfet.window_ymax_raw[net.name]).OnlyEnforceIf(
                finfet.opt.Add(u_node_y <= max_row).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])

                # And node v_node must be in window (x,y)
                # finfet.opt.Add(v_node_x >= finfet.window_xmin_raw[net.name]).OnlyEnforceIf(
                finfet.opt.Add(v_node_x >= 0).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                # finfet.opt.Add(v_node_x <= finfet.window_xmax_raw[net.name]).OnlyEnforceIf(
                finfet.opt.Add(v_node_x <= max_col).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                # finfet.opt.Add(v_node_y >= finfet.window_ymin_raw[net.name]).OnlyEnforceIf(
                finfet.opt.Add(v_node_y >= 0).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                # finfet.opt.Add(v_node_y <= finfet.window_ymax_raw[net.name]).OnlyEnforceIf(
                finfet.opt.Add(v_node_y <= max_row).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                # TODO: further constrain the flow of the net as well
                for k in range(finfet.net_to_flow_cnt[net.name]):
                    finfet.opt.Add(u_node_x >= finfet.window_xmin_raw[net.name]).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    finfet.opt.Add(u_node_x <= finfet.window_xmax_raw[net.name]).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    finfet.opt.Add(u_node_y >= finfet.window_ymin_raw[net.name]).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    finfet.opt.Add(u_node_y <= finfet.window_ymax_raw[net.name]).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    finfet.opt.Add(v_node_x >= finfet.window_xmin_raw[net.name]).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    finfet.opt.Add(v_node_x <= finfet.window_xmax_raw[net.name]).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    finfet.opt.Add(v_node_y >= finfet.window_ymin_raw[net.name]).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    finfet.opt.Add(v_node_y <= finfet.window_ymax_raw[net.name]).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])

    # ^ enforce that each net must be routed within the boundary
    else:
        finfet.opt.log_comment(f"Enforcing routing window constraints within the canvas ...")
        # NOTE this +2 is the default transistor size, might change later
        max_col = (finfet.cpp_cost + (_NUM_COL_SDG_ - 1)) * int(finfet.fin_tech.get_pitch("PC"))
        max_row = (finfet.fin_tech.num_rt_track - 1) * int(finfet.fin_tech.get_pitch("M0")) * 2
        for net in finfet.circuit.get_nets(with_power_ground=False):
            # 3. Define routing window boundaries using tolerance
            # 4. Constrain used arcs for this net to be within the calculated window (X and Y)
            # Arc (u,v) is used by 'net' if net_arc[net][(u,v)] is true.
            for u_arc, v_arc in finfet.lgg.arcs():
                u_node_x = u_arc[2]
                u_node_y = u_arc[1]
                v_node_x = v_arc[2]
                v_node_y = v_arc[1]

                # If arc (u_node, v_node) is used by this net, then node u_node must be in window (x,y)
                finfet.opt.Add(u_node_x >= 0).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                # finfet.opt.Add(u_node_x <= finfet.window_xmax_raw[net.name]).OnlyEnforceIf(
                finfet.opt.Add(u_node_x <= max_col).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                # finfet.opt.Add(u_node_y >= finfet.window_ymin_raw[net.name]).OnlyEnforceIf(
                finfet.opt.Add(u_node_y >= 0).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                # finfet.opt.Add(u_node_y <= finfet.window_ymax_raw[net.name]).OnlyEnforceIf(
                finfet.opt.Add(u_node_y <= max_row).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])

                # And node v_node must be in window (x,y)
                # finfet.opt.Add(v_node_x >= finfet.window_xmin_raw[net.name]).OnlyEnforceIf(
                finfet.opt.Add(v_node_x >= 0).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                # finfet.opt.Add(v_node_x <= finfet.window_xmax_raw[net.name]).OnlyEnforceIf(
                finfet.opt.Add(v_node_x <= max_col).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                # finfet.opt.Add(v_node_y >= finfet.window_ymin_raw[net.name]).OnlyEnforceIf(
                finfet.opt.Add(v_node_y >= 0).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                # finfet.opt.Add(v_node_y <= finfet.window_ymax_raw[net.name]).OnlyEnforceIf(
                finfet.opt.Add(v_node_y <= max_row).OnlyEnforceIf(finfet.net_arc_vars[(net.name, u_arc, v_arc)])
                # TODO: further constrain the flow of the net as well
                for k in range(finfet.net_to_flow_cnt[net.name]):
                    finfet.opt.Add(u_node_x >= 0).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    finfet.opt.Add(u_node_x <= max_col).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    finfet.opt.Add(u_node_y >= 0).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    finfet.opt.Add(u_node_y <= max_row).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    finfet.opt.Add(v_node_x >= 0).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    finfet.opt.Add(v_node_x <= max_col).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    finfet.opt.Add(v_node_y >= 0).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
                    finfet.opt.Add(v_node_y <= max_row).OnlyEnforceIf(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)])
