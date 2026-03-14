"""
Pin-related constraints for FinFET layout optimization.
This module contains all pin constraint implementations.
"""

from absl import logging as absl_logging
from src.utility.util import split_into_parts, spaced_subsequences, half_permutations


def m1_minimum_pin_opening(finfet, top_layer, mar_params, eol_params):
    """
    Enforce minimum pin opening for M1 pins.
    
    Args:
        finfet: The FinFET instance
        top_layer: The top metal layer name (e.g., "M2")
        mar_params: Metal-to-metal spacing parameters
        eol_params: End-of-line spacing parameters
    """
    finfet.opt.log_comment(f"Enforcing SON entry point for M1 ...")
    if finfet.M1_MPO > finfet.lgg.num_rows_in_layer(top_layer):
        raise ValueError(f"Invalid M1 MPO: Number of entry points for M1 is greater than number of rows in {top_layer}")
    top_layer_MAR = mar_params[top_layer]
    top_layer_EOL = eol_params[top_layer]
    for netname in finfet.node_is_SON_vars.keys():
        top_layer_usage_var = finfet.net_use_top_track[netname]
        # NOTE in Nexus, k is added to represent multi-pin scenario, However, usually there just one k
        for k in finfet.node_is_SON_vars[netname].keys():
            for node in finfet.node_is_SON_vars[netname][k].keys():
                node_col = node[2]
                SON_var = finfet.node_is_SON_vars[netname][k][node]
                # if SON_var is set to true and there is no M2 access, then MPO rule is enforced
                # NOTE: since we always enforce that no two SONs can occupy the same M1 track, we assume valid M1 access across the entire row
                tmp_entry_point_vars = {}
                for row in finfet.lgg.rows_in_layer(top_layer):
                    tmp_entry_point_vars[row] = finfet.opt.NewBoolVar(f"SON_entry_point_{netname}_{k}_{node}_at_{row}")
                    # entry point is valid if and only if one of the M2 window is valid or entire track is empty
                    # 1. if entire track is empty, then entry point is valid
                    curr_track_vars = [finfet.net_use_top_track_row_var[net.name][row] for net in finfet.circuit.get_nets(with_power_ground=False)]
                    # # if X = false then at least one track_var must be 1
                    # finfet.opt.Add(sum(curr_track_vars) >= 1).OnlyEnforceIf(tmp_entry_point_vars[row].Not())
                    finfet.opt.Add(tmp_entry_point_vars[row] == 1).OnlyEnforceIf([sv.Not() for sv in curr_track_vars])
                    # 2. M2 window is valid <=> entry point is valid
                    upper_node = (finfet.lgg.layer_to_idx[top_layer], row, node_col)
                    assert finfet.lgg.is_node_in_graph(upper_node)
                    # gather all the arcs that needs to be banned from upper layer for this entry point to be valid
                    prohibited_net_arcs = finfet.extract_windows_horizontal_bidirectional(upper_node, top_layer_MAR + top_layer_EOL * 2)
                    # absl_logging.info(
                    #     f"Net: {netname} Row: {row} upper_node: {upper_node} top_layer prohibit zone: {top_layer_MAR+ top_layer_EOL * 2}, prohibited_net_arcs: {prohibited_net_arcs}"
                    # )
                    # for each window along the track, create a var and bind it
                    tmp_window_vars = []
                    # for each window, create a var and bind it to an window var
                    for pna in prohibited_net_arcs:
                        tmp_window_vars.append(
                            finfet.opt.NewBoolVar(f"SON_window_{netname}_{k}_{node}_at_{row}_start_{pna['start']}_end_{pna['end']}")
                        )
                        # if the arc is not empty, then we need to add the constraints
                        if len(pna["arcs"]) > 0:
                            # strictly prohibiting all other nets
                            tmp_other_net_arc_vars = []
                            for other_net in finfet.circuit.get_nets(with_power_ground=False):
                                for arc in pna["arcs"]:
                                    if other_net.name == netname:
                                        continue
                                    other_net_arc_var = finfet.net_arc_vars[(other_net.name, arc[0], arc[1])]
                                    tmp_other_net_arc_vars.append(other_net_arc_var)
                                    # If window is valid, then net arc must be NOT
                                    finfet.opt.AddImplication(tmp_window_vars[-1], other_net_arc_var.Not())
                            # If all net arcs are NOT, then window is valid
                            finfet.opt.Add(tmp_window_vars[-1] == 1).OnlyEnforceIf(
                                [other_net_arc_var.Not() for other_net_arc_var in tmp_other_net_arc_vars]
                            )
                        else:
                            absl_logging.info(f"\tEmpty arc for window {tmp_window_vars[-1]}")
                            finfet.opt.Add(tmp_window_vars[-1] == 0)
                    # an entry point is valid if and only if at least one of the windows is valid
                    if len(tmp_window_vars) > 0:
                        # entry point -> at least one window is valid
                        finfet.opt.Add(sum(tmp_window_vars) >= 1).OnlyEnforceIf(tmp_entry_point_vars[row])
                        # NOT entry point -> all windows are invalid
                        finfet.opt.Add(sum(tmp_window_vars) == 0).OnlyEnforceIf(tmp_entry_point_vars[row].Not())

                # if M1 pin SON and top layer is not used, sum of entry point vars must be at least M1_MPO
                finfet.opt.Add(sum(tmp_entry_point_vars.values()) >= finfet.M1_MPO).OnlyEnforceIf([SON_var, top_layer_usage_var.Not()])


