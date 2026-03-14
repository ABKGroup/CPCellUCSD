"""
Via-related design rules for FinFET layout optimization.
This module contains constraints for via induction and via-metal connectivity.
"""

from absl import logging as absl_logging


def via_induce_vertical_metal(finfet, supervia_params):
    """
    At layer M1, if a node is connected to a via, it must be connected to the metal layer.

    Args:
        finfet: The FinFET instance
        supervia_params: Dictionary of supervia parameters per layer
    """
    finfet.opt.log_comment("At layer M1, if a node is connected to a via, it must be connected to the metal layer ...")
    # NOTE: SMTCell implements this at flow level
    for u in finfet.lgg.nodes_in_layer("M1"):
        if supervia_params["M1"]:
            # if the layer is a supervia, then we need to skip this layer
            continue
        # get the down neighbor
        layer_idx = u[0]
        row = u[1]
        col = u[2]
        u_d = (layer_idx - 1, row, col)
        if not finfet.lgg.is_node_in_graph(u_d):
            continue
        via_edge = finfet.edge_vars[(u_d, u)]
        metal_edges = []
        # get the front neighbor
        u_f = finfet.lgg.get_front_neighbor(u)
        if u_f is not None:
            metal_edges.append(finfet.edge_vars[(u_f, u)])
        # get the back neighbor
        u_b = finfet.lgg.get_back_neighbor(u)
        if u_b is not None:
            metal_edges.append(finfet.edge_vars[(u, u_b)])

        # Reify the condition that at least one metal edge is active
        # u is (M1_layer_idx, row, col)
        has_metal_connection_var = finfet.opt.NewBoolVar(f"has_metal_conn_M1_R{u[1]}_C{u[2]}")

        if not metal_edges:
            # If there are no possible metal edges connected to u on M1,
            # then has_metal_connection_var must be false.
            finfet.opt.Add(has_metal_connection_var == 0)
        else:
            # has_metal_connection_var is true if OR(metal_edges) is true
            finfet.opt.AddBoolOr(metal_edges).OnlyEnforceIf(has_metal_connection_var)
            # If any metal_edge is true, then has_metal_connection_var must be true
            # (This establishes the other direction of the equivalence: OR(metal_edges) => has_metal_connection_var)
            for metal_edge_var in metal_edges:
                finfet.opt.AddImplication(metal_edge_var, has_metal_connection_var)

        # if the via edge exists, then there must be a metal edge connection at u on M1
        finfet.opt.AddImplication(via_edge, has_metal_connection_var)


def via_induce_horizontal_metal(finfet, supervia_params):
    """
    At layer M0, if a node is connected to a via, it must be connected to the metal layer.

    Args:
        finfet: The FinFET instance
        supervia_params: Dictionary of supervia parameters per layer
    """
    finfet.opt.log_comment("At layer M0, if a node is connected to a via, it must be connected to the metal layer ...")
    # NOTE: SMTCell implements this at flow level
    for u in finfet.lgg.nodes_in_layer("M0"):
        if supervia_params["M0"]:
            # if the layer is a supervia, then we need to skip this layer
            continue
        # get the down neighbor
        layer_idx = u[0]
        row = u[1]
        col = u[2]
        u_d = (layer_idx - 1, row, col)
        if not finfet.lgg.is_node_in_graph(u_d):
            continue
        via_edge = finfet.edge_vars[(u_d, u)]
        metal_edges = []
        # get the left neighbor
        u_l = finfet.lgg.get_left_neighbor(u)
        if u_l is not None:
            metal_edges.append(finfet.edge_vars[(u_l, u)])
        # get the right neighbor
        u_r = finfet.lgg.get_right_neighbor(u)
        if u_r is not None:
            metal_edges.append(finfet.edge_vars[(u, u_r)])
        # Reify the condition that at least one metal edge is active
        # u is (M0_layer_idx, row, col)
        has_metal_connection_var = finfet.opt.NewBoolVar(f"has_metal_conn_M0_R{u[1]}_C{u[2]}")
        if not metal_edges:
            # If there are no possible metal edges connected to u on M0,
            # then has_metal_connection_var must be false.
            finfet.opt.Add(has_metal_connection_var == 0)
        else:
            # has_metal_connection_var is true if OR(metal_edges) is true
            finfet.opt.AddBoolOr(metal_edges).OnlyEnforceIf(has_metal_connection_var)
            # If any metal_edge is true, then has_metal_connection_var must be true
            # (This establishes the other direction of the equivalence: OR(metal_edges) => has_metal_connection_var)
            for metal_edge_var in metal_edges:
                finfet.opt.AddImplication(metal_edge_var, has_metal_connection_var)
        # if the via edge exists, then there must be a metal edge connection at u on M0
        finfet.opt.AddImplication(via_edge, has_metal_connection_var)


