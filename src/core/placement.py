"""
Placement-related constraints for FinFET layout optimization.
This module contains all placement constraint implementations.
"""

from absl import logging as absl_logging
from src.utility.entity import Model


def link_source_drain_gate_columns_to_transistor_placement(finfet):
    """
    Link source/drain/gate columns to transistor placement.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Linking source/drain/gate columns to transistor placement")
    for tran in finfet.circuit.transistors.values():
        tvar = finfet.transistor_vars[tran.name]
        source_net, gate_net, drain_net = tran.source, tran.gate, tran.drain
        for ci in finfet.plc_ci:
            # tran_is_placed_col_var = finfet.opt.NewBoolVar(f"tran_placed_col_{tran.name}_{ci}")
            tran_is_placed_col_var = finfet.placed_tran_ci_vars.get((tran.name, ci))
            # finfet.placed_tran_ci_vars[(tran.name, ci)] = tran_is_placed_col_var
            # # if x_var is placed at col, then turn on this variable
            # finfet.opt.Add(tvar.x_var == ci).OnlyEnforceIf(tran_is_placed_col_var)
            # finfet.opt.Add(tvar.x_var != ci).OnlyEnforceIf(tran_is_placed_col_var.Not())
            # build
            col = finfet.lgg.col_in_layer("PC", ci)  # s/d col
            ci_r = ci + 1
            col_r = finfet.lgg.col_in_layer("PC", ci_r)  # gate col
            ci_rr = ci + 2
            col_rr = finfet.lgg.col_in_layer("PC", ci_rr)  # s/d col
            # ^ if flipped, then s_col_idx_var = x_var + 2 * pitch, d_col_idx_var = x_var
            if tran.model == Model.PMOS:
                nodes_at_s_col = finfet.gather_nodes_in_pmos_region(col=col_rr)
                nodes_at_d_col = finfet.gather_nodes_in_pmos_region(col=col)
            elif tran.model == Model.NMOS:
                nodes_at_s_col = finfet.gather_nodes_in_nmos_region(col=col_rr)
                nodes_at_d_col = finfet.gather_nodes_in_nmos_region(col=col)
            else:
                raise ValueError(f"Unknown model: {tran.model}")
            # ^ enforce exactly one of the s_col_idx_var must be 1 at col_rr
            s_col_vars_on_col_rr = []
            for net, col_vars in tvar.s_col_idx_var.items():
                s_col_vars = col_vars.get(col_rr, [])
                if len(s_col_vars) > 0:
                    s_col_vars_on_col_rr.extend(s_col_vars)
            if len(s_col_vars_on_col_rr) > 0:
                finfet.opt.Add(sum(s_col_vars_on_col_rr) == 1).OnlyEnforceIf(
                    [
                        tvar.flip_var,
                        tran_is_placed_col_var,
                    ]
                )
            # ban all other col_vars from using the source column
            (
                ban_other_nets_from_using_nodes(
                    finfet,
                    net_to_skip=source_net,
                    nodes=nodes_at_s_col,
                    cond=[tvar.flip_var, tran_is_placed_col_var],
                )
            )
            # then all other col_vars must be 0
            for net, col_vars in tvar.s_col_idx_var.items():
                for col_other, s_col_vars in col_vars.items():
                    if col_other != col_rr and len(s_col_vars) > 0:
                        finfet.opt.Add(sum(s_col_vars) == 0).OnlyEnforceIf([tvar.flip_var, tran_is_placed_col_var])
            # ^ enforce exactly one of the d_col_idx_var must be 1 at col
            d_col_vars_on_col = []
            for net, col_vars in tvar.d_col_idx_var.items():
                d_col_vars = col_vars.get(col, [])
                if len(d_col_vars) > 0:
                    d_col_vars_on_col.extend(d_col_vars)
            if len(d_col_vars_on_col) > 0:
                finfet.opt.Add(sum(d_col_vars_on_col) == 1).OnlyEnforceIf(
                    [
                        tvar.flip_var,
                        tran_is_placed_col_var,
                    ]
                )
            # ban all other col_vars from using the drain column
            ban_other_nets_from_using_nodes(
                finfet,
                net_to_skip=drain_net,
                nodes=nodes_at_d_col,
                cond=[tvar.flip_var, tran_is_placed_col_var],
            )
            # then all other col_vars must be 0
            for net, col_vars in tvar.d_col_idx_var.items():
                for col_other, d_col_vars in col_vars.items():
                    if col_other != col and len(d_col_vars) > 0:
                        finfet.opt.Add(sum(d_col_vars) == 0).OnlyEnforceIf(tvar.flip_var, tran_is_placed_col_var)
            # ^ if not flipped, then s_col_idx_var = x_var, d_col_idx_var = x_var + 2 * pitch
            if tran.model == Model.PMOS:
                nodes_at_s_col = finfet.gather_nodes_in_pmos_region(col=col)
                nodes_at_d_col = finfet.gather_nodes_in_pmos_region(col=col_rr)
            elif tran.model == Model.NMOS:
                nodes_at_s_col = finfet.gather_nodes_in_nmos_region(col=col)
                nodes_at_d_col = finfet.gather_nodes_in_nmos_region(col=col_rr)
            else:
                raise ValueError(f"Unknown model {tran.model}")
            # ^ enforce exactly one of the d_col_idx_var must be 1 at col
            s_col_vars_on_col = []
            for net, col_vars in tvar.s_col_idx_var.items():
                s_col_vars = col_vars.get(col, [])
                if len(s_col_vars) > 0:
                    s_col_vars_on_col.extend(s_col_vars)
            if len(s_col_vars_on_col) > 0:
                finfet.opt.Add(sum(s_col_vars_on_col) == 1).OnlyEnforceIf(
                    [
                        tvar.flip_var.Not(),
                        tran_is_placed_col_var,
                    ]
                )
            # ban all other col_vars from using the source column
            (
                ban_other_nets_from_using_nodes(
                    finfet,
                    net_to_skip=source_net,
                    nodes=nodes_at_s_col,
                    cond=[tvar.flip_var.Not(), tran_is_placed_col_var],
                )
            )
            # then all other col_vars must be 0
            for net, col_vars in tvar.s_col_idx_var.items():
                for col_other, s_col_vars in col_vars.items():
                    if col_other != col and len(s_col_vars) > 0:
                        finfet.opt.Add(sum(s_col_vars) == 0).OnlyEnforceIf([tvar.flip_var.Not(), tran_is_placed_col_var])
            # ^ enforce exactly one of the d_col_idx_var must be 1 at col_rr
            d_col_vars_on_col_rr = []
            for net, col_vars in tvar.d_col_idx_var.items():
                d_col_vars = col_vars.get(col_rr, [])
                if len(d_col_vars) > 0:
                    d_col_vars_on_col_rr.extend(d_col_vars)
            if len(d_col_vars_on_col_rr) > 0:
                finfet.opt.Add(sum(d_col_vars_on_col_rr) == 1).OnlyEnforceIf(
                    [
                        tvar.flip_var.Not(),
                        tran_is_placed_col_var,
                    ]
                )
            # ban all other col_vars from using the drain column
            (
                ban_other_nets_from_using_nodes(
                    finfet,
                    net_to_skip=drain_net,
                    nodes=nodes_at_d_col,
                    cond=[tvar.flip_var.Not(), tran_is_placed_col_var],
                )
            )
            # then all other col_vars must be 0
            for net, col_vars in tvar.d_col_idx_var.items():
                for col_other, d_col_vars in col_vars.items():
                    if col_other != col_rr and len(d_col_vars) > 0:
                        finfet.opt.Add(sum(d_col_vars) == 0).OnlyEnforceIf([tvar.flip_var.Not(), tran_is_placed_col_var])
            # ^ regardless of flip, g_col_idx_var = x_var + 1
            g_col_vars_on_col_r = []
            for net, col_vars in tvar.g_col_idx_var.items():
                g_col_vars = col_vars.get(col_r, [])
                if len(g_col_vars) > 0:
                    g_col_vars_on_col_r.extend(g_col_vars)
            if len(g_col_vars_on_col_r) > 0:
                finfet.opt.Add(sum(g_col_vars_on_col_r) == 1).OnlyEnforceIf(
                    [
                        tran_is_placed_col_var,
                    ]
                )
            if tran.model == Model.PMOS:
                nodes_at_g_col = finfet.gather_nodes_in_pmos_region(col=col_r)
            elif tran.model == Model.NMOS:
                nodes_at_g_col = finfet.gather_nodes_in_nmos_region(col=col_r)
            # ban all other col_vars from using the gate column
            (
                ban_other_nets_from_using_nodes(
                    finfet,
                    net_to_skip=gate_net,
                    nodes=nodes_at_g_col,
                    cond=tran_is_placed_col_var,
                )
            )
            # then all other col_vars must be 0
            for net, col_vars in tvar.g_col_idx_var.items():
                for col_other, g_col_vars in col_vars.items():
                    if col_other != col_r and len(g_col_vars) > 0:
                        finfet.opt.Add(sum(g_col_vars) == 0).OnlyEnforceIf(tran_is_placed_col_var)


def diffusion_alignment(finfet):
    """
    Enforce diffusion alignment between PMOS and NMOS.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing diffusion alignment between PMOS and NMOS...")
    # NOTE: double implication is somehow better than the single bidirectional implication
    finfet.db_cols_vars = {}
    if finfet.fin_tech.enforce_diffusion_alignment:
        absl_logging.info("\t==\tEnforcing diffusion alignment between PMOS and NMOS...")
        for ci in finfet.plc_ci:
            finfet.opt.AddImplication(
                finfet.db_pmos_cols_vars[ci],
                finfet.db_nmos_cols_vars[ci],
            )
            finfet.opt.AddImplication(
                finfet.db_nmos_cols_vars[ci],
                finfet.db_pmos_cols_vars[ci],
            )
            finfet.db_cols_vars[ci] = finfet.opt.NewBoolVar(f"db_ci_{ci}")
            finfet.opt.Add(finfet.db_cols_vars[ci] == 1).OnlyEnforceIf(
                [
                    finfet.db_pmos_cols_vars[ci],
                    finfet.db_nmos_cols_vars[ci],
                ]
            )
            finfet.opt.Add(finfet.db_cols_vars[ci] == 0).OnlyEnforceIf(
                [
                    finfet.db_pmos_cols_vars[ci].Not(),
                    finfet.db_nmos_cols_vars[ci].Not(),
                ]
            )


