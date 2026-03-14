"""
Acceleration and analysis functions for circuit optimization.

This module contains functions for:
- Circuit analysis and transistor grouping
- Circuit clustering for improved placement
- Graph-based circuit representations
"""

import copy
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from sklearn.cluster import DBSCAN
from absl import logging as absl_logging


def analyze_circuit(finfet_instance):
    """
    Extract transistor groups from the circuit.
    
    Args:
        finfet_instance: The FinFET instance containing circuit and configuration
    """
    finfet_instance.net_to_tran_group = finfet_instance.circuit.group_transistors_by_nets()
    finfet_instance.net_to_pmos_tran_group = finfet_instance.net_to_tran_group["PMOS"] 
    finfet_instance.net_to_nmos_tran_group = finfet_instance.net_to_tran_group["NMOS"]
    finfet_instance.tran_group_by_low_degree_nets = finfet_instance.circuit.group_transistors_by_low_degree_nets_and_types()
    
    # Check if most pmos are partitioned, if so, then do not use breaking symmetry later on 
    merged_list = []
    for _, value_set in finfet_instance.net_to_pmos_tran_group.items():
        merged_list.extend(list(value_set))
    num_added_pmos_partition = len(merged_list)
    merged_list = []
    for _, value_set in finfet_instance.net_to_nmos_tran_group.items():
        merged_list.extend(list(value_set))
    num_added_nmos_partition = len(merged_list)    
    
    # NOTE: although BS is not a hard constraints on partition, CP-SAT presolve can result in INFEASIBLE
    if num_added_pmos_partition > finfet_instance.circuit.num_pmos_transistors() // 2:
        absl_logging.info(f"Detecting {num_added_pmos_partition} partition is provided for PMOS. Disabled breaking symmetry.")
        finfet_instance.use_break_symmetry = False
    elif num_added_nmos_partition > finfet_instance.circuit.num_nmos_transistors() // 2:
        absl_logging.info(f"Detecting {num_added_nmos_partition} partition is provided for NMOS. Disabled breaking symmetry.")
        finfet_instance.use_break_symmetry = False
    else:
        absl_logging.info(f"Provided {num_added_pmos_partition} partition for PMOS. Using breaking symmetry.")
    
    absl_logging.info(f"net_to_tran_group : {finfet_instance.net_to_tran_group}")
    absl_logging.info(f"tran_group_by_low_degree_nets : {finfet_instance.tran_group_by_low_degree_nets}")


