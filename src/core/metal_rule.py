"""
Design Rule Checking functions for FinFET layout.

This module contains functions for enforcing various design rules including:
- End-of-Line (EOL) rules
- Minimum Area Rule (MAR)
- Via separation rules
- Via-to-metal connection rules
"""

from absl import logging as absl_logging


def eol_rules_in_horizontal_layers(finfet_instance, eol_params):
    """
    Enforce EOL (End-of-Line) design rule checking for horizontal layers.

    Args:
        finfet_instance: The FinFET instance containing the opt, lgg, and geometric_vars
        eol_params: Dictionary mapping layer names to EOL distance parameters
    """
    DEBUG_EOL = False
    finfet_instance.opt.log_comment(f"Enforcing EOL design rule checking for horizontal layers ...")
    # Horizontal layers
    for layer, idx in finfet_instance.lgg.layer_to_idx.items():
        if idx == 0:  # NOTE: no design rule checking for the first layer # BUG this is dangerous
            continue
        if finfet_instance.lgg.layer_to_direction[layer] != "H":
            continue
        for row in finfet_instance.lgg.rows_in_layer(layer):
            for col in finfet_instance.lgg.cols_in_layer(layer):
                # ^ --- 8.1) From right to left
                u = (idx, row, col)
                gvr_u = finfet_instance.geometric_vars[u]["right"]
                # iterate util the given parameter
                eol_dist = eol_params[layer]
                walked_dist = 0
                eol_list = []
                eol_list.append(gvr_u)
                curr_u = u
                absl_logging.info(f"Node: {u} EOL dist: {eol_dist}") if DEBUG_EOL else None
                while walked_dist < eol_dist:
                    # check if the right neighbor exists
                    u_r = finfet_instance.lgg.get_right_neighbor(curr_u)
                    if u_r is None:
                        break
                    gvl_u_r = finfet_instance.geometric_vars[u_r]["left"]
                    # add the constraints
                    eol_list.append(gvl_u_r)
                    # extract current col
                    curr_col = u_r[2]
                    walked_dist = abs(curr_col - col)
                    if walked_dist >= eol_dist:
                        # if the distance is greater or equal to the eol distance, then we need to break
                        break
                    absl_logging.info(f"\t EOL Right-to-Left Banning {gvl_u_r} EOL, walked_dist: {walked_dist}") if DEBUG_EOL else None
                    # update the current node
                    curr_u = u_r
                # add the eol constraints
                if len(eol_list) > 1:
                    # if the list is empty, then there is no need to add the constraints
                    finfet_instance.opt.AddAtMostOne(eol_list)
                # ^ --- 8.2) From left to right
                u = (idx, row, col)
                gvl_u = finfet_instance.geometric_vars[u]["left"]
                # iterate util the given parameter
                eol_dist = eol_params[layer]
                walked_dist = 0
                eol_list = []
                eol_list.append(gvl_u)
                curr_u = u 
                while walked_dist < eol_dist:
                    # check if the left neighbor exists
                    u_l = finfet_instance.lgg.get_left_neighbor(curr_u)
                    if u_l is None:
                        break
                    gvr_u_l = finfet_instance.geometric_vars[u_l]["right"]
                    # add the constraints
                    eol_list.append(gvr_u_l)
                    # extract current col
                    curr_col = u_l[2]
                    walked_dist = abs(curr_col - col)
                    if walked_dist >= eol_dist:
                        # if the distance is greater or equal to the eol distance, then we need to break
                        break
                    absl_logging.info(f"\t EOL Left-to-Right Banning {gvr_u_l} EOL, walked_dist: {walked_dist}") if DEBUG_EOL else None
                    # update the current node
                    curr_u = u_l
                # add the eol constraints
                if len(eol_list) > 1:
                    # if the list is empty, then there is no need to add the constraints
                    finfet_instance.opt.AddAtMostOne(eol_list)