def pin_separation_by_minimum_gap(finfet, pin_min_gaps):
    """
    Separate SON terminals by enforcing a minimum gap between pins.
    
    Args:
        finfet: The FinFET instance
        pin_min_gaps: List of minimum gap values to try
    """
    max_col = finfet.lgg.max_col_in_layer("M1")
    # lexicographically sort the net order
    net_orders = list(half_permutations(finfet.circuit.io_net_names()))
    for min_gap in pin_min_gaps:
        if finfet.lgg.num_cols_in_layer("M1") <= finfet.num_pins_for_io:  # there is no enough space to separate the SON terminals
            continue
        # spacing out the SON terminals
        valid_pin_location = spaced_subsequences(lst=finfet.lgg.cols_in_layer("M1"), k=finfet.num_pins_for_io, min_gap=min_gap)
        absl_logging.info(f"Valid pin locations for min_gap {min_gap}: {valid_pin_location}")
        if len(valid_pin_location) == 0:  # in case no valid separation is found
            continue
        finfet.min_gap_to_pin_placement_case_vars[min_gap] = []
        # bind it to the SON terminals
        for valid_pin_cols in valid_pin_location:
            for net_order in net_orders:
                pin_col_net_var = finfet.opt.NewBoolVar(f"valid_pin_cols_{valid_pin_cols}_for_{net_order}")
                absl_logging.info(f"Valid pin location for net {net_order}: {valid_pin_cols}")
                assert len(valid_pin_cols) == len(net_order)
                tmp_pin_net_case = []
                row = finfet.fin_tech.get_pitch("M0")
                for i, pin_col in enumerate(valid_pin_cols):
                    node = (finfet.lgg.layer_to_idx["M1"], row, pin_col)
                    # NOTE: alternating the row for the SON terminals
                    # WARNING: THIS MIGHT BE A PROBLEM for DH and CFET
                    if row == finfet.fin_tech.get_pitch("M0"):
                        row = finfet.fin_tech.get_pitch("M0") * 2
                    else:
                        row = finfet.fin_tech.get_pitch("M0")
                    # tmp_pin_net_case.append(finfet.node_is_SON_vars[net_order[i]][][node])
                    io_net = finfet.circuit.nets[net_order[i]]
                    for k in range(io_net.num_terminals(), finfet.net_to_flow_cnt[io_net.name], 1):
                        tmp_pin_net_case.append(finfet.node_is_SON_vars[io_net.name][k][node])
                # bind to recify the SON terminals
                # Enforce A ⇒ (b1 ∧ b2 ∧ …)
                finfet.opt.AddBoolAnd(tmp_pin_net_case).OnlyEnforceIf(pin_col_net_var)
                # # Enforce (b1 ∧ b2 ∧ …) ⇒ A
                finfet.opt.AddBoolOr([pnc.Not() for pnc in tmp_pin_net_case] + [pin_col_net_var])
                finfet.pin_placement_case_vars.append(pin_col_net_var)
                finfet.min_gap_to_pin_placement_case_vars[min_gap].append(pin_col_net_var)
    absl_logging.info(f"Valid pin locations for SON terminals: {finfet.pin_placement_case_vars}")
    absl_logging.info(f"min_gap_to_pin_placement_case_vars: {finfet.min_gap_to_pin_placement_case_vars}")
    # enforce the SON terminals to be separated
    finfet.opt.AddBoolOr(finfet.pin_placement_case_vars)


