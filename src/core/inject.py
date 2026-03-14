from absl import logging as absl_logging
import sys
import networkx as nx
from itertools import pairwise

from src.utility.entity import Model

_NUM_COL_SDG_ = 3  # number of columns needed for source/drain/gate


def _process_path(finfet, pid, path):
    var = finfet.opt.NewBoolVar(f"cluster_path_{path}_id_{pid}")
    for tran_i_name, tran_j_name in pairwise(path):
        tran_i_name = str(tran_i_name)
        tran_j_name = str(tran_j_name)
        # entity
        tran_i = finfet.circuit.transistors[tran_i_name]
        tran_j = finfet.circuit.transistors[tran_j_name]
        # variable
        tvar_i = finfet.transistor_vars[tran_i_name]
        tvar_j = finfet.transistor_vars[tran_j_name]
        # P-P
        if tran_i.model == Model.PMOS and tran_j.model == Model.PMOS:
            # i left of j
            finfet.opt.Add(tvar_j.x_var == tvar_i.x_var + (_NUM_COL_SDG_ - 1)).OnlyEnforceIf(var)
        # N-P
        if tran_i.model == Model.NMOS and tran_j.model == Model.PMOS:
            # i align of j
            finfet.opt.Add(tvar_j.x_var == tvar_i.x_var).OnlyEnforceIf(var)
        # P-N
        if tran_i.model == Model.PMOS and tran_j.model == Model.NMOS:
            # i align of j
            finfet.opt.Add(tvar_j.x_var == tvar_i.x_var).OnlyEnforceIf(var)
        # N-N
        if tran_i.model == Model.NMOS and tran_j.model == Model.NMOS:
            # i left of j
            finfet.opt.Add(tvar_j.x_var == tvar_i.x_var + (_NUM_COL_SDG_ - 1)).OnlyEnforceIf(var)
    return var


def _is_valid_path_transition(path):
    """
    All travel path should just be handled in ordered P/N because we do not want zigzag paths
    """
    block = []
    for item in path:
        if item.startswith('MMN'):
            block.append('N')
        elif item.startswith('MMP'):
            block.append('P')
    # Valid if block is all Ns then all Ps or all Ps then all Ns
    return block == sorted(block) or block == sorted(block, reverse=True)


def eulerian_subpaths(finfet, netlist_graph, cluster):
    """
    TODO: reference find_path script to update eulerian path finding
    - Do not mix P/N order when construct path as it may be spatially similar to other paths
    - If use clique model for VDD/VSS, then VDD/VSS node must be traveled consecutively for correctness
    - remove duplicated path
    - add reverse path
    - Optionally, use cluster constrain instead (min/max on x range)
    """
    # extract subgraph only containing the nodes
    # and immediate connected neighbors
    # Get one-hop neighbors of the subset
    neighbors = set()
    for node in cluster:
        neighbors.update(netlist_graph.neighbors(node))
    # Remove original subset nodes (if needed)
    neighbors -= set(cluster)

    subg = netlist_graph.subgraph(cluster + list(neighbors))
    # if not connected
    if not nx.is_connected(subg):
        return False
    # get all paths
    paths = []
    for i in range(len(cluster)):
        src = cluster[i]
        for j in range(i, len(cluster)):
            tgt = cluster[j]
            for path in nx.all_simple_paths(subg, source=src, target=tgt):
                if set(cluster).issubset(path):
                    # filter out path that contains net node
                    paths.append([node for node in path if node.startswith("MM")])
    # ^ remove paths that are mixing P and N orders
    new_paths = []
    for p in paths:
        if _is_valid_path_transition(p):
            new_paths.append(p)
    # ^ remove duplicated paths
    unique_paths = [list(p) for p in {tuple(path) for path in new_paths}]
    # add reversed paths
    path_w_reverse = []
    for p in unique_paths:
        path_w_reverse.append(p)
        path_w_reverse.append(list(reversed(p)))
    return path_w_reverse


def _process_cluster_range(finfet, cluster):
    """
    """
    min_x_var = finfet.opt.NewIntVarFromDomain(
        finfet.domain_mos_placable_ci,
        f"cluster_min_x_{cluster}"
    )
    max_x_var = finfet.opt.NewIntVarFromDomain(
        finfet.domain_mos_placable_ci,
        f"cluster_max_x_{cluster}"
    )
    pmos_group = []
    nmos_group = []
    for tran_name in cluster:
        if finfet.circuit.transistors[tran_name].model == Model.PMOS:
            pmos_group.append(tran_name)
        elif finfet.circuit.transistors[tran_name].model == Model.NMOS:
            nmos_group.append(tran_name)
    if len(pmos_group) >= len(nmos_group):
        pmos_xs = [finfet.transistor_vars[pmos_tran_name].x_var for pmos_tran_name in pmos_group]
        # placement range
        finfet.opt.AddMinEquality(
            min_x_var,
            pmos_xs,
        )
        finfet.opt.AddMaxEquality(
            max_x_var,
            pmos_xs,
        )
        # bag everything within range regardless order
        finfet.opt.Add(max_x_var - min_x_var == int((_NUM_COL_SDG_ - 1) * (len(pmos_group) - 1)))
        # nmos within such range
        for nmos_tran_name in nmos_group:
            nmos_tvar = finfet.transistor_vars[nmos_tran_name].x_var
            finfet.opt.Add(min_x_var <= nmos_tvar)
            finfet.opt.Add(nmos_tvar <= max_x_var)
    elif len(pmos_group) < len(nmos_group):
        nmos_xs = [finfet.transistor_vars[nmos_tran_name].x_var for nmos_tran_name in nmos_group]
        # placement range
        finfet.opt.AddMinEquality(
            min_x_var,
            nmos_xs,
        )
        finfet.opt.AddMaxEquality(
            max_x_var,
            nmos_xs,
        )
        # bag everything within range regardless order
        finfet.opt.Add(max_x_var - min_x_var == int((_NUM_COL_SDG_ - 1) * (len(nmos_group) - 1)))
        # pmos within such range
        for pmos_tran_name in pmos_group:
            pmos_tvar = finfet.transistor_vars[pmos_tran_name].x_var
            finfet.opt.Add(min_x_var <= pmos_tvar)
            finfet.opt.Add(pmos_tvar <= max_x_var)