def eol_rules_in_vertical_layers(finfet_instance, eol_params):
    """
    Enforce EOL (End-of-Line) design rule checking for vertical layers.

    Args:
        finfet_instance: The FinFET instance containing the opt, lgg, and geometric_vars
        eol_params: Dictionary mapping layer names to EOL distance parameters
    """
    DEBUG_EOL = False
    finfet_instance.opt.log_comment(f"Enforcing EOL design rule checking for vertical layers ...")
    # Vertical layers
    for layer, idx in finfet_instance.lgg.layer_to_idx.items():
        if idx == 0:  # NOTE: no design rule checking for the first layer # BUG this is dangerous
            continue
        if finfet_instance.lgg.layer_to_direction[layer] != "V":
            continue
        for row in finfet_instance.lgg.rows_in_layer(layer):
            for col in finfet_instance.lgg.cols_in_layer(layer):
                # ^ --- 8.3) From front to back
                u = (idx, row, col)
                gvb_u = finfet_instance.geometric_vars[u]["back"]
                # iterate util the given parameter
                eol_dist = eol_params[layer]
                walked_dist = 0
                eol_list = []
                eol_list.append(gvb_u)
                curr_u = u
                absl_logging.info(f"Node: {u} EOL dist: {eol_dist}") if DEBUG_EOL else None
                while walked_dist < eol_dist:
                    # check if the back neighbor exists
                    u_b = finfet_instance.lgg.get_back_neighbor(curr_u)
                    if u_b is None:
                        break
                    gvf_u_b = finfet_instance.geometric_vars[u_b]["front"]
                    # extract current col
                    curr_row = u_b[1]
                    walked_dist = abs(curr_row - row)
                    if walked_dist >= eol_dist:
                        # if the distance is greater or equal to the eol distance, then we need to break
                        break
                    # add the constraints
                    eol_list.append(gvf_u_b)
                    absl_logging.info(f"\t EOL Front-to-Back Banning {gvf_u_b} EOL, walked_dist: {walked_dist}") if DEBUG_EOL else None
                    # update the current node
                    curr_u = u_b
                # add the eol constraints
                if len(eol_list) > 1:
                    # if the list is empty, then there is no need to add the constraints
                    finfet_instance.opt.AddAtMostOne(eol_list)
                # ^ --- 8.4) From back to front
                u = (idx, row, col)
                absl_logging.info(f"Node: {u} EOL dist: {eol_dist}") if DEBUG_EOL else None
                gvf_u = finfet_instance.geometric_vars[u]["front"]
                # iterate util the given parameter
                eol_dist = eol_params[layer]
                walked_dist = 0
                eol_list = []
                eol_list.append(gvf_u)
                curr_u = u
                while walked_dist < eol_dist:
                    # check if the front neighbor exists
                    u_f = finfet_instance.lgg.get_front_neighbor(curr_u)
                    if u_f is None:
                        break
                    gvb_u_f = finfet_instance.geometric_vars[u_f]["back"]
                    # extract current row
                    curr_row = u_f[1]
                    walked_dist = abs(curr_row - row)
                    if walked_dist >= eol_dist:
                        # if the distance is greater or equal to the eol distance, then we need to break
                        break
                    # add the constraints
                    eol_list.append(gvb_u_f)
                    absl_logging.info(f"\t EOL Back-to-Front Banning {gvb_u_f} EOL, walked_dist: {walked_dist}") if DEBUG_EOL else None
                    # update the current node
                    curr_u = u_f
                # add the eol constraints
                if len(eol_list) > 1:
                    # if the list is empty, then there is no need to add the constraints
                    finfet_instance.opt.AddAtMostOne(eol_list)