def _gather_bottom_via_between_nodes(finfet, layer_idx, u_1, u_2):
    """
    Helper function to gather via edges between two nodes u_1 and u_2 on a specific layer.
    Returns a list of via edges if they exist, otherwise returns an empty list.

    Args:
        finfet: The FinFET instance
        layer_idx: The layer index
        u_1: First node tuple (layer_idx, row, col)
        u_2: Second node tuple (layer_idx, row, col)

    Returns:
        List of via edge variables
    """
    via_edges = []
    assert finfet.lgg.is_node_in_graph(u_1), f"Node {u_1} does not exist in the graph"
    assert finfet.lgg.is_node_in_graph(u_2), f"Node {u_2} does not exist in the graph"
    assert layer_idx == u_1[0] == u_2[0], f"Layer index mismatch: {layer_idx} != {u_1[0]} or {u_2[0]}"

    if finfet.lgg.layer_to_direction[finfet.lgg.idx_to_layer[layer_idx]] == "V":
        assert u_1[2] == u_2[2], f"Nodes {u_1} and {u_2} must be in the same column for vertical layers"
        bottom_layer_idx = layer_idx - 1
        if bottom_layer_idx < 0:
            return via_edges
        start_row = min(u_1[1], u_2[1])
        end_row = max(u_1[1], u_2[1])
        col = u_1[2]

        # get the nearest node in the bottom layer
        nearest_node = finfet.lgg.get_nearest_node_in_layer(layer=bottom_layer_idx, row=start_row, col=u_1[2])
        assert nearest_node is not None, f"No nearest node found in layer {bottom_layer_idx} at column {u_1[2]}"
        # latch on to the nearest node and start iterating through the rows
        current_row = nearest_node[1]
        for row in finfet.lgg.get_layer_rows_starting_from(layer=bottom_layer_idx, row=current_row):
            if not (start_row <= row <= end_row):
                continue
            current_bottom_node = (bottom_layer_idx, row, col)
            # check if the current bottom node has a via above
            if finfet.lgg.has_via_above(node=current_bottom_node):
                nn_above = finfet.lgg.get_via_above(node=current_bottom_node)
                via_edge = finfet.edge_vars.get((current_bottom_node, nn_above))
                assert via_edge is not None, f"Via edge between {current_bottom_node} and {nn_above} does not exist"
                via_edges.append(via_edge)

    elif finfet.lgg.layer_to_direction[finfet.lgg.idx_to_layer[layer_idx]] == "H":
        assert u_1[1] == u_2[1], f"Nodes {u_1} and {u_2} must be in the same row for horizontal layers"
        bottom_layer_idx = layer_idx - 1
        if bottom_layer_idx < 0:
            return via_edges
        start_col = min(u_1[2], u_2[2])
        end_col = max(u_1[2], u_2[2])
        row = u_1[1]

        # get the nearest node in the bottom layer
        nearest_node = finfet.lgg.get_nearest_node_in_layer(layer=bottom_layer_idx, row=u_1[1], col=start_col)
        assert nearest_node is not None, f"No nearest node found in layer {bottom_layer_idx} at row {u_1[1]}"
        # latch on to the nearest node and start iterating through the columns
        current_col = nearest_node[2]
        for col in finfet.lgg.get_layer_cols_starting_from(layer=bottom_layer_idx, col=current_col):
            if not (start_col <= col <= end_col):
                continue
            current_bottom_node = (bottom_layer_idx, row, col)
            # check if the current bottom node has a via above
            if finfet.lgg.has_via_above(node=current_bottom_node):
                nn_above = finfet.lgg.get_via_above(node=current_bottom_node)
                via_edge = finfet.edge_vars.get((current_bottom_node, nn_above))
                assert via_edge is not None, f"Via edge between {current_bottom_node} and {nn_above} does not exist"
                via_edges.append(via_edge)
    else:
        raise ValueError(f"Layer {finfet.lgg.idx_to_layer[layer_idx]} is neither horizontal nor vertical")

    return via_edges


