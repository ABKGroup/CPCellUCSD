import os
import time
import math
import itertools
from itertools import pairwise
import logging
import signal
import networkx as nx
# import src.config as config
from absl import logging as absl_logging
from collections import OrderedDict
from collections import deque

# from z3 import *

import datetime
import re
from ortools.sat.python import cp_model
# custom
import src.utility.config as config
from src.tech.tech import FinFET_Tech
from src.utility.entity import Circuit, LayerStack, Model, PinType
from src.solve.CPLOG import LoggingCpModel
from src.solve.graph import LayeredGridGraph
from src.solve.variable import TransistorVar
from src.core import accelerate
from src.core.objective import Objective
from src.core import inject
from src.core import metal_rule
from src.core import via_rule
from src.core import placement
from src.core import routing
from src.core import pin
from src.utility.util import log_variable_info, write_finfet_sh_result

# Set up logging to print messages
# Custom log format: [LEVEL] TIMESTAMP - MESSAGE
# NOTE: level available: DEBUG, INFO, WARNING, ERROR, CRITICAL
logging.basicConfig(format="[%(levelname)s] %(asctime)s - %(message)s", level=logging.INFO)


class FinFET:
    """
    Formulate and place FinFETs in the circuit.
    """

    def __init__(
        self,
        circuit: Circuit,
        fin_tech: FinFET_Tech,  # contains layer information
        output_dir="./output/",
        num_col=None,
        cell_config=None,
        flag_log_constraints=False,
    ):
        self.circuit = circuit
        self.output_dir = output_dir
        self.cell_config = config.read(cell_config)
        self.SET = self.cell_config["model_preset"]["value"]
        self.insert_num_db = self.cell_config["insert_num_db"]["value"]
        # ^ speedup
        self.use_break_symmetry = self.cell_config["use_break_symmetry_for_placement"]["value"]
        self.fix_placement_across_pn = self.cell_config["use_placement_order_for_identical_transistors"]["value"]
        self.use_low_degree_net = self.cell_config["close_in_low_degree_net"]["value"]
        # use the minimum cpp for the circuit
        if num_col is None:
            self.num_col = circuit.get_minimum_col(num_db=self.insert_num_db + 1)
        else:
            self.num_col = num_col

        self.fin_tech = fin_tech
        absl_logging.info("" + "-" * 80)
        absl_logging.info(" " * 64 + "┏┓┳┳┓┏┳┓┏┓┏┓┓ ┓ ")
        absl_logging.info(" " * 64 + "┗┓┃┃┃ ┃ ┃ ┣ ┃ ┃ ")
        absl_logging.info(" " * 64 + "┗┛┛ ┗ ┻ ┗┛┗┛┗┛┗┛")
        absl_logging.info(f"\t FinFET Technology: {self.fin_tech.lib_name} ")
        absl_logging.info(f"\t {self.circuit.subckt_name}")
        absl_logging.info("" + "-" * 80 + "\n")
        # ^ tech configuration
        self.canvas_width = 0
        self.canvas_height = 0

        self.mos_to_num_finger = {}  # mos_name -> num_finger
        self.nmos_placeable_row_indices = []  # rows where NMOS can be placed
        self.pmos_placeable_row_indices = []  # rows where PMOS can be placed
        self.nmos_pin_access_ri = []  # rows where NMOS pins can be accessed
        self.pmos_pin_access_ri = []  # rows where PMOS pins can be accessed
         # ^ model
        if flag_log_constraints:
            self.opt = LoggingCpModel(logfile=f"{output_dir}/constraint/{self.circuit.subckt_name}.log")
        else:
            self.opt = LoggingCpModel(logfile=None)
        # ^ variable
        self.transistor_vars = {}  # transistor name -> TransistorVar
        self.net_vars = {}  # net name -> NetVar
        # ^ initialization
        self._init_graph()
        self._init_tech()
        self._init_CP_domain()  # this is special to CP model
        self._init_var()
        # ^ build the model
        self._placement_constraints()
        self._routing_constraints()
        # ^ Clustering
        if self.cell_config["inject_cluster"]["value"]:
            G, clusters = accelerate.cluster_circuit(self, method="kkhdb", visualize=self.cell_config["inject_cluster"]["method"], remove_2d_nets=self.cell_config["inject_cluster"]["remove_2d_nets"])
            inject.inject_clusters(self, G, clusters)
        # ^ solve the model
        self.stats()
        if self.cell_config["use_strategy"]["value"] == "PLACE":
            self.use_placement_strategy()
        elif self.cell_config["use_strategy"]["value"] == "ROUTE":
            self.use_routing_window_strategy()
        elif self.cell_config["use_strategy"]["value"] == "ALL":
            self.use_placement_strategy()
            self.use_routing_window_strategy()
        # ^ Edge/Arc/Flow Injection
        for k, v in self.cell_config["inject_edge"]["value"].items():
            inject.inject_edge(self, (k[0], k[1], k[2]), (k[3], k[4], k[5]), value=v)
        for k, v in self.cell_config["inject_arc"]["value"].items():
            inject.inject_arc(self, k[0], (k[1], k[2], k[3]), (k[4], k[5], k[6]), value=v)
        for k, v in self.cell_config["inject_flow"]["value"].items():
            inject.inject_flow(self, k[0], k[1], (k[2], k[3], k[4]), (k[5], k[6], k[7]), value=v)
        # ^ Placement Injection
        for t in self.cell_config["inject_placement"]["value"]:
            inject.inject_placement(self, tran_name=t[0], x=t[1], y=t[2], flip=t[3])
        self.solve(
            mode="wsum",
            objectives=[
                (lambda: Objective.cpp(self), 1000, "min"),
                (lambda: Objective.gate_sharing(self), 1, "max"),
                (lambda: Objective.lisd_sharing(self), 1, "max"),
                (lambda: Objective.weighted_wirelength(self), 1, "min"),
                (lambda: Objective.db_placement(self), 1, "max"),
                (lambda: Objective.top_layer_usage(self), 100, "min"),  # this is very helpful
            ],
        )
        # ^ debug
        # self.log_debug_info()
        log_variable_info(self.opt, self.solver, filename=f"{output_dir}/result/{self.circuit.subckt_name}.var")
        # ^ write result
        write_finfet_sh_result(
            self.solver, self.circuit, self.transistor_vars, self.edge_vars,
            self.net_arc_vars, self.fin_tech, self.cpp_cost,
            filename=f"{output_dir}/result/{self.circuit.subckt_name}.res"
        )

    def _init_tech(self):
        """
        Initialize the graph configuration.
        """
        absl_logging.info("Initializing technology configuration...")
        # map transistor to number of fingers
        for tran in self.circuit.transistors.values():
            tran_width = tran.get_width()
            self.mos_to_num_finger[tran.name] = int(tran_width / self.fin_tech.unit_width)
        absl_logging.info(f"\tNumber of fingers: {self.mos_to_num_finger}")

        # row idx where MOSFETs can be placed on
        if self.fin_tech.height_config == "SH" and self.fin_tech.num_rt_track == 4:
            self.nmos_placeable_row_indices = [0]
            self.pmos_placeable_row_indices = [2]
            # row idx where MOSFETs' pin can be acessed
            self.nmos_pin_access_ri = [0, 1]
            self.pmos_pin_access_ri = [2, 3]
        elif self.fin_tech.height_config == "SH" and self.fin_tech.num_rt_track == 3:
            self.nmos_placeable_row_indices = [0]
            self.pmos_placeable_row_indices = [2]
            # row idx where MOSFETs' pin can be acessed
            self.nmos_pin_access_ri = [0]
            self.pmos_pin_access_ri = [2]
        absl_logging.info(f"\tNMOS placeable rows: {self.nmos_placeable_row_indices}, PMOS placeable rows: {self.pmos_placeable_row_indices}")
        absl_logging.info(f"\tNMOS pin accessible rows: {self.nmos_pin_access_ri}, PMOS pin accessible rows: {self.pmos_pin_access_ri}")

    def _init_graph(self):
        """
        Initialize the technology configuration.
        """
        absl_logging.info("Initializing graph configuration...")
        # NOTE: for all other layers we double the pitch because PC layer is expected to have float point values for SD columns
        # Later, we divide by 2 to get the actual column values
        # NOTE: num col reflects source/drain/gate columns. No need to double the pitch
        self.canvas_width = self.num_col * self.fin_tech.layer_stack.metal_layers[0].pitch
        self.canvas_height = self.fin_tech.num_rt_track * self.fin_tech.layer_stack.metal_layers[1].pitch * 2
        absl_logging.info(f"\tCanvas width: {self.canvas_width}, Canvas height: {self.canvas_height}")
        # map index to layer name
        idx_to_layer = {}
        layer_to_direction = {}
        layer_to_cols = {}
        layer_to_rows = {}
        for li, layer in enumerate(self.fin_tech.layer_stack.metal_layers):
            idx_to_layer[li] = layer.layer_name
        # columns on each layer
        for layer in self.fin_tech.layer_stack.metal_layers:
            layer_to_direction[layer.layer_name] = layer.direction
            if layer.direction == "H":
                continue
            # Later, we divide by 2 to get the actual column values
            tmp_pitch = layer.pitch * 2 if layer.layer_name != "PC" else layer.pitch
            tmp_offset = layer.offset * 2
            num_cols = int(math.ceil((self.canvas_width - tmp_offset) / tmp_pitch))
            layer_to_cols[layer.layer_name] = [tmp_offset + i * tmp_pitch for i in range(num_cols)]
        absl_logging.info(f"\tLayer to cols: {layer_to_cols}")
        # rows on each layer
        for layer in self.fin_tech.layer_stack.metal_layers:
            if layer.direction == "V":
                continue
            # Later, we divide by 2 to get the actual column values
            tmp_pitch = layer.pitch * 2 if layer.layer_name != "PC" else layer.pitch
            tmp_offset = layer.offset * 2
            num_rows = int(math.ceil((self.canvas_height - tmp_offset) / tmp_pitch))
            layer_to_rows[layer.layer_name] = [tmp_offset + i * tmp_pitch for i in range(num_rows)]
        self.lgg = LayeredGridGraph(layer_to_rows, layer_to_cols, idx_to_layer, layer_to_direction)
        self.lgg.stats()

    def _init_CP_domain(self):
        """
        Initialize the domain of the variables.
        """
        absl_logging.debug("Initializing variable domain...")
        # NOTE: we use col index here to reduce the size of the domain
        # self.plc_ci = self.lgg.col_indices_in_layer("PC", parity="even")[:-1]
        self.plc_ci = self.lgg.col_indices_in_layer("PC", parity="odd")[:-1]
        self.domain_mos_placable_ci = cp_model.Domain.FromValues(self.plc_ci)
        absl_logging.info(f"Domain MOS placeable col indices: {self.domain_mos_placable_ci}")
        self.plc_ri = self.lgg.row_indices_in_layer("PC", parity="even")
        self.domain_mos_placable_ri = cp_model.Domain.FromValues(self.plc_ri)
        absl_logging.debug(f"Domain MOS placeable row indices: {self.domain_mos_placable_ri}")
        # source/drain/gate col indices
        # self.sd_ci = self.lgg.col_indices_in_layer("PC", parity="even")
        self.sd_ci = self.lgg.col_indices_in_layer("PC", parity="odd")
        self.domain_sd_ci = cp_model.Domain.FromValues(self.sd_ci)
        absl_logging.debug(f"Domain SD indices: {self.domain_sd_ci}")
        # self.g_ci = self.lgg.col_indices_in_layer("PC", parity="odd")
        self.g_ci = self.lgg.col_indices_in_layer("PC", parity="even")
        self.domain_g_ci = cp_model.Domain.FromValues(self.g_ci)
        absl_logging.debug(f"Domain G col indices: {self.domain_g_ci}")
        # all col indices in the PC layer
        self.pc_ci = self.lgg.col_indices_in_layer("PC")
        self.domain_pc_ci = cp_model.Domain.FromValues(self.pc_ci)
        absl_logging.info(f"Domain placement column indices: {self.domain_pc_ci}")
        # all row indices in the PC layer
        self.pc_ri = self.lgg.row_indices_in_layer("PC")
        self.domain_pc_ri = cp_model.Domain.FromValues(self.pc_ri)
        absl_logging.info(f"Domain placement row indices: {self.domain_pc_ri}")
        # all row in the PC layer
        self.all_pc_row = self.lgg.rows_in_layer("PC")
        self.domain_pc_ri = cp_model.Domain.FromValues(self.all_pc_row)
        absl_logging.info(f"Domain PC row: {self.domain_pc_ri}")
        # all col in the PC layer
        self.all_pc_col = self.lgg.cols_in_layer("PC")
        self.domain_pc_ci = cp_model.Domain.FromValues(self.all_pc_col)
        absl_logging.info(f"Domain PC col: {self.domain_pc_ci}")

    def _init_var(self):
        """
        Initialize the placement variables for the transistors.
        """
        # ^ Transistors
        self.placed_tran_ci_vars = {}  # Bind transistor placement to bool variables (for later usages)
        self.has_tran_at_ci_vars = {}  # (ci) -> bool var
        self._init_transistor_vars()
        self._init_cpp()

        # ^ enforce the min/max column boundaries
        self._init_cell_boundaries()

        # ^ Diffusion breaks
        self.db_pmos_cols_vars = {}
        self.db_nmos_cols_vars = {}
        self._init_diffusion_break_vars()

        # ^ (NET SRC) Super Inner Nodes for internal pins
        self.node_is_src_vars = {}  # (net) -> (layer, row, col) -> bool var
        self._init_src_super_inner_nodes_vars()

        # ^ (NET TERMINAL) Super Inner Nodes for internal pins
        self.node_is_term_vars = {}  # (net) -> k -> (layer, row, col) -> bool var
        self._init_term_super_inner_nodes_vars()

        # ^ One source node per net and one node per k-th terminal, distinctness?
        self.adj_in = {node: [] for node in self.lgg.nodes()}
        self.adj_out = {node: [] for node in self.lgg.nodes()}
        for u_arc, v_arc in self.lgg.arcs():
            self.adj_out[u_arc].append((u_arc, v_arc))
            self.adj_in[v_arc].append((u_arc, v_arc))
        # --- 2) Variables --------------------------------------------------------
        # ^ Net variables: directed flow of net 'net', to terminal k, along directed arc (u→v)
        # also considers I/O pin flow
        self.num_pins_for_io = 0
        self.net_flow_vars = {}
        self.net_to_flow_cnt = {}  # net -> flow count
        self._init_net_flow_vars()
        # absl_logging.info(f"\t{len(self.net_flow_vars)} net flow variables created")

        # ^ Net Arc variables: "net touches arc (u→v)" (for capacity & objective)
        self.opt.log_comment(f"Net arc variables")
        self.net_arc_vars = {}
        self._init_net_arc_vars()
        # absl_logging.info(f"\t{len(self.net_arc_vars)} net arc variables created")

        # ^ Edge variables: an undirected edge {u,v} is used by any net (for objective)
        self.opt.log_comment(f"Edge variables")
        self.edge_vars = {}
        self.edge_to_cost = {}  # use for objective
        self._init_edge_vars()
        # absl_logging.info(f"\t{len(self.edge_vars)} edge variables created")

        # ^ normalize the edge cost to order (reduce the size of the domain)
        self.all_possible_edge_cost = sorted(list(self.edge_to_cost.values()))

        # ^ Super Outer Nodes for I/O pins
        self.son_terminal_nodes = {}
        # for net in self.circuit.nets.values():
        self._init_SON_positions()
        # absl_logging.info(f"\t{len(self.son_terminal_nodes['M1'])} SON M1 nodes recorded")

        # ^ Bind SON to each input and output nets
        self.node_is_SON_vars = {}  # (net) ->
        self.node_to_net_SON_vars = {}  # (layer, row, col) -> (net) -> bool var
        self._init_SON_vars()
        # absl_logging.info(f"\t{len(self.node_is_SON_vars)} SON variables created for {len(self.circuit.get_nets(with_power_ground=False))} nets")

        # absl_logging.info(f"\t{len(self.placed_tran_ci_vars)} transistor is placed column variables created")
        absl_logging.info(f"\tEnd of variable initilization ...")

    def _init_transistor_vars(self):
        tmp_pmos_x_var = []
        tmp_nmos_x_var = []
        self.opt.log_comment(f"Transistor variables")
        for tran in self.circuit.transistors.values():
            tvar = TransistorVar(tran.name)
            self.transistor_vars[tran.name] = tvar
            # Variables for placement
            tvar.x_var = self.opt.NewIntVarFromDomain(
                self.domain_mos_placable_ci,
                f"{tran.name}_x",
            )
            tvar.y_var = self.opt.NewIntVarFromDomain(
                self.domain_mos_placable_ri,
                f"{tran.name}_y",
            )
            tvar.flip_var = self.opt.NewBoolVar(
                f"{tran.name}_flip",
            )
            # if SH then y_var is fixed
            if self.fin_tech.height_config == "SH":
                if tran.model == Model.PMOS:
                    self.opt.Add(tvar.y_var == self.pmos_placeable_row_indices[0])
                    tmp_pmos_x_var.append(tvar.x_var)
                elif tran.model == Model.NMOS:
                    self.opt.Add(tvar.y_var == self.nmos_placeable_row_indices[0])
                    tmp_nmos_x_var.append(tvar.x_var)
        # each transistor must be placed in a different column
        if self.fin_tech.height_config == "SH":
            self.opt.AddAllDifferent(tmp_pmos_x_var)
            self.opt.AddAllDifferent(tmp_nmos_x_var)

        for tran in self.circuit.transistors.values():
            tvar = self.transistor_vars[tran.name]
            for ci in self.plc_ci:
                tran_is_placed_col_var = self.opt.NewBoolVar(f"tran_placed_col_{tran.name}_{ci}")
                self.placed_tran_ci_vars[(tran.name, ci)] = tran_is_placed_col_var
                # if x_var is placed at col, then turn on this variable
                self.opt.Add(tvar.x_var == ci).OnlyEnforceIf(tran_is_placed_col_var)
                self.opt.Add(tvar.x_var != ci).OnlyEnforceIf(tran_is_placed_col_var.Not())
        # has tran at col variable
        for ci in self.plc_ci:
            # 1) Gather ALL the "placed‐transistor‐at‐ci" vars
            # placed_here = [self.placed_tran_ci_vars[(tran, ci)] for tran in self.transistor_vars.keys()]
            placed_here = [self.placed_tran_ci_vars[(tran, ci)] for tran in self.transistor_vars.keys()]
            # 2) Make has_tran_at_ci == True ⇔ OR(placed_here)
            has_tran = self.opt.NewBoolVar(f"has_tran_at_ci_{ci}")
            self.opt.AddBoolOr(placed_here).OnlyEnforceIf(has_tran)
            self.opt.Add(sum(placed_here) == 0).OnlyEnforceIf(has_tran.Not())
            self.has_tran_at_ci_vars[ci] = has_tran

    def _init_diffusion_break_vars(self):
        # NOTE diffusion break should only be inserted in plc columns
        self.opt.log_comment(f"Diffusion break variables")
        for ci in self.plc_ci:
            pdb_var = self.opt.NewBoolVar(f"db_pmos_ci_{ci}")
            self.db_pmos_cols_vars[ci] = pdb_var
            ndb_var = self.opt.NewBoolVar(f"db_nmos_ci_{ci}")
            self.db_nmos_cols_vars[ci] = ndb_var
            # 1) if db then no MOSFETs sits at this column
            for tran in self.circuit.transistors.values():
                tvar = self.transistor_vars[tran.name]
                if tran.model == Model.PMOS:
                    self.opt.Add(tvar.x_var != ci).OnlyEnforceIf(pdb_var)
                elif tran.model == Model.NMOS:
                    self.opt.Add(tvar.x_var != ci).OnlyEnforceIf(ndb_var)
            # 2) build reifiers eq_k_col for “x_pmos[k] == col”
            tmp_pmos_eqs = []
            tmp_nmos_eqs = []
            for tran in self.circuit.transistors.values():
                tvar = self.transistor_vars[tran.name]
                if tran.model == Model.PMOS:
                    # eq = self.opt.NewBoolVar(f"eq_pmos_{tran.name}_{ci}")
                    # self.opt.Add(tvar.x_var == ci).OnlyEnforceIf(eq)
                    # self.opt.Add(tvar.x_var != ci).OnlyEnforceIf(eq.Not())
                    plc_var = self.placed_tran_ci_vars[(tran.name, ci)]
                    tmp_pmos_eqs.append(plc_var)
                elif tran.model == Model.NMOS:
                    # eq = self.opt.NewBoolVar(f"eq_nmos_{tran.name}_{ci}")
                    # self.opt.Add(tvar.x_var == ci).OnlyEnforceIf(eq)
                    # self.opt.Add(tvar.x_var != ci).OnlyEnforceIf(eq.Not())
                    plc_var = self.placed_tran_ci_vars[(tran.name, ci)]
                    tmp_nmos_eqs.append(plc_var)
            # if not db then somebody *must* sit at col
            self.opt.Add(sum(tmp_pmos_eqs) >= 1).OnlyEnforceIf(pdb_var.Not())
            self.opt.Add(sum(tmp_nmos_eqs) >= 1).OnlyEnforceIf(ndb_var.Not())

    def _init_src_super_inner_nodes_vars(self):
        self.opt.log_comment(f"Super Inner Nodes for src pins")
        self.node_is_src_vars = {}  # (net) -> (layer, row, col) -> bool var
        for net in self.circuit.get_nets(with_power_ground=False):
            self.node_is_src_vars[net.name] = {}  # (layer, row, col) -> bool var
            src_tran_name, src_pin = net.source()
            src_tvar = self.transistor_vars[src_tran_name]
            src_tran = self.circuit.transistors[src_tran_name]
            if src_tran.model == Model.PMOS:
                tmp_pin_accessible_row_indices = self.pmos_pin_access_ri
            elif src_tran.model == Model.NMOS:
                tmp_pin_accessible_row_indices = self.nmos_pin_access_ri
            else:
                raise ValueError(f"Transistor {src_tran_name} is not a PMOS or NMOS transistor")
            layer_idx = self.lgg.layer_index("PC")  # internal pin can only be placed on PC layer
            for ri in tmp_pin_accessible_row_indices:
                row = self.lgg.row_in_layer("PC", ri)
                # absl_logging.info(f"\tRI: {ri}, row: {row} for {src_tran_name} is {src_tran.model}")
                for ci in self.pc_ci:
                    # absl_logging.info(f"\tCI: {ci} for {src_tran_name} is {src_tran.model}")
                    col = self.lgg.col_in_layer("PC", ci)
                    # absl_logging.info(f"\tCI: {ci} => {col}")
                    # # even col is source/drain
                    # if src_pin == "source" and self.lgg.is_even_col(layer="PC", col=col):  # is sd col
                    # odd col is source/drain
                    if src_pin == "source" and self.lgg.is_odd_col(layer="PC", col=col):  # is src col
                        s_col_var = self.opt.NewBoolVar(f"net_issrc_{net.name}_R{row}_C{col}")
                        # add to possible source pin location
                        # src_tvar.s_col_idx_var.setdefault(col, []).append(s_col_var)
                        src_tvar.s_col_idx_var.setdefault(net.name, {}).setdefault(col, []).append(s_col_var)
                        self.node_is_src_vars[net.name][
                            (
                                layer_idx,
                                row,
                                col,
                            )
                        ] = s_col_var
                    # # odd col is gate
                    # elif src_pin == "gate" and self.lgg.is_odd_col(layer="PC", col=col):  # is gate col
                    # even col is gate
                    elif src_pin == "gate" and self.lgg.is_even_col(layer="PC", col=col):  # is gate col
                        g_col_var = self.opt.NewBoolVar(f"net_issrc_{net.name}_R{row}_C{col}")
                        # add to possible gate pin location
                        # src_tvar.g_col_idx_var.setdefault(col, []).append(g_col_var)
                        src_tvar.g_col_idx_var.setdefault(net.name, {}).setdefault(col, []).append(g_col_var)
                        self.node_is_src_vars[net.name][
                            (
                                layer_idx,
                                row,
                                col,
                            )
                        ] = g_col_var
                    # elif src_pin == "drain" and self.lgg.is_even_col(layer="PC", col=col):  # is sd col
                    # odd col is source/drain
                    elif src_pin == "drain" and self.lgg.is_odd_col(layer="PC", col=col):  # is sd col
                        d_col_var = self.opt.NewBoolVar(f"net_issrc_{net.name}_R{row}_C{col}")
                        # add to possible drain pin location
                        # src_tvar.d_col_idx_var.setdefault(col, []).append(d_col_var)
                        src_tvar.d_col_idx_var.setdefault(net.name, {}).setdefault(col, []).append(d_col_var)
                        self.node_is_src_vars[net.name][
                            (
                                layer_idx,
                                row,
                                col,
                            )
                        ] = d_col_var

    def _init_term_super_inner_nodes_vars(self):
        self.opt.log_comment(f"Super Inner Nodes for terminal pins")
        for net in self.circuit.get_nets(with_power_ground=False):
            self.node_is_term_vars[net.name] = {}  # k -> (layer, row, col) -> bool var
            # conn = net.connected_transistors
            # for tran_name, p in conn:
            for k, (term_tran_name, term_pin) in enumerate(net.terminals()):
                self.node_is_term_vars[net.name][k] = {}  # (layer, row, col) -> bool var
                term_tran = self.circuit.transistors[term_tran_name]
                term_tvar = self.transistor_vars[term_tran_name]
                tmp_pin_accessible_row_indices = None
                if term_tran.model == Model.PMOS:
                    tmp_pin_accessible_row_indices = self.pmos_pin_access_ri
                elif term_tran.model == Model.NMOS:
                    tmp_pin_accessible_row_indices = self.nmos_pin_access_ri
                else:
                    raise ValueError(f"Transistor {term_tran} is not a PMOS or NMOS transistor")
                layer_idx = self.lgg.layer_index("PC")  # internal pin can only be placed on PC layer
                for ri in tmp_pin_accessible_row_indices:
                    row = self.lgg.row_in_layer("PC", ri)
                    for ci in self.pc_ci:
                        col = self.lgg.col_in_layer("PC", ci)
                        # # even col is source/drain
                        # if term_pin == "source" and self.lgg.is_even_col(layer="PC", col=col):
                        # odd col is source/drain
                        if term_pin == "source" and self.lgg.is_odd_col(layer="PC", col=col):
                            s_col_var = self.opt.NewBoolVar(f"net_isterm_{net.name}_{k}_R{row}_C{col}")
                            # add to possible source pin location
                            # term_tvar.s_col_idx_var.setdefault(col, []).append(s_col_var)
                            term_tvar.s_col_idx_var.setdefault(net.name, {}).setdefault(col, []).append(s_col_var)
                            self.node_is_term_vars[net.name][k][(layer_idx, row, col)] = s_col_var
                        # # odd col is gate
                        # elif term_pin == "gate" and self.lgg.is_odd_col(layer="PC", col=col):
                        # even col is gate
                        elif term_pin == "gate" and self.lgg.is_even_col(layer="PC", col=col):
                            g_col_var = self.opt.NewBoolVar(f"net_isterm_{net.name}_{k}_R{row}_C{col}")
                            # add to possible gate pin location
                            # term_tvar.g_col_idx_var.setdefault(col, []).append(g_col_var)
                            term_tvar.g_col_idx_var.setdefault(net.name, {}).setdefault(col, []).append(g_col_var)
                            self.node_is_term_vars[net.name][k][(layer_idx, row, col)] = g_col_var
                        # elif term_pin == "drain" and self.lgg.is_even_col(layer="PC", col=col):
                        # odd col is source/drain
                        elif term_pin == "drain" and self.lgg.is_odd_col(layer="PC", col=col):
                            d_col_var = self.opt.NewBoolVar(f"net_isterm_{net.name}_{k}_R{row}_C{col}")
                            # add to possible drain pin location
                            # term_tvar.d_col_idx_var.setdefault(col, []).append(d_col_var)
                            term_tvar.d_col_idx_var.setdefault(net.name, {}).setdefault(col, []).append(d_col_var)
                            self.node_is_term_vars[net.name][k][(layer_idx, row, col)] = d_col_var

    def _init_net_flow_vars(self):
        self.opt.log_comment(f"Net flow variables")
        for net in self.circuit.get_nets(with_power_ground=False):
            num_extra_flow = 0
            if net.is_io_net():
                num_extra_flow = 1
                self.num_pins_for_io += 1
            for k in range(net.num_terminals() + num_extra_flow):
                for u_arc, v_arc in self.lgg.arcs():
                    net_flow_var = self.opt.NewBoolVar(f"flow_{net.name}_{k}_{u_arc}_{v_arc}")
                    self.net_flow_vars[(net.name, k, u_arc, v_arc)] = net_flow_var
            self.net_to_flow_cnt[net.name] = net.num_terminals() + num_extra_flow

    def _init_net_arc_vars(self):
        self.opt.log_comment(f"Net arc variables")
        for net in self.circuit.get_nets(with_power_ground=False):
            for u_arc, v_arc in self.lgg.arcs():
                # create a new net arc variable for each net and edge
                net_arc_var = self.opt.NewBoolVar(f"arc_{net.name}_{u_arc}_{v_arc}")
                self.net_arc_vars[(net.name, u_arc, v_arc)] = net_arc_var

    def _init_edge_vars(self):
        self.opt.log_comment(f"Edge variables")
        for u_edge, v_edge in self.lgg.edges():
            # create a new edge variable for each edge
            edge_var = self.opt.NewBoolVar(f"edge_{u_edge}_{v_edge}")
            self.edge_vars[(u_edge, v_edge)] = edge_var
            # if edge is a via
            if u_edge[0] != v_edge[0]:
                # add to via cost
                # self.edge_to_cost[(u_edge, v_edge)] = 100 * max(u_edge[0] + 1, v_edge[0] + 1) # avoid 0
                # NOTE try just use 5, make optimization a lot
                self.edge_to_cost[(u_edge, v_edge)] = 5
            else:
                # add to wire cost (associated to layer, wire length)
                # wl = abs(u_edge[1] - v_edge[1]) + abs(u_edge[2] - v_edge[2])
                # self.edge_to_cost[(u_edge, v_edge)] = wl * (u_edge[0] + 1)  # avoid 0
                # NOTE try just use 1, make optimization  alot
                self.edge_to_cost[(u_edge, v_edge)] = 1

    def _init_SON_positions(self):
        # allow pin access at M0
        tmp_son_row_indices = self._get_son_row_indices()
        self.son_terminal_nodes["M0"] = []
        for nodes in self.lgg.nodes_in_layer("M0"):
            pass
        self.son_terminal_nodes["M1"] = []
        for nodes in self.lgg.nodes_in_layer("M1"):
            for ri in tmp_son_row_indices:
                row = self.lgg.row_in_layer("M1", ri)
                # gather the nodes in the middle two rows
                if nodes[1] == row:
                    self.son_terminal_nodes["M1"].append(nodes)
        self.son_terminal_nodes["M2"] = []
        for nodes in self.lgg.nodes_in_layer("M2"):
            pass

    def _init_SON_vars(self):
        self.opt.log_comment(f"Super Outer Nodes for I/O pins")
        for net in self.circuit.get_nets(with_power_ground=False):
            if not net.is_io_net():
                continue
            self.node_is_SON_vars[net.name] = {}  # k -> (layer, row, col) -> bool var
            for k in range(net.num_terminals(), self.net_to_flow_cnt[net.name], 1):
                self.node_is_SON_vars[net.name][k] = {}  # (layer, row, col) -> bool var
                for node in self.son_terminal_nodes["M1"]:
                    layer_idx = node[0]
                    row = node[1]
                    col = node[2]
                    self.node_is_SON_vars[net.name][k][(layer_idx, row, col)] = self.opt.NewBoolVar(
                        f"net_isSON_{net.name}_{k}_L{layer_idx}_R{row}_C{col}"
                    )
                    self.node_to_net_SON_vars.setdefault((layer_idx, row, col), {}).setdefault(net.name, []).append(
                        self.node_is_SON_vars[net.name][k][(layer_idx, row, col)]
                    )
                # ^ enforce that for each net and for each pin, exactly one SON node must be used
                self.opt.Add(sum(self.node_is_SON_vars[net.name][k].values()) == 1)

    def _init_cpp(self):
        self.opt.log_comment(f"Enforcing total cpp...")
        # NOTE: define cpp_cost early to provide boundary constraints
        self.cpp_cost = self.opt.NewIntVarFromDomain(
            self.domain_sd_ci,
            f"cpp_cost",
        )
        self.opt.AddMaxEquality(
            self.cpp_cost,
            [self.transistor_vars[tran.name].x_var for tran in self.circuit.transistors.values()],
        )

    def _init_cell_boundaries(self):
        self.min_boundary_col = self.lgg.max_col_in_layer("PC") - self.insert_num_db * 2 * self.fin_tech.get_pitch("PC")
        self.max_boundary_col = self.lgg.max_col_in_layer("PC")
        absl_logging.info(f"min_boundary_col {self.min_boundary_col}, max_boundary_col {self.max_boundary_col}")

    def _placement_constraints(self):
        """
        build placement constraints
        """
        """
        Build placement constraints.

        Args:
            finfet: The FinFET instance
        """
        # ^ Linking source/drain/gate columns to transistor placement
        placement.link_source_drain_gate_columns_to_transistor_placement(self)
        # ^ ban other net from using power columns
        placement.ban_other_nets_on_pwr_columns(self)
        # # ^ no CA contact allowed unless the column resides a source or term
        placement.prohibit_CA_contact_on_non_source_term_columns(self)
        # ^ enforce that if a diffusion break is used in PMOS, then NMOS must also use it at the same column
        placement.diffusion_alignment(self)

        # ^ reduce the number of diffusion breaks by setting the allowable diffusion break columns
        self.opt.log_comment(f"Setting allowable diffusion break columns...")
        absl_logging.info(f"\t==\tSetting allowable diffusion break columns to {self.fin_tech.allowable_diffusion_break_cols}...")
        placement.limit_diffusion_breaks(self)

        # ^ Enforce Lexicographic Order Symmetry Breaking
        placement.placement_lexico_order_symmetry_breaking(self) if self.use_break_symmetry else None

        # ^ enforce pairwise diffusion sharing
        placement.pairwise_diffusion_sharing(self)

        # ^ enforce pairwise lisd sharing
        placement.pairwise_lisd_sharing(self)

        # ^ enforce pairwise gate sharing
        placement.pairwise_gate_sharing(self)

    def _routing_constraints(self):
        # ^ prohibit routing to touch left cell boundaries
        if not (self._is_1_to_1_gr() and self.circuit.subckt_name.lower()):
            absl_logging.info(f"Prohibiting routing to left cell boundaries ...")
            routing.prohibit_routing_to_left_cell_boundaries(self)

        routing.prohibit_routing_to_right_cell_boundaries(self)

        # ^ enforce that gate cut is continous and is at least X CPP long
        self.gate_share_at_col_vars = OrderedDict()  # ci -> gate_share_vars
        routing.bind_gate_sharing_to_columns(self, db_as_gs=True)

        # ^ enforce that gate cut is continous and is at least X CPP long
        self.min_gate_cut_len = self.cell_config["minimum_gate_cut_length"]["value"]
        self.gate_cut_window_vars = {}
        routing.gate_cut_window(self)

        # ^ If a db is placed at col, then no net arc and no net edge can use the immediate right gate col
        routing.prohibit_pc_routing_in_diffusion_break_cols(self)

        # ^ enforce that if gate cut, then CA must pick up at the top or bottom
        routing.enforce_CA_pickup_for_gate_cut(self)

        LIG_ROUTING = self.cell_config["lig_routing"]["value"]
        if LIG_ROUTING:
            pass
        else:
            # ^ [TURN OFF LIG Routing]limit gate contact
            routing.limit_gate_contact(self, num_contact=1)

        # ^ enforce that lisd sharing
        self.lisd_share_at_col_vars = OrderedDict()  # ci -> lisd_share_vars
        routing.bind_lisd_sharing_to_columns(self)

        LISD_ROUTING = self.cell_config["lisd_routing"]["value"]
        if LISD_ROUTING:
            pass
        else:
            # ^ [TURN OFF LISD Routing] limit lisd contact
            routing.limit_lisd_contact(self, num_contact=1)

        # ^ alwasys fix the first db to be 0
        self.opt.log_comment(f"No db at the first column ...")
        # self.opt.Add(self.db_cols_vars[1] == 0)

        # ^ Variables for Routing Window Constraint (NEW)
        self.opt.log_comment(f"Routing Window Constraint ...")
        # coordinates of the source pin and the terminals
        self.s_coord_x = {}
        self.s_coord_y = {}
        self.t_coord_x = {}  # self.t_coord_x[net][k_idx]
        self.t_coord_y = {}  # self.t_coord_y[net][k_idx]
        # actual coordinates of the terminals
        self.net_min_x = {}
        self.net_max_x = {}
        self.net_min_y = {}
        self.net_max_y = {}
        # enforced constrains on the routing window
        self.window_xmin_raw = {}
        self.window_xmax_raw = {}
        self.window_ymin_raw = {}
        self.window_ymax_raw = {}
        # -1    =>  Free for all routing
        # 0     =>  No tolerance routing (dangerous)
        # > 0   =>  With tolerance routing (preferred)
        if self.cell_config["routing_tolerance"]["value"] == True:
            self.routing_tolerance = int(self.cell_config["routing_tolerance"]["tol"] * self.fin_tech.get_pitch("PC")) # X cpp
        else:
            self.routing_tolerance = -1
        routing.routing_localization(self)

        # ^ --- 3) Linking flow variables to arc usage
        self.opt.log_comment(f"Linking flow variables to arc usage ...")
        # NOTE: flow is the minimum route. arc is on top of the flow and can be extended as needed (satisfy DR). edge is used to abstract the flow
        routing.link_flow_to_arc(self)
        routing.link_arc_to_edge(self)

        #  ^ --- 3.1) Net unique edge constraint
        routing.net_has_one_src_and_k_terminals(self)

        # ^ --- Constraint: A node cannot be a source for more than one net.
        routing.net_src_node_uniqueness(self)

        # ^ --- Constraint: A node cannot be a terminal for more than one net.
        routing.net_term_node_uniqueness(self)

        # ^ --- Constraint: an SON terminal cannot be a terminal for more than one net.
        routing.net_SON_node_uniqueness(self)

        # ^ --- Constraint: an SON cannot be aligned at the same column
        routing.prohibit_multiple_SONs_same_column(self)

        # ^ --- 5) Directed flow-conservation per net, per terminal (Ignore diffusion shared) ------------------
        routing.induce_internal_routing_flow_with_diffusion(self)

        # ^ --- 5.1) Route to I/O pins
        routing.induce_external_routing_flow(self)

        # ^ --- 6) A node cannot be propagated flow for more than one net.
        routing.node_exclusivity(self)

        # ^ --- 7) Geometric variables for design rule checking
        self.opt.log_comment(f"Adding geometric variables...")
        self.geometric_vars = {}  # node -> left, right, front, back
        metal_rule.geometric_vars_in_horizontal_layers(self)
        metal_rule.geometric_vars_in_vertical_layers(self)

        # ^ --- 8) EOL Design Rule Checking (C2C)
        eol_params = self.cell_config["eol_c2c_rule"]["value"]
        metal_rule.eol_rules_in_horizontal_layers(self, eol_params)
        metal_rule.eol_rules_in_vertical_layers(self, eol_params)

        # ^ --- 9) MAR Design Rule Checking (C2C)
        mar_params = self.cell_config["mar_c2c_rule"]["value"]
        supervia_params = {layer:False for layer in self.lgg.layer_to_idx.keys()}
        for layer in self.cell_config["supervia"]["value"]:
            if layer in supervia_params:
                supervia_params[layer] = True
        metal_rule.mar_rules_in_horizontal_layers(self, mar_params, supervia_params)
        metal_rule.mar_rules_in_vertical_layers(self, mar_params, supervia_params)

        # ^ --- 10) Via to metal connection rule
        via_rule.via_induce_vertical_metal(self, supervia_params)
        via_rule.via_induce_horizontal_metal(self, supervia_params)

        via_rule.vertical_metal_must_be_connected_to_via(self)
        via_rule.horizontal_metal_must_be_connected_to_via(self)

        # ^ --- 11) Via distance rule
        via_params = {
            tuple(k.strip() for k in key.split(',')): value
            for key, value in self.cell_config["via_c2c_rule"]["value"].items()
        }
        via_rule.via_separation_rules(self, via_params)

        # ^ --- 12) Pin Accessibility Rule
        self.opt.log_comment(f"Binding net usage on top layer ...")
        top_layer = "M2"
        self.net_use_top_track = {}  # netname -> bool var
        self.net_use_top_track_row_var = {}  # netname -> list of tracks row var
        pin.top_layer_net_usage(self, top_layer)

        # ^ Each net uses one M2 track at most
        pin.one_top_layer_track_per_net(self, top_layer)

        # ^ Each M2 track can be used by one net at most
        pin.one_net_per_top_layer_track(self, top_layer)

        # ^ Enforce that for each M1 pin, there is at least MPO entry point that can be used for routing on M2
        self.M1_MPO = self.cell_config["MPO"]["value"]  # number of entry points for M1
        if self.M1_MPO > 0:
            pin.m1_minimum_pin_opening(self, top_layer, mar_params, eol_params)

        # ^ Enforce that if a pin is an M0 Pin, then at least MPO entry point (besides its M1 SON) can be used for routing
        pin.m0_pin(self)

        # ^ Enforce that M0 pins are separated across different rows (no two M0 pins on same row)
        if self.cell_config["m0_pin_separation"]["value"]:
            pin.m0_pin_separation(self)
        
        # ^ Extend M0 pin to vacancy edges
        if self.cell_config["m0_pin_extension"]["value"]:
            pin.m0_pin_extension(self, vacancy_edges=self.cell_config["m0_pin_extension"]["vacancy_edges"]) 


    def _get_son_row_indices(self):
        if self.fin_tech.height_config != "SH":
            return None

        _ROW_MAP: dict[int, list[int]] = {
            2: [0, 1],
            3: [0, 2],
            4: [1, 2],
            5: [1, 3],
            6: [2, 3],
        }

        try:
            return _ROW_MAP[self.fin_tech.num_rt_track]
        except KeyError:
            raise ValueError(f"Unsupported number of rows: {self.fin_tech.num_rt_track}")

    def gather_src_term_vars_in_pmos_region(self, col):
        gathered_vars = []
        for tran in self.circuit.transistors.values():
            tvar = self.transistor_vars[tran.name]
            if tran.model == Model.PMOS:
                # source
                for net, col_vars in tvar.s_col_idx_var.items():
                    for var in col_vars.get(col, []):
                        gathered_vars.append(var)
                # drain
                for net, col_vars in tvar.d_col_idx_var.items():
                    for var in col_vars.get(col, []):
                        gathered_vars.append(var)
                # gate
                for net, col_vars in tvar.g_col_idx_var.items():
                    for var in col_vars.get(col, []):
                        gathered_vars.append(var)
        return gathered_vars

    def gather_src_term_vars_in_nmos_region(self, col):
        gathered_vars = []
        for tran in self.circuit.transistors.values():
            tvar = self.transistor_vars[tran.name]
            if tran.model == Model.NMOS:
                # source
                for net, col_vars in tvar.s_col_idx_var.items():
                    for var in col_vars.get(col, []):
                        gathered_vars.append(var)
                # drain
                for net, col_vars in tvar.d_col_idx_var.items():
                    for var in col_vars.get(col, []):
                        gathered_vars.append(var)
                # gate
                for net, col_vars in tvar.g_col_idx_var.items():
                    for var in col_vars.get(col, []):
                        gathered_vars.append(var)
        return gathered_vars

    def _is_1_to_1_gr(self):
        if self.fin_tech.get_pitch("M1") == self.fin_tech.get_pitch("PC") and self.fin_tech.get_offset("M1") == 0:
            # if M1 pitch and PC pitch are the same, then it is 1-to-1 grid
            return True
        return False

    def _gather_via_arcs(self, net_name, layer_1, layer_2):
        tmp_via_arcs = []
        for u, v in self.lgg.arcs():
            if u[0] == self.lgg.layer_to_idx[layer_1] and v[0] == self.lgg.layer_to_idx[layer_2]:
                tmp_via_arcs.append(self.net_arc_vars[(net_name, u, v)])
            if u[0] == self.lgg.layer_to_idx[layer_2] and v[0] == self.lgg.layer_to_idx[layer_1]:
                tmp_via_arcs.append(self.net_arc_vars[(net_name, u, v)])
        return tmp_via_arcs

    def extract_windows_horizontal_bidirectional(self, u, X):
        """
        arcs : list of tuples (a, b), each a directed edge a→b
            (you store both u→v and v→u for bidirectionality)
        u    : the node of interest, e.g. (layer_u, row_u, col_u)
        X    : window length along the column axis

        Returns a list of dicts { 'start': s, 'end': s+X, 'arcs': [...] },
        where each window [s, s+X] covers u and collects all directed arcs
        whose both endpoints are reachable from u and lie within [s, s+X].
        """
        layer_u, row_u, col_u = u

        # 1) Restrict to arcs on the same layer & row as u
        same_track = [(a, b) for (a, b) in self.lgg.arcs() if a[0] == layer_u and b[0] == layer_u and a[1] == row_u and b[1] == row_u]

        # 2) Build undirected adjacency and BFS to find every node reachable from u
        adj = {}
        for a, b in same_track:
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)

        reachable = {u}
        queue = deque([u])
        while queue:
            node = queue.popleft()
            for nbr in adj.get(node, ()):
                if nbr not in reachable:
                    reachable.add(nbr)
                    queue.append(nbr)

        # 3) Gather all column positions of those reachable nodes
        col_positions = sorted({n[2] for n in reachable})

        # 4) Slide windows of length X starting at each of those positions
        windows = []
        for s in col_positions:
            e = s + X
            # keep only windows that contain u
            if not (s <= col_u <= e):
                continue

            # collect all directed arcs whose endpoints are both reachable
            # and whose columns lie within [s, e]
            in_window = [(a, b) for (a, b) in same_track if a in reachable and b in reachable and s <= a[2] <= e and s <= b[2] <= e]

            if in_window:
                windows.append({"start": s, "end": e, "arcs": in_window})

        return windows

    def gather_via_vars_in_pmos_region(self, col=None):
        gathered_edge_vars = []
        pmos_pin_access_row = []
        for ri in self.pmos_pin_access_ri:
            pmos_pin_access_row.append(self.lgg.row_in_layer("PC", ri))
        for u, v in self.lgg.edges():
            if u[0] == self.lgg.layer_to_idx["PC"] and u[0] != v[0]:
                if col is not None:
                    if u[2] == col and u[1] in pmos_pin_access_row and v[1] in pmos_pin_access_row:
                        gathered_edge_vars.append(self.edge_vars[(u, v)])
                else:
                    if u[1] in pmos_pin_access_row and v[1] in pmos_pin_access_row:
                        gathered_edge_vars.append(self.edge_vars[(u, v)])
        return gathered_edge_vars

    def gather_via_vars_in_nmos_region(self, col=None):
        gathered_edge_vars = []
        nmos_pin_access_row = []
        for ri in self.nmos_pin_access_ri:
            nmos_pin_access_row.append(self.lgg.row_in_layer("PC", ri))
        for u, v in self.lgg.edges():
            if u[0] == self.lgg.layer_to_idx["PC"] and u[0] != v[0]:
                if col is not None:
                    if u[2] == col and u[1] in nmos_pin_access_row and v[1] in nmos_pin_access_row:
                        gathered_edge_vars.append(self.edge_vars[(u, v)])
                else:
                    if u[1] in nmos_pin_access_row and v[1] in nmos_pin_access_row:
                        gathered_edge_vars.append(self.edge_vars[(u, v)])
        return gathered_edge_vars

    def gather_nodes_in_pmos_region(self, col=None):
        gathered_nodes = []
        pmos_pin_access_row = []
        for ri in self.pmos_pin_access_ri:
            pmos_pin_access_row.append(self.lgg.row_in_layer("PC", ri))
        for node in self.lgg.nodes_in_layer("PC"):
            if col is not None:
                if node[2] == col and node[1] in pmos_pin_access_row:
                    gathered_nodes.append(node)
            else:
                if node[1] in pmos_pin_access_row:
                    gathered_nodes.append(node)
        return gathered_nodes

    def gather_nodes_in_nmos_region(self, col=None):
        gathered_nodes = []
        nmos_pin_access_row = []
        for ri in self.nmos_pin_access_ri:
            nmos_pin_access_row.append(self.lgg.row_in_layer("PC", ri))
        for node in self.lgg.nodes_in_layer("PC"):
            if col is not None:
                if node[2] == col and node[1] in nmos_pin_access_row:
                    gathered_nodes.append(node)
            else:
                if node[1] in nmos_pin_access_row:
                    gathered_nodes.append(node)
        return gathered_nodes

    def gather_ds_shareable_vars(self, net_name, tran_name_1, tran_name_2, pin_1, pin_2):
        """
        Gather shareable variables for a given net and two transistors.
        """
        if pin_1 == "gate" or pin_2 == "gate":
            return []
        key_left_12 = f"ds_left_{tran_name_1}_{tran_name_2}_{net_name}"
        key_left_21 = f"ds_left_{tran_name_2}_{tran_name_1}_{net_name}"
        key_right_12 = f"ds_right_{tran_name_1}_{tran_name_2}_{net_name}"
        key_right_21 = f"ds_right_{tran_name_2}_{tran_name_1}_{net_name}"
        shareable_vars = []
        if key_left_12 in self.ds_pair_vars:
            shareable_vars.append(self.ds_pair_vars[key_left_12])
        if key_left_21 in self.ds_pair_vars:
            shareable_vars.append(self.ds_pair_vars[key_left_21])
        if key_right_12 in self.ds_pair_vars:
            shareable_vars.append(self.ds_pair_vars[key_right_12])
        if key_right_21 in self.ds_pair_vars:
            shareable_vars.append(self.ds_pair_vars[key_right_21])
        return shareable_vars

    def gather_lisd_shareable_vars(self, net_name, tran_name_1, tran_name_2, pin_1, pin_2):
        """
        Gather shareable variables for a given net and two transistors.
        """
        if pin_1 == "gate" or pin_2 == "gate":
            return []
        key_12 = f"lisd_share_{tran_name_1}_{tran_name_2}_{net_name}"
        key_21 = f"lisd_share_{tran_name_2}_{tran_name_1}_{net_name}"
        shareable_vars = []
        if key_12 in self.lisd_share_pair_vars:
            shareable_vars.append(self.lisd_share_pair_vars[key_12])
        if key_21 in self.lisd_share_pair_vars:
            shareable_vars.append(self.lisd_share_pair_vars[key_21])
        return shareable_vars

    def gather_gate_shareable_vars(self, net_name, tran_name_1, tran_name_2, pin_1=None, pin_2=None, check_pin=True):
        """
        Gather shareable variables for a given net and two transistors.
        """
        if check_pin and not (pin_1 == "gate" and pin_2 == "gate"):
            return []
        key_12 = f"gate_share_{tran_name_1}_{tran_name_2}_{net_name}"
        key_21 = f"gate_share_{tran_name_2}_{tran_name_1}_{net_name}"
        shareable_vars = []
        if key_12 in self.gate_share_pair_vars:
            shareable_vars.append(self.gate_share_pair_vars[key_12])
        if key_21 in self.gate_share_pair_vars:
            shareable_vars.append(self.gate_share_pair_vars[key_21])
        return shareable_vars

    def stats(self, detail=False):
        # Get the model's protocol buffer
        model_proto = self.opt.Proto()
        # Get the count of variables defined in the proto
        num_variables = len(model_proto.variables)
        absl_logging.info("" + "-" * 80 + "\n")
        absl_logging.info(f"Total number of variables defined in the model: {num_variables}")
        # Get the count of constraints defined in the proto
        num_constraints = len(model_proto.constraints)
        absl_logging.info(f"Total number of constraints defined in the model: {num_constraints}\n")
        absl_logging.info("" + "-" * 80)
        if detail:
            absl_logging.info(f"\nList of {len(model_proto.constraints)} ConstraintProto objects:")
            for i, constraint in enumerate(model_proto.constraints):
                absl_logging.info(f"--- Constraint {i} ---")
                # You can check which field is populated to determine the constraint type
                if constraint.HasField("linear"):
                    absl_logging.info(f"  Type: Linear")
                    absl_logging.info(f"  Details: {constraint.linear}")  # Might be verbose
                elif constraint.HasField("all_diff"):
                    absl_logging.info(f"  Type: AllDifferent")
                    absl_logging.info(f"  Details: {constraint.all_diff}")
                elif constraint.HasField("bool_or") and len(constraint.enforcement_literal) > 0:
                    # Implications are often represented as BoolOr with enforcement literals
                    absl_logging.info(f"  Type: Implication (likely, via BoolOr + Enforcement)")
                elif constraint.HasField("no_overlap"):
                    absl_logging.info(f"  Type: NoOverlap")
                # Add more elif checks for other constraint types you use
                # (e.g., 'interval', 'cumulative', 'circuit', 'routes', 'table', etc.)
                else:
                    absl_logging.info(f"  Type: Other/Unknown in this example")
                    # You can print the whole constraint to see what it is:
                    absl_logging.info(constraint)

                # You can also inspect the constraint name if you set one (less common)
                if constraint.name:
                    absl_logging.info(f"  Name: {constraint.name}")

    # Placement/edge/flow/arc injection functions moved to src/core/inject.py

    def use_routing_window_strategy(self):
        """
        Use routing window strategy to reduce the number of routing windows.
        """
        self.opt.log_comment(f"Using routing window strategy ...")
        absl_logging.info("\t==\tUsing routing window strategy ...")
        # assert self.routing_tolerance != -1, "Routing tolerance must be set to use this strategy."
        if self.routing_tolerance == -1:
            absl_logging.error("Routing tolerance must be set to use this strategy.")
            return None
        routing_coord_decision_vars = []
        # for net_id in nets:
        for net in self.circuit.get_nets(with_power_ground=False):
            # routing_coord_decision_vars.append(s_coord_x[net_id])
            # routing_coord_decision_vars.append(s_coord_y[net_id])
            routing_coord_decision_vars.append(self.s_coord_x[net.name])
            routing_coord_decision_vars.append(self.s_coord_y[net.name])
            # for k_idx in range(args.net_degree):
            #     routing_coord_decision_vars.append(t_coord_x[net_id][k_idx])
            #     routing_coord_decision_vars.append(t_coord_y[net_id][k_idx])
            for k in range(net.num_terminals()):
                routing_coord_decision_vars.append(self.t_coord_x[net.name][k])
                routing_coord_decision_vars.append(self.t_coord_y[net.name][k])

        # Add bounding box variables after actual coordinates
        for net in self.circuit.get_nets(with_power_ground=False):
            routing_coord_decision_vars.append(self.net_min_x[net.name])
            routing_coord_decision_vars.append(self.net_max_x[net.name])
            routing_coord_decision_vars.append(self.net_min_y[net.name])
            routing_coord_decision_vars.append(self.net_max_y[net.name])
            # Potentially window_..._raw variables too

        if routing_coord_decision_vars:
            self.opt.AddDecisionStrategy(
                routing_coord_decision_vars,
                cp_model.CHOOSE_LOWEST_MIN,  # Variable selection: pick var with smallest LB
                cp_model.SELECT_MIN_VALUE,  # Value selection: try its LB
            )

    def use_placement_strategy(self):
        """
        Use placement strategy to guide the solver to assign variables in a specific order.
        Sort variables by layer, then row, then column to utilize spatial locality.
        """
        self.opt.log_comment(f"Using placement strategy ...")
        absl_logging.info("\t==\tUsing placement strategy ...")

        # Collect all placement variables with their node coordinates
        all_placement_vars_with_node_info = []

        # Add source node variables
        for net in self.circuit.get_nets(with_power_ground=False):
            for node, var in self.node_is_src_vars[net.name].items():
                # node is (layer, row, col)
                all_placement_vars_with_node_info.append({"var": var, "coords": node})

        # Add terminal node variables
        for net in self.circuit.get_nets(with_power_ground=False):
            for k in range(net.num_terminals()):
                for node, var in self.node_is_term_vars[net.name][k].items():
                    all_placement_vars_with_node_info.append({"var": var, "coords": node})

        # Add SON (Super Outer Node) variables for I/O pins if they exist
        for net_name in self.node_is_SON_vars:
            for k in self.node_is_SON_vars[net_name]:
                for node, var in self.node_is_SON_vars[net_name][k].items():
                    all_placement_vars_with_node_info.append({"var": var, "coords": node})

        # Sort by layer, then row, then column (z, y, x order)
        all_placement_vars_with_node_info.sort(key=lambda item: (item["coords"][0], item["coords"][1], item["coords"][2]))
        sorted_spatial_placement_vars = [item["var"] for item in all_placement_vars_with_node_info]

        # Add transistor placement variables at the beginning for higher priority
        transistor_placement_vars = []
        for __, tvar in self.transistor_vars.items():
            if self.fin_tech.height_config == "SH":
                transistor_placement_vars.append(tvar.x_var)
                transistor_placement_vars.append(tvar.flip_var)
            else:
                transistor_placement_vars.append(tvar.x_var)
                transistor_placement_vars.append(tvar.site_var)
                transistor_placement_vars.append(tvar.flip_var)

        # Combine transistor variables and node placement variables
        all_placement_vars = transistor_placement_vars + sorted_spatial_placement_vars
        # print("all_placement_vars", len(all_placement_vars))

        if all_placement_vars:
            absl_logging.info(f"\t==\tAdding decision strategy for {len(all_placement_vars)} placement variables")
            self.opt.AddDecisionStrategy(all_placement_vars, cp_model.CHOOSE_HIGHEST_MAX, cp_model.SELECT_MAX_VALUE)

    def wsum(self, solve_setting, objectives=None, silence=False):
        self.opt.log_comment(f"Defining the objective function ...")
        self.solver = cp_model.CpSolver()
        self.solver.parameters.num_search_workers = self.cell_config["num_search_workers"]["value"]  # smaller number of workers actually faster
        self.solver.parameters.random_seed = self.cell_config["seed"]["value"]
        if silence:
            self.solver.parameters.log_search_progress = False 
        else:
            self.solver.parameters.log_search_progress = True 
            self.solver.log_callback = print
        if self.cell_config["max_time"]["value"]:
            self.solver.parameters.max_time_in_seconds = self.cell_config["max_time"]["time"]
        if solve_setting == 0:
            self.solver.parameters.cp_model_presolve = True
            self.solver.parameters.cp_model_probing_level = 3  # try 2 or 3
            # self.solver.parameters.linearization_level = 3
            self.solver.parameters.symmetry_level = 3
            self.solver.parameters.ignore_subsolvers.extend(
                [
                    "default_lp",
                    "max_lp",
                    # "QUICK_RESTART",
                    # "GRAPH_ARC_LNS",
                    # "GRAPH_CST_LNS",
                    # "GRAPH_DEC_LNS",
                    # "GRAPH_VAR_LNS",
                    # "RND_CST_LNS",
                    # "RND_VAR_LNS",
                    # "REDUCED_COSTS",
                    "packing_random_lns",  # did not close any gaps
                    "packing_square_lns",
                    # "fs_random_no_lp",    # not seeing promise bump
                    # "fs_random",
                    # "ls",
                    # "fj",
                    "packing_precedences_lns",
                    "packing_slice_lns",
                    "packing_swap_lns",
                    "scheduling_precedences_lns",
                    "graph_dec_lns",
                    "graph_var_lns",
                    "max_lp_sym",
                ]
            )
        elif solve_setting == 1:
            # ? Experiment with CFET 1
            # By default CP-SAT cycles many sub-solvers (LP-based, LNS, quick_restart, …). You can force a single strategy (and avoid expensive context switches) via:
            self.solver.parameters.search_branching = cp_model.FIXED_SEARCH
            # When interleaving portfolio solvers, set the batch size to ≈ 2× workers so each subsolver runs longer before synchronizing:
            self.solver.parameters.interleave_search = True
            self.solver.parameters.interleave_batch_size = 2 * self.solver.parameters.num_search_workers
        elif solve_setting == 2:
            # ? Experiment with CFET 2
            # Too many boolean, disable linearization
            self.solver.parameters.ignore_subsolvers.extend(
                [
                    "quick_restart",
                    "graph_arc_lns",
                    "graph_cst_lns",
                    "graph_dec_lns",
                    "graph_var_lns",
                    "rnd_cst_lns",
                    "rnd_var_lns",
                    "reduced_costs" # not enforced
                    "max_lp_sym",   # not enforced
                    "default_lp",
                ]
            )
            self.solver.parameters.linearization_level = 0
            self.solver.parameters.cp_model_presolve = True
            self.solver.parameters.cp_model_probing_level = 3  # try 1 or 2
            self.solver.parameters.symmetry_level = 3
        elif solve_setting == 2.5:
            # ? Experiment with CFET 2
            # Too many boolean, disable linearization
            self.solver.parameters.ignore_subsolvers.extend(
                [
                    "QUICK_RESTART",
                    "GRAPH_ARC_LNS",
                    "GRAPH_CST_LNS",
                    "GRAPH_DEC_LNS",
                    "GRAPH_VAR_LNS",
                    "RND_CST_LNS",
                    "RND_VAR_LNS",
                    "REDUCED_COSTS",
                    "MAX_LP_SYM",
                ]
            )
            self.solver.parameters.linearization_level = 0
            self.solver.parameters.cp_model_presolve = False
        total_obj = 0
        self.obj_terms = []
        if objectives is None or not objectives:
            absl_logging.info("\t==\tNo objectives defined. Using default objective function ...")
            total_obj = Objective.cpp(self)
        else:
            for i, obj in enumerate(objectives):
                if len(obj) != 3:
                    raise ValueError(f"Invalid objective function format: {obj}. Expected format: (obj, weight, opt)")
                obj_func, weight, opt = obj
                if not callable(obj_func):
                    raise ValueError(f"Invalid objective function: {obj_func}. Expected a callable function.")
                if not isinstance(weight, (int)):
                    raise ValueError(f"Invalid weight: {weight}. Expected an Integer.")
                if opt not in ("min", "max"):
                    raise ValueError(f"Invalid objective function option: {opt}. Expected 'min' or 'max'.")
                # Extract actual function name from lambda if needed
                obj_name = obj_func.__name__
                if obj_name == "<lambda>":
                    import inspect
                    try:
                        src = inspect.getsource(obj_func).strip()
                        # Extract method name from patterns like "Objective.cpp(self)" or "Objective.gate_sharing(self)"
                        match = re.search(r'Objective\.(\w+)\s*\(', src)
                        if match:
                            obj_name = match.group(1)
                    except (OSError, TypeError):
                        pass  # Keep "<lambda>" if source inspection fails
                absl_logging.info(f"\t==\tAdding objective function {i + 1}: [{opt}] {obj_name} with weight {weight}")
                obj_expr = obj_func()
                # record the objective function term for later use
                self.obj_terms.append((obj_name, obj_expr, weight, opt))
                if opt == "min":
                    total_obj += weight * obj_expr
                elif opt == "max":
                    total_obj += (-weight) * obj_expr

        # absl_logging.info(f"\t==\tTotal objective function: {total_obj}")
        self.opt.Minimize(total_obj)
        # check for optimality gap
        if self.cell_config["use_relative_gap"]["value"]:
            self.solver.parameters.relative_gap_limit = self.cell_config["use_relative_gap"]["perc"]
        time_start = time.time()
        absl_logging.info(f"\t==\tSolving the model with objective function: WSUM ...")
        status = self.solver.Solve(self.opt)
        time_end = time.time()
        elapsed_time = time_end - time_start
        absl_logging.info(f"Elapsed time: {elapsed_time:.2f} seconds")
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            absl_logging.info("\t┏┓┏┓┏┳┓")
            absl_logging.info("\t┗┓┣┫ ┃ ")
            absl_logging.info("\t┗┛┛┗ ┻ \n")
            absl_logging.info(f"\t==\tObjective function value: {self.solver.ObjectiveValue()}")
            for i, (name, expr, weight, opt) in enumerate(self.obj_terms, start=1):
                val = self.solver.Value(expr)
                print(f" Obj#{i} {name:20s} = {val:6d}" f"    ({opt}imize, weight={weight}, result={val * weight})")
        elif status == cp_model.UNKNOWN:
            absl_logging.info("\t???????")
            absl_logging.info("\t???????")
            absl_logging.info("\t???????\n")
            exit(1)
        else:
            absl_logging.info("No solution found.")
            absl_logging.info(f"\t╻╻╻  ┳┳┳┓┏┓┏┓┏┳┓  ╻╻╻")
            absl_logging.info(f"\t┃┃┃  ┃┃┃┃┗┓┣┫ ┃   ┃┃┃")
            absl_logging.info(f"\t•••  ┗┛┛┗┗┛┛┗ ┻   •••")
            exit(1)
        return total_obj, self.solver.ObjectiveValue()

    def solve(self, mode="wsum", objectives=None):
        """
        Define the objective function.
        """
        if mode == "wsum":
            self.wsum(objectives=objectives, solve_setting=self.SET, silence=False)
        elif mode == "lex":
            # first pass
            raise NotImplementedError("Lexicographic objective function is not implemented yet")
        else:
            raise ValueError(f"Invalid objective function mode: {mode}")