def mar_rules_in_horizontal_layers(finfet_instance, mar_params, supervia_params):
    """
    Enforce MAR (Minimum Area Rule) design rule checking for horizontal layers.

    Args:
        finfet_instance: The FinFET instance containing the opt, lgg, and geometric_vars
        mar_params: Dictionary mapping layer names to MAR distance parameters
        supervia_params: Dictionary indicating which layers are supervias
    """
    DEBUG_MAR = False
    finfet_instance.opt.log_comment(f"Enforcing MAR design rule checking for horizontal layers ...")
    for layer, idx in finfet_instance.lgg.layer_to_idx.items():
        if idx == 0:
            continue
        if finfet_instance.lgg.layer_to_direction[layer] != "H":
            continue
        if supervia_params[layer]:
            # if the layer is a supervia, then we need to skip this layer
            continue
        for row in finfet_instance.lgg.rows_in_layer(layer):
            for col in finfet_instance.lgg.cols_in_layer(layer):
                # ^ --- 9.1) From right to left
                u = (idx, row, col)
                gvr_u = finfet_instance.geometric_vars[u]["right"]
                gvl_u = finfet_instance.geometric_vars[u]["left"]
                # iterate util the given parameter
                mar_dist = mar_params[layer]
                walked_dist = 0
                mar_list = []
                mar_list.append(gvr_u)
                mar_list.append(gvl_u)
                curr_u = u
                absl_logging.info(f"Node: {u} MAR dist: {mar_dist}") if DEBUG_MAR else None
                while walked_dist < mar_dist:
                    # check if the right neighbor exists
                    u_l = finfet_instance.lgg.get_left_neighbor(curr_u)
                    if u_l is None:
                        break
                    gvl_u_l = finfet_instance.geometric_vars[u_l]["left"]
                    # gvr_u_r = finfet_instance.geometric_vars[u_r]["right"]
                    # extract current col
                    curr_col = u_l[2]
                    walked_dist = abs(curr_col - col)
                    if walked_dist >= mar_dist:
                        # if the distance is greater or equal to the mar distance, then we need to break
                        break
                    # add the constraints
                    mar_list.append(gvl_u_l)
                    # mar_list.append(gvr_u_r) # BUG: why add this
                    absl_logging.info(f"\t MAR Right-to-Left Banning {gvl_u_l} MAR, walked_dist: {walked_dist}") if DEBUG_MAR else None
                    # update the current node
                    curr_u = u_l
                # add the mar constraints
                finfet_instance.opt.AddAtMostOne(mar_list)
                # ^ --- 9.1) From left to right
                u = (idx, row, col)
                gvr_u = finfet_instance.geometric_vars[u]["right"]
                gvl_u = finfet_instance.geometric_vars[u]["left"]
                # iterate util the given parameter
                mar_dist = mar_params[layer]
                walked_dist = 0
                mar_list = []
                mar_list.append(gvl_u)
                mar_list.append(gvr_u)
                curr_u = u
                absl_logging.info(f"Node: {u} MAR dist: {mar_dist}") if DEBUG_MAR else None
                while walked_dist < mar_dist:
                    # check if the right neighbor exists
                    u_r = finfet_instance.lgg.get_right_neighbor(curr_u)
                    if u_r is None:
                        break
                    gvr_u_r = finfet_instance.geometric_vars[u_r]["right"]
                    # gvr_u_r = finfet_instance.geometric_vars[u_r]["right"]
                    # extract current col
                    curr_col = u_r[2]
                    walked_dist = abs(curr_col - col)
                    if walked_dist >= mar_dist:
                        # if the distance is greater or equal to the mar distance, then we need to break
                        break
                    # add the constraints
                    mar_list.append(gvr_u_r)
                    # mar_list.append(gvr_u_r) # BUG: why add this
                    absl_logging.info(f"\t MAR Left-to-Right Banning {gvr_u_r} MAR, walked_dist: {walked_dist}") if DEBUG_MAR else None
                    # update the current node
                    curr_u = u_r
                # add the mar constraints
                finfet_instance.opt.AddAtMostOne(mar_list)