def vertical_metal_must_be_connected_to_via(finfet):
    """
    For each vertical layer, if a node is connected to a vertical metal edge,
    it must also be connected to a via.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment("Vertical metal must be connected to a via ...")
    for layer, idx in finfet.lgg.layer_to_idx.items():
        if finfet.lgg.layer_to_direction[layer] != "V":
            continue
        if idx == 0:  # Skip the first layer
            continue
        for row in finfet.lgg.rows_in_layer(layer):
            for col in finfet.lgg.cols_in_layer(layer):
                u = (idx, row, col)
                gvf_u = finfet.geometric_vars[u]["front"]
                current_u = u
                while True:
                    u_b = finfet.lgg.get_front_neighbor(current_u)  # BUG: front/back are swapped
                    if u_b is None:
                        break
                    gvb_u = finfet.geometric_vars[u]["back"]
                    # gather all via edges between u and its back neighbor
                    via_edges = _gather_bottom_via_between_nodes(finfet, layer_idx=idx, u_1=u, u_2=u_b)
                    # if there are no via edges, then these two nodes cannot be true together
                    if not via_edges:
                        # not((gvf_u and gvb_u))
                        finfet.opt.AddImplication(gvf_u, gvb_u.Not())
                        finfet.opt.AddImplication(gvb_u, gvf_u.Not())
                    else:
                        # if there are via edges, then we need to ensure that at least one of them is true when gvf_u and gvb_u are true
                        # Create a variable for the conjunction (gvf_u AND gvb_u)
                        both_vars = finfet.opt.NewBoolVar(f"both_gv_L{idx}_R{row}_C{col}_and_gvB_L{idx}_R{u_b[1]}_C{u_b[2]}")

                        # Set both_vars to be equivalent to (gvf_u AND gvb_u)
                        finfet.opt.AddBoolAnd([gvf_u, gvb_u]).OnlyEnforceIf(both_vars)
                        finfet.opt.Add(gvf_u + gvb_u < 2).OnlyEnforceIf(both_vars.Not())

                        # If both_vars is true, then at least one via edge must be true
                        # Add a constraint that if both geometric variables are true, at least one via must be true
                        finfet.opt.Add(sum(via_edges) >= 1).OnlyEnforceIf(both_vars)
                    current_u = u_b  # Move to the next node in the vertical direction


def horizontal_metal_must_be_connected_to_via(finfet):
    """
    For each horizontal layer, if a node is connected to a horizontal metal edge,
    it must also be connected to a via.

    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment("Horizontal metal must be connected to a via ...")
    for layer, idx in finfet.lgg.layer_to_idx.items():
        if finfet.lgg.layer_to_direction[layer] != "H":
            continue
        if idx == 0:
            continue
        for row in finfet.lgg.rows_in_layer(layer):
            for col in finfet.lgg.cols_in_layer(layer):
                u = (idx, row, col)
                gvl_u = finfet.geometric_vars[u]["left"]
                current_u = u
                while True:
                    u_r = finfet.lgg.get_right_neighbor(current_u)
                    if u_r is None:
                        break
                    gvr_u = finfet.geometric_vars[u]["right"]
                    # gather all via edges between u and its right neighbor
                    via_edges = _gather_bottom_via_between_nodes(finfet, layer_idx=idx, u_1=u, u_2=u_r)
                    # if there are no via edges, then these two nodes cannot be true together
                    if not via_edges:
                        # not((gvl_u and gvr_u))
                        finfet.opt.AddImplication(gvl_u, gvr_u.Not())
                        finfet.opt.AddImplication(gvr_u, gvl_u.Not())
                    else:
                        # if there are via edges, then we need to ensure that at least one of them is true when gvl_u and gvr_u are true
                        # Create a variable for the conjunction (gvl_u AND gvr_u)
                        both_vars = finfet.opt.NewBoolVar(f"both_gv_L{idx}_R{row}_C{col}_and_gvR_L{idx}_R{u_r[1]}_C{u_r[2]}")

                        # Set both_vars to be equivalent to (gvl_u AND gvr_u)
                        finfet.opt.AddBoolAnd([gvl_u, gvr_u]).OnlyEnforceIf(both_vars)
                        finfet.opt.Add(gvl_u + gvr_u < 2).OnlyEnforceIf(both_vars.Not())

                        # If both_vars is true, then at least one via edge must be true
                        # Add a constraint that if both geometric variables are true, at least one via must be true
                        finfet.opt.Add(sum(via_edges) >= 1).OnlyEnforceIf(both_vars)
                    current_u = u_r