def inject_clusters(finfet, graph, clusters):
    """
    Inject cluster constraints into the provided FinFET instance.
    """
    for idx, clst in enumerate(clusters):
        absl_logging.info(f"Injecting Clusters: {clst}")
        finfet.opt.log_comment(f"Injecting Clusters: {clst}")
        if len(clst) == 2:  # small cluster constrain placement adjacency
            # extract paths
            paths = eulerian_subpaths(finfet, graph, clst)
            if paths:
                absl_logging.info(f"clst has paths {paths}")
            if not paths:
                continue
            pids = []
            for pid, p in enumerate(paths):
                path_var = _process_path(finfet, pid, p)
                pids.append(path_var)
            # at least one
            finfet.opt.Add(sum(pids) == 1)
        else:  # larger cluster constrain placement range
            _process_cluster_range(finfet, clst)


def inject_placement(finfet, tran_name, x=None, y=None, flip=None):
    """
    Inject a placement solution into the model for a single transistor.
    """
    finfet.opt.log_comment(f"Injecting placement for {tran_name} ...")
    if tran_name not in finfet.transistor_vars:
        absl_logging.error(f"Transistor {tran_name} not found in the model. Please check the name.")
        sys.exit(1)
    if x is not None:
        finfet.opt.Add(finfet.transistor_vars[tran_name].x_var == x)
    if y is not None:
        finfet.opt.Add(finfet.transistor_vars[tran_name].y_var == y)
    if flip is not None:
        if flip:
            finfet.opt.Add(finfet.transistor_vars[tran_name].flip_var == 1)
        else:
            finfet.opt.Add(finfet.transistor_vars[tran_name].flip_var == 0)


def inject_placements(finfet, tran_names, xs, flips, hint=False):
    """
    Inject placement solutions into the model for multiple transistors.
    """
    if not all(isinstance(param, list) for param in [tran_names, xs, flips]):
        absl_logging.error("All parameters (tran_names, xs, flips) must be lists.")
        sys.exit(1)

    if not (len(tran_names) == len(xs) == len(flips)):
        absl_logging.error(
            f"All lists must have the same length. Got: tran_names({len(tran_names)}), xs({len(xs)}), flips({len(flips)})"
        )
        sys.exit(1)

    finfet.opt.log_comment(f"{'Hinting' if hint else 'Injecting'} placement for transistors: {tran_names} ...")

    for name in tran_names:
        if name not in finfet.transistor_vars:
            absl_logging.error(f"Transistor {name} not found in the model. Please check the name.")
            sys.exit(1)

    for i in range(len(tran_names)):
        name = tran_names[i]
        x = xs[i]
        flip = flips[i]

        if hint:
            finfet.opt.AddHint(finfet.transistor_vars[name].x_var, x)
            finfet.opt.AddHint(finfet.transistor_vars[name].flip_var, 1 if flip else 0)
        else:
            print(f"Injecting placement for {name} at x={x}, flip={flip}")
            finfet.opt.Add(finfet.transistor_vars[name].x_var == x)
            finfet.opt.Add(finfet.transistor_vars[name].flip_var == (1 if flip else 0))


def inject_edge(finfet, u, v, value=1):
    finfet.opt.log_comment(f"Injecting edge ({u}, {v}) ...")
    if (u, v) not in finfet.edge_vars:
        absl_logging.error(f"Edge ({u}, {v}) not found in the model. Please check the coordinates.")
        sys.exit(1)
    finfet.opt.Add(finfet.edge_vars[(u, v)] == value)


def inject_flow(finfet, net_name, k_idx, u, v, value=1):
    finfet.opt.log_comment(f"Injecting flow ({net_name}, {k_idx}, {u}, {v}) ...")
    if (net_name, k_idx, u, v) not in finfet.net_flow_vars:
        absl_logging.error(f"Flow ({net_name}, {k_idx}, {u}, {v}) not found in the model. Please check the coordinates.")
        absl_logging.error(f"Possible keys under net_name {net_name} k_idx {k_idx}")
        for key in finfet.net_flow_vars.keys():
            if key[0] == net_name and key[1] == k_idx:
                absl_logging.error(f"Key: {key}")
        sys.exit(1)
    finfet.opt.Add(finfet.net_flow_vars[(net_name, k_idx, u, v)] == value)


def inject_arc(finfet, net_name, u, v, value=1):
    finfet.opt.log_comment(f"Injecting arc ({net_name}, {u}, {v}) ...")
    if (net_name, u, v) not in finfet.net_arc_vars:
        absl_logging.error(f"Arc ({net_name}, {u}, {v}) not found in the model. Please check the coordinates.")
        sys.exit(1)
    finfet.opt.Add(finfet.net_arc_vars[(net_name, u, v)] == value)