def mar_rules_in_vertical_layers(finfet_instance, mar_params, supervia_params):
    """
    Enforce MAR (Minimum Area Rule) design rule checking for vertical layers.

    Args:
        finfet_instance: The FinFET instance containing the opt, lgg, and geometric_vars
        mar_params: Dictionary mapping layer names to MAR distance parameters
        supervia_params: Dictionary indicating which layers are supervias
    """
    DEBUG_MAR = False
    finfet_instance.opt.log_comment("Enforcing MAR design rule checking for vertical layers ...")
    for layer, idx in finfet_instance.lgg.layer_to_idx.items():
        # no MAR on first layer
        if idx == 0:  # NOTE: no design rule checking for the first layer # BUG this is dangerous
            continue
        # only vertical layers
        if finfet_instance.lgg.layer_to_direction[layer] != "V":
            continue
        # skip supervia layers entirely
        if supervia_params[layer]:
            continue
        mar_dist = mar_params[layer]
        for row in finfet_instance.lgg.rows_in_layer(layer):
            for col in finfet_instance.lgg.cols_in_layer(layer):
                # ^ Front to Back
                u = (idx, row, col)
                gvf_u = finfet_instance.geometric_vars[u]["front"]
                gvb_u = finfet_instance.geometric_vars[u]["back"]
                # iterate util the given parameter
                mar_dist = mar_params[layer]
                walked_dist = 0
                mar_list = []
                mar_list.append(gvf_u)
                mar_list.append(gvb_u)
                curr_u = u
                absl_logging.info(f"Node: {u} MAR dist: {mar_dist}") if DEBUG_MAR else None
                while walked_dist < mar_dist:
                    # check if the right neighbor exists
                    u_b = finfet_instance.lgg.get_back_neighbor(curr_u)
                    if u_b is None:
                        break
                    # NOTE: if u_b is the last row, dont restrict it.
                    if u_b[1] == finfet_instance.lgg.rows_in_layer(layer)[-1]:
                        absl_logging.info(f"MAR on {layer} exceeding max row. Ignoring last row.") if DEBUG_MAR else None
                        break
                    # gvf_u_b = finfet_instance.geometric_vars[u_b]["front"]
                    gvb_u_b = finfet_instance.geometric_vars[u_b]["back"]
                    # extract current col
                    curr_row = u_b[1]
                    walked_dist = abs(curr_row - row)
                    if walked_dist >= mar_dist:
                        # if the distance is greater or equal to the mar distance, then we need to break
                        break
                    # add the constraints
                    # mar_list.append(gvf_u_b)
                    mar_list.append(gvb_u_b)
                    absl_logging.info(f"\t MAR Front-to-Back Banning {gvb_u_b} MAR, walked_dist: {walked_dist}") if DEBUG_MAR else None
                    # update the current node
                    curr_u = u_b
                # add the mar constraints
                finfet_instance.opt.AddAtMostOne(mar_list)
                # ^ Back to Front
                u = (idx, row, col)
                gvf_u = finfet_instance.geometric_vars[u]["front"]
                gvb_u = finfet_instance.geometric_vars[u]["back"]
                # iterate util the given parameter
                mar_dist = mar_params[layer]
                walked_dist = 0
                mar_list = []
                mar_list.append(gvb_u)
                mar_list.append(gvf_u)
                curr_u = u
                absl_logging.info(f"Node: {u} MAR dist: {mar_dist}") if DEBUG_MAR else None
                while walked_dist < mar_dist:
                    # check if the right neighbor exists
                    u_f = finfet_instance.lgg.get_front_neighbor(curr_u)
                    if u_f is None:
                        break
                    # NOTE: if u_f is the first row, dont restrict it.
                    if u_f[1] == finfet_instance.lgg.rows_in_layer(layer)[0]:
                        absl_logging.info(f"MAR on {layer} exceeding min row. Ignoring first row.") if DEBUG_MAR else None
                        break
                    # gvf_u_b = finfet_instance.geometric_vars[u_b]["front"]
                    gvf_u_f = finfet_instance.geometric_vars[u_f]["front"]
                    # extract current col
                    curr_row = u_f[1]
                    walked_dist = abs(curr_row - row)
                    if walked_dist >= mar_dist:
                        # if the distance is greater or equal to the mar distance, then we need to break
                        break
                    # add the constraints
                    # mar_list.append(gvf_u_b)
                    mar_list.append(gvf_u_f)
                    absl_logging.info(f"\t MAR Front-to-Back Banning {gvf_u_f} MAR, walked_dist: {walked_dist}") if DEBUG_MAR else None
                    # update the current node
                    curr_u = u_f
                # add the mar constraints
                finfet_instance.opt.AddAtMostOne(mar_list)


def via_induce_vertical_metal(finfet_instance, supervia_params):
    """
    At layer M1, if a node is connected to a via, it must be connected to the metal layer.

    Args:
        finfet_instance: The FinFET instance containing the opt, lgg, edge_vars, and geometric_vars
        supervia_params: Dictionary indicating which layers are supervias
    """
    # At layer M1, if a node is connected to a via, it must be connected to the metal layer
    finfet_instance.opt.log_comment(f"At layer M1, if a node is connected to a via, it must be connected to the metal layer ...")
    # NOTE: SMTCell implements this at flow level
    for u in finfet_instance.lgg.nodes_in_layer("M1"):
        if supervia_params["M1"]:
            # if the layer is a supervia, then we need to skip this layer
            continue
        # get the down neighbor
        layer_idx = u[0]
        row = u[1]
        col = u[2]
        u_d = (layer_idx - 1, row, col)
        if not finfet_instance.lgg.is_node_in_graph(u_d):
            continue
        via_edge = finfet_instance.edge_vars[(u_d, u)]
        metal_edges = []
        # get the front neighbor
        u_f = finfet_instance.lgg.get_front_neighbor(u)
        if u_f is not None:
            metal_edges.append(finfet_instance.edge_vars[(u_f, u)])
        # get the back neighbor
        u_b = finfet_instance.lgg.get_back_neighbor(u)
        if u_b is not None:
            metal_edges.append(finfet_instance.edge_vars[(u, u_b)])

        # Reify the condition that at least one metal edge is active
        # u is (M1_layer_idx, row, col)
        has_metal_connection_var = finfet_instance.opt.NewBoolVar(f"has_metal_conn_M1_R{u[1]}_C{u[2]}")

        if not metal_edges:
            # If there are no possible metal edges connected to u on M1,
            # then has_metal_connection_var must be false.
            finfet_instance.opt.Add(has_metal_connection_var == 0)
        else:
            # has_metal_connection_var is true if OR(metal_edges) is true
            finfet_instance.opt.AddBoolOr(metal_edges).OnlyEnforceIf(has_metal_connection_var)
            # If any metal_edge is true, then has_metal_connection_var must be true
            # (This establishes the other direction of the equivalence: OR(metal_edges) => has_metal_connection_var)
            for metal_edge_var in metal_edges:
                finfet_instance.opt.AddImplication(metal_edge_var, has_metal_connection_var)

        # if the via edge exists, then there must be a metal edge connection at u on M1
        finfet_instance.opt.AddImplication(via_edge, has_metal_connection_var)