def pin_separation_by_partition(finfet, mode):
    """
    Separate SON terminals into partitions based on mode.
    
    Args:
        finfet: The FinFET instance
        mode: "SAFE" or "AGGRESSIVE" partition mode
    """
    # print(f"finfet.num_pins_for_io: {finfet.num_pins_for_io}")
    routing_partition_group = split_into_parts(lst=finfet.lgg.cols_in_layer("M1"), n=finfet.num_pins_for_io, must_equal_length=True)
    if mode == "SAFE":
        # check if each partition has more than 2 allocated points
        for partition in routing_partition_group:
            if len(partition) <= 2:
                absl_logging.error(f"Partition {partition} has less than 3 allocated points. Disabling pin separation.")
                return
            # NOTE: do not partition small cells like INVX1 to avoid infeasibility
        canvas_width_is_enough = finfet.min_boundary_col > 4 * finfet.fin_tech.get_pitch("PC")
    elif mode == "AGGRESSIVE":
        canvas_width_is_enough = finfet.min_boundary_col > 2 * finfet.fin_tech.get_pitch("PC")
        pass
    # cache the routing pin variables
    routing_pin_vars = {}
    # lexicographically sort the net order
    net_orders = list(half_permutations(finfet.circuit.io_net_names()))
    # routing_partition_group = [[15, 75, 135], [195, 255, 315], [375, 435, 495], [495, 555, 615]]
    all_net_order_vars = []
    absl_logging.info(f"Routing partition group: {routing_partition_group}")
    if canvas_width_is_enough:
        for net_order in net_orders:
            # represent the order of the nets given
            routing_net_order_var = finfet.opt.NewBoolVar(f"net_partition_{net_order}")
            all_net_order_vars.append(routing_net_order_var)
            # net_order = ["I1", "S", "I0", "Z"]
            # net_order = ["QN", "D", "CLK"]
            tmp_partitioned_pin_locations_vars = []
            for i, net_pin in enumerate(net_order):
                key_pin = (net_pin, i)
                if key_pin not in routing_pin_vars:
                    name = f"routing_{net_pin}_within_partition_group_{i}"
                    routing_pin_vars[key_pin] = finfet.opt.NewBoolVar(name)
                tmp_net_pin = routing_pin_vars[key_pin]
                # tmp_net_pin = finfet.opt.NewBoolVar(f"routing_{net_pin}_within_partition_group_{i}")
                absl_logging.info(f"Net {net_pin} is in {routing_partition_group[i]}")
                io_net = finfet.circuit.nets[net_pin]
                # represent each net's routing range within the partition
                tmp_partitioned_pin_locations = []
                for col in routing_partition_group[i]:
                    # bind it to the SON terminals
                    row = finfet.fin_tech.get_pitch("M0")  # fix
                    node = (finfet.lgg.layer_to_idx["M1"], row, col)
                    for k in range(io_net.num_terminals(), finfet.net_to_flow_cnt[io_net.name], 1):
                        tmp_partitioned_pin_locations.append(finfet.node_is_SON_vars[io_net.name][k][node])
                absl_logging.info(f"Partitioned pin locations for net {net_pin}: {tmp_partitioned_pin_locations}")
                finfet.opt.Add(sum(tmp_partitioned_pin_locations) == 1).OnlyEnforceIf(tmp_net_pin)
                finfet.opt.Add(sum(tmp_partitioned_pin_locations) == 0).OnlyEnforceIf(tmp_net_pin.Not())
                tmp_partitioned_pin_locations_vars.append(tmp_net_pin)
            # if tmp_partitioned_pin_locations_vars are all true, then routing_net_order_var must be true
            finfet.opt.AddBoolAnd(tmp_partitioned_pin_locations_vars).OnlyEnforceIf(routing_net_order_var)
            # if routing_net_order_var is true, then all tmp_partitioned_pin_locations_vars must be true
            finfet.opt.AddBoolOr([tnp_var.Not() for tnp_var in tmp_partitioned_pin_locations_vars] + [routing_net_order_var])
        # enforce the SON terminals to be separated
        finfet.opt.AddExactlyOne(all_net_order_vars)


