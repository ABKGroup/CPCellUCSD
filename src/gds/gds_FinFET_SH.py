import klayout.db as pya
import math
from typing import NamedTuple, List, Tuple
import os
import re
import argparse
import logging
from absl import logging as absl_logging
from src.utility.entity import Model

SOLVER_RESCALE = 2.0
PERCISION_DIGITS = 4
SCALE = 4  # 1nm = 0.001um
# SCALE = 2.5

# Set up logging to print messages
# Custom log format: [LEVEL] TIMESTAMP - MESSAGE
# NOTE: level available: DEBUG, INFO, WARNING, ERROR, CRITICAL
logging.basicConfig(format="[%(levelname)s] %(asctime)s - %(message)s", level=logging.INFO)


class TechData(NamedTuple):
    """a docstring"""

    col: int
    track: int
    cp_pitch: float
    m0_pitch: float
    m1_pitch: float
    m2_pitch: float
    cp_width: float
    m0_width: float
    m1_width: float
    m2_width: float
    active_gap: float
    power_rail_thickness: float
    power_config: str
    io_pins: list


class TransistorData(NamedTuple):
    """a docstring"""

    name: str
    x: float
    y: float
    flip: bool
    width: float
    height: float
    source_col: float
    source_net: str
    drain_col: float
    drain_net: str
    gate_col: float
    gate_net: str
    model: str


class MetalData(NamedTuple):
    """a docstring"""

    metal_0: int
    metal_1: int
    row_0: float
    row_1: float
    col_0: float
    col_1: float
    net: str


# custom module
class TextShape:
    """
    Class to create a text shape object.
    Because not fond of klayout's text object
    """

    def __init__(self, textstring, x, y):
        self.textstring = textstring
        self.x = round(x, PERCISION_DIGITS) * SCALE
        self.y = round(y, PERCISION_DIGITS) * SCALE

    def pyatext_obj(self):
        return pya.Text(self.textstring, x=self.x, y=self.y)


class Box:
    """
    Class to create a box shape object.
    Because python cannot handle precision of klayout's box object
    """

    def __init__(self, lx, ly, ux, uy):
        self.lx = round(lx, PERCISION_DIGITS)
        self.ly = round(ly, PERCISION_DIGITS)
        self.ux = round(ux, PERCISION_DIGITS)
        self.uy = round(uy, PERCISION_DIGITS)

    def pyabox_obj(self):
        return pya.Box(
            pya.Point(self.lx * SCALE, self.ly * SCALE),
            pya.Point(self.ux * SCALE, self.uy * SCALE),
        )


class Box2:
    """
    Class to create a box shape object.
    Because python cannot handle precision of klayout's box object
    """

    def __init__(self, lx, ly, w, h):
        self.lx = round(lx, PERCISION_DIGITS)
        self.ly = round(ly, PERCISION_DIGITS)
        self.ux = round(lx + w, PERCISION_DIGITS)
        self.uy = round(ly + h, PERCISION_DIGITS)

    def pyabox_obj(self):
        return pya.Box(
            pya.Point(self.lx * SCALE, self.ly * SCALE),
            pya.Point(self.ux * SCALE, self.uy * SCALE),
        )