def via_induce_horizontal_metal(finfet_instance, supervia_params):
    """
    At layer M0, if a node is connected to a via, it must be connected to the metal layer.

    Args:
        finfet_instance: The FinFET instance containing the opt, lgg, edge_vars, and geometric_vars
        supervia_params: Dictionary indicating which layers are supervias
    """
    finfet_instance.opt.log_comment(f"At layer M0, if a node is connected to a via, it must be connected to the metal layer ...")
    # NOTE: SMTCell implements this at flow level
    for u in finfet_instance.lgg.nodes_in_layer("M0"):
        if supervia_params["M0"]:
            # if the layer is a supervia, then we need to skip this layer
            continue
        # get the down neighbor
        layer_idx = u[0]
        row = u[1]
        col = u[2]
        u_d = (layer_idx - 1, row, col)
        if not finfet_instance.lgg.is_node_in_graph(u_d):
            continue
        via_edge = finfet_instance.edge_vars[(u_d, u)]
        metal_edges = []
        # get the left neighbor
        u_l = finfet_instance.lgg.get_left_neighbor(u)
        if u_l is not None:
            metal_edges.append(finfet_instance.edge_vars[(u_l, u)])
        # get the right neighbor
        u_r = finfet_instance.lgg.get_right_neighbor(u)
        if u_r is not None:
            metal_edges.append(finfet_instance.edge_vars[(u, u_r)])
        # Reify the condition that at least one metal edge is active
        # u is (M0_layer_idx, row, col)
        has_metal_connection_var = finfet_instance.opt.NewBoolVar(f"has_metal_conn_M0_R{u[1]}_C{u[2]}")
        if not metal_edges:
            # If there are no possible metal edges connected to u on M0,
            # then has_metal_connection_var must be false.
            finfet_instance.opt.Add(has_metal_connection_var == 0)
        else:
            # has_metal_connection_var is true if OR(metal_edges) is true
            finfet_instance.opt.AddBoolOr(metal_edges).OnlyEnforceIf(has_metal_connection_var)
            # If any metal_edge is true, then has_metal_connection_var must be true
            # (This establishes the other direction of the equivalence: OR(metal_edges) => has_metal_connection_var)
            for metal_edge_var in metal_edges:
                finfet_instance.opt.AddImplication(metal_edge_var, has_metal_connection_var)
        # if the via edge exists, then there must be a metal edge connection at u on M0
        finfet_instance.opt.AddImplication(via_edge, has_metal_connection_var)


