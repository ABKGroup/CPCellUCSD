import logging
from absl import logging as absl_logging
import math
import itertools
# custom
import src.utility.config as config
from src.utility.entity import Circuit

# Set up logging to print messages
# Custom log format: [LEVEL] TIMESTAMP - MESSAGE
# NOTE: level available: DEBUG, INFO, WARNING, ERROR, CRITICAL
logging.basicConfig(format="[%(levelname)s] %(asctime)s - %(message)s", level=logging.INFO)


def parse_netlist(netlist_text, circuit):
    """
    Parses a subcircuit netlist text and fills in the given Circuit object.
    The netlist should have a .SUBCKT header, transistor lines, and a .ENDS line.
    """
    lines = netlist_text.strip().splitlines()

    for line in lines:
        # Remove any extra whitespace and ignore empty or comment lines.
        line = line.strip()
        if not line or line.startswith("*"):
            continue

        # Parse subcircuit header line
        if line.upper().startswith(".SUBCKT"):
            tokens = line.split()
            if len(tokens) >= 3:
                circuit.subckt_name = tokens[1]
                # circuit.pins = tokens[2:]
                circuit.assign_pins(tokens[2:])
                absl_logging.debug(f"Parsing subcircuit '{circuit}")
            continue

        # End of subcircuit
        if line.upper().startswith(".ENDS"):
            break

        # Otherwise, assume the line is a transistor instance
        tokens = line.split()
        if len(tokens) < 6:
            # Not enough tokens for a valid transistor line
            absl_logging.warning(f"Invalid transistor line: {line}")
            continue

        # The first 6 tokens are fixed:
        # [0]: transistor name, [1]: drain, [2]: gate, [3]: source, [4]: bulk, [5]: model
        t_name = tokens[0]
        source = tokens[1]
        gate = tokens[2]
        drain = tokens[3]
        bulk = tokens[4]
        model = tokens[5]

        # The remaining tokens are parameters (e.g., "w=23.0n", "l=16n", "nfin=1")
        params = {}
        for token in tokens[6:]:
            if "=" in token:
                key, val = token.split("=", 1)
                params[key.lower()] = val  # using lower-case for keys

        # Retrieve parameters; if a parameter is missing, you can set a default (or raise an error)
        w = params.get("w")
        l = params.get("l")
        nfin = params.get("nfin")

        # Add the transistor to the circuit
        circuit.add_transistor(t_name, source=source, gate=gate, drain=drain, bulk=bulk, model=model, w=w, l=l, nfin=nfin)


def read_cdl_file(filename):
    """
    Reads a CDL file and returns all circuit objects found in the file."""
    circuits = []
    with open(filename, "r") as file:
        netlist_texts = file.read()
    flag_subckt = False
    for line in netlist_texts.splitlines():
        if line.startswith("*"):
            continue
        if line.startswith(".SUBCKT"):
            netlist_text = ""
            flag_subckt = True
        if flag_subckt:
            netlist_text += line + "\n"
        if line.startswith(".ENDS"):
            new_circuit = Circuit()
            parse_netlist(netlist_text, new_circuit)
            circuits.append(new_circuit)
            netlist_text = ""
            flag_subckt = False
    return circuits


def is_g_col(col_idx):
    """
    Check if the given column is a gate column.
    """
    return col_idx % 2 == 0 and col_idx != 0


def is_sd_col(col_idx):
    """
    Check if the given column is a source/drain column.
    """
    return col_idx % 2 == 1


def max_func(xs):
    """
    Return the maximum value of the given arguments.
    """
    val = xs[0]
    for x in xs[1:]:
        val = If(UGT(x, val), x, val)
    return val


def min_func(xs):
    """
    Return the minimum value of the given arguments.
    """
    val = xs[0]
    for x in xs[1:]:
        val = If(x < val, x, val)
    return val