def top_layer_net_usage(finfet, top_layer):
    """
    Bind net usage on top layer.
    
    Args:
        finfet: The FinFET instance
        top_layer: The top metal layer name
    """
    finfet.opt.log_comment(f"Binding net usage on top layer ...")
    for net in finfet.circuit.get_nets(with_power_ground=False):
        finfet.net_use_top_track_row_var[net.name] = {}
        finfet.net_use_top_track[net.name] = finfet.opt.NewBoolVar(f"net_{net.name}_{top_layer}_TRACK")
        tmp_vars = []
        for row in finfet.lgg.rows_in_layer(top_layer):
            finfet.net_use_top_track_row_var[net.name][row] = finfet.opt.NewBoolVar(f"net_{net.name}_{top_layer}_TRACK_R{row}")
            tmp_vars.append(finfet.net_use_top_track_row_var[net.name][row])
            tmp_net_arcs = []
            tmp_net_flows = []
            # check if the net is connected to the top layer
            # NOTE: In SMTCell, this is binded to flow
            # NOTE: In Nexus, we should bind it to the net arc to prevent unwanted edges
            for u, v in finfet.lgg.arcs():
                # either u or v must reach the top layer
                if not (u[0] == finfet.lgg.layer_to_idx[top_layer] or v[0] == finfet.lgg.layer_to_idx[top_layer]):
                    continue
                # both u and v must be on the same row
                if u[1] != v[1]:
                    continue
                # both u and v must have the same row as the row of the top layer
                if u[1] != row and v[1] != row:
                    continue
                tmp_net_arcs.append(finfet.net_arc_vars[(net.name, u, v)])
                for k in range(finfet.net_to_flow_cnt[net.name]):
                    tmp_net_flows.append(finfet.net_flow_vars[(net.name, k, u, v)])
            # absl_logging.info(f"Net: {net.name} Row: {row} tmp_net_arcs: {tmp_net_arcs}")
            # binding the track access var to the net arcs
            if len(tmp_net_arcs) > 0:
                # 1. X implies (A or B or C ...)
                finfet.opt.Add(sum(tmp_net_arcs) >= 1).OnlyEnforceIf(finfet.net_use_top_track_row_var[net.name][row])
                # 2. (not X) implies (not (A or B or C ...))
                finfet.opt.Add(sum(tmp_net_arcs) == 0).OnlyEnforceIf(finfet.net_use_top_track_row_var[net.name][row].Not())
            if len(tmp_net_flows) > 0:
                # 1. X implies (A or B or C ...)
                finfet.opt.Add(sum(tmp_net_flows) >= 1).OnlyEnforceIf(finfet.net_use_top_track_row_var[net.name][row])
                # 2. (not X) implies (not (A or B or C ...))
                finfet.opt.Add(sum(tmp_net_flows) == 0).OnlyEnforceIf(finfet.net_use_top_track_row_var[net.name][row].Not())
        finfet.opt.Add(sum(tmp_vars) >= 1).OnlyEnforceIf(finfet.net_use_top_track[net.name])
        finfet.opt.Add(sum(tmp_vars) == 0).OnlyEnforceIf(finfet.net_use_top_track[net.name].Not())


def one_top_layer_track_per_net(finfet, top_layer):
    """
    Enforce that each net uses one top layer track at most.
    
    Args:
        finfet: The FinFET instance
        top_layer: The top metal layer name
    """
    finfet.opt.log_comment(f"Enforcing Each net uses one M2 track at most ...")
    for net in finfet.circuit.get_nets(with_power_ground=False):
        tmp_net_row_vars = []
        for row in finfet.lgg.rows_in_layer(top_layer):
            tmp_net_row_vars.append(finfet.net_use_top_track_row_var[net.name][row])
        # at most one track can be used for each net
        finfet.opt.AddAtMostOne(tmp_net_row_vars)