def via_separation_rules(finfet_instance, via_params):
    """
    Enforce via separation rules to ensure vias maintain minimum L1 (Manhattan) distance.

    Args:
        finfet_instance: The FinFET instance containing the opt, lgg, and edge_vars
        via_params: Dictionary mapping layer pairs to via separation distance parameters
    """
    DEBUG_VR_DIST = False
    finfet_instance.opt.log_comment(f"Enforcing via separation rules (L1 Manhattan distance)...")
    for layer_pair, via_dist in via_params.items():
        layer_1, layer_2 = layer_pair
        # check layer direction
        hori_layer, vert_layer = None, None
        if finfet_instance.lgg.layer_to_direction[layer_1] == "H":
            hori_layer = layer_1
            vert_layer = layer_2
        elif finfet_instance.lgg.layer_to_direction[layer_2] == "H":
            hori_layer = layer_2
            vert_layer = layer_1
        else:
            raise ValueError(f"Layer {layer_1} and {layer_2} are not horizontal or vertical")
        
        # Get all rows and columns
        all_rows = finfet_instance.lgg.rows_in_layer(hori_layer)
        all_cols = finfet_instance.lgg.cols_in_layer(vert_layer)
        
        for row in all_rows:
            for col in all_cols:
                u_1 = (finfet_instance.lgg.layer_to_idx[layer_1], row, col)
                u_2 = (finfet_instance.lgg.layer_to_idx[layer_2], row, col)
                via_edge = finfet_instance.edge_vars[(u_1, u_2)]
                absl_logging.info(f"Node: {u_1} via dist: {via_dist}") if DEBUG_VR_DIST else None
                # check if the edge exists
                if via_edge is None:
                    raise ValueError(f"Edge {u_1} and {u_2} does not exist") if DEBUG_VR_DIST else None
                
                via_list = []
                via_list.append(via_edge)
                
                # Iterate over all possible positions within L1 distance
                # L1 distance = |row_delta| + |col_delta| < via_dist
                for other_row in all_rows:
                    row_delta = abs(other_row - row)
                    if row_delta >= via_dist:
                        continue  # Too far in row direction alone
                    
                    # Calculate remaining distance budget for column
                    max_col_delta = via_dist - row_delta - 1
                    
                    for other_col in all_cols:
                        col_delta = abs(other_col - col)
                        
                        # Skip the current via position
                        if other_row == row and other_col == col:
                            continue
                        
                        # Check if within L1 distance
                        l1_distance = row_delta + col_delta
                        if l1_distance >= via_dist:
                            continue
                        
                        # Check if this via position exists in the graph
                        u_1_other = (finfet_instance.lgg.layer_to_idx[layer_1], other_row, other_col)
                        u_2_other = (finfet_instance.lgg.layer_to_idx[layer_2], other_row, other_col)
                        
                        if not finfet_instance.lgg.is_node_in_graph(u_2_other):
                            continue
                        
                        # Get the via edge variable
                        other_via_edge = finfet_instance.edge_vars.get((u_1_other, u_2_other))
                        if other_via_edge is not None:
                            via_list.append(other_via_edge)
                            absl_logging.info(
                                f"\tBanning via at ({other_row}, {other_col}), "
                                f"L1 distance: {l1_distance} < {via_dist}"
                            ) if DEBUG_VR_DIST else None
                
                # add the via constraints
                if len(via_list) > 1:
                    # At most one via can be active among all vias within L1 distance
                    finfet_instance.opt.AddAtMostOne(via_list)