def geometric_vars_in_horizontal_layers(finfet_instance):
    """
    Create geometric variables for horizontal layers to track wire segment boundaries.

    Args:
        finfet_instance: The FinFET instance containing the opt, lgg, edge_vars, and geometric_vars
    """
    # --- 7.1) Geometric variables (left)
    finfet_instance.opt.log_comment("Adding geometric variables (left)...")
    for layer, idx in finfet_instance.lgg.layer_to_idx.items():
        if finfet_instance.lgg.layer_to_direction[layer] != "H":
            continue

        # helper to get/create gvL at node u
        def get_left_gv(u):
            inner = finfet_instance.geometric_vars.setdefault(u, {})
            if "left" not in inner:
                r, c = u[1], u[2]
                inner["left"] = finfet_instance.opt.NewBoolVar(f"gvL_L{idx}_R{r}_C{c}")
            return inner["left"]

        for row in finfet_instance.lgg.rows_in_layer(layer):
            for col in finfet_instance.lgg.cols_in_layer(layer):
                u = (idx, row, col)
                u_r = finfet_instance.lgg.get_right_neighbor(u)
                u_l = finfet_instance.lgg.get_left_neighbor(u)
                if u_r is None:
                    continue

                gvl = get_left_gv(u)
                gvl_u_r = get_left_gv(u_r)
                edge = finfet_instance.edge_vars[(u, u_r)]

                # start ⇒ outgoing edge
                finfet_instance.opt.AddImplication(gvl, edge)

                if u_l is not None:
                    prev = finfet_instance.edge_vars[(u_l, u)]
                    tmp = finfet_instance.opt.NewBoolVar(f"tmp_left_continue_L{idx}_R{row}_C{col}")
                    # continuation indicator
                    finfet_instance.opt.AddBoolOr([gvl, prev]).OnlyEnforceIf(tmp)
                    finfet_instance.opt.AddImplication(gvl, tmp)
                    finfet_instance.opt.AddImplication(prev, tmp)
                    finfet_instance.opt.AddImplication(tmp.Not(), edge.Not())
                else:
                    # first column can't have an incoming edge
                    finfet_instance.opt.AddImplication(gvl.Not(), edge.Not())

                # can't both start here and continue
                finfet_instance.opt.AddAtMostOne([gvl_u_r, edge])

    # --- 7.2) Geometric variables (right)
    finfet_instance.opt.log_comment("Adding geometric variables (right)...")
    for layer, idx in finfet_instance.lgg.layer_to_idx.items():
        if finfet_instance.lgg.layer_to_direction[layer] != "H":
            continue

        # helper to get/create gvR at node u
        def get_right_gv(u):
            inner = finfet_instance.geometric_vars.setdefault(u, {})
            if "right" not in inner:
                r, c = u[1], u[2]
                inner["right"] = finfet_instance.opt.NewBoolVar(f"gvR_L{idx}_R{r}_C{c}")
            return inner["right"]

        for row in finfet_instance.lgg.rows_in_layer(layer):
            for col in finfet_instance.lgg.cols_in_layer(layer):
                u = (idx, row, col)
                u_r = finfet_instance.lgg.get_right_neighbor(u)
                u_l = finfet_instance.lgg.get_left_neighbor(u)

                gvr = get_right_gv(u)

                if u_r is not None:
                    gvr_u_r = get_right_gv(u_r)
                    edge = finfet_instance.edge_vars[(u, u_r)]

                    # can't both end here and continue
                    finfet_instance.opt.AddAtMostOne([gvr, edge])

                    tmp = finfet_instance.opt.NewBoolVar(f"tmp_right_continue_L{idx}_R{row}_C{col}")
                    finfet_instance.opt.AddBoolOr([gvr, edge]).OnlyEnforceIf(tmp)
                    finfet_instance.opt.AddImplication(gvr, tmp)
                    finfet_instance.opt.AddImplication(edge, tmp)

                    if u_l is not None:
                        prev = finfet_instance.edge_vars[(u_l, u)]
                        finfet_instance.opt.AddImplication(gvr, prev)
                        finfet_instance.opt.AddImplication(tmp.Not(), prev.Not())
                    else:
                        # first column can never have an incoming edge
                        finfet_instance.opt.Add(gvr == 0)

                    # neighbor's end ⇒ outgoing edge
                    finfet_instance.opt.AddImplication(gvr_u_r, edge)
                else:
                    # boundary column: must match incoming edge (if any)
                    if u_l is not None:
                        prev = finfet_instance.edge_vars[(u_l, u)]
                        finfet_instance.opt.Add(prev == gvr)
                    else:
                        # single-cell row
                        finfet_instance.opt.Add(gvr == 0)