def one_net_per_top_layer_track(finfet, top_layer):
    """
    Enforce that each top layer track can be used by one net at most.
    
    Args:
        finfet: The FinFET instance
        top_layer: The top metal layer name
    """
    finfet.opt.log_comment(f"Enforcing each M2 track can be used by one net at most ...")
    for row in finfet.lgg.rows_in_layer(top_layer):
        tmp_row_net_vars = []
        for net in finfet.circuit.get_nets(with_power_ground=False):
            tmp_row_net_vars.append(finfet.net_use_top_track_row_var[net.name][row])
        # absl_logging.info(f"Row: {row} tmp_row_net_vars: {tmp_row_net_vars}")
        # at most one net can use each track
        finfet.opt.AddAtMostOne(tmp_row_net_vars)


def m0_pin(finfet):
    """
    Enforce SON entry point for M0 pins.
    
    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing SON entry point for M0 ...")
    if finfet.M1_MPO > finfet.lgg.num_cols_in_layer("M1"):
        raise ValueError(f"Invalid M0 MPO: Number of entry points for M0 is greater than number of cols in M1")
    # Store M0 pin variables for later use in separation constraint
    finfet.m0_pin_vars = {}  # netname -> m0_pin_var
    finfet.m0_pin_rows = {}  # netname -> M0 row (when it's an M0 pin)
    for netname in finfet.node_is_SON_vars.keys():
        # A net is an M0 Pin if and only if:
        # 1. It has NO arcs activated on M2 layer
        # 2. It has exactly one via connection from M0 to M1
        
        m0_pin_var = finfet.opt.NewBoolVar(f"M0_pin_{netname}")
        
        # Gather all M2 arcs for this net
        tmp_m2_arcs = []
        for u, v in finfet.lgg.arcs():
            if u[0] == finfet.lgg.layer_to_idx["M2"] and v[0] == finfet.lgg.layer_to_idx["M2"]:
                tmp_m2_arcs.append(finfet.net_arc_vars[(netname, u, v)])
        
        # Gather all V0 vias (M0 to M1) for this net
        tmp_v0_vias = finfet._gather_via_arcs(netname, "M0", "M1")
        
        # Condition 1: No M2 arcs
        no_m2_arc = finfet.opt.NewBoolVar(f"no_m2_arc_{netname}")
        if len(tmp_m2_arcs) > 0:
            finfet.opt.Add(sum(tmp_m2_arcs) == 0).OnlyEnforceIf(no_m2_arc)
            finfet.opt.Add(sum(tmp_m2_arcs) > 0).OnlyEnforceIf(no_m2_arc.Not())
        else:
            # No M2 arcs exist for this net, so condition is always true
            finfet.opt.Add(no_m2_arc == 1)
        
        # Condition 2: Exactly one V0 via
        one_v0_via = finfet.opt.NewBoolVar(f"one_v0_via_{netname}")
        if len(tmp_v0_vias) > 0:
            finfet.opt.Add(sum(tmp_v0_vias) == 1).OnlyEnforceIf(one_v0_via)
            finfet.opt.Add(sum(tmp_v0_vias) != 1).OnlyEnforceIf(one_v0_via.Not())
        else:
            # No V0 vias exist, so condition is always false
            finfet.opt.Add(one_v0_via == 0)
        
        # Store the M0 pin variable for separation constraint
        finfet.m0_pin_vars[netname] = m0_pin_var
        
        # m0_pin_var is true if and only if both conditions are true
        finfet.opt.AddMultiplicationEquality(m0_pin_var, [no_m2_arc, one_v0_via])


def m0_pin_separation(finfet):
    """
    Enforce that no two IO nets can have M0 routing on the same M0 row.
    This prevents nets from evading the constraint by using multiple vias.
    For each M0 row, gather all IO nets that could have M0 routing on that row,
    and ensure at most one IO net is active on that row.
    
    Args:
        finfet: The FinFET instance
    """
    finfet.opt.log_comment(f"Enforcing M0 routing separation across rows ...")
    absl_logging.info("\t==\tEnforcing M0 routing separation: no two IO nets on same M0 row")
    
    M0_layer_idx = finfet.lgg.layer_to_idx["M0"]
    
    # For each M0 row, collect all IO nets that could route there
    row_to_net_routing_vars = {}  # m0_row -> list of (netname, net_routes_on_row_var)
    
    # Get all IO net names
    io_net_names = set()
    for net in finfet.circuit.get_nets(with_power_ground=False):
        if net.is_io_net():
            io_net_names.add(net.name)
    
    for m0_row in finfet.lgg.rows_in_layer("M0"):
        row_to_net_routing_vars[m0_row] = []
        
        for netname in io_net_names:
            # Collect all M0 arcs for this net on this row
            net_m0_arcs_on_row = []
            for u, v in finfet.lgg.arcs():
                # Only M0 layer arcs on this row
                if u[0] != M0_layer_idx or v[0] != M0_layer_idx:
                    continue
                if u[1] != m0_row or v[1] != m0_row:
                    continue
                
                arc_key = (netname, u, v)
                if arc_key in finfet.net_arc_vars:
                    net_m0_arcs_on_row.append(finfet.net_arc_vars[arc_key])
            
            if len(net_m0_arcs_on_row) == 0:
                continue
            
            # Create indicator: this net has M0 routing on this row
            net_routes_on_row = finfet.opt.NewBoolVar(f"M0_route_{netname}_on_row_{m0_row}")
            
            # net_routes_on_row = OR(net_m0_arcs_on_row) - at least one M0 arc is active
            finfet.opt.Add(sum(net_m0_arcs_on_row) >= 1).OnlyEnforceIf(net_routes_on_row)
            finfet.opt.Add(sum(net_m0_arcs_on_row) == 0).OnlyEnforceIf(net_routes_on_row.Not())
            
            row_to_net_routing_vars[m0_row].append((netname, net_routes_on_row))
    
    # For each row, at most one IO net can have M0 routing
    for m0_row, net_var_list in row_to_net_routing_vars.items():
        if len(net_var_list) > 1:
            net_vars = [nv for (_, nv) in net_var_list]
            netnames = [nn for (nn, _) in net_var_list]
            finfet.opt.AddAtMostOne(net_vars)
            absl_logging.info(f"\t\tRow {m0_row}: at most one IO net M0 routing among {len(net_vars)} nets: {netnames}")
        elif len(net_var_list) == 1:
            netnames = [nn for (nn, _) in net_var_list]
            absl_logging.info(f"\t\tRow {m0_row}: only {len(net_var_list)} IO net(s): {netnames}")
    
    # Store for use in m0_pin_extension (use the new routing-based vars)
    finfet.m0_pin_row_to_net_vars = row_to_net_routing_vars


def m0_pin_extension(finfet, vacancy_edges=2):
    """
    Ensure that M0 pins have vacant edges at their end-of-line positions.
    For each M0 pin active on a row, find the leftmost and rightmost columns
    used by the net, and ensure at least vacancy_edges adjacent edges are vacant
    beyond these endpoints (combined from left and right).
    
    Args:
        finfet: The FinFET instance
        vacancy_edges: Minimum number of vacant edges required beyond end-of-line
    """
    finfet.opt.log_comment(f"Enforcing M0 pin extension with {vacancy_edges} vacant edges ...")
    absl_logging.info(f"\t==\tEnforcing M0 pin extension: at least {vacancy_edges} vacant edges at end-of-line")
    
    if not hasattr(finfet, 'm0_pin_row_to_net_vars'):
        absl_logging.info("\t\tCreating M0 pin data structure independently...")
        # Create the data structure without separation constraints
        M0_layer_idx = finfet.lgg.layer_to_idx["M0"]
        
        # For each M0 row, collect all IO nets that could route there
        row_to_net_routing_vars = {}  # m0_row -> list of (netname, net_routes_on_row_var)
        
        # Get all IO net names
        io_net_names = set()
        for net in finfet.circuit.get_nets(with_power_ground=False):
            if net.is_io_net():
                io_net_names.add(net.name)
        
        for m0_row in finfet.lgg.rows_in_layer("M0"):
            row_to_net_routing_vars[m0_row] = []
            
            for netname in io_net_names:
                # Collect all M0 arcs for this net on this row
                net_m0_arcs_on_row = []
                for u, v in finfet.lgg.arcs():
                    # Only M0 layer arcs on this row
                    if u[0] != M0_layer_idx or v[0] != M0_layer_idx:
                        continue
                    if u[1] != m0_row or v[1] != m0_row:
                        continue
                    
                    arc_key = (netname, u, v)
                    if arc_key in finfet.net_arc_vars:
                        net_m0_arcs_on_row.append(finfet.net_arc_vars[arc_key])
                
                if len(net_m0_arcs_on_row) == 0:
                    continue
                
                # Create indicator: this net has M0 routing on this row
                net_routes_on_row = finfet.opt.NewBoolVar(f"M0_route_{netname}_on_row_{m0_row}")
                
                # net_routes_on_row = OR(net_m0_arcs_on_row) - at least one M0 arc is active
                finfet.opt.Add(sum(net_m0_arcs_on_row) >= 1).OnlyEnforceIf(net_routes_on_row)
                finfet.opt.Add(sum(net_m0_arcs_on_row) == 0).OnlyEnforceIf(net_routes_on_row.Not())
                
                row_to_net_routing_vars[m0_row].append((netname, net_routes_on_row))
        
        # Store for use in the rest of this function
        finfet.m0_pin_row_to_net_vars = row_to_net_routing_vars
        absl_logging.info(f"\t\tCreated M0 pin data for {len(io_net_names)} IO nets")
    
    M0_layer_idx = finfet.lgg.layer_to_idx["M0"]
    all_m0_cols = sorted(finfet.lgg.cols_in_layer("M0"))
    
    # For each row with potential M0 pins
    for m0_row, net_var_list in finfet.m0_pin_row_to_net_vars.items():
        for netname, net_on_row_var in net_var_list:
            # Collect all M0 horizontal arcs for this net on this row
            # and track which columns are touched
            net_arc_col_vars = {}  # col -> list of arc_vars that touch this col
            
            for u, v in finfet.lgg.arcs():
                # Only M0 horizontal arcs on this row
                if u[0] != M0_layer_idx or v[0] != M0_layer_idx:
                    continue
                if u[1] != m0_row or v[1] != m0_row:
                    continue
                
                arc_key = (netname, u, v)
                if arc_key not in finfet.net_arc_vars:
                    continue
                
                arc_var = finfet.net_arc_vars[arc_key]
                # This arc touches columns u[2] and v[2]
                for col in [u[2], v[2]]:
                    if col not in net_arc_col_vars:
                        net_arc_col_vars[col] = []
                    net_arc_col_vars[col].append(arc_var)
            
            if len(net_arc_col_vars) == 0:
                continue
            
            # Create indicator variables for each column: net uses this column
            col_to_active_var = {}
            for col in all_m0_cols:
                if col in net_arc_col_vars:
                    active_var = finfet.opt.NewBoolVar(f"M0_{netname}_R{m0_row}_C{col}_active")
                    arc_vars = net_arc_col_vars[col]
                    # active if at least one arc touching this col is used
                    finfet.opt.Add(sum(arc_vars) >= 1).OnlyEnforceIf(active_var)
                    finfet.opt.Add(sum(arc_vars) == 0).OnlyEnforceIf(active_var.Not())
                    col_to_active_var[col] = active_var
            
            # Find leftmost active column indicator
            # leftmost_col_var[c] = net uses col c AND net does NOT use any col < c
            leftmost_col_vars = {}
            for i, col in enumerate(all_m0_cols):
                if col not in col_to_active_var:
                    continue
                
                leftmost_var = finfet.opt.NewBoolVar(f"M0_{netname}_R{m0_row}_leftmost_C{col}")
                
                # Cols to the left that this net could use
                left_cols_active = [col_to_active_var[c] for c in all_m0_cols[:i] if c in col_to_active_var]
                
                if len(left_cols_active) == 0:
                    # No cols to left, so leftmost if this col is active
                    finfet.opt.Add(leftmost_var == col_to_active_var[col])
                else:
                    # leftmost = active AND none to the left are active
                    no_left_active = finfet.opt.NewBoolVar(f"M0_{netname}_R{m0_row}_no_left_of_C{col}")
                    finfet.opt.Add(sum(left_cols_active) == 0).OnlyEnforceIf(no_left_active)
                    finfet.opt.Add(sum(left_cols_active) >= 1).OnlyEnforceIf(no_left_active.Not())
                    finfet.opt.AddMultiplicationEquality(leftmost_var, [col_to_active_var[col], no_left_active])
                
                leftmost_col_vars[col] = leftmost_var
            
            # Find rightmost active column indicator
            # rightmost_col_var[c] = net uses col c AND net does NOT use any col > c
            rightmost_col_vars = {}
            for i, col in enumerate(all_m0_cols):
                if col not in col_to_active_var:
                    continue
                
                rightmost_var = finfet.opt.NewBoolVar(f"M0_{netname}_R{m0_row}_rightmost_C{col}")
                
                # Cols to the right that this net could use
                right_cols_active = [col_to_active_var[c] for c in all_m0_cols[i+1:] if c in col_to_active_var]
                
                if len(right_cols_active) == 0:
                    # No cols to right, so rightmost if this col is active
                    finfet.opt.Add(rightmost_var == col_to_active_var[col])
                else:
                    # rightmost = active AND none to the right are active
                    no_right_active = finfet.opt.NewBoolVar(f"M0_{netname}_R{m0_row}_no_right_of_C{col}")
                    finfet.opt.Add(sum(right_cols_active) == 0).OnlyEnforceIf(no_right_active)
                    finfet.opt.Add(sum(right_cols_active) >= 1).OnlyEnforceIf(no_right_active.Not())
                    finfet.opt.AddMultiplicationEquality(rightmost_var, [col_to_active_var[col], no_right_active])
                
                rightmost_col_vars[col] = rightmost_var
            
            # Now collect vacant edge options
            # For each potential leftmost column, collect the `vacancy_edges` edges immediately to its left
            # For each potential rightmost column, collect the `vacancy_edges` edges immediately to its right
            # These edges must ALL be vacant (contiguous vacancy requirement)
            
            # Left EOL: for each leftmost candidate, require edges immediately to its left to be vacant
            for col, leftmost_var in leftmost_col_vars.items():
                col_idx = all_m0_cols.index(col)
                # Collect the first `vacancy_edges` edges immediately to the left
                left_edges_to_check = []
                for j in range(col_idx - 1, max(col_idx - 1 - vacancy_edges, -1), -1):
                    if j < 0:
                        break
                    left_col = all_m0_cols[j]
                    right_col = all_m0_cols[j + 1]
                    node1 = (M0_layer_idx, m0_row, left_col)
                    node2 = (M0_layer_idx, m0_row, right_col)
                    
                    edge_key = (node1, node2) if (node1, node2) in finfet.edge_vars else (node2, node1)
                    if edge_key not in finfet.edge_vars:
                        continue
                    
                    left_edges_to_check.append(finfet.edge_vars[edge_key])
                
                # If this is the leftmost AND we have enough edges, all must be vacant
                if len(left_edges_to_check) >= vacancy_edges:
                    # All these edges must be vacant when leftmost_var is true
                    for edge_var in left_edges_to_check[:vacancy_edges]:
                        finfet.opt.AddImplication(leftmost_var, edge_var.Not())
                    absl_logging.info(
                        f"\t\t\tNet {netname} leftmost at col {col}: {len(left_edges_to_check)} edges to left, require {vacancy_edges} vacant"
                    )
            
            # Right EOL: for each rightmost candidate, require edges immediately to its right to be vacant
            for col, rightmost_var in rightmost_col_vars.items():
                col_idx = all_m0_cols.index(col)
                # Collect the first `vacancy_edges` edges immediately to the right
                right_edges_to_check = []
                for j in range(col_idx, min(col_idx + vacancy_edges, len(all_m0_cols) - 1)):
                    left_col = all_m0_cols[j]
                    right_col = all_m0_cols[j + 1]
                    node1 = (M0_layer_idx, m0_row, left_col)
                    node2 = (M0_layer_idx, m0_row, right_col)
                    
                    edge_key = (node1, node2) if (node1, node2) in finfet.edge_vars else (node2, node1)
                    if edge_key not in finfet.edge_vars:
                        continue
                    
                    right_edges_to_check.append(finfet.edge_vars[edge_key])
                
                # If this is the rightmost AND we have enough edges, all must be vacant
                if len(right_edges_to_check) >= vacancy_edges:
                    # All these edges must be vacant when rightmost_var is true
                    for edge_var in right_edges_to_check[:vacancy_edges]:
                        finfet.opt.AddImplication(rightmost_var, edge_var.Not())
                    absl_logging.info(
                        f"\t\t\tNet {netname} rightmost at col {col}: {len(right_edges_to_check)} edges to right, require {vacancy_edges} vacant"
                    )