def write_pinlayout_file(circuit, output_dir, ignore_bulk=True, style="nex"):
    """
    Export the pinlayout file for the given circuits.
    Legacy step from SMTCell and it is used for debugging purposes.
    """
    with open(f"{output_dir}/{circuit.subckt_name}.pinlayout", "w") as f:
        # header
        f.write(f"a   DesignName = {circuit.subckt_name}\n")
        f.write(f"a   Output File = {output_dir}/{circuit.subckt_name}.pinlayout\n")
        f.write(f"a   Width of Routing Clip    = {0}\n")
        f.write(f"a   Height of Routing Clip   = {0}\n")
        f.write(f"a   Tracks per Placement Row = {0}\n")
        f.write(f"a   Width of Placement Clip  = {0}\n")
        f.write(f"a   Tracks per Placement Clip= {0}\n")
        # transistors (instances)
        f.write(f"i   ===InstanceInfo===\n")
        if style == "spr":
            f.write(f"i   InstID Type Width\n")
        elif style == "nex":
            f.write(f"i   InstID Type Width Length Nfin\n")
        for t in circuit.transistors.values():
            if style == "spr":
                f.write(f"i   ins{t.name} {t.model} {t.w}\n")
            elif style == "nex":
                f.write(f"i   {t.name} {t.model} {t.w} {t.l} {t.nfin}\n")
        # pins
        f.write(f"i   ===PinInfo===\n")
        f.write(f"i   PinID NetID InstID PinName PinDirection PinLength\n")
        # internal pins
        for i, t in enumerate(circuit.transistors.values()):
            # absl_logging.info(f"[YW] Transistor {t.name} has terminals: {t.terminals}")
            for j, (term, net_name) in enumerate(t.terminals.items()):
                if ignore_bulk and term == "bulk":
                    continue
                if style == "spr":
                    f.write(f"i   pin{i*3+j} {net_name} ins{t.name} {term.upper()[0]} 0\n")
                elif style == "nex":
                    f.write(f"i   pin{i*3+j} {net_name} {t.name} {term} 0\n")
        # external
        for pin in circuit.pins:
            f.write(f"i   pin{len(circuit.transistors)*3+circuit.pins.index(pin)} ext {pin} t -1 0\n")
        # nets
        f.write(f"i   ===NetInfo===\n")
        f.write(f"i   NetID N-PinNet PinList\n")
        for net in circuit.nets.values():
            f.write(f"i   {net.name}")
            for tn, p in net.connected_transistors:
                if ignore_bulk and p == "bulk":
                    continue
                f.write(f" {tn}_{p}")
            f.write("\n")


def centered_windows(lst, target, X):
    try:
        idx = lst.index(target)
    except ValueError:
        raise ValueError(f"{target!r} is not in the list")

    # compute bounds for the window's start index
    start_min = max(0, idx - (X - 1))
    start_max = min(idx, len(lst) - X)

    # collect each valid window
    windows = []
    for start in range(start_min, start_max + 1):
        windows.append(lst[start : start + X])
    return windows


def sliding_windows(lst, X):
    # compute bounds for the window's start index
    start_min = 0
    start_max = len(lst) - X

    # collect each valid window
    windows = []
    for start in range(start_min, start_max + 1):
        windows.append(tuple(lst[start : start + X]))
    return windows


def split_into_parts(lst, n, must_equal_length=False, overlap: int = 0):
    if n <= 0:
        raise ValueError("n must be a positive integer")

    length = len(lst)
    if not must_equal_length:
        base_size, remainder = divmod(length, n)
        parts = []
        start = 0
        for i in range(n):
            size = base_size + (1 if i < remainder else 0)
            parts.append(lst[start : start + size])
            start += size
        return parts

    pure_size = math.ceil(length / n)
    if overlap < 0 or overlap >= pure_size:
        raise ValueError(f"overlap must be between 0 and {pure_size-1}")

    window_size = math.ceil((length + (n - 1) * overlap) / n)
    step = window_size - overlap

    parts = []
    for i in range(n):
        start = i * step
        if start > length - window_size:
            start = length - window_size
        parts.append(lst[start : start + window_size])

    return parts


def spaced_subsequences(lst, k, min_gap=1):
    n = len(lst)
    if k <= 0:
        return []
    step = min_gap + 1
    max_start = n - 1 - (k - 1) * step
    if max_start < 0:
        return []
    out = []
    for start in range(max_start + 1):
        seq = [lst[start + i * step] for i in range(k)]
        out.append(seq)
    return out


def half_permutations(lst):
    n = len(lst)
    if n <= 1:
        yield tuple(lst)
        return

    for a, b in itertools.combinations(lst, 2):
        if a < b:
            first, last = a, b
        else:
            first, last = b, a

        rest = [x for x in lst if x is not first and x is not last]
        for mid in itertools.permutations(rest):
            yield (first,) + mid + (last,)