def limit_diffusion_breaks(finfet):
    """
    Set allowable diffusion break columns.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Setting allowable diffusion break columns...")
    if finfet.fin_tech.allowable_diffusion_break_cols == "ALL":
        # diffusion break is allowed in all placeable columns.
        pass
    elif finfet.fin_tech.allowable_diffusion_break_cols == "NONE":
        # diffusion break is not allowed in any placeable columns.
        for ci in finfet.plc_ci:
            finfet.opt.Add(finfet.db_pmos_cols_vars[ci] == 0)
            finfet.opt.Add(finfet.db_nmos_cols_vars[ci] == 0)
    elif finfet.fin_tech.allowable_diffusion_break_cols == "SPLIT":
        # diffusion break is allowed in the two end portions of the placeable columns.
        col_indices = finfet.plc_ci
        total_cols = len(col_indices)
        one_fourth_col_idx = int(total_cols / 4) + 1  # +1 to make it less aggressive
        for ci in col_indices:
            if ci >= one_fourth_col_idx and ci <= total_cols - one_fourth_col_idx:
                finfet.opt.Add(finfet.db_pmos_cols_vars[ci] == 0)
                finfet.opt.Add(finfet.db_nmos_cols_vars[ci] == 0)
    elif finfet.fin_tech.allowable_diffusion_break_cols == "CENTER":
        # diffusion break is allowed in the center portion of the placeable columns.
        col_indices = finfet.plc_ci
        total_cols = len(col_indices)
        one_fourth_col_idx = int(total_cols / 4) - 1  # -1 to make it less aggressive
        for ci in col_indices:
            if ci >= one_fourth_col_idx and ci <= total_cols - one_fourth_col_idx:
                finfet.opt.Add(finfet.db_pmos_cols_vars[ci] == 0)
                finfet.opt.Add(finfet.db_nmos_cols_vars[ci] == 0)
    elif finfet.fin_tech.allowable_diffusion_break_cols == "OTHER":
        # diffusion break is allowed on every other column.
        for i, ci in enumerate(finfet.plc_ci):
            if i % 2 == 0:
                finfet.opt.Add(finfet.db_pmos_cols_vars[ci] == 0)
                finfet.opt.Add(finfet.db_nmos_cols_vars[ci] == 0)
    else:
        raise ValueError(f"Unknown diffusion break cols: {finfet.fin_tech.allowable_diffusion_break_cols}")


def placement_lexico_order_symmetry_breaking(finfet):
    """
    Enforce Lexicographic Order Symmetry Breaking.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing Lexicographic Order Symmetry Breaking...")
    tmp_X = [finfet.transistor_vars[tran.name].x_var for tran in sorted(finfet.circuit.transistors.values())]
    tmp_X_rev = list(reversed(tmp_X))
    # 1) for each position i build
    #   -   eq[i] a (X[i] == XR[i])
    #   -   lt[i] a (X[i] <  XR[i])
    tmp_eq, tmp_lt = [], []
    for i in range(len(tmp_X)):
        ei = finfet.opt.NewBoolVar(f"eq_{i}")
        li = finfet.opt.NewBoolVar(f"lt_{i}")
        finfet.opt.Add(tmp_X[i] == tmp_X_rev[i]).OnlyEnforceIf(ei)
        finfet.opt.Add(tmp_X[i] != tmp_X_rev[i]).OnlyEnforceIf(ei.Not())
        finfet.opt.Add(tmp_X[i] < tmp_X_rev[i]).OnlyEnforceIf(li)
        finfet.opt.Add(tmp_X[i] >= tmp_X_rev[i]).OnlyEnforceIf(li.Not())
        tmp_eq.append(ei)
        tmp_lt.append(li)
    # 2) build the disjunction of all eq[i] and lt[i]
    #       (lt[0]) ( (eq[0] ' lt[1]) ( (eq[0]'eq[1]'lt[2]) ( �
    tmp_clause = []
    tmp_prefix = None
    for i in range(len(tmp_X)):
        if i == 0:
            tmp_clause.append(tmp_lt[i])
            tmp_prefix = tmp_eq[i]
        else:
            # create a new literal c[i] a prefix ' lt[i]
            ci = finfet.opt.NewBoolVar(f"lex_break_{i}")
            finfet.opt.AddBoolAnd([tmp_prefix, tmp_lt[i]]).OnlyEnforceIf(ci)
            finfet.opt.AddBoolOr([tmp_prefix.Not(), tmp_lt[i].Not()]).OnlyEnforceIf(ci.Not())
            tmp_clause.append(ci)

            # update prefix a prefix ' eq[i]
            new_pref = finfet.opt.NewBoolVar(f"lex_pref_{i}")
            finfet.opt.AddBoolAnd([tmp_prefix, tmp_eq[i]]).OnlyEnforceIf(new_pref)
            finfet.opt.AddBoolOr([tmp_prefix.Not(), tmp_eq[i].Not()]).OnlyEnforceIf(new_pref.Not())
            tmp_prefix = new_pref
    # finfet.opt.AddBoolOr(tmp_clause)
    # # finally enforce the disjunction
    if not tmp_X:
        pass
    elif not tmp_clause and tmp_prefix is not None:
        finfet.opt.Add(tmp_prefix == 1)
    else:
        finfet.opt.AddBoolOr(tmp_clause + [tmp_prefix])