def geometric_vars_in_vertical_layers(finfet_instance):
    """
    Create geometric variables for vertical layers to track wire segment boundaries.

    Args:
        finfet_instance: The FinFET instance containing the opt, lgg, edge_vars, and geometric_vars
    """
    # ^ --- 7.3) Geometric variables (back) - Defines gvb at u
    # gvb at u: node u is a "back end," meaning a vertical segment (u_b, u) ends at u.
    # This implies:
    # 1. Edge (u_b, u) MUST exist (this was locally named curr_edge in the original 7.3).
    # 2. Edge (u, u_f) (to u's front neighbor) MUST NOT exist (this was locally named prev_edge
    #    in the original 7.3, if u_f itself exists).
    finfet_instance.opt.log_comment(f"Adding geometric variables (back)...")
    for layer, idx in finfet_instance.lgg.layer_to_idx.items():
        if idx == 0:
            continue
        if finfet_instance.lgg.layer_to_direction[layer] != "V":  # Only for vertical layers
            continue
        for row in finfet_instance.lgg.rows_in_layer(layer):
            for col in finfet_instance.lgg.cols_in_layer(layer):
                u = (idx, row, col)
                u_b = finfet_instance.lgg.get_back_neighbor(u)  # u_b defines the incoming edge from the back
                u_f = finfet_instance.lgg.get_front_neighbor(u)  # u_f defines the potential outgoing edge to the back
                # print("u", u, "u_f", u_f, "u_b", u_b)
                # Retrieve or create the geometric variable for "back end" at u
                gvf = finfet_instance.geometric_vars.setdefault(u, {}).setdefault("front", finfet_instance.opt.NewBoolVar(f"gvF_L{idx}_R{row}_C{col}"))

                if u_b is None:
                    # If there is no back neighbor, the required incoming edge (u_b,u) cannot exist.
                    # Since gvf being true implies this edge exists, gvf must be false.
                    finfet_instance.opt.Add(gvf == False)
                    continue

                # If u_b exists, curr_edge is the incoming edge from the back (u_b, u).
                # This is the edge whose existence is primary for gvf.
                # curr_edge = finfet_instance.edge_vars[(u_b, u)]
                curr_edge = finfet_instance.edge_vars[(u, u_b)]

                # Definition of gvf at u:
                # gvf is true <=> (curr_edge is true AND (prev_edge is false OR u_f is None))

                # Part 1: gvf => curr_edge
                # If u is a "back end" (gvf is true), then curr_edge (u_b, u) must exist.
                finfet_instance.opt.AddImplication(gvf, curr_edge)

                if u_f is not None:  # If there is a potential "next" node u_f and thus a potential outgoing edge (u, u_f)
                    # The edge (u, u_f) was locally named prev_edge in the original 7.3 code.
                    # prev_edge = finfet_instance.edge_vars[(u, u_f)]
                    prev_edge = finfet_instance.edge_vars[(u_f,u)]

                    # Part 2: gvf => prev_edge.Not()
                    # If u is a "back end" (gvf is true), the outgoing edge (prev_edge) to u_f must NOT exist.
                    # AddAtMostOne([gvf, prev_edge]) ensures that gvf and prev_edge cannot both be true.
                    finfet_instance.opt.AddAtMostOne([gvf, prev_edge])

                    # Part 3: (curr_edge AND prev_edge.Not()) => gvf
                    # This is typically handled by a "reason" constraint for the primary edge (curr_edge):
                    # curr_edge => (gvf OR prev_edge)
                    # If curr_edge is true AND prev_edge is false, this forces gvf to be true.

                    # Create an indicator variable for the condition (gvf OR prev_edge)
                    # Original naming was tmp_back_continue_indicator, let's use a more general "reason" name
                    tmp_back_reason_indicator = finfet_instance.opt.NewBoolVar(f"tmp_back_reason_indicator_L{idx}_R{row}_C{col}")

                    # Establish tmp_back_reason_indicator <=> (gvf OR prev_edge)
                    finfet_instance.opt.AddImplication(gvf, tmp_back_reason_indicator)
                    finfet_instance.opt.AddImplication(prev_edge, tmp_back_reason_indicator)
                    finfet_instance.opt.AddBoolOr([gvf, prev_edge]).OnlyEnforceIf(tmp_back_reason_indicator)

                    # Link curr_edge to this reason: curr_edge => (gvf OR prev_edge)
                    finfet_instance.opt.AddImplication(curr_edge, tmp_back_reason_indicator)

                else:  # u_f is None (u is at the foremost boundary of the layer)
                    # In this scenario, the outgoing edge (prev_edge) does not exist (implicitly false).
                    # The condition "prev_edge.Not()" is automatically met.
                    # Therefore, gvf should be true if and only if curr_edge (the incoming edge) exists.
                    # We already have: gvf => curr_edge (from Part 1).
                    # We need to add: curr_edge => gvf to complete the equivalence.
                    finfet_instance.opt.AddImplication(curr_edge, gvf)

    # ^ --- 7.4) Geometric variables (front)
    finfet_instance.opt.log_comment(f"Adding geometric variables (front)...")
    for layer, idx in finfet_instance.lgg.layer_to_idx.items():
        if idx == 0:
            continue
        if finfet_instance.lgg.layer_to_direction[layer] != "V":  # Only for vertical layers
            continue
        for row in finfet_instance.lgg.rows_in_layer(layer):
            for col in finfet_instance.lgg.cols_in_layer(layer):
                u = (idx, row, col)
                u_f = finfet_instance.lgg.get_front_neighbor(u)  # u_f is the "next" node in the segment's direction
                u_b = finfet_instance.lgg.get_back_neighbor(u)  # u_b is the "previous" node in this direction
                gvb = finfet_instance.geometric_vars.setdefault(u, {}).setdefault("back", finfet_instance.opt.NewBoolVar(f"gvB_L{idx}_R{row}_C{col}"))
                # If u_f is None, the main edge (u, u_f) cannot exist.
                # Therefore, u cannot be the "back end" (i.e., start) of such a segment.
                if u_f is None:
                    # If there is no back neighbor, the required incoming edge (u_b,u) cannot exist.
                    # Since gvb being true implies this edge exists, gvb must be false.
                    finfet_instance.opt.Add(gvb == False)
                    continue

                # If u_f exists, main_edge_vf is the primary edge associated with gvb at u.
                # This edge goes from u to u_f.
                # main_edge_vf = finfet_instance.edge_vars[(u, u_f)]
                main_edge_vf = finfet_instance.edge_vars[(u_f, u)]

                # Definition of gvb at u:
                # gvb is true <=> (main_edge_vf is true AND (incoming_edge_vb is false OR u_b is None))

                # Part 1: gvb => main_edge_vf
                # If u is a "front end" (gvb is true), then the main_edge_vf (u, u_f) must exist.
                finfet_instance.opt.AddImplication(gvb, main_edge_vf)

                if u_b is not None:  # If there is a potential "previous" node u_b
                    # incoming_edge_vb = finfet_instance.edge_vars[(u_b, u)]  # This is the edge (u_b, u)
                    incoming_edge_vb = finfet_instance.edge_vars[(u, u_b)]
                    # Part 2: gvb => incoming_edge_vb.Not()
                    # If u is a "front end", the incoming_edge_vb from u_b must NOT exist.
                    # AddAtMostOne([gvb, incoming_edge_vb]) ensures that gvb and incoming_edge_vb
                    # cannot both be true. This implies:
                    #   gvb => incoming_edge_vb.Not()
                    #   incoming_edge_vb => gvb.Not()
                    finfet_instance.opt.AddAtMostOne([gvb, incoming_edge_vb])

                    # Part 3: (main_edge_vf AND incoming_edge_vb.Not()) => gvb
                    # This is established using a "reason" constraint for main_edge_vf:
                    # main_edge_vf => (gvb OR incoming_edge_vb)
                    # If main_edge_vf is true AND incoming_edge_vb is false, this forces gvb to be true.

                    # Create an indicator variable for the condition (gvb OR incoming_edge_vb)
                    tmp_reason_for_main_edge_vf = finfet_instance.opt.NewBoolVar(f"tmp_reason_main_vf_gvb_L{idx}_R{row}_C{col}")  # Clarified name

                    # Establish tmp_reason_for_main_edge_vf <=> (gvb OR incoming_edge_vb)
                    finfet_instance.opt.AddImplication(gvb, tmp_reason_for_main_edge_vf)
                    finfet_instance.opt.AddImplication(incoming_edge_vb, tmp_reason_for_main_edge_vf)
                    finfet_instance.opt.AddBoolOr([gvb, incoming_edge_vb]).OnlyEnforceIf(tmp_reason_for_main_edge_vf)

                    # Link main_edge_vf to this reason: main_edge_vf => (gvb OR incoming_edge_vb)
                    finfet_instance.opt.AddImplication(main_edge_vf, tmp_reason_for_main_edge_vf)

                else:  # u_b is None (u is at the rearmost boundary of the layer for vertical tracks)
                    # In this scenario, incoming_edge_vb effectively does not exist (is implicitly false).
                    # The condition "incoming_edge_vb.Not()" is automatically met.
                    # Therefore, gvb should be true if and only if main_edge_vf exists.
                    # We already have: gvb => main_edge_vf (from Part 1).
                    # We need to add: main_edge_vf => gvb to complete the equivalence.
                    finfet_instance.opt.AddImplication(main_edge_vf, gvb)