def log_variable_info(opt, solver, filename=None):
    """
    A general way to log all variable information in a solved problem.

    Args:
        opt: The CP-SAT model (CpModel instance)
        solver: The CP-SAT solver (CpSolver instance)
        filename: Optional filename to write the output to. If None, logs to console.
    """
    # Grab the raw protobufs
    model_proto = opt.Proto()
    response_proto = solver.ResponseProto()
    # Zip through every declared variable
    if filename:
        with open(filename, "w") as f:
            f.write("Debugging variable information:\n")
            for var_proto, value in zip(model_proto.variables, response_proto.solution):
                # Each var_proto has `.name` and a domain, `value` is the int assigned (0 or 1 for BoolVars).
                f.write(f"{value}    {var_proto.name:<100}\n")
    else:
        absl_logging.info("Debugging variable information:")
        for var_proto, value in zip(model_proto.variables, response_proto.solution):
            # Each var_proto has `.name` and a domain, `value` is the int assigned (0 or 1 for BoolVars).
            absl_logging.info(f"{var_proto.name:<100} {value}")


def _get_true_edge_netname(solver, net_arc_vars, u_edge, v_edge):
    """
    Get the net name for a given edge by checking the net_arc_vars.

    Args:
        solver: The CP-SAT solver (CpSolver instance)
        net_arc_vars: Dictionary mapping (net_name, u_arc, v_arc) to arc variables
        u_edge: Start node of the edge
        v_edge: End node of the edge

    Returns:
        The net name if found, None otherwise.
    """
    for (net_name, u_arc, v_arc), net_arc_var in net_arc_vars.items():
        if (u_edge, v_edge) == (u_arc, v_arc) and solver.Value(net_arc_var) == 1:
            return net_name
        if (v_edge, u_edge) == (u_arc, v_arc) and solver.Value(net_arc_var) == 1:
            return net_name
    return None