def cluster_circuit(finfet_instance, method="kkhdb", visualize=False, remove_2d_nets=False):
    """
    Cluster the circuit for improved placement.
    
    KKHDB : Kamada-Kawai + HDBSCAN
    - Remove 2-degree nets but optionally preserve them (Good for SDFFSQ) 
    - Remove VDD/VSS but optionally add them back later (Good for SDFFSQ?)
    - Constrained max_cluster_size to only 4 because generating Euler path for large cluster is not efficient
    - When adding back VDD/VSS node, use clique model to represent.  
    - (TODO) Later we can use max/min x to constrain KNN-like clusters
    - Discard noise clusters (-1)
    
    Args:
        finfet_instance: The FinFET instance containing circuit and configuration
        method: Clustering method to use ("kkhdb" or "kkdb")
        visualize: Whether to generate visualization plots
        remove_2d_nets: Whether to remove 2-degree nets
        
    Returns:
        tuple: (networkx graph, list of clusters)
    """
    # Build circuit graph
    G = build_circuit_graph(finfet_instance)
    
    # Remove VDD and VSS but preserve their structure
    vdd_neighbors = list(G.neighbors('VDD'))
    vdd_node_attrs = G.nodes['VDD'] if 'VDD' in G.nodes else {}
    vdd_edge_attrs = {
        ('VDD', nbr): G.get_edge_data('VDD', nbr)
        for nbr in vdd_neighbors
    }
    G.remove_node('VDD')
    vss_neighbors = list(G.neighbors('VSS'))
    vss_node_attrs = G.nodes['VSS'] if 'VSS' in G.nodes else {}
    vss_edge_attrs = {
        ('VSS', nbr): G.get_edge_data('VSS', nbr)
        for nbr in vss_neighbors
    }
    G.remove_node('VSS')
    
    # Remove 2-degree net nodes and connect transistor directly together
    # SDFFSQ ==> False
    if remove_2d_nets:
        static_node_list = copy.deepcopy(G.nodes)
        for node in static_node_list:
            if not str(node).startswith("MM"):
                degree = G.degree(node)
                if degree > 2:
                    continue
                else:
                    # clique conn style
                    for neighbor_1 in G.neighbors(node):
                        for neighbor_2 in G.neighbors(node):
                            # every other node
                            if neighbor_1 == neighbor_2:
                                continue
                            # assign a default edge weight of 1
                            G.add_edge(neighbor_1, neighbor_2, weight=1)
                    # remove the net node
                    G.remove_node(node)
    
    # Add a weight to the net node's edges based on their net degree
    for node in G.nodes:
        if not str(node).startswith("MM"):
            degree = G.degree(node)
            for neighbor in G.neighbors(node):
                # Ensure consistent ordering for undirected edges
                u, v = sorted([node, neighbor])
                # You can set the weight to the degree of the current node
                G[u][v]['weight'] = degree
    
    if method == "kkhdb":
        from sklearn.cluster import HDBSCAN
        pos = nx.kamada_kawai_layout(G)
        nx.set_node_attributes(G, pos, 'pos')
        if visualize:
            plt.figure(figsize=(10, 10))
            nx.draw(
                G,
                pos,
                with_labels=True,
                edge_color='gray',
            )
        # Filter out any node that is a net
        G_prime = G.copy()
        static_node_list = copy.deepcopy(G_prime.nodes)
        for node in static_node_list:
            if not str(node).startswith("MM"):
                G_prime.remove_node(node)
        X = np.array([pos[node] for node in G_prime.nodes])
        db = HDBSCAN(
            min_cluster_size=finfet_instance.cell_config["inject_cluster"]["min_cluster_size"],
            max_cluster_size=finfet_instance.cell_config["inject_cluster"]["max_cluster_size"]
        ).fit(X)
        labels = db.labels_
    elif method == "kkdb":
        from sklearn.cluster import HDBSCAN
        pos = nx.kamada_kawai_layout(G)
        nx.set_node_attributes(G, pos, 'pos')
        # Filter out any node that is a net
        G_prime = G.copy()
        static_node_list = copy.deepcopy(G_prime.nodes)
        for node in static_node_list:
            if not str(node).startswith("MM"):
                G_prime.remove_node(node)
        X = np.array([pos[node] for node in G_prime.nodes])
        db = DBSCAN(eps=0.05, min_samples=2).fit(X)  # min sample should be 2
        labels = db.labels_
    
    # Collect clusters
    clusters = defaultdict(list)
    for node, label in zip(G_prime.nodes, labels):
        clusters[int(label)].append(node)
    
    # Map labels to nodes
    node_cluster = dict(zip(G_prime.nodes, labels))
    
    # Generate a color map
    unique_labels = sorted(set(labels))
    num_clusters = len(unique_labels)
    # Use a colormap
    cmap = plt.get_cmap('tab10')  # or 'tab20', 'hsv', etc.
    color_map = {label: cmap(label % cmap.N) for label in unique_labels}
    
    # Assign colors to each node
    node_colors = []
    for node in G.nodes():
        try:
            node_colors.append(color_map[node_cluster[node]])
        except KeyError:
            node_colors.append("grey")
    
    if visualize:
        plt.figure(figsize=(10, 10))
        nx.draw(
            G,
            pos,
            node_color=node_colors,
            with_labels=True,
            edge_color='gray',
        )
        plt.savefig(f"{finfet_instance.output_dir}/view/cluster_{finfet_instance.circuit.subckt_name}.png")
        plt.close()
    
    # Remove -1 noise
    clusters.pop(-1, None)
    return G, list(clusters.values())


def build_circuit_graph(finfet_instance):
    """
    Build a NetworkX graph representation of the circuit.
    
    Args:
        finfet_instance: The FinFET instance containing the circuit
        
    Returns:
        networkx.Graph: Graph representation of the circuit
    """
    return finfet_instance.circuit.generate_networkx_graph()