def pairwise_diffusion_sharing(finfet):
    """
    Enforce pairwise diffusion sharing.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing pairwise diffusion sharing...")
    # absl_logging.info(f"\t==\tEnforcing pairwise diffusion sharing to {finfet.fin_tech.diffusion_break_type}...")
    db_dist = None
    if finfet.fin_tech.diffusion_break_type == "SDB":
        db_dist = 2
    elif finfet.fin_tech.diffusion_break_type == "DDB":
        db_dist = 4
    elif finfet.fin_tech.diffusion_break_type == "MDB":
        raise NotImplementedError("Mixed Diffusion Break is not implemented yet.")
    finfet.ds_pair_vars = {}  # ? new variable flag
    finfet.net_ds_sharable_pairs = {}  # later in routing, used to check if lisd sharing is possible
    tmp_tran = sorted(list(finfet.circuit.transistors.values()))

    for i, tran_1 in enumerate(tmp_tran):
        x_var_1 = finfet.transistor_vars[tran_1.name].x_var
        flip_var_1 = finfet.transistor_vars[tran_1.name].flip_var
        for tran_2 in tmp_tran[i + 1 :]:
            x_var_2 = finfet.transistor_vars[tran_2.name].x_var
            flip_var_2 = finfet.transistor_vars[tran_2.name].flip_var
            # same mos type
            if tran_1.model != tran_2.model:
                continue

            # 1) Collect all nets that connect k1 and k2 (src/drn on either)
            shared_nets = [
                (net.name, net.connected_transistors)
                for net in finfet.circuit.nets.values()
                if ((tran_1.name, "source") in net.connected_transistors or (tran_1.name, "drain") in net.connected_transistors)
                and ((tran_2.name, "source") in net.connected_transistors or (tran_2.name, "drain") in net.connected_transistors)
            ]

            # 1a) If no shared net at all, forbid adjacency outright:
            if not shared_nets:
                finfet.opt.Add(x_var_1 != x_var_2 + db_dist)
                finfet.opt.Add(x_var_2 != x_var_1 + db_dist)
                continue

            for shared_net in shared_nets:
                net_name = shared_net[0]
                finfet.net_ds_sharable_pairs.setdefault(net_name, []).append((tran_1.name, tran_2.name))

            # 2) One BoolVar "sel" per shared net; pick at most one
            selectors = []
            for net, _ in shared_nets:
                sel = finfet.opt.NewBoolVar(f"sel_{tran_1.name}_{tran_2.name}_{net}")
                selectors.append(sel)
            finfet.opt.Add(sum(selectors) <= 1)

            # 2a) If *none* is selected, forbid adjacency entirely:
            #    (OnlyEnforceIf takes a list of literals that all must be true)
            none_selected = [sel.Not() for sel in selectors]
            finfet.opt.Add(x_var_1 != x_var_2 + db_dist).OnlyEnforceIf(none_selected)
            finfet.opt.Add(x_var_2 != x_var_1 + db_dist).OnlyEnforceIf(none_selected)

            # 3) For each net, gate its adjacency+flip logic on sel==True
            for (net, conn), sel in zip(shared_nets, selectors):
                # reuse or create the two adjacency reifiers
                keyL = f"ds_left_{tran_1.name}_{tran_2.name}_{net}"
                keyR = f"ds_right_{tran_1.name}_{tran_2.name}_{net}"
                adj_left = finfet.ds_pair_vars.get(keyL, finfet.opt.NewBoolVar(keyL))
                adj_right = finfet.ds_pair_vars.get(keyR, finfet.opt.NewBoolVar(keyR))
                finfet.ds_pair_vars[keyL] = adj_left
                finfet.ds_pair_vars[keyR] = adj_right

                # 3a) exactly one orientation if sel, none otherwise
                finfet.opt.Add(adj_left + adj_right == 1).OnlyEnforceIf(sel)
                finfet.opt.Add(adj_left == 0).OnlyEnforceIf(sel.Not())
                finfet.opt.Add(adj_right == 0).OnlyEnforceIf(sel.Not())

                # 3b) Now recover your four sharingcases, *all* under sel:
                # 3b.1) sourcesource sharing
                if (tran_1.name, "source") in conn and (
                    tran_2.name,
                    "source",
                ) in conn:
                    # tran_1 immediately left of tran_2
                    finfet.opt.Add(x_var_1 + db_dist == x_var_2).OnlyEnforceIf([adj_left, sel])
                    finfet.opt.Add(x_var_1 + db_dist != x_var_2).OnlyEnforceIf([adj_left.Not(), sel])
                    # tran_1 is flipped and tran_2 is not
                    finfet.opt.AddImplication(adj_left, flip_var_1).OnlyEnforceIf(sel)
                    finfet.opt.AddImplication(adj_left, flip_var_2.Not()).OnlyEnforceIf(sel)

                    # tran_1 immediately right of tran_2
                    finfet.opt.Add(x_var_1 == x_var_2 + db_dist).OnlyEnforceIf([adj_right, sel])
                    finfet.opt.Add(x_var_1 != x_var_2 + db_dist).OnlyEnforceIf([adj_right.Not(), sel])
                    # tran_1 is not flipped and tran_2 is flipped
                    finfet.opt.AddImplication(adj_right, flip_var_2).OnlyEnforceIf(sel)
                    finfet.opt.AddImplication(adj_right, flip_var_1.Not()).OnlyEnforceIf(sel)
                # 3b.2) draindrain sharing
                elif (tran_1.name, "drain") in conn and (
                    tran_2.name,
                    "drain",
                ) in conn:
                    # tran_1 immediately right of tran_2
                    finfet.opt.Add(x_var_1 == x_var_2 + db_dist).OnlyEnforceIf([adj_right, sel])
                    finfet.opt.Add(x_var_1 != x_var_2 + db_dist).OnlyEnforceIf([adj_right.Not(), sel])
                    # tran_1 is flipped and tran_2 is not flipped
                    finfet.opt.AddImplication(adj_right, flip_var_1).OnlyEnforceIf(sel)
                    finfet.opt.AddImplication(adj_right, flip_var_2.Not()).OnlyEnforceIf(sel)

                    # tran_1 immediately left of tran_2
                    finfet.opt.Add(x_var_1 + db_dist == x_var_2).OnlyEnforceIf([adj_left, sel])
                    finfet.opt.Add(x_var_1 + db_dist != x_var_2).OnlyEnforceIf([adj_left.Not(), sel])
                    # tran_1 is not flipped and tran_2 is flipped
                    finfet.opt.AddImplication(adj_left, flip_var_2).OnlyEnforceIf(sel)
                    finfet.opt.AddImplication(adj_left, flip_var_1.Not()).OnlyEnforceIf(sel)
                # 3b.3) source-drain sharing
                elif (tran_1.name, "source") in conn and (
                    tran_2.name,
                    "drain",
                ) in conn:
                    # tran_1 immediately left of tran_2
                    finfet.opt.Add(x_var_1 + db_dist == x_var_2).OnlyEnforceIf([adj_left, sel])
                    finfet.opt.Add(x_var_1 + db_dist != x_var_2).OnlyEnforceIf([adj_left.Not(), sel])
                    # tran_1 is flipped and tran_2 is flipped
                    finfet.opt.AddImplication(adj_left, flip_var_1).OnlyEnforceIf(sel)
                    finfet.opt.AddImplication(adj_left, flip_var_2).OnlyEnforceIf(sel)

                    # tran_1 immediately right of tran_2
                    finfet.opt.Add(x_var_1 == x_var_2 + db_dist).OnlyEnforceIf([adj_right, sel])
                    finfet.opt.Add(x_var_1 != x_var_2 + db_dist).OnlyEnforceIf([adj_right.Not(), sel])
                    # tran_1 is not flipped and tran_2 is not flipped
                    finfet.opt.AddImplication(adj_right, flip_var_1.Not()).OnlyEnforceIf(sel)
                    finfet.opt.AddImplication(adj_right, flip_var_2.Not()).OnlyEnforceIf(sel)
                # 3b.4) drain-source sharing
                elif (tran_1.name, "drain") in conn and (
                    tran_2.name,
                    "source",
                ) in conn:
                    # tran_1 immediately left of tran_2
                    finfet.opt.Add(x_var_1 + db_dist == x_var_2).OnlyEnforceIf([adj_left, sel])
                    finfet.opt.Add(x_var_1 + db_dist != x_var_2).OnlyEnforceIf([adj_left.Not(), sel])
                    # tran_1 is not flipped and tran_2 is not flipped
                    finfet.opt.AddImplication(adj_left, flip_var_1.Not()).OnlyEnforceIf(sel)
                    finfet.opt.AddImplication(adj_left, flip_var_2.Not()).OnlyEnforceIf(sel)

                    # tran_1 immediately right of tran_2
                    finfet.opt.Add(x_var_1 == x_var_2 + db_dist).OnlyEnforceIf([adj_right, sel])
                    finfet.opt.Add(x_var_1 != x_var_2 + db_dist).OnlyEnforceIf([adj_right.Not(), sel])
                    # tran_1 is flipped and tran_2 is flipped
                    finfet.opt.AddImplication(adj_right, flip_var_1).OnlyEnforceIf(sel)
                    finfet.opt.AddImplication(adj_right, flip_var_2).OnlyEnforceIf(sel)
    absl_logging.info(f"\t==\t{len(finfet.ds_pair_vars)} pairwise diffusion sharing variables created ...")


def pairwise_lisd_sharing(finfet):
    """
    Enforce pairwise LISD sharing.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing pairwise lisd sharing...")
    absl_logging.info(f"\t==\tEnforcing pairwise lisd sharing ...")
    tmp_tran = sorted(list(finfet.circuit.transistors.values()))
    finfet.lisd_share_pair_vars = {}
    for i, tran_1 in enumerate(tmp_tran):
        x_var_1 = finfet.transistor_vars[tran_1.name].x_var
        flip_var_1 = finfet.transistor_vars[tran_1.name].flip_var
        for tran_2 in tmp_tran[i + 1 :]:
            x_var_2 = finfet.transistor_vars[tran_2.name].x_var
            flip_var_2 = finfet.transistor_vars[tran_2.name].flip_var
            # diff mos type
            if tran_1.model == tran_2.model:
                continue

            # 1) gather all nets where k1,k2 share a source or drain
            shared_nets = [
                (net.name, net.connected_transistors)
                for net in finfet.circuit.get_nets(with_power_ground=False)
                if ((tran_1.name, "source") in net.connected_transistors or (tran_1.name, "drain") in net.connected_transistors)
                and ((tran_2.name, "source") in net.connected_transistors or (tran_2.name, "drain") in net.connected_transistors)
            ]

            for shared_net in shared_nets:
                net_name = shared_net[0]

            # 1a) if no shared net, forbid any vertical alignment
            if not shared_nets:
                # finfet.opt.Add(x_var_1 != x_var_2)
                continue

            # 2) one selector per net; pick at most one
            selectors = []
            for net, _ in shared_nets:
                sel = finfet.opt.NewBoolVar(f"sel_{tran_1.name}_{tran_2.name}_{net}")
                selectors.append(sel)
            finfet.opt.Add(sum(selectors) <= 1)

            # 2a) if none selected, forbid adjacency entirely
            none_selected = [sel.Not() for sel in selectors]
            # finfet.opt.Add(x_var_1 != x_var_2).OnlyEnforceIf(none_selected)

            # 3) for each net, lisd its vertical alignment+flip under sel
            for (net, conn), sel in zip(shared_nets, selectors):
                key = f"lisd_share_{tran_1.name}_{tran_2.name}_{net}"
                lisd_var = finfet.lisd_share_pair_vars.get(
                    key,
                    finfet.opt.NewBoolVar(key),
                )
                finfet.lisd_share_pair_vars[key] = lisd_var

                # 3a) force verti=1 when sel, verti=0 otherwise
                finfet.opt.Add(lisd_var == 1).OnlyEnforceIf(sel)
                finfet.opt.Add(lisd_var == 0).OnlyEnforceIf(sel.Not())

                # 3b) geometry: same column iff verti & sel
                finfet.opt.Add(x_var_1 == x_var_2).OnlyEnforceIf([lisd_var, sel])
                finfet.opt.Add(x_var_1 != x_var_2).OnlyEnforceIf([lisd_var.Not(), sel])

                # 3c) fliprelation under sel
                if ((tran_1.name, "source") in conn and (tran_2.name, "source") in conn) or (
                    (tran_1.name, "drain") in conn and (tran_2.name, "drain") in conn
                ):
                    finfet.opt.Add(flip_var_1 == flip_var_2).OnlyEnforceIf(sel)
                else:
                    finfet.opt.Add(flip_var_1 != flip_var_2).OnlyEnforceIf(sel)
    absl_logging.info(f"\t==\t{len(finfet.lisd_share_pair_vars)} pairwise lisd sharing variables created ...")