def write_finfet_sh_result(solver, circuit, transistor_vars, edge_vars, net_arc_vars,
                           fin_tech, cpp_cost, filename, merge_segments=True):
    """
    Write the FinFET placement and routing result to a file with neatly aligned columns.

    Args:
        solver: The CP-SAT solver (CpSolver instance)
        circuit: The Circuit object
        transistor_vars: Dictionary of transistor variables
        edge_vars: Dictionary of edge variables
        net_arc_vars: Dictionary of net arc variables
        fin_tech: The FinFET_Tech object
        cpp_cost: The CPP cost variable
        filename: Output filename
        merge_segments: Whether to merge routing segments (default True)
    """
    rescaler = 1.0

    # ——— Placement ———
    placement_rows = []
    for tran in circuit.transistors.values():
        tran_var = transistor_vars[tran.name]
        x = solver.Value(transistor_vars[tran.name].x_var) * fin_tech.get_pitch(layer_name="PC") / rescaler
        y = solver.Value(transistor_vars[tran.name].y_var) * fin_tech.get_pitch(layer_name="M0") * 2 / rescaler
        model = str(tran.model).split(".")[1]
        flip = "F" if solver.Value(transistor_vars[tran.name].flip_var) == 1 else "NF"
        width = fin_tech.get_pitch(layer_name="PC") * 2 / rescaler
        height = fin_tech.num_rt_track // 2 * fin_tech.get_pitch(layer_name="M0")
        s_col, d_col, g_col = -1, -1, -1
        s_net, d_net, g_net = tran.source, tran.drain, tran.gate
        for net_name, col_vars in tran_var.s_col_idx_var.items():
            for col, col_var_list in col_vars.items():
                for col_var_item in col_var_list:
                    if solver.Value(col_var_item) == 1:
                        s_col = col / rescaler
        for net_name, col_vars in tran_var.d_col_idx_var.items():
            for col, col_var_list in col_vars.items():
                for col_var_item in col_var_list:
                    if solver.Value(col_var_item) == 1:
                        d_col = col / rescaler
        for net_name, col_vars in tran_var.g_col_idx_var.items():
            for col, col_var_list in col_vars.items():
                for col_var_item in col_var_list:
                    if solver.Value(col_var_item) == 1:
                        g_col = col / rescaler
        placement_rows.append(
            (
                tran.name,
                f"{x:.1f}",
                f"{y:.1f}",
                flip,
                f"{width:.1f}",
                f"{height:.1f}",
                f"{s_col:.1f}",
                f"{s_net}",
                f"{d_col:.1f}",
                f"{d_net}",
                f"{g_col:.1f}",
                f"{g_net}",
                f"{model}",
            )
        )

    headers = (
        "Name",
        "X",
        "Y",
        "Flip",
        "Width",
        "Height",
        "SrcCol",
        "SrcNet",
        "DrnCol",
        "DrnNet",
        "GCol",
        "GNet",
        "Model",
    )
    cols = list(zip(headers, *placement_rows))
    col_widths = [max(len(str(item)) for item in col) for col in cols]

    parts = []
    for i, w in enumerate(col_widths):
        if i == 0:
            parts.append(f"{{:<{w}}}")
        else:
            parts.append(f"{{:>{w}}}")
    fmt = "  ".join(parts) + "\n"

    with open(filename, "w") as f:
        f.write(f"** Objective value: {solver.ObjectiveValue()}\n\n")
        f.write("** Placement Result **\n")
        f.write(fmt.format(*headers))
        f.write("-" * (sum(col_widths) + 22) + "\n")
        for row in placement_rows:
            f.write(fmt.format(*row))

        # write cell information
        f.write("\n** Cell Information **\n")
        f.write("IO Pins\n")
        f.write("-" * 22 + "\n")
        f.write(" ".join(circuit.io_pins))
        f.write("\n")

        # ——— Routing, with aligned METAL ROW COL NET ———
        f.write("\n** Routing Result **\n")
        if merge_segments:
            # 1) Collect all active segments with their properties
            active_segments_data = []
            for (u_edge, v_edge), edge_var_obj in edge_vars.items():
                if solver.Value(edge_var_obj) == 1:
                    net_name = _get_true_edge_netname(solver, net_arc_vars, u_edge, v_edge)
                    if net_name is None:
                        net_name = "N/A"

                    segment_info = {
                        "net": net_name,
                        "u_raw": u_edge,
                        "v_raw": v_edge,
                        "layer_u_s": u_edge[0],
                        "row_u_s": u_edge[1] / rescaler,
                        "col_u_s": u_edge[2] / rescaler,
                        "layer_v_s": v_edge[0],
                        "row_v_s": v_edge[1] / rescaler,
                        "col_v_s": v_edge[2] / rescaler,
                    }
                    active_segments_data.append(segment_info)

            routing_rows = []
            processed_segment_indices = [False] * len(active_segments_data)

            # 2) Iterate through collected segments to merge them
            for i in range(len(active_segments_data)):
                if processed_segment_indices[i]:
                    continue

                initial_segment = active_segments_data[i]
                processed_segment_indices[i] = True

                current_path_u_raw = initial_segment["u_raw"]
                current_path_v_raw = initial_segment["v_raw"]
                current_path_net = initial_segment["net"]

                # Handle VIAs
                if current_path_u_raw[0] != current_path_v_raw[0]:
                    routing_rows.append(
                        (
                            str(initial_segment["layer_u_s"]),
                            str(initial_segment["row_u_s"]),
                            str(initial_segment["col_u_s"]),
                            current_path_net,
                            "=>",
                            str(initial_segment["layer_v_s"]),
                            str(initial_segment["row_v_s"]),
                            str(initial_segment["col_v_s"]),
                            current_path_net,
                        )
                    )
                    continue

                current_path_layer_raw_idx = current_path_u_raw[0]
                path_is_horizontal = current_path_u_raw[1] == current_path_v_raw[1]
                path_is_vertical = current_path_u_raw[2] == current_path_v_raw[2]

                if not (path_is_horizontal ^ path_is_vertical):
                    routing_rows.append(
                        (
                            str(initial_segment["layer_u_s"]),
                            str(initial_segment["row_u_s"]),
                            str(initial_segment["col_u_s"]),
                            current_path_net,
                            "=>",
                            str(initial_segment["layer_v_s"]),
                            str(initial_segment["row_v_s"]),
                            str(initial_segment["col_v_s"]),
                            current_path_net,
                        )
                    )
                    continue

                # 3) Try to extend this path iteratively
                while True:
                    was_extended_in_this_pass = False
                    for j in range(len(active_segments_data)):
                        if processed_segment_indices[j]:
                            continue

                        candidate_segment = active_segments_data[j]
                        cand_u_raw = candidate_segment["u_raw"]
                        cand_v_raw = candidate_segment["v_raw"]

                        if (
                            cand_u_raw[0] != cand_v_raw[0]
                            or cand_u_raw[0] != current_path_layer_raw_idx
                            or candidate_segment["net"] != current_path_net
                        ):
                            continue

                        cand_is_horizontal = cand_u_raw[1] == cand_v_raw[1]
                        cand_is_vertical = cand_u_raw[2] == cand_v_raw[2]

                        if not (cand_is_horizontal ^ cand_is_vertical):
                            continue

                        segment_merged_with_candidate = False
                        if path_is_horizontal and cand_is_horizontal:
                            if current_path_v_raw == cand_u_raw:
                                current_path_v_raw = cand_v_raw
                                segment_merged_with_candidate = True
                            elif cand_v_raw == current_path_u_raw:
                                current_path_u_raw = cand_u_raw
                                segment_merged_with_candidate = True
                        elif path_is_vertical and cand_is_vertical:
                            if current_path_v_raw == cand_u_raw:
                                current_path_v_raw = cand_v_raw
                                segment_merged_with_candidate = True
                            elif cand_v_raw == current_path_u_raw:
                                current_path_u_raw = cand_u_raw
                                segment_merged_with_candidate = True

                        if segment_merged_with_candidate:
                            processed_segment_indices[j] = True
                            was_extended_in_this_pass = True
                            break

                    if not was_extended_in_this_pass:
                        break

                # 4) Add the final merged path
                final_layer_u_s = current_path_u_raw[0]
                final_row_u_s = current_path_u_raw[1] / rescaler
                final_col_u_s = current_path_u_raw[2] / rescaler
                final_layer_v_s = current_path_v_raw[0]
                final_row_v_s = current_path_v_raw[1] / rescaler
                final_col_v_s = current_path_v_raw[2] / rescaler

                routing_rows.append(
                    (
                        str(final_layer_u_s),
                        str(final_row_u_s),
                        str(final_col_u_s),
                        current_path_net,
                        "=>",
                        str(final_layer_v_s),
                        str(final_row_v_s),
                        str(final_col_v_s),
                        current_path_net,
                    )
                )

        else:
            # Non-merged routing output
            routing_rows = []
            for (u_edge, v_edge), edge_var in edge_vars.items():
                if solver.Value(edge_var) == 1:
                    net = _get_true_edge_netname(solver, net_arc_vars, u_edge, v_edge)
                    if net is None:
                        net = "N/A"
                    layer_u, row_u, col_u = (
                        u_edge[0],
                        u_edge[1] / rescaler,
                        u_edge[2] / rescaler,
                    )
                    layer_v, row_v, col_v = (
                        v_edge[0],
                        v_edge[1] / rescaler,
                        v_edge[2] / rescaler,
                    )
                    routing_rows.append(
                        (
                            str(layer_u),
                            str(row_u),
                            str(col_u),
                            net,
                            "=>",
                            str(layer_v),
                            str(row_v),
                            str(col_v),
                            net,
                        )
                    )

        if routing_rows:
            hdrs2 = ("MET", "ROW", "COL", "NET", "", "MET", "ROW", "COL", "NET")
            cols2 = list(zip(hdrs2, *routing_rows))
            widths2 = [max(len(item) for item in col) for col in cols2]

            fmt2 = (
                f"{{:<{widths2[0]}}}  "
                f"{{:>{widths2[1]}}}  "
                f"{{:>{widths2[2]}}}  "
                f"{{:>{widths2[3]}}}  "
                f"{{:^{widths2[4]}}}  "
                f"{{:<{widths2[5]}}}  "
                f"{{:>{widths2[6]}}}  "
                f"{{:>{widths2[7]}}}  "
                f"{{:>{widths2[8]}}}\n"
            )

            f.write(fmt2.format(*hdrs2))
            f.write("-" * (sum(widths2) + 16) + "\n")

            for row in routing_rows:
                f.write(fmt2.format(*row))

        # ——— Technology ———
        f.write("\n** Technology Parameters **\n")
        f.write(f"{'Name':<25} {'Value':>10}\n")
        f.write("-" * 40 + "\n")
        tech_params = {
            "COL": solver.Value(cpp_cost) // 2 + 2,
            "TRACK": fin_tech.num_rt_track,
            "CPP": fin_tech.get_pitch(layer_name="PC"),
            "M0P": fin_tech.get_pitch(layer_name="M0"),
            "M1P": fin_tech.get_pitch(layer_name="M1"),
            "M2P": fin_tech.get_pitch(layer_name="M2"),
            "CP_WIDTH": fin_tech.get_width(layer_name="PC") / rescaler,
            "M0_WIDTH": fin_tech.get_width(layer_name="M0") / rescaler,
            "M1_WIDTH": fin_tech.get_width(layer_name="M1") / rescaler,
            "M2_WIDTH": fin_tech.get_width(layer_name="M2") / rescaler,
            "ACTIVE_GAP": fin_tech.active_gap * 1e3,
            "PWR_RAIL_THICKNESS": fin_tech.power_rail_thickness * 1e3,
            "PWR_CONFIG": fin_tech.power_config,
        }
        for name, value in tech_params.items():
            f.write(f"{name:<25} {value:>10}\n")

    absl_logging.info(f"Result written to {filename}")