class FinFETLayout:
    def __init__(self, result_file, subckt_name, gds_file="./output/gds"):
        self.result_file = result_file
        self.subckt_name = subckt_name
        self.tech_data, self.pmos_transistor_data, self.nmos_transistor_data, self.metal_data = self._parse_result(self.result_file)
        # sort pmos_transistor_data by x
        self.pmos_transistor_data.sort(key=lambda x: x.x)
        # sort nmos_transistor_data by x
        self.nmos_transistor_data.sort(key=lambda x: x.x)
        # print(f"PMOS Transistors: {(self.pmos_transistor_data)}")
        # print(f"NMOS Transistors: {(self.nmos_transistor_data)}")

        self.width = self.tech_data.cp_pitch * (self.tech_data.col)
        self.height = self.tech_data.m0_pitch * (self.tech_data.track + 2)
        # add these to tech_data
        self.fin_y_offset = 21
        self.fin_pitch = 18
        self.fin_width = 6
        self.poly_height = 154
        self.active_x_overlap = 14
        self.active_height = 46
        # self.active_x_offset = 15.5
        self.active_x_offset = -7
        self.active_y_offset = (self.height - self.active_height * 2 - self.tech_data.active_gap) / 2
        self.gate_cut_boundary_height = 37
        self.gate_cut_height = 10
        
        self.lig_width = 14
        self.lig_height = 14
        self.lisd_width = 16
        # self.lisd_x_offset = 14.5
        self.lisd_x_offset = -8
        self.lisd_signal_height = 48
        self.lisd_power_height = 66
        self.lisd_signal_gap = 8
        self.lisd_power_gap = 10
        self.lisd_y_offset = 20
        self.sdt_gap = 12
        self.sdt_y_offset = 24
        self.sdt_height = 42
        # self.ca_x_offset = 15.5
        self.ca_x_offset = -7
        self.ca_y_offset = 29
        self.ca_width = 14
        self.ca_height = 14
        self.m0_y_offset = 29
        # self.m0_x_offset = 15.5
        self.m0_x_offset = -7
        self.m0_h_ovl = 3
        self.m0_v_ovl = 0
        self.v0_y_offset = 29
        # self.v0_x_offset = 15.5
        self.v0_x_offset = -7
        self.v0_width = 14
        self.v0_height = 14
        self.m1_y_offset = 29
        # self.m1_x_offset = 15.5
        self.m1_x_offset = -7
        self.m1_h_ovl = 0.5
        self.m1_v_ovl = 5
        self.v1_y_offset = 29
        # self.v1_x_offset = 15.5
        self.v1_x_offset = -7
        self.v1_width = 14
        self.v1_height = 14
        self.m2_y_offset = 29
        # self.m2_x_offset = 15.5
        self.m2_x_offset = -7
        self.m2_v_ovl = 0
        self.m2_h_ovl = 5

        self.cell = None
        if os.path.isfile(gds_file):
            self.layout = pya.Layout()
            self.layout.read(gds_file)
            print(f"[WARNING] GDS PATH already exists: {gds_file}. Writing to an existing file.")
            # check if cell already exists
            for cell in self.layout.top_cells():
                if self.subckt_name == cell.name:
                    # cell.clear()
                    print(f"[WARNING] {cell.name} is deleted.")
                    self.layout.delete_cell(cell.cell_index())
                    break
        else:
            print(f"[INFO] Creating new GDS file: {gds_file}.")
            self.layout = pya.Layout()
        
        print(f"[INFO] Creating new cell: {self.subckt_name}.")
        self.layout.dbu = 0.00025  # 0.25nm # default in PROBE3.0
        self.cell = self.layout.create_cell(self.subckt_name)
        self.draw()
        self.save(filename=gds_file)

    def _parse_result(self, path: str) -> Tuple[TechData, List[TransistorData], List[TransistorData], List[MetalData]]:
        tech_params = {}
        pmos_transistors: List[TransistorData] = []
        nmos_transistors: List[TransistorData] = []
        metals: List[MetalData] = []

        section = None
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # detect section headers
                if line.startswith("**") and "Technology Parameters" in line:
                    section = "tech"
                    continue
                elif line.startswith("**") and "Placement Result" in line:
                    section = "place"
                    # skip header line
                    header = next(f)
                    continue
                elif line.startswith("**") and "Routing Result" in line:
                    section = "route"
                    # skip header
                    header = next(f)
                    continue
                elif line.startswith("**") and "Cell Information" in line:
                    section = "cell"
                    # skip header
                    header = next(f)

                if section == "tech":
                    # each line: KEY   VALUE
                    parts = line.split()
                    key = parts[0]
                    val = " ".join(parts[1:])
                    tech_params[key] = val

                elif section == "place":
                    # parse placement rows
                    # Name X Y Flip Width Height SrcCol SrcNet DrnCol DrnNet GCol GNet Model
                    parts = line.split()
                    if len(parts) < 13:
                        continue
                    name = parts[0]
                    x = float(parts[1])
                    y = float(parts[2])
                    flip_str = parts[3]
                    flip = flip_str == "F"
                    width = float(parts[4])
                    height = float(parts[5])
                    src_col = float(parts[6])
                    src_net = parts[7]
                    drn_col = float(parts[8])
                    drn_net = parts[9]
                    gate_col = float(parts[10])
                    gate_net = parts[11]
                    if parts[12].lower() == "pmos":
                        model = Model.PMOS
                        pmos_transistors.append(
                            TransistorData(name, x, y, flip, width, height, src_col, src_net, drn_col, drn_net, gate_col, gate_net, model)
                        )
                    elif parts[12].lower() == "nmos":
                        model = Model.NMOS
                        nmos_transistors.append(
                            TransistorData(name, x, y, flip, width, height, src_col, src_net, drn_col, drn_net, gate_col, gate_net, model)
                        )

                elif section == "route":
                    # each line: M0 ROW0 COL0 NET => M1 ROW1 COL1 NET
                    m = re.match(r"(\d+)\s+([\d\.]+)\s+([\d\.]+)\s+(\S+)\s*=>\s*(\d+)\s+([\d\.]+)\s+([\d\.]+)\s+(\S+)", line)
                    if not m:
                        continue
                    m0, r0, c0, net0, m1, r1, c1, net1 = m.groups()
                    assert net0 == net1, f"Net mismatch in routing data, {net0} != {net1}"
                    # net0 and net1 should be identical
                    metals.append(
                        MetalData(metal_0=int(m0), metal_1=int(m1), row_0=float(r0), row_1=float(r1), col_0=float(c0), col_1=float(c1), net=net0)
                    )
                elif section == "cell":
                    pins = line.split()
                    tech_params["IO_PINS"] = pins

        # build TechData, converting types
        td = TechData(
            col=int(tech_params["COL"]),
            track=int(tech_params["TRACK"]),
            cp_pitch=float(tech_params["CPP"]),
            m0_pitch=float(tech_params["M0P"]),
            m1_pitch=float(tech_params["M1P"]),
            m2_pitch=float(tech_params["M2P"]),
            cp_width=float(tech_params["CP_WIDTH"]),
            m0_width=float(tech_params["M0_WIDTH"]),
            m1_width=float(tech_params["M1_WIDTH"]),
            m2_width=float(tech_params["M2_WIDTH"]),
            active_gap=float(tech_params["ACTIVE_GAP"]),
            power_rail_thickness=float(tech_params["PWR_RAIL_THICKNESS"]),
            power_config=tech_params["PWR_CONFIG"],
            io_pins=tech_params["IO_PINS"]
        )

        return td, pmos_transistors, nmos_transistors, metals

    def draw(self):
        """
        Layer naming convention:
        <layer_number>/<layer_type>
        layer_number: 0-255
        layer_type: 0-255
            - 0         :   DR layer
            - 251       :   Text layer
            - 1-199     :   Auxiliary layer
            - 200-250   :   Auxiliary text layer
        """
        # Layout and cell are already created in __init__
        # Well layer (1/0)
        self.well_layer_idx = self.layout.layer(1, 0)
        self.well_text_layer_idx = self.layout.layer(1, 251)
        # Fin layer (2/0)
        self.fin_layer_idx = self.layout.layer(2, 0)
        # PSUB Text layer (3/251)
        self.psub_text_layer_idx = self.layout.layer(3, 251)
        # Gate layer (7/0)
        self.gate_layer_idx = self.layout.layer(7, 0)
        # Gate cut layer (10/0)
        self.gate_cut_layer_idx = self.layout.layer(10, 0)
        # Active layer (11/0)
        self.active_layer_idx = self.layout.layer(11, 0)
        self.p_active_layer_idx = self.layout.layer(11, 1)
        self.p_active_text_layer_idx = self.layout.layer(11, 201)
        self.n_active_layer_idx = self.layout.layer(11, 2)
        self.n_active_text_layer_idx = self.layout.layer(11, 202)
        # NSELECT layer (12/0)
        self.nselect_layer_idx = self.layout.layer(12, 0)
        # PSELECT layer (13/0)
        self.pselect_layer_idx = self.layout.layer(13, 0)
        # CA DR layer (14/0)
        self.CA_layer_idx = self.layout.layer(14, 0)
        # self.CA_text_layer_idx = self.layout.layer(14, 251)
        self.CA_SD_layer_idx = self.layout.layer(14, 1)
        self.CA_GB_layer_idx = self.layout.layer(14, 2)
        self.CA_debug_layer_idx = self.layout.layer(14, 50)
        self.CA_upper_debug_layer_idx = self.layout.layer(14, 51)
        self.CA_lower_debug_layer_idx = self.layout.layer(14, 51)
        self.CA_debug_text_layer_idx = self.layout.layer(14, 250)
        # M0 DR layer (15/0)
        self.M0_layer_idx = self.layout.layer(15, 0)
        self.M0_text_layer_idx = self.layout.layer(15, 251)
        self.M0_debug_layer_idx = self.layout.layer(15, 50)
        self.M0_debug_text_layer_idx = self.layout.layer(15, 250)
        # LIG layer (16/0)
        self.lig_layer_idx = self.layout.layer(16, 0)
        self.lig_text_layer_idx = self.layout.layer(16, 251)
        self.lig_debug_layer_idx = self.layout.layer(16, 50)
        self.lig_debug_text_layer_idx = self.layout.layer(16, 250)
        # LISD layer (17/0)
        self.LISD_layer_idx = self.layout.layer(17, 0)
        self.LISD_text_layer_idx = self.layout.layer(17, 251)
        self.LISD_debug_layer_idx = self.layout.layer(17, 50)
        self.LISD_debug_text_layer_idx = self.layout.layer(17, 250)
        # V0 layer (18/0)
        self.V0_layer_idx = self.layout.layer(18, 0)
        self.V0_text_layer_idx = self.layout.layer(18, 251)
        self.V0_debug_layer_idx = self.layout.layer(18, 50)
        self.V0_debug_text_layer_idx = self.layout.layer(18, 250)
        # M1 DR layer (19/0)
        self.M1_layer_idx = self.layout.layer(19, 0)
        self.M1_text_layer_idx = self.layout.layer(19, 251)
        self.M1_debug_layer_idx = self.layout.layer(19, 50)
        self.M1_debug_text_layer_idx = self.layout.layer(19, 250)
        # V1 layer (21/0)
        self.V1_layer_idx = self.layout.layer(21, 0)
        self.V1_text_layer_idx = self.layout.layer(21, 251)
        self.V1_debug_layer_idx = self.layout.layer(21, 50)
        self.V1_debug_text_layer_idx = self.layout.layer(21, 250)
        # M2 DR layer (20/0)
        self.M2_layer_idx = self.layout.layer(20, 0)
        self.M2_text_layer_idx = self.layout.layer(20, 251)
        self.M2_debug_layer_idx = self.layout.layer(20, 50)
        self.M2_debug_text_layer_idx = self.layout.layer(20, 250)
        # SDT layer (88/0)
        self.SDT_layer_idx = self.layout.layer(88, 0)
        self.SDT_text_layer_idx = self.layout.layer(88, 251)
        self.SDT_debug_layer_idx = self.layout.layer(88, 50)
        # Boundary layer (100/0)
        self.boundary_layer_idx = self.layout.layer(100, 0)
        # Draw guidelines
        # self.draw_guidelines()
        # Draw the power rail
        self.draw_power_rail()
        # Draw the gate
        # self.draw_gate()

        self.draw_boundary()
        self.draw_auxiliary_layers()
        self.draw_gate()
        self.draw_fin()
        self.draw_actives()
        self.draw_routes()

    def save(self, filename):
        self.layout.write(filename)

    def draw_boundary(self):
        """
        Draw the boundary of the layout
        """
        # create a box for the boundary
        boundary_box = Box(0, 0, self.width, self.height).pyabox_obj()
        self.cell.shapes(self.boundary_layer_idx).insert(boundary_box)

    def draw_auxiliary_layers(self):
        """
        Draw the auxiliary layers
        """
        # Well layer
        self.__well__()
        # PSELECT layer
        self.__pselect__()
        # NSELECT layer
        self.__nselect__()
        # Gate cut layer
        self.__gate_cut_boundary__(num_gate=self.tech_data.col)

    def draw_gate(self):
        self.__gate__(self.tech_data.col)
        self.__gate_cut__()

    def draw_fin(self):
        self.__fin__()

    def draw_power_rail(self):
        if self.tech_data.power_config == "M0BPR":
            self.__m0_bpr__()
            self.__ca_on_m0_bpr__()
            self.__lig_on_m0_bpr__()
        else:
            raise ValueError(f"Power rail configuration {self.tech_data.power_config} not supported.")

    def draw_actives(self):
        for i, (ptran, ntran) in enumerate(zip(self.pmos_transistor_data, self.nmos_transistor_data)):
            assert ptran.x == ntran.x, f"PMOS and NMOS transistors must have the same x coordinate, but got PMOS: {ptran.x}, NMOS: {ntran.x}"
            # Draw PMOS
            self.__pmos__(ptran)
            # Draw NMOS
            self.__nmos__(ntran)
            if self._is_left_lisd_merged(ptran, ntran):
                # If left LISD is merged, draw LISD on the left side
                self._lisd_merged(ptran.x)
            else:
                # If left LISD is not merged, draw LISD separately
                self.__lisd_pmos__(transistor=ptran, col=ptran.x, is_power=self._is_lisd_power_at_col(ptran, col=ptran.x))
                self.__lisd_nmos__(transistor=ntran, col=ntran.x, is_power=self._is_lisd_power_at_col(ntran, col=ntran.x))

            if self._is_right_lisd_merged(ptran, ntran):
                # If right LISD is merged, draw LISD on the right side
                self._lisd_merged(col=ptran.x + ptran.width)
            else:
                # If right LISD is not merged, draw LISD separately
                self.__lisd_pmos__(transistor=ptran, col=ptran.x + ptran.width, is_power=self._is_lisd_power_at_col(ptran, col=ptran.x + ptran.width))
                self.__lisd_nmos__(transistor=ntran, col=ntran.x + ntran.width, is_power=self._is_lisd_power_at_col(ntran, col=ntran.x + ntran.width))

    def draw_routes(self):
        """
        Draw the routes
        """
        # Draw CA layer
        for metal in self.metal_data:
            assert metal.metal_0 <= metal.metal_1, f"Metal layer {metal.metal_0} cannot be greater than {metal.metal_1}"
            if metal.metal_0 == 0 and metal.metal_1 == 0:  # PC layer (ignore)
                pass
            elif metal.metal_0 == 0 and metal.metal_1 == 1:  # CA layer
                # print(f"Drawing CA layer for metal: {metal}")
                self.__ca__(metal)
                # draw lig or cb
                if self._is_on_poly(metal):
                    self.__lig__(metal)
            elif metal.metal_0 == 1 and metal.metal_1 == 1:  # M0 layer
                self.__m0__(metal)
            elif metal.metal_0 == 1 and metal.metal_1 == 2:  # V0 layer
                self.__v0__(metal)
            elif metal.metal_0 == 2 and metal.metal_1 == 2:  # M1 layer
                self.__m1__(metal, debug=False)
            elif metal.metal_0 == 2 and metal.metal_1 == 3:  # V1 layer
                self.__v1__(metal)
            elif metal.metal_0 == 3 and metal.metal_1 == 3:  # M2 layer
                self.__m2__(metal, debug=False)
            else:
                raise ValueError(f"Unsupported metal layer combination: {metal.metal_0}, {metal.metal_1}")

    def __ca__(self, metal: MetalData, debug: bool = False):
        """
        Draw the CA layer
        """
        # CA layer
        lx = metal.col_0 / SOLVER_RESCALE + self.ca_x_offset
        ly = metal.row_0 / SOLVER_RESCALE + self.ca_y_offset
        ux = metal.col_1 / SOLVER_RESCALE + self.ca_x_offset + self.ca_width
        uy = metal.row_1 / SOLVER_RESCALE + self.ca_y_offset + self.ca_height
        box = Box(lx, ly, ux, uy).pyabox_obj()
        self.cell.shapes(self.CA_layer_idx).insert(box)
        # CA text layer
        ca_text = TextShape(metal.net, (lx + ux) / 2, (ly + uy) / 2).pyatext_obj()
        self.cell.shapes(self.CA_layer_idx).insert(ca_text) if debug else None

    def __lig__(self, metal: MetalData, debug: bool = False):
        """
        Draw the LIG layer
        """
        lx = metal.col_0 / SOLVER_RESCALE + self.ca_x_offset
        ly = metal.row_0 / SOLVER_RESCALE + self.ca_y_offset
        ux = metal.col_1 / SOLVER_RESCALE + self.ca_x_offset + self.lig_width
        uy = metal.row_1 / SOLVER_RESCALE + self.ca_y_offset + self.lig_height
        box = Box(lx, ly, ux, uy).pyabox_obj()
        # LIG layer
        self.cell.shapes(self.lig_layer_idx).insert(box)

    def _is_on_poly(self, metal: MetalData) -> bool:
        """
        Check if the metal is on the poly layer
        """
        return (metal.col_0 // self.tech_data.cp_pitch) % 2 == 0 and (metal.col_1 // self.tech_data.cp_pitch) % 2 == 0

    def __v0__(self, metal: MetalData, debug: bool = False):
        """
        Draw the V0 layer
        """
        # V0 layer
        lx = metal.col_0 / SOLVER_RESCALE + self.v0_x_offset
        ly = metal.row_0 / SOLVER_RESCALE + self.v0_y_offset
        ux = metal.col_1 / SOLVER_RESCALE + self.v0_x_offset + self.v0_width
        uy = metal.row_1 / SOLVER_RESCALE + self.v0_y_offset + self.v0_height
        box = Box(lx, ly, ux, uy).pyabox_obj()
        self.cell.shapes(self.V0_layer_idx).insert(box)
        # V0 text layer
        v0_text = TextShape(metal.net, (lx + ux) / 2, (ly + uy) / 2).pyatext_obj()
        self.cell.shapes(self.V0_text_layer_idx).insert(v0_text) if debug else None

    def __v1__(self, metal: MetalData, debug: bool = False):
        """
        Draw the V1 layer
        """
        # V1 layer
        lx = metal.col_0 / SOLVER_RESCALE + self.v1_x_offset
        ly = metal.row_0 / SOLVER_RESCALE + self.v1_y_offset
        ux = metal.col_1 / SOLVER_RESCALE + self.v1_x_offset + self.v1_width
        uy = metal.row_1 / SOLVER_RESCALE + self.v1_y_offset + self.v1_height
        box = Box(lx, ly, ux, uy).pyabox_obj()
        self.cell.shapes(self.V1_layer_idx).insert(box)
        # V1 text layer
        v1_text = TextShape(metal.net, (lx + ux) / 2, (ly + uy) / 2).pyatext_obj()
        self.cell.shapes(self.V1_text_layer_idx).insert(v1_text) if debug else None

    def __m0__(self, metal: MetalData, debug: bool = False):
        """
        Draw the M0 layer
        """
        # M0 layer is drawn on M0 layer
        # M0 layer
        lx = metal.col_0 / SOLVER_RESCALE + self.m0_x_offset - self.m0_h_ovl
        ly = metal.row_0 / SOLVER_RESCALE + self.m0_y_offset - self.m0_v_ovl
        ux = metal.col_1 / SOLVER_RESCALE + self.m0_x_offset + self.ca_width + self.m0_h_ovl  # use lower via to extend
        uy = metal.row_1 / SOLVER_RESCALE + self.m0_y_offset + self.tech_data.m0_width + self.m0_v_ovl
        box = Box(lx, ly, ux, uy).pyabox_obj()
        self.cell.shapes(self.M0_layer_idx).insert(box)
        # M0 text layer
        m0_text = TextShape(metal.net, (lx + ux) / 2, (ly + uy) / 2).pyatext_obj()
        self.cell.shapes(self.M0_text_layer_idx).insert(m0_text) if debug else None

    def __m1__(self, metal: MetalData, debug: bool = False):
        """
        Draw the M1 layer
        """
        # M1 layer is drawn on M1 layer
        # M1 layer
        lx = metal.col_0 / SOLVER_RESCALE + self.m1_x_offset - self.m1_h_ovl
        ly = metal.row_0 / SOLVER_RESCALE + self.m1_y_offset - self.m1_v_ovl
        ux = metal.col_1 / SOLVER_RESCALE + self.m1_x_offset + self.tech_data.m1_width + self.m1_h_ovl
        uy = metal.row_1 / SOLVER_RESCALE + self.m1_y_offset + self.v0_height + self.m1_v_ovl  # use lower via to extend
        box = Box(lx, ly, ux, uy).pyabox_obj()
        self.cell.shapes(self.M1_layer_idx).insert(box)
        # M1 text layer
        m1_text = TextShape(metal.net, (lx + ux) / 2, (ly + uy) / 2).pyatext_obj()
        if metal.net in self.tech_data.io_pins or debug:
            self.cell.shapes(self.M1_text_layer_idx).insert(m1_text)

    def __m2__(self, metal: MetalData, debug: bool = False):
        """
        Draw the M2 layer
        """
        # M2 layer is drawn on M2 layer
        # M2 layer
        lx = metal.col_0 / SOLVER_RESCALE + self.m2_x_offset - self.m2_h_ovl
        ly = metal.row_0 / SOLVER_RESCALE + self.m2_y_offset - self.m2_v_ovl
        ux = metal.col_1 / SOLVER_RESCALE + self.m2_x_offset + self.v1_width + self.m2_h_ovl  # use lower via to extend
        uy = metal.row_1 / SOLVER_RESCALE + self.m2_y_offset + self.tech_data.m2_width + self.m2_v_ovl
        box = Box(lx, ly, ux, uy).pyabox_obj()
        self.cell.shapes(self.M2_layer_idx).insert(box)
        # M2 text layer
        m2_text = TextShape(metal.net, (lx + ux) / 2, (ly + uy) / 2).pyatext_obj()
        if metal.net in self.tech_data.io_pins or debug:
            self.cell.shapes(self.M2_text_layer_idx).insert(m2_text)

    def __well__(self):
        """
        Draw the well
        """
        lx = 0
        ly = self.height / 2
        ux = self.width
        uy = self.height
        well_box = Box(lx, ly, ux, uy).pyabox_obj()
        self.cell.shapes(self.well_layer_idx).insert(well_box)
        well_text = TextShape("VDD", self.width / 2, self.height).pyatext_obj()
        self.cell.shapes(self.well_text_layer_idx).insert(well_text)
        psub_text = TextShape("VSS", self.width / 2, 0).pyatext_obj()
        self.cell.shapes(self.psub_text_layer_idx).insert(psub_text)

    def __pselect__(self):
        """
        Draw the PSELECT layer
        """
        lx = 0
        ly = self.height / 2
        ux = self.width
        uy = self.height
        pselect_box = Box(lx, ly, ux, uy).pyabox_obj()
        self.cell.shapes(self.pselect_layer_idx).insert(pselect_box)

    def __nselect__(self):
        """
        Draw the NSELECT layer
        """
        lx = 0
        ly = 0
        ux = self.width
        uy = self.height / 2
        nselect_box = Box(lx, ly, ux, uy).pyabox_obj()
        self.cell.shapes(self.nselect_layer_idx).insert(nselect_box)
        
    def __gate_cut_boundary__(self, num_gate):
        """
        Draw the gate cut layer
        """
        # bottom power rail
        lx_1 = 0
        ly_1 = -self.gate_cut_boundary_height / 2
        ux_1 = self.tech_data.cp_pitch * self.tech_data.col
        uy_1 = 0.5 * self.gate_cut_boundary_height
        box = Box(lx_1, ly_1, ux_1, uy_1).pyabox_obj()
        self.cell.shapes(self.gate_cut_layer_idx).insert(box)
        # upper power rail
        lx_2 = 0
        ly_2 = ly_1 + self.tech_data.m0_pitch * (self.tech_data.track + 2)
        ux_2 = ux_1
        uy_2 = ly_2 + self.gate_cut_boundary_height
        box = Box(lx_2, ly_2, ux_2, uy_2).pyabox_obj()
        self.cell.shapes(self.gate_cut_layer_idx).insert(box)
        # leftmost gate cut
        prev_lx = -self.tech_data.cp_width / SOLVER_RESCALE
        prev_ly = self.height / 2 - self.poly_height / 2
        prev_ux = prev_lx + self.tech_data.cp_width
        prev_uy = prev_ly + self.poly_height
        box = Box(prev_lx, prev_ly, prev_ux, prev_uy).pyabox_obj()
        self.cell.shapes(self.gate_cut_layer_idx).insert(box)
        # rightmost gate cut
        last_lx = self.tech_data.cp_pitch * self.tech_data.col - self.tech_data.cp_width / SOLVER_RESCALE
        last_ly = self.height / 2 - self.poly_height / 2
        last_ux = last_lx + self.tech_data.cp_width
        last_uy = last_ly + self.poly_height
        box = Box(last_lx, last_ly, last_ux, last_uy).pyabox_obj()
        self.cell.shapes(self.gate_cut_layer_idx).insert(box)

    def _lisd_merged(self, col):
        # LISD is drawn on M0 layer
        # LISD is drawn on the bottom of the transistor
        lx = self.lisd_x_offset + col / SOLVER_RESCALE
        ly = self.lisd_y_offset
        width = self.lisd_width
        height = self.lisd_signal_height * 2 + self.lisd_signal_gap
        box = Box2(lx, ly, width, height).pyabox_obj()
        self.cell.shapes(self.LISD_layer_idx).insert(box)
        self.cell.shapes(self.SDT_layer_idx).insert(box)

    def __pmos__(self, transistor):
        lx = self.active_x_offset + transistor.x / SOLVER_RESCALE
        ly = transistor.y / ((self.tech_data.m0_pitch * SOLVER_RESCALE) * 2) * self.active_height + self.active_y_offset + self.tech_data.active_gap
        width = transistor.width / SOLVER_RESCALE + self.active_x_overlap
        height = transistor.height / (self.tech_data.m0_pitch * SOLVER_RESCALE) * self.active_height
        box = Box2(lx, ly, width, height).pyabox_obj()
        self.cell.shapes(self.active_layer_idx).insert(box)

    def __nmos__(self, transistor):
        lx = self.active_x_offset + transistor.x / SOLVER_RESCALE
        ly = transistor.y / (self.tech_data.m0_pitch * SOLVER_RESCALE) * self.active_height + self.active_y_offset
        width = transistor.width / SOLVER_RESCALE + self.active_x_overlap
        height = transistor.height / (self.tech_data.m0_pitch * SOLVER_RESCALE) * self.active_height
        box = Box2(lx, ly, width, height).pyabox_obj()
        self.cell.shapes(self.active_layer_idx).insert(box)

    def __lisd_pmos__(self, col, transistor, is_power=False):
        """
        Draw the LISD (Local Interconnect Source/Drain) layer
        """
        # LISD is drawn on M0 layer
        # LISD is drawn on the bottom of the transistor
        lx = self.lisd_x_offset + col / SOLVER_RESCALE

        if is_power:
            ly = self.lisd_y_offset + transistor.y / ((self.tech_data.m0_pitch * SOLVER_RESCALE) * 2) * self.lisd_signal_height + self.lisd_power_gap
            height = self.lisd_power_height
        else:
            ly = self.lisd_y_offset + transistor.y / ((self.tech_data.m0_pitch * SOLVER_RESCALE) * 2) * self.lisd_signal_height + self.lisd_signal_gap
            height = self.lisd_signal_height

        width = self.lisd_width
        box = Box2(lx, ly, width, height).pyabox_obj()
        self.cell.shapes(self.LISD_layer_idx).insert(box)

        # Draw SDT layer
        lx = self.lisd_x_offset + col / SOLVER_RESCALE
        ly = self.sdt_y_offset + transistor.y / ((self.tech_data.m0_pitch * SOLVER_RESCALE) * 2) * self.sdt_height + self.sdt_gap
        ux = lx + self.lisd_width
        uy = ly + self.sdt_height
        box = Box(lx, ly, ux, uy).pyabox_obj()
        self.cell.shapes(self.SDT_layer_idx).insert(box)

    def __lisd_nmos__(self, col, transistor, is_power=False):
        """
        Draw the LISD (Local Interconnect Source/Drain) layer
        """
        # LISD is drawn on M0 layer
        # LISD is drawn on the bottom of the transistor
        lx = self.lisd_x_offset + col / SOLVER_RESCALE

        if is_power:
            ly = transistor.y / ((self.tech_data.m0_pitch * SOLVER_RESCALE) * 2) * self.lisd_signal_height
            height = self.lisd_power_height
        else:
            ly = self.lisd_y_offset + transistor.y / ((self.tech_data.m0_pitch * SOLVER_RESCALE) * 2) * self.lisd_signal_height
            height = self.lisd_signal_height

        width = self.lisd_width
        box = Box2(lx, ly, width, height).pyabox_obj()
        self.cell.shapes(self.LISD_layer_idx).insert(box)

        # Draw SDT layer
        lx = self.lisd_x_offset + col / SOLVER_RESCALE
        ly = self.sdt_y_offset + transistor.y / ((self.tech_data.m0_pitch * SOLVER_RESCALE) * 2) * self.sdt_height
        ux = lx + self.lisd_width
        uy = ly + self.sdt_height
        box = Box(lx, ly, ux, uy).pyabox_obj()
        self.cell.shapes(self.SDT_layer_idx).insert(box)
        
    def __gate_cut__(self):
        """
        Cut the gate if signal is not present
        """
        # Collect all cut boxes first
        cut_boxes = []
        
        for i, (ptran, ntran) in enumerate(zip(self.pmos_transistor_data, self.nmos_transistor_data)):
            assert ptran.x == ntran.x, f"PMOS and NMOS transistors must have the same x coordinate, but got PMOS: {ptran.x}, NMOS: {ntran.x}"
            if ptran.gate_net == ntran.gate_net:
                continue  # skip if gate net is the same for both transistors
            # create a box for the gate cut
            lx = ptran.x / SOLVER_RESCALE - self.tech_data.cp_width / SOLVER_RESCALE + self.tech_data.cp_pitch / 2
            ly = self.height / 2 - self.gate_cut_height / 2
            ux = lx + self.tech_data.cp_width
            uy = self.height / 2 + self.gate_cut_height / 2
            cut_box = Box(lx, ly, ux, uy).pyabox_obj()
            cut_boxes.append(cut_box)
        
        # If there are any cuts to make
        if cut_boxes:
            # Create gate region from the shapes layer directly
            gate_shapes = self.cell.shapes(self.gate_layer_idx)
            gate_region = pya.Region(gate_shapes)
            
            # Create a combined cut region from all cut boxes
            cut_region = pya.Region()
            for cut_box in cut_boxes:
                cut_region.insert(cut_box)
            
            # Perform the subtraction using the correct method
            result_region = gate_region - cut_region
            
            # Clear the existing shapes in the gate layer and insert the modified region
            self.cell.shapes(self.gate_layer_idx).clear()
            self.cell.shapes(self.gate_layer_idx).insert(result_region)
            self.cell.shapes(self.gate_cut_layer_idx).insert(cut_region)

    def __gate__(self, num_gate):
        """
        Draw the gate
        """
        # prev_lx = -self.fin_tech.gate_width / 2
        prev_lx = -self.tech_data.cp_width / SOLVER_RESCALE
        # prev_ly = self.center_y - self.fin_tech.gate_height / 2
        prev_ly = self.height / 2 - self.poly_height / 2
        # prev_ux = prev_lx + self.fin_tech.gate_width
        prev_ux = prev_lx + self.tech_data.cp_width
        # prev_uy = prev_ly + self.fin_tech.gate_height
        prev_uy = prev_ly + self.poly_height
        box = Box(prev_lx, prev_ly, prev_ux, prev_uy).pyabox_obj()
        self.cell.shapes(self.gate_layer_idx).insert(box)

        for g_i in range(num_gate):
            lx = prev_lx + self.tech_data.cp_pitch
            ly = prev_ly
            ux = lx + self.tech_data.cp_width
            uy = prev_uy
            box = Box(lx, ly, ux, uy).pyabox_obj()
            self.cell.shapes(self.gate_layer_idx).insert(box)
            prev_lx = lx
            prev_ly = ly
            prev_ux = ux
            prev_uy = uy

    def __fin__(self):
        """
        Draw the fin
        """
        curr_y = self.fin_y_offset
        fin_count = 0
        while True:
            # calculate the fin position
            lx = 0
            ly = curr_y
            ux = self.width
            uy = curr_y + self.fin_width
            box = Box(lx, ly, ux, uy).pyabox_obj()
            self.cell.shapes(self.fin_layer_idx).insert(box)
            curr_y += self.fin_pitch + self.fin_width
            fin_count += 1
            if curr_y + self.fin_width > self.height:
                break
        absl_logging.info(f"Total fins drawn: {fin_count}, Fin pitch: {self.fin_pitch}, Fin width: {self.fin_width}")

    def __m0_bpr__(self):
        """
        Draw the M0 backside power supply rail
        """
        # bottom power rail
        lx_1 = 0
        ly_1 = -self.tech_data.power_rail_thickness / 2
        ux_1 = self.tech_data.cp_pitch * self.tech_data.col
        uy_1 = 0.5 * self.tech_data.power_rail_thickness
        box = Box(lx_1, ly_1, ux_1, uy_1).pyabox_obj()
        cx, cy = (lx_1 + ux_1) / 2, (ly_1 + uy_1) / 2
        self.cell.shapes(self.M0_layer_idx).insert(box)
        vdd_text = TextShape("VSS", cx, cy).pyatext_obj()
        self.cell.shapes(self.M0_text_layer_idx).insert(vdd_text)
        # upper power rail
        lx_2 = 0
        ly_2 = ly_1 + self.tech_data.m0_pitch * (self.tech_data.track + 2)
        ux_2 = ux_1
        uy_2 = ly_2 + self.tech_data.power_rail_thickness
        box = Box(lx_2, ly_2, ux_2, uy_2).pyabox_obj()
        self.cell.shapes(self.M0_layer_idx).insert(box)
        cx, cy = (lx_2 + ux_2) / 2, (ly_2 + uy_2) / 2
        vss_text = TextShape("VDD", cx, cy).pyatext_obj()
        self.cell.shapes(self.M0_text_layer_idx).insert(vss_text)

    def __lig_on_m0_bpr__(self):
        # bottom lig on power rail
        lx_1 = 0
        ly_1 = -self.lig_height / 2
        ux_1 = self.tech_data.cp_pitch * self.tech_data.col
        uy_1 = 0.5 * self.lig_height
        box = Box(lx_1, ly_1, ux_1, uy_1).pyabox_obj()
        self.cell.shapes(self.lig_layer_idx).insert(box)
        # upper lig on power rail
        lx_2 = 0
        ly_2 = ly_1 + self.tech_data.m0_pitch * (self.tech_data.track + 2)
        ux_2 = ux_1
        uy_2 = ly_2 + self.lig_height
        box = Box(lx_2, ly_2, ux_2, uy_2).pyabox_obj()
        self.cell.shapes(self.lig_layer_idx).insert(box)

    def __ca_on_m0_bpr__(self):
        """
        Draw CA contacts on M0 backside power rail across the full width
        """
        # Calculate spacing between CA contacts based on cp_pitch
        ca_spacing = self.tech_data.cp_pitch

        # Calculate number of CA contacts that fit across the width
        num_ca_contacts = int(self.width / ca_spacing) + 1

        for i in range(num_ca_contacts):
            x_position = i * ca_spacing

            # Skip if we exceed the width
            if x_position > self.width:
                break

            # Bottom CA on power rail
            lx_1 = x_position - self.ca_width / 2
            ly_1 = -self.ca_height / 2
            ux_1 = lx_1 + self.ca_width
            uy_1 = 0.5 * self.ca_height
            box = Box(lx_1, ly_1, ux_1, uy_1).pyabox_obj()
            self.cell.shapes(self.CA_layer_idx).insert(box)

            # Upper CA on power rail
            lx_2 = x_position - self.ca_width / 2
            ly_2 = ly_1 + self.tech_data.m0_pitch * (self.tech_data.track + 2)
            ux_2 = lx_2 + self.ca_width
            uy_2 = ly_2 + self.ca_height
            box = Box(lx_2, ly_2, ux_2, uy_2).pyabox_obj()
            self.cell.shapes(self.CA_layer_idx).insert(box)

    def _is_left_lisd_merged(self, tran_1, tran_2):
        """
        Check if the left LISD of two transistors are merged.
        This is used to determine if the LISD should be drawn on the left side of the transistor.
        """
        if tran_1.flip:
            tran_1_left_net = tran_1.drain_net
            # tran_1_right_net = tran_1.source_net
        else:
            tran_1_left_net = tran_1.source_net
            # tran_1_right_net = tran_1.drain_net
        if tran_2.flip:
            tran_2_left_net = tran_2.drain_net
            # tran_2_right_net = tran_2.source_net
        else:
            tran_2_left_net = tran_2.source_net
            # tran_2_right_net = tran_2.drain_net
        # check if the left net of tran_1 is the same as the right net of tran_2
        if tran_1_left_net == tran_2_left_net:
            return True
        return False

    def _is_right_lisd_merged(self, tran_1, tran_2):
        """
        Check if the right LISD of two transistors are merged.
        This is used to determine if the LISD should be drawn on the right side of the transistor.
        """
        if tran_1.flip:
            tran_1_right_net = tran_1.source_net
            # tran_1_left_net = tran_1.drain_net
        else:
            tran_1_right_net = tran_1.drain_net
            # tran_1_left_net = tran_1.source_net
        if tran_2.flip:
            tran_2_right_net = tran_2.source_net
            # tran_2_left_net = tran_2.drain_net
        else:
            tran_2_right_net = tran_2.drain_net
            # tran_2_left_net = tran_2.source_net
        # check if the right net of tran_1 is the same as the left net of tran_2
        if tran_1_right_net == tran_2_right_net:
            return True
        return False

    def _is_lisd_power_at_col(self, transistor, col):
        """
        Check if the LISD is a power rail at the given column.
        This is used to determine if the LISD should be drawn as a power rail.
        """
        # This will never happen, as I do not set the column of power rail
        if transistor.source_col == col:
            if transistor.source_net.startswith("VDD") or transistor.source_net.startswith("VSS"):
                return True
        if transistor.drain_col == col:
            if transistor.drain_net.startswith("VDD") or transistor.drain_net.startswith("VSS"):
                return True
        # If the transistor is not at the given column, check if it is a power rail
        if transistor.source_col != col:
            if transistor.drain_net == "VDD" and transistor.drain_col == -1:
                return True
            if transistor.drain_net == "VSS" and transistor.drain_col == -1:
                return True
        if transistor.drain_col != col:
            if transistor.source_net == "VDD" and transistor.source_col == -1:
                return True
            if transistor.source_net == "VSS" and transistor.source_col == -1:
                return True
        return False


if __name__ == "__main__":
    # Example usage
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--result_file",
        type=str,
        help="Path to the result file.",
    )
    parser.add_argument(
        "--subckt_name",
        type=str,
        help="Subcircuit name to extract.",
    )
    parser.add_argument(
        "--gds_file",
        type=str,
        help="Path to the GDS file.",
    )
    args = parser.parse_args()
    fflayout = FinFETLayout(
        result_file=args.result_file,
        subckt_name=args.subckt_name,
        gds_file=args.gds_file,
    )
    # print("Technology:")
    # print(fflayout.tech_data)
    # print("Transistors:")
    # for transistor in fflayout.transistor_data:
    #     print(transistor)
    # print("\nMetals:")
    # for metal in fflayout.metal_data:
    #     print(metal)