def pairwise_gate_sharing(finfet):
    """
    Enforce pairwise gate sharing.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing pairwise gate sharing...")
    absl_logging.info(f"\t==\tEnforcing pairwise gate sharing ...")
    finfet.gate_share_pair_vars = {}  # ? new variable flag
    tmp_tran = sorted(list(finfet.circuit.transistors.values()))
    finfet.net_gate_sharable_pairs = {}  # later in routing, used to check if gate sharing is possible
    for i, tran_1 in enumerate(tmp_tran):
        x_var_1 = finfet.transistor_vars[tran_1.name].x_var
        for tran_2 in tmp_tran[i + 1 :]:
            x_var_2 = finfet.transistor_vars[tran_2.name].x_var
            # diff mos type
            if tran_1.model == tran_2.model:
                continue
            shared_any_diffusion = False
            for net in finfet.circuit.get_nets(with_power_ground=False):
                conn = net.connected_transistors
                # 1) sourcesource sharing and drain-drain sharing
                if (tran_1.name, "gate") in conn and (tran_2.name, "gate") in conn:
                    finfet.net_gate_sharable_pairs.setdefault(net.name, []).append((tran_1.name, tran_2.name))
                    shared_any_diffusion = True
                    # 1.1) tran_1 immediately left of tran_2
                    key = f"gate_share_{tran_1.name}_{tran_2.name}_{net.name}"
                    gate_var = finfet.gate_share_pair_vars.get(
                        key,
                        finfet.opt.NewBoolVar(key),
                    )
                    finfet.opt.Add(x_var_1 == x_var_2).OnlyEnforceIf(gate_var)
                    finfet.opt.Add(x_var_1 != x_var_2).OnlyEnforceIf(gate_var.Not())
                    finfet.gate_share_pair_vars[key] = gate_var
            # 2) no sharing => forbid gate cut
            if not shared_any_diffusion:
                pass
    absl_logging.info(f"\t==\t{len(finfet.gate_share_pair_vars)} pairwise gate sharing variables created ...")


def net_span_from_placement(finfet, use_span_limit=False):
    """
    Enforce net spanning from placement.

    Args:
        finfet: The FinFET instance
        use_span_limit: Whether to enforce span limit (default False)
    """
    finfet.opt.log_comment(f"Enforcing net spanning...")
    # TODO This is a pre-mature implementation for placement only flow
    absl_logging.info(f"\t==\tEnforcing net spanning ...")
    finfet.net_span_min_vars = {}
    finfet.net_span_max_vars = {}
    for net in finfet.circuit.get_nets(with_power_ground=False):
        conn = net.connected_transistors
        tmp_net_x_vars = []
        for tran_name, p in conn:
            tvar = finfet.transistor_vars[tran_name]
            tmp_net_x_vars.append(tvar.x_var)
        # min and max x vars
        net_span_min_var = finfet.opt.NewIntVarFromDomain(
            finfet.domain_pc_ci,
            f"{net.name}_min",
        )
        net_span_min_var = finfet.opt.NewIntVar(0, finfet.lgg.num_cols_in_layer("PC"), f"{net.name}_net_span_min")
        net_span_max_var = finfet.opt.NewIntVar(0, finfet.lgg.num_cols_in_layer("PC"), f"{net.name}_net_span_max")
        finfet.net_span_min_vars[net.name] = net_span_min_var
        finfet.net_span_max_vars[net.name] = net_span_max_var
        finfet.opt.AddMinEquality(
            net_span_min_var,
            tmp_net_x_vars,
        )
        finfet.opt.AddMaxEquality(
            net_span_max_var,
            tmp_net_x_vars,
        )
    # conditional constrain net spanning
    # NOTE: do not use this
    if use_span_limit:
        absl_logging.info(f"\t==\tEnforcing net spanning limit ...")
        finfet.opt.log_comment(f"Enforcing net spanning limit ...")
        # enforce that the net spanning is within the limit
        for net in finfet.circuit.get_nets(with_power_ground=False):
            net_degree = len(net.connected_transistors)
            # enforce that the net spanning is within the limit
            span_limit = int(net_degree**2)
            finfet.opt.Add((finfet.net_span_max_vars[net.name] - finfet.net_span_min_vars[net.name]) <= span_limit)
    absl_logging.info(f"\tEnd of placement constraints ...")


def ban_other_nets_from_using_nodes(finfet, net_to_skip, nodes, cond, debug_mode=False):
    """
    Ban other nets from using specified nodes.

    Args:
        finfet: The FinFET instance
        net_to_skip: The net name to skip
        nodes: List of nodes to protect
        cond: Condition for enforcement
        debug_mode: Enable debug logging (default False)
    """
    for net in finfet.circuit.get_nets(with_power_ground=False):
        if net.name == net_to_skip:
            continue
        for u_arc, v_arc in finfet.lgg.arcs():
            # if (u_arc in nodes or v_arc in nodes) and (u_arc[0] != v_arc[0]):
            if u_arc in nodes or v_arc in nodes:
                (absl_logging.info(f"\t\t{net_to_skip} banning {net.name} from using ({u_arc}, {v_arc}) if {cond}") if debug_mode else None)
                finfet.opt.Add(finfet.net_arc_vars[(net.name, u_arc, v_arc)] == 0).OnlyEnforceIf(cond)
                for k in range(net.num_terminals()):
                    finfet.opt.Add(finfet.net_flow_vars[(net.name, k, u_arc, v_arc)] == 0).OnlyEnforceIf(cond)


def ban_other_nets_on_pwr_columns(finfet):
    """
    CFET FLAG
    Do not allow any other net to use the power columns on PC layer.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing no other net on power columns ...")
    for net in finfet.circuit.get_power_ground_nets():
        absl_logging.info(f"Net: {net.name} Connected Transistors: {net.connected_transistors}")
        for tran_name, tran_pin in net.connected_transistors:
            tran = finfet.circuit.transistors[tran_name]
            tvar = finfet.transistor_vars[tran_name]
            for ci in finfet.plc_ci:
                tran_is_placed_col_var = finfet.placed_tran_ci_vars.get((tran_name, ci))
                col = finfet.lgg.col_in_layer("PC", ci)  # s/d col
                ci_rr = ci + 2
                col_rr = finfet.lgg.col_in_layer("PC", ci_rr)  # s/d col
                # print(f"Checking transistor {tran_name} at col {col} and col_rr {col_rr} in site {si} ...")
                # ^ if flipped, then s_col_idx_var = x_var + 2 * pitch, d_col_idx_var = x_var
                if tran.model == Model.PMOS and tran_pin == "source":
                    pmos_source_contact_edge_vars = finfet.gather_via_vars_in_pmos_region(col=col_rr)
                    # print(f"\tPMOS source contact edge vars: {pmos_source_contact_edge_vars}")
                    # ban all edges
                    finfet.opt.Add(sum(pmos_source_contact_edge_vars) == 0).OnlyEnforceIf(tran_is_placed_col_var, tvar.flip_var)
                elif tran.model == Model.PMOS and tran_pin == "drain":
                    pmos_drain_contact_edge_vars = finfet.gather_via_vars_in_pmos_region(col=col)
                    # print(f"\tPMOS drain contact edge vars: {pmos_drain_contact_edge_vars}")
                    # ban all edges
                    finfet.opt.Add(sum(pmos_drain_contact_edge_vars) == 0).OnlyEnforceIf(tran_is_placed_col_var, tvar.flip_var)
                elif tran.model == Model.NMOS and tran_pin == "source":
                    nmos_source_contact_edge_vars = finfet.gather_via_vars_in_nmos_region(col=col_rr)
                    # print(f"\tNMOS source contact edge vars: {nmos_source_contact_edge_vars}")
                    # ban all edges
                    finfet.opt.Add(sum(nmos_source_contact_edge_vars) == 0).OnlyEnforceIf(tran_is_placed_col_var, tvar.flip_var)
                elif tran.model == Model.NMOS and tran_pin == "drain":
                    nmos_drain_contact_edge_vars = finfet.gather_via_vars_in_nmos_region(col=col)
                    # print(f"\tNMOS drain contact edge vars: {nmos_drain_contact_edge_vars}")
                    # ban all edges
                    finfet.opt.Add(sum(nmos_drain_contact_edge_vars) == 0).OnlyEnforceIf(tran_is_placed_col_var, tvar.flip_var)
                else:
                    raise ValueError(f"Unknown model: {tran.model}")
                # ^ if not flipped, then s_col_idx_var = x_var, d_col_idx_var = x_var + 2 * pitch
                if tran.model == Model.PMOS and tran_pin == "source":
                    pmos_source_contact_edge_vars = finfet.gather_via_vars_in_pmos_region(col=col)
                    # ban all edges
                    finfet.opt.Add(sum(pmos_source_contact_edge_vars) == 0).OnlyEnforceIf(tran_is_placed_col_var, tvar.flip_var.Not())
                elif tran.model == Model.PMOS and tran_pin == "drain":
                    pmos_drain_contact_edge_vars = finfet.gather_via_vars_in_pmos_region(col=col_rr)
                    # ban all edges
                    finfet.opt.Add(sum(pmos_drain_contact_edge_vars) == 0).OnlyEnforceIf(tran_is_placed_col_var, tvar.flip_var.Not())
                elif tran.model == Model.NMOS and tran_pin == "source":
                    nmos_source_contact_edge_vars = finfet.gather_via_vars_in_nmos_region(col=col)
                    # ban all edges
                    finfet.opt.Add(sum(nmos_source_contact_edge_vars) == 0).OnlyEnforceIf(tran_is_placed_col_var, tvar.flip_var.Not())
                elif tran.model == Model.NMOS and tran_pin == "drain":
                    nmos_drain_contact_edge_vars = finfet.gather_via_vars_in_nmos_region(col=col_rr)
                    # ban all edges
                    finfet.opt.Add(sum(nmos_drain_contact_edge_vars) == 0).OnlyEnforceIf(tran_is_placed_col_var, tvar.flip_var.Not())
                else:
                    raise ValueError(f"Unknown model: {tran.model}")


