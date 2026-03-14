import os
import math
import logging
from collections import defaultdict
from absl import logging as absl_logging

from itertools import product
import networkx as nx
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
# custom
import src.utility.config as config

# Set up logging to print messages
# Custom log format: [LEVEL] TIMESTAMP - MESSAGE
# NOTE: level available: DEBUG, INFO, WARNING, ERROR, CRITICAL
logging.basicConfig(format="[%(levelname)s] %(asctime)s - %(message)s", level=logging.INFO)


class LayeredGridGraph:
    def __init__(self, layer_to_rows, layer_to_cols, idx_to_layer, layer_to_direction, virtual_connect_layer_pairs=[], virtual_conn_method="overlap", site_div_line=-1):
        # ensure that rows and cols are sorted are sorted and in integer format
        for L in layer_to_rows:
            layer_to_rows[L] = sorted({int(r) for r in layer_to_rows[L]})
        for L in layer_to_cols:
            layer_to_cols[L] = sorted({int(c) for c in layer_to_cols[L]})
        # 1) Build “complete” row & col maps by merging across neighbors
        complete_rows = {}
        complete_cols = {}
        # sorted list of layer‐indices, so adjacency is by ±1 in this list
        layer_indices = sorted(idx_to_layer)
        # build reverse mapping
        layer_to_idx = {L: z for z, L in idx_to_layer.items()}

        # used to check site specific constraints
        self.site_div_line = site_div_line

        for z in layer_indices:
            L = idx_to_layer[z]
            # rows
            if L in layer_to_rows:
                complete_rows[L] = layer_to_rows[L]
            else:
                nbrs = [layer_to_rows[idx_to_layer[z2]] for dz in (-1, 1) if (z2 := z + dz) in idx_to_layer and idx_to_layer[z2] in layer_to_rows]
                if not nbrs:
                    raise ValueError(f"Cannot infer rows for {L!r}")
                complete_rows[L] = sorted(set().union(*nbrs))
            # cols
            if L in layer_to_cols:
                complete_cols[L] = layer_to_cols[L]
            else:
                nbrs = [layer_to_cols[idx_to_layer[z2]] for dz in (-1, 1) if (z2 := z + dz) in idx_to_layer and idx_to_layer[z2] in layer_to_cols]
                if not nbrs:
                    raise ValueError(f"Cannot infer cols for {L!r}")
                complete_cols[L] = sorted(set().union(*nbrs))

        # check that all layers have rows and cols are unique
        for L in complete_rows:
            if len(complete_rows[L]) != len(set(complete_rows[L])):
                raise ValueError(f"Duplicate rows in layer {L!r}")

        for L in complete_cols:
            # print(f"Layer {L}: {complete_cols[L]}")
            if len(complete_cols[L]) != len(set(complete_cols[L])):
                raise ValueError(f"Duplicate cols in layer {L!r}")

        # store for later lookup
        self.complete_rows = complete_rows
        self.complete_cols = complete_cols
        self.idx_to_layer = idx_to_layer
        self.layer_to_idx = layer_to_idx
        self.layer_to_direction = layer_to_direction

        # map virtual connected layers
        self.virtual_conn_method = virtual_conn_method
        tmp_virtual_connect_layeridx_pairs = []
        if virtual_connect_layer_pairs != []:
            for layer_pair in virtual_connect_layer_pairs:
                tmp_virtual_connect_layeridx_pairs.append((layer_to_idx[layer_pair[0]],
                                                          layer_to_idx[layer_pair[1]]))
            
        # 2) build the graph
        self.G = nx.Graph()
        self._build_graph(complete_rows, complete_cols, idx_to_layer, tmp_virtual_connect_layeridx_pairs)

        # 3) make a directed graph for easy lookup
        self.Gd = nx.DiGraph(self.G)
        # adj list for both directions
        self._pred = {n: [] for n in self.G.nodes()}
        self._succ = {n: [] for n in self.G.nodes()}
        for u, v in self.G.edges():
            self._succ[u].append(v)
            self._pred[v].append(u)

    def _build_graph(self, rows_map, cols_map, idx2layer, virtual_connect_layeridx_pairs=[]):
        # add nodes exactly as before…
        for z, L in idx2layer.items():
            for r, c in product(rows_map[L], cols_map[L]):
                self.G.add_node((z, r, c), layer_idx=z, layer=L, row=r, col=c)

        # add edges, but restrict same-layer moves to layer_to_direction[L]
        for z, L in idx2layer.items():
            direction = self.layer_to_direction[L]  # "H" or "V"
            rows, cols = rows_map[L], cols_map[L]
            row_i = {r: i for i, r in enumerate(rows)}
            col_j = {c: j for j, c in enumerate(cols)}

            for r, c in product(rows, cols):
                u = (z, r, c)
                i, j = row_i[r], col_j[c]

                # same-layer neighbors, only along the specified axis
                if direction == "H":
                    # left/right only
                    if j + 1 < len(cols):
                        self.G.add_edge(u, (z, r, cols[j + 1]))
                    if j - 1 >= 0:
                        self.G.add_edge(u, (z, r, cols[j - 1]))
                elif direction == "V":
                    # up/down only
                    if i + 1 < len(rows):
                        self.G.add_edge(u, (z, rows[i + 1], c))
                    if i - 1 >= 0:
                        self.G.add_edge(u, (z, rows[i - 1], c))
                else:
                    raise ValueError(f"Unknown direction {direction!r} for layer {L}")

                # cross-layer neighbors (vias) stay the same
                for dz in (-1, +1):
                    z2 = z + dz
                    if z2 in idx2layer:
                        L2 = idx2layer[z2]
                        if r in rows_map[L2] and c in cols_map[L2]:
                            self.G.add_edge(u, (z2, r, c))
        
        self.virtual_edges_along_col = defaultdict(list)
        # add cross-layer edges that are virtually connected
        if self.virtual_conn_method == "overlap" and len(virtual_connect_layeridx_pairs) > 0:
            # NOTE: only connects overlapping nodes
            for li_pair in virtual_connect_layeridx_pairs:
                # bottom layer info
                zb = li_pair[0]
                Lb = idx2layer[zb]
                r_bot = rows_map[Lb]
                c_bot = cols_map[Lb]
                # top layer info
                zt = li_pair[1]
                Lt = idx2layer[zt]
                r_top = rows_map[Lt]
                c_top = cols_map[Lt]
                for rb, cb in product(r_bot, c_bot):
                    ub = (zb, rb, cb)
                    for rt, ct in product(r_top, c_top):
                        ut = (zt, rt, ct)
                        if rb == rt and cb == ct:
                            # bottom to top direction
                            self.G.add_edge(ub, ut)
                            # top to bottom direction
                            self.G.add_edge(ut, ub)
                            self.virtual_edges_along_col[cb].append((ub, ut)) # always assume bot first, top second
                            # self.virtual_edges_along_col[cb].append((ut, ub))
        elif self.virtual_conn_method == "colwise" and len(virtual_connect_layeridx_pairs) > 0:
            # NOTE: connects every node with every other node along the col
            for li_pair in virtual_connect_layeridx_pairs:
                # bottom layer info
                zb = li_pair[0]
                Lb = idx2layer[zb]
                r_bot = rows_map[Lb]
                c_bot = cols_map[Lb]
                # top layer info
                zt = li_pair[1]
                Lt = idx2layer[zt]
                r_top = rows_map[Lt]
                c_top = cols_map[Lt]
                for rb, cb in product(r_bot, c_bot):
                    ub = (zb, rb, cb)
                    for rt, ct in product(r_top, c_top):
                        ut = (zt, rt, ct)
                        if cb == ct:
                            # bottom to top direction
                            self.G.add_edge(ub, ut)
                            # top to bottom direction
                            self.G.add_edge(ut, ub)
                            self.virtual_edges_along_col[cb].append((ub, ut)) # always assume bot first, top second
                            # self.virtual_edges_along_col[cb].append((ut, ub))
        elif self.virtual_conn_method == "sdcolwise" and len(virtual_connect_layeridx_pairs) > 0:
            # NOTE: connects every node with every other node along the col
            for li_pair in virtual_connect_layeridx_pairs:
                # bottom layer info
                zb = li_pair[0]
                Lb = idx2layer[zb]
                r_bot = rows_map[Lb]
                c_bot = cols_map[Lb]
                # top layer info
                zt = li_pair[1]
                Lt = idx2layer[zt]
                r_top = rows_map[Lt]
                c_top = cols_map[Lt]
                for rb, cb in product(r_bot, c_bot):
                    ub = (zb, rb, cb)
                    for rt, ct in product(r_top, c_top):
                        ut = (zt, rt, ct)
                        if self.is_even_col(layer="PC", col=cb):
                            continue
                        if cb == ct:
                            # bottom to top direction
                            self.G.add_edge(ub, ut)
                            # top to bottom direction
                            self.G.add_edge(ut, ub)
                            self.virtual_edges_along_col[cb].append((ub, ut)) # always assume bot first, top second
                            # self.virtual_edges_along_col[cb].append((ut, ub))
        # debug assert that G is undirected
        if nx.is_directed(self.G):
            raise ValueError("Graph is not undirected")

    def degree(self, node):
        return self.G.degree[node]

    def neighbors(self, node):
        return list(self.G.neighbors(node))

    def is_node_in_graph(self, node):
        """
        Check if the node (z, row, col) is in the graph.
        """
        return node in self.G.nodes()

    def row_in_layer(self, layer, idx):
        """
        Return the row‐coordinate at position `idx` in the given layer.
        """
        z, L = self._resolve_layer(layer)
        rows = self.complete_rows[L]
        if not (0 <= idx < len(rows)):
            raise IndexError(f"Row index {idx} out of range for layer {L!r}")
        return rows[idx]

    def col_in_layer(self, layer, idx):
        """
        Return the col‐coordinate at position `idx` in the given layer.
        """
        z, L = self._resolve_layer(layer)
        cols = self.complete_cols[L]
        if not (0 <= idx < len(cols)):
            raise IndexError(f"Col index {idx} out of range for layer {L!r}")
        return cols[idx]

    def is_edge_cross_site(self, node_1, node_2):
        """
        DH cell only
        """
        if node_1[1] > self.site_div_line and node_2[1] < self.site_div_line:
            return True 
        if node_2[1] > self.site_div_line and node_1[1] < self.site_div_line:
            return True 
        return False

    def right_col_in_layer(self, layer, col):
        """
        Return the right column coordinate in the given layer.
        """
        z, L = self._resolve_layer(layer)
        cols = self.complete_cols[L]
        if col not in cols:
            raise ValueError(f"Col {col} not in layer {L!r}")
        idx = cols.index(col)
        if idx == len(cols) - 1:
            return None
        return cols[idx + 1]

    def left_col_in_layer(self, layer, col):
        """
        Return the left column coordinate in the given layer.
        """
        z, L = self._resolve_layer(layer)
        cols = self.complete_cols[L]
        if col not in cols:
            raise ValueError(f"Col {col} not in layer {L!r}")
        idx = cols.index(col)
        if idx == 0:
            return None
        return cols[idx - 1]

    def front_row_in_layer(self, layer, row, check_site=False):
        """
        Return the front row coordinate in the given layer.
        """
        z, L = self._resolve_layer(layer)
        rows = self.complete_rows[L]
        if row not in rows:
            raise ValueError(f"Row {row} not in layer {L!r}")
        idx = rows.index(row)
        if idx == 0:
            return None
        # prevent crossing site division line
        if check_site and self.site_div_line != -1:
            if rows[idx - 1] <= self.site_div_line and row >= self.site_div_line:
                return None
        return rows[idx - 1]

    def back_row_in_layer(self, layer, row, check_site=False):
        """
        Return the back row coordinate in the given layer.
        """
        z, L = self._resolve_layer(layer)
        rows = self.complete_rows[L]
        if row not in rows:
            raise ValueError(f"Row {row} not in layer {L!r}")
        idx = rows.index(row)
        if idx == len(rows) - 1:
            return None
        # prevent crossing site division line
        if check_site and self.site_div_line != -1:
            if rows[idx + 1] >= self.site_div_line and row <= self.site_div_line:
                return None
        return rows[idx + 1]

    def col_index_in_layer(self, layer, col):
        """
        Return the index of the given column in the given layer.
        """
        z, L = self._resolve_layer(layer)
        cols = self.complete_cols[L]
        if col not in cols:
            raise ValueError(f"Col {col} not in layer {L!r}")
        return cols.index(col)

    def row_index_in_layer(self, layer, row):
        """
        Return the index of the given row in the given layer.
        """
        z, L = self._resolve_layer(layer)
        rows = self.complete_rows[L]
        if row not in rows:
            raise ValueError(f"Row {row} not in layer {L!r}")
        return rows.index(row)

    def node_in_layer_row_col(self, layer, row, col):
        """
        Return the node (z, row, col) in the given layer.
        """
        z, L = self._resolve_layer(layer)
        if row not in self.complete_rows[L]:
            raise ValueError(f"Row {row} not in layer {L!r}")
        if col not in self.complete_cols[L]:
            raise ValueError(f"Col {col} not in layer {L!r}")
        return (z, row, col)

    def nodes_in_layer(self, layer, parity=None):
        """
        Iterate over all nodes (z, row, col) in the given layer,
        optionally filtering to only those whose row/col index is even or odd.

        Args:
          layer : int (layer index) or str (layer name)
          parity: None (default) → return all nodes
                  "even"   → return only nodes whose index along the *directional*
                              axis is even
                  "odd"    → return only nodes whose index along that axis is odd

        Directional axis:
          - if layer_to_direction[layer]=="vertical", we look at the *column* index
          - if layer_to_direction[layer]=="horizontal", we look at the *row* index
        """
        # resolve
        z, L = self._resolve_layer(layer)

        # grab all nodes in layer z
        all_nodes = [n for n in self.G.nodes() if n[0] == z]
        if parity is None:
            return all_nodes

        if parity not in ("even", "odd"):
            raise ValueError("parity must be one of {None, 'even', 'odd'}")

        # pick the right index-map
        direction = self.layer_to_direction[L]
        if direction == "vertical":
            # index by col
            idx_map = {c: i for i, c in enumerate(self.complete_cols[L])}
            get_idx = lambda n: idx_map[n[2]]
        else:
            # index by row
            idx_map = {r: i for i, r in enumerate(self.complete_rows[L])}
            get_idx = lambda n: idx_map[n[1]]

        want_even = parity == "even"
        filtered = [n for n in all_nodes if (get_idx(n) % 2 == 0) is want_even]
        return filtered

    def nodes_in_layer_at(self, layer, row=None, col=None):
        """
        Return the list of nodes in the given vertical layer.
        """
        z, L = self._resolve_layer(layer)
        if row is None and col is None:
            return [n for n in self.G.nodes() if n[0] == z]
        elif row is not None and col is not None:
            return [(z, row, col)]
        elif row is not None:
            return [(z, row, c) for c in self.complete_cols[L]]
        elif col is not None:
            return [(z, r, col) for r in self.complete_rows[L]]

    def edges_in_layer(self, layer, sorted=False):
        """
        Return the list of edges in the given layer.
        """
        z, L = self._resolve_layer(layer)
        edges = [(u, v) for u, v in self.G.edges() if u[0] == z and v[0] == z]
        if sorted:
            edges.sort()
        return edges

    def cols_in_layer(self, layer, parity=None):
        """
        Return the list of column coordinates in the given layer.
        """
        z, L = self._resolve_layer(layer)
        cols = self.complete_cols[L]
        if parity is None:
            return cols
        if parity not in ("even", "odd"):
            raise ValueError("parity must be one of {None, 'even', 'odd'}")
        return [c for c in cols if (cols.index(c) % 2 == 0) is (parity == "even")]

    def col_indices_in_layer(self, layer, parity=None):
        """
        Return the list of column indices in the given layer.
        """
        z, L = self._resolve_layer(layer)
        cols = self.complete_cols[L]
        if parity is None:
            return list(range(len(cols)))
        if parity not in ("even", "odd"):
            raise ValueError("parity must be one of {None, 'even', 'odd'}")
        return [i for i in range(len(cols)) if (i % 2 == 0) is (parity == "even")]

    def rows_in_layer(self, layer, parity=None):
        """
        Return the list of row coordinates in the given layer.
        """
        z, L = self._resolve_layer(layer)
        rows = self.complete_rows[L]
        if parity is None:
            return rows
        if parity not in ("even", "odd"):
            raise ValueError("parity must be one of {None, 'even', 'odd'}")
        return [r for r in rows if (rows.index(r) % 2 == 0) is (parity == "even")]

    def layer_index(self, layer):
        """
        Return the layer index (z) for the given layer name.
        """
        if isinstance(layer, int):
            return layer
        elif isinstance(layer, str):
            if layer not in self.layer_to_idx:
                raise KeyError(f"Unknown layer name {layer!r}")
            return self.layer_to_idx[layer]
        else:
            raise TypeError("layer must be int (index) or str (name)")

    def is_even_col(self, layer, col):
        """
        Return True if the given column is even in the given layer.
        # Gate
        """
        z, L = self._resolve_layer(layer)
        cols = self.complete_cols[L]
        if col not in cols:
            raise ValueError(f"Col {col} not in layer {L!r}")
        return cols.index(col) % 2 == 0

    def is_odd_col(self, layer, col):
        """
        Return True if the given column is odd in the given layer.
        # Source / Drain
        """
        z, L = self._resolve_layer(layer)
        cols = self.complete_cols[L]
        if col not in cols:
            raise ValueError(f"Col {col} not in layer {L!r}")
        return cols.index(col) % 2 == 1

    def row_indices_in_layer(self, layer, parity=None):
        """
        Return the list of row indices in the given layer.
        """
        z, L = self._resolve_layer(layer)
        rows = self.complete_rows[L]
        if parity is None:
            return list(range(len(rows)))
        if parity not in ("even", "odd"):
            raise ValueError("parity must be one of {None, 'even', 'odd'}")
        return [i for i in range(len(rows)) if (i % 2 == 0) is (parity == "even")]

    def max_col_in_layer(self, layer):
        """
        Return the maximum column coordinate in the given layer.
        """
        z, L = self._resolve_layer(layer)
        cols = self.complete_cols[L]
        return max(cols)

    def max_row_in_layer(self, layer):
        """
        Return the maximum row coordinate in the given layer.
        """
        z, L = self._resolve_layer(layer)
        rows = self.complete_rows[L]
        return max(rows)

    def num_cols_in_layer(self, layer):
        """
        Return the number of columns in the given layer.
        """
        z, L = self._resolve_layer(layer)
        cols = self.complete_cols[L]
        return len(cols)

    def num_rows_in_layer(self, layer):
        """
        Return the number of rows in the given layer.
        """
        z, L = self._resolve_layer(layer)
        rows = self.complete_rows[L]
        return len(rows)

    def _resolve_layer(self, layer):
        """
        Returns (z, L) given layer either as int z or str name L.
        """
        if isinstance(layer, int):
            z = layer
            if z not in self.idx_to_layer:
                raise KeyError(f"Unknown layer index {z}")
            return z, self.idx_to_layer[z]
        elif isinstance(layer, str):
            matches = [z for z, name in self.idx_to_layer.items() if name == layer]
            if not matches:
                raise KeyError(f"Unknown layer name {layer!r}")
            return matches[0], layer
        else:
            raise TypeError("layer must be int (index) or str (name)")

    def get_row(self, layer, idx):
        """
        Return the row‐coordinate at position `idx` in the given layer.
        """
        z, L = self._resolve_layer(layer)
        rows = self.complete_rows[L]
        if not (0 <= idx < len(rows)):
            raise IndexError(f"Row index {idx} out of range for layer {L!r}")
        return rows[idx]

    def get_col(self, layer, idx):
        """
        Return the col‐coordinate at position `idx` in the given layer.
        """
        z, L = self._resolve_layer(layer)
        cols = self.complete_cols[L]
        if not (0 <= idx < len(cols)):
            raise IndexError(f"Col index {idx} out of range for layer {L!r}")
        return cols[idx]

    def edges(self):
        """
        Return the list of edges in the graph.
        """
        return list(self.G.edges())

    def arcs(self):
        """
        Return the list of arcs (bidirectional edges) in the graph.
        """
        return [(u, v) for u, v in self.G.edges()] + [(v, u) for u, v in self.G.edges()]

    def nodes(self):
        """
        Return the list of nodes in the graph.
        """
        return list(self.G.nodes())

    def stats(self):
        """
        Print the number of nodes and edges in the graph.
        """
        num_nodes = len(self.G.nodes())
        num_edges = len(self.G.edges())
        num_layers = len(self.idx_to_layer)
        num_arcs = len(self.arcs())
        logging.info(f"LayeredGridGraph has {num_nodes} nodes and {num_edges} edges and {num_layers} layers")
        logging.info(f"                 has {num_arcs} arcs (bidirectional edges)")
        return num_nodes, num_edges

    def has_via_above(self, node):
        """
        Check if the node has a via above it in the graph.
        """
        if not self.is_node_in_graph(node):
            raise ValueError(f"Node {node} does not exist in the graph.")
        z, r, c = node
        above_node = (z + 1, r, c)
        return above_node in self.G.nodes()

    def has_via_below(self, node):
        """
        Check if the node has a via below it in the graph.
        """
        if not self.is_node_in_graph(node):
            raise ValueError(f"Node {node} does not exist in the graph.")
        z, r, c = node
        above_node = (z - 1, r, c)
        return above_node in self.G.nodes()
    
    def get_via_above(self, node):
        """
        Return the node above the given node in the graph.
        """
        if not self.is_node_in_graph(node):
            raise ValueError(f"Node {node} does not exist in the graph.")
        z, r, c = node
        above_node = (z + 1, r, c)
        if above_node not in self.G.nodes():
            raise LookupError(f"Expected via above {node} missing from graph.")
        return above_node
    
    def get_via_below(self, node):
        """
        Return the node below the given node in the graph.
        """
        if not self.is_node_in_graph(node):
            raise ValueError(f"Node {node} does not exist in the graph.")
        z, r, c = node
        below_node = (z - 1, r, c)
        if below_node not in self.G.nodes():
            raise LookupError(f"Expected via below {node} missing from graph.")
        return below_node
    
    def get_layer_rows_starting_from(self, layer, row):
        """
        Return the list of rows in the given layer starting from the specified row.
        If the row does not exist, it will return an empty list.
        """
        z, L = self._resolve_layer(layer)
        rows = self.complete_rows[L]
        if row not in rows:
            raise ValueError(f"Row {row} not in layer {L!r}")
        start_index = rows.index(row)
        return rows[start_index:]
    
    def get_layer_cols_starting_from(self, layer, col):
        """
        Return the list of columns in the given layer starting from the specified column.
        If the column does not exist, it will return an empty list.
        """
        z, L = self._resolve_layer(layer)
        cols = self.complete_cols[L]
        if col not in cols:
            raise ValueError(f"Col {col} not in layer {L!r}")
        start_index = cols.index(col)
        return cols[start_index:]

    def get_right_neighbor(self, node):
        if not self.is_node_in_graph(node):
            raise ValueError(f"Node {node} does not exist in the graph.")
        z, r, c = node

        # Resolve layer and direction in one go
        try:
            layer = self.idx_to_layer[z]
            direction = self.layer_to_direction[layer]
        except KeyError as e:
            raise ValueError(f"Graph data inconsistency: {e}")

        if direction == "V":
            raise ValueError(f"Layer '{layer}' is vertical; no horizontal neighbor.")
        if direction != "H":
            raise ValueError(f"Unknown direction '{direction}' for layer '{layer}'.")

        # Find next column
        cols = self.complete_cols.get(layer)
        if cols is None:
            raise ValueError(f"No column data for layer '{layer}'.")
        try:
            i = cols.index(c)
        except ValueError:
            raise ValueError(f"Column {c} not in layer '{layer}'.")
        if i == len(cols) - 1:
            return None  # No neighbor to the right

        neighbor = (z, r, cols[i + 1])
        if not self.is_node_in_graph(neighbor):
            raise LookupError(f"Expected neighbor {neighbor} missing from graph.")
        return neighbor

    def get_left_neighbor(self, node):
        if not self.is_node_in_graph(node):
            raise ValueError(f"Node {node} does not exist in the graph.")
        z, r, c = node

        # Resolve layer and direction in one go
        try:
            layer = self.idx_to_layer[z]
            direction = self.layer_to_direction[layer]
        except KeyError as e:
            raise ValueError(f"Graph data inconsistency: {e}")

        if direction == "V":
            raise ValueError(f"Layer '{layer}' is vertical; no horizontal neighbor.")
        if direction != "H":
            raise ValueError(f"Unknown direction '{direction}' for layer '{layer}'.")

        # Find previous column
        cols = self.complete_cols.get(layer)
        if cols is None:
            raise ValueError(f"No column data for layer '{layer}'.")
        try:
            i = cols.index(c)
        except ValueError:
            raise ValueError(f"Column {c} not in layer '{layer}'.")
        if i == 0:
            return None
        neighbor = (z, r, cols[i - 1])
        if not self.is_node_in_graph(neighbor):
            raise LookupError(f"Expected neighbor {neighbor} missing from graph.")
        return neighbor

    # 07/26/25 Debugged incorrect front direction (was mapped to back)
    def get_front_neighbor(self, node, check_site=False):
        if not self.is_node_in_graph(node):
            raise ValueError(f"Node {node} does not exist in the graph.")
        z, r, c = node

        # Resolve layer and direction in one go
        try:
            layer = self.idx_to_layer[z]
            direction = self.layer_to_direction[layer]
        except KeyError as e:
            raise ValueError(f"Graph data inconsistency: {e}")

        if direction == "H":
            raise ValueError(f"Layer '{layer}' is horizontal; no vertical neighbor.")
        if direction != "V":
            raise ValueError(f"Unknown direction '{direction}' for layer '{layer}'.")

        # Find next row
        rows = self.complete_rows.get(layer)
        if rows is None:
            raise ValueError(f"No row data for layer '{layer}'.")
        try:
            i = rows.index(r)
        except ValueError:
            raise ValueError(f"Row {r} not in layer '{layer}'.")
        # if i == len(rows) - 1:
        #     return None
        if i == 0:
            return None
        neighbor = (z, rows[i - 1], c)
        if not self.is_node_in_graph(neighbor):
            raise LookupError(f"Expected neighbor {neighbor} missing from graph.")
        # prevent crossing site division line
        if check_site and self.site_div_line != -1:
            if neighbor[1] <= self.site_div_line and r >= self.site_div_line:
                return None
        return neighbor

    # 07/26/25 Debugged incorrect back direction (was mapped to front)
    def get_back_neighbor(self, node, check_site=False):
        if not self.is_node_in_graph(node):
            raise ValueError(f"Node {node} does not exist in the graph.")
        z, r, c = node

        # Resolve layer and direction in one go
        try:
            layer = self.idx_to_layer[z]
            direction = self.layer_to_direction[layer]
        except KeyError as e:
            raise ValueError(f"Graph data inconsistency: {e}")

        if direction == "H":
            raise ValueError(f"Layer '{layer}' is horizontal; no vertical neighbor.")
        if direction != "V":
            raise ValueError(f"Unknown direction '{direction}' for layer '{layer}'.")

        # Find previous row
        rows = self.complete_rows.get(layer)
        if rows is None:
            raise ValueError(f"No row data for layer '{layer}'.")
        try:
            i = rows.index(r)
        except ValueError:
            raise ValueError(f"Row {r} not in layer '{layer}'.")
        # if i == 0:
        #     return None
        if i == len(rows) - 1:
            return None
        neighbor = (z, rows[i + 1], c)
        if not self.is_node_in_graph(neighbor):
            raise LookupError(f"Expected neighbor {neighbor} missing from graph.")
        # prevent crossing site division line
        if check_site and self.site_div_line != -1:
            if neighbor[1] >= self.site_div_line and r <= self.site_div_line:
                return None
        return neighbor

    def get_nearest_node_in_layer(self, layer, row, col):
        """
        Return the nearest node in the given layer to the specified row and column.
        If the exact node does not exist, it will return the closest one.
        """
        z, L = self._resolve_layer(layer)

        # Remove validation checks that require exact row/col matches
        # Instead, find truly nearest node regardless of whether row/col exists

        # Find the closest node
        closest_node = None
        min_distance = float("inf")
        for n in self.G.nodes():
            if n[0] == z:
                distance = math.sqrt((n[1] - row) ** 2 + (n[2] - col) ** 2)
                if distance < min_distance:
                    min_distance = distance
                    closest_node = n

        if closest_node is None:
            raise ValueError(f"No nodes found in layer {L!r} at all.")

        return closest_node

    @staticmethod
    def draw_one_layer_grid_2d(G, layer, node_size=40, edge_color="gray", node_edge_color="k", outdir=""):
        """
        Draw a single layer of G in 2D.

        Parameters:
          G               : networkx.Graph with nodes (z, r, c) and node['layer'] name
          layer           : int (layer index) or str (layer name)
          node_size       : size of each node marker
          edge_color      : color for in‐layer edges
          node_edge_color : edgecolor for node markers
        """
        # sanity check
        if not hasattr(G, "nodes") or not hasattr(G, "edges"):
            raise TypeError("Expected a networkx.Graph")

        # extract unique layer‐indices and names
        layers = sorted({n[0] for n in G.nodes()})
        layer_names = {z: next(iter({G.nodes[n]["layer"] for n in G.nodes() if n[0] == z})) for z in layers}

        # positions in 2D
        pos2d = {n: (n[2], n[1]) for n in G.nodes()}
        # x=col, y=row
        # collect nodes & in‐layer edges
        nodes_z = [n for n in G.nodes() if n[0] == layer]
        edges_z = [(u, v) for u, v in G.edges() if u[0] == v[0] == layer]
        # draw edges
        fig, ax = plt.subplots(figsize=(6, 6))
        for u, v in edges_z:
            x0, y0 = pos2d[u]
            x1, y1 = pos2d[v]
            ax.plot([x0, x1], [y0, y1], color=edge_color, alpha=0.6, linewidth=1)
        # draw nodes
        xs = [pos2d[n][0] for n in nodes_z]
        ys = [pos2d[n][1] for n in nodes_z]
        ax.scatter(
            xs,
            ys,
            s=node_size,
            c=[plt.get_cmap("tab10")(layers.index(layer))],
            edgecolor=node_edge_color,
            zorder=5,
        )
        # remove border
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        # disable grid
        ax.xaxis.set_major_locator(plt.NullLocator())
        ax.yaxis.set_major_locator(plt.NullLocator())
        # rotate ticks
        ax.tick_params(axis="x", rotation=45)
        ax.set_title(layer_names[layer])
        ax.set_xlabel("Column (x)")
        ax.set_ylabel("Row (y)")
        ax.set_aspect("equal")
        ax.grid(True, linestyle="--", alpha=0.3)
        plt.tight_layout()
        # plt.show()
        if outdir != "":
            plt.savefig(f"{outdir}/debug/graph_{layer}.png")
        else:
            plt.show()

    @staticmethod
    def draw_layered_grid_2d(G, node_size=40, edge_color="gray", node_edge_color="k", figsize_per_layer=(4, 4), outdir=""):
        """
        Draw every layer of G in its own 2D subplot, arranged side by side.

        Parameters:
          G               : networkx.Graph with nodes (z, r, c) and node['layer'] name
          node_size       : size of each node marker
          edge_color      : color for in‐layer edges
          node_edge_color : edgecolor for node markers
          figsize_per_layer : (width, height) of each subplot
        """
        # sanity check
        if not hasattr(G, "nodes") or not hasattr(G, "edges"):
            raise TypeError("Expected a networkx.Graph")

        # extract unique layer‐indices and names
        layers = sorted({n[0] for n in G.nodes()})
        layer_names = {z: next(iter({G.nodes[n]["layer"] for n in G.nodes() if n[0] == z})) for z in layers}

        # positions in 2D
        pos2d = {n: (n[2], n[1]) for n in G.nodes()}  # x=col, y=row

        # build subplots
        n = len(layers)
        fig, axes = plt.subplots(1, n, figsize=(figsize_per_layer[0] * n, figsize_per_layer[1]), sharex=True, sharey=True)
        if n == 1:
            axes = [axes]

        for ax, z in zip(axes, layers):
            # collect nodes & in‐layer edges
            nodes_z = [n for n in G.nodes() if n[0] == z]
            edges_z = [(u, v) for u, v in G.edges() if u[0] == v[0] == z]

            # draw edges
            for u, v in edges_z:
                x0, y0 = pos2d[u]
                x1, y1 = pos2d[v]
                ax.plot([x0, x1], [y0, y1], color=edge_color, alpha=0.6, linewidth=1)

            # draw nodes
            xs = [pos2d[n][0] for n in nodes_z]
            ys = [pos2d[n][1] for n in nodes_z]
            ax.scatter(
                xs,
                ys,
                s=node_size,
                c=[plt.get_cmap("tab10")(layers.index(z))],
                edgecolor=node_edge_color,
                zorder=5,
            )
            # remove border
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_visible(False)
            ax.spines["bottom"].set_visible(False)
            # rotate ticks
            ax.tick_params(axis="x", rotation=45)
            ax.set_title(layer_names[z])
            ax.set_xlabel("Column (x)")
            ax.set_ylabel("Row (y)")
            ax.set_aspect("equal")
            ax.grid(True, linestyle="--", alpha=0.3)

        plt.tight_layout()
        # plt.show()
        if outdir != "":
            plt.savefig(f"{outdir}/debug/grid_2d.png")
        else:
            plt.show()

    @staticmethod
    def draw_layered_grid_3d(
        G,
        elev=30,
        azim=45,
        node_size=40,
        intra_edge_alpha=0.6,
        inter_edge_alpha=0.3,
        intra_color="gray",
        inter_color="black",
    ):
        """
        Draws a 3D networkx.Graph G with transparent background
        and no z-axis ticks.  Nodes are (z, r, c) triples.
        """
        if not hasattr(G, "nodes") or not hasattr(G, "edges"):
            raise TypeError("Expected networkx.Graph")

        # 1) positions & layer-info
        pos3d = {n: (n[2], n[1], n[0]) for n in G.nodes()}
        layers = sorted({n[0] for n in G.nodes()})
        layer_names = {z: next(iter({G.nodes[n]["layer"] for n in G.nodes() if n[0] == z})) for z in layers}
        cmap = plt.get_cmap("tab10")
        colors = {z: cmap(i % 10) for i, z in enumerate(layers)}

        # 2) figure & transparent background
        fig = plt.figure(figsize=(8, 6), facecolor="none")
        fig.patch.set_alpha(0)  # transparent figure
        ax = fig.add_subplot(111, projection="3d", facecolor="none")

        # make the 3D panes transparent
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.set_pane_color((1, 1, 1, 0))
            axis._axinfo["grid"]["color"] = (1, 1, 1, 0)

        # 3) view angles
        ax.view_init(elev=elev, azim=azim)

        # 4) split edges
        intra = [(u, v) for u, v in G.edges() if u[0] == v[0]]
        inter = [(u, v) for u, v in G.edges() if u[0] != v[0]]

        # 5) draw edges
        for u, v in intra:
            x, y, z = zip(pos3d[u], pos3d[v])
            ax.plot(x, y, z, color=intra_color, alpha=intra_edge_alpha, linewidth=1)
        for u, v in inter:
            x, y, z = zip(pos3d[u], pos3d[v])
            ax.plot(x, y, z, color=inter_color, alpha=inter_edge_alpha, linestyle="dashed", linewidth=1)

        # 6) draw nodes per layer
        for z in layers:
            xs = [pos3d[n][0] for n in G.nodes() if n[0] == z]
            ys = [pos3d[n][1] for n in G.nodes() if n[0] == z]
            zs = [pos3d[n][2] for n in G.nodes() if n[0] == z]
            ax.scatter(
                xs,
                ys,
                zs,
                s=node_size,
                c=[colors[z]],
                label=layer_names[z],
                edgecolor="k",
                alpha=0.9,
            )

        # 7) labels & legend & disable z-ticks
        ax.set_xlabel("Column (x)")
        ax.set_ylabel("Row (y)")
        ax.set_zlabel("Layer (z)")
        ax.set_zticks([])
        ax.legend(title="Layer Name", loc="upper left", bbox_to_anchor=(1.05, 1))
        plt.tight_layout()
        plt.show()