def prohibit_CA_contact_on_non_source_term_columns(finfet):
    """
    Prohibit CA contact on non-source term columns.

    Args:
        finfet: The FinFET instance
    """
    for ci in finfet.sd_ci:
        col = finfet.lgg.col_in_layer("PC", ci)
        finfet.opt.log_comment(f"Prohibiting CA contact on non-source term at columns {col} ...")
        # PMOS region
        src_term_vars_pmos = finfet.gather_src_term_vars_in_pmos_region(col=col)
        pmos_contact_edge_vars = finfet.gather_via_vars_in_pmos_region(col=col)
        # at least one source/terminal must be placed in the PMOS region for a CA contact to be valid
        # print(f"\tPMOS source term vars: {src_term_vars}")
        for p_via_var in pmos_contact_edge_vars:
            # If p_via_var is true, then at least one of src_term_vars_pmos must be true.
            finfet.opt.AddBoolOr(src_term_vars_pmos).OnlyEnforceIf(p_via_var)
        # NMOS region
        src_term_vars_nmos = finfet.gather_src_term_vars_in_nmos_region(col=col)
        nmos_contact_edge_vars = finfet.gather_via_vars_in_nmos_region(col=col)
        # print(f"\tNMOS source term vars: {src_term_vars_nmos}")
        for n_via_var in nmos_contact_edge_vars:
            # If n_via_var is true, then at least one of src_term_vars_nmos must be true.
            finfet.opt.AddBoolOr(src_term_vars_nmos).OnlyEnforceIf(n_via_var)
