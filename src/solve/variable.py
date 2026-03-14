import bisect
import re
from dataclasses import dataclass

@dataclass
class TechData:
    cpp: int


@dataclass
class TransistorData:
    tran_name: str
    x: int
    y: int
    z: int
    flip: bool
    lds: bool
    rds: bool


@dataclass
class PinData:
    tran_name: str
    pin_type: str
    tier: int
    layer_idx: int
    col: int
    row: int
    
@dataclass
class VertexData:
    layer_idx: int
    row: int
    col: int
    net_name: str

    def __lt__(self, other):
        # First sort by layer index
        if self.layer_idx != other.layer_idx:
            return self.layer_idx < other.layer_idx
        # When on the same layer, use different criteria:
        if self.layer_idx % 2 == 0:  # TODO: detect vertical layer
            # Even layer: sort by col first, then row
            if self.col != other.col:
                return self.col < other.col
            return self.row < other.row
        else:  # TODO: detect horizontal layer
            # Odd layer: sort by row first, then col
            if self.row != other.row:
                return self.row < other.row
            return self.col < other.col

    def __eq__(self, other):
        if not isinstance(other, VertexData):
            return NotImplemented
        # Two vertices are equal if they are on the same layer and their sort keys match.
        if self.layer_idx != other.layer_idx:
            return False
        if self.layer_idx % 2 == 0:
            return (self.col, self.row) == (other.col, other.row)
        else:
            return (self.row, self.col) == (other.row, other.col)


@dataclass
class MetalData:
    layer_idx: int
    l_row: int
    l_col: int
    u_row: int
    u_col: int
    net_name: str


@dataclass  # TODO: finish this
class IOPinData:
    pass


class TransistorVar:
    """
    Transistor variable class to hold the placement information.
    """

    def __init__(self, name, transistor=None):
        self.name = name
        self.x_var = None
        self.y_var = None
        self.site_var = None  # site (for multi-height)
        self.z_var = None  # tier
        self.lds_var = None
        self.rds_var = None
        self.w_col_idx = None
        self.h_col_idx = None
        self.flip_var = None  # flip condition
        self.s_col_idx_var = {}  # source
        self.d_col_idx_var = {}  # drain
        self.g_col_idx_var = {}  # gate
        
        # holds real x coordinate of source, drain, gate
        self.s_x_var = None
        self.d_x_var = None
        self.g_x_var = None
        # store the result
        self.data = None
        self.s_data = None
        self.d_data = None
        self.g_data = None

    def read_col_idx_var(self, col_idx_var):
        """
        Read the result from the column index variable.
        (Tier, Layer, Row, Column, Net)
        """
        pass

    def add_source_col_idx_var(self, s_col_idx_var):
        """
        Add source column index variable.
        check if the variable is already in the list.
        """
        if s_col_idx_var not in self.s_col_idx_var:
            self.s_col_idx_var.append(s_col_idx_var)

    def add_drain_col_idx_var(self, d_col_idx_var):
        """
        Add drain column index variable.
        check if the variable is already in the list.
        """
        if d_col_idx_var not in self.d_col_idx_var:
            self.d_col_idx_var.append(d_col_idx_var)

    def add_gate_col_idx_var(self, g_col_idx_var):
        """
        Add gate column index variable.
        check if the variable is already in the list.
        """
        if g_col_idx_var not in self.g_col_idx_var:
            self.g_col_idx_var.append(g_col_idx_var)

    def get_gate_col_idx_var_by_col(self, col):
        """
        Get the gate column index variable.
        """
        tier_layer_row_col_pattern = re.compile(r"T(\d+)L(\d+)R(\d+)C(\d+)")
        tmp_g_col_idx_var = []
        for var in self.g_col_idx_var:
            # absl_logging.info(f"var: {var}")
            match = tier_layer_row_col_pattern.match(var.decl().name())
            if match is None:
                continue
            tmp_col = int(match.group(4))
            if col == tmp_col:
                tmp_g_col_idx_var.append(var)
        return tmp_g_col_idx_var

    def get_gate_col_idx_var_by_row_col(self, col, row):
        """
        Get the gate column index variable.
        """
        tier_layer_row_col_pattern = re.compile(r"T(\d+)L(\d+)R(\d+)C(\d+)")
        tmp_g_col_idx_var = []
        for var in self.g_col_idx_var:
            # absl_logging.info(f"var: {var}")
            match = tier_layer_row_col_pattern.match(var.decl().name())
            if match is None:
                continue
            tmp_row = int(match.group(3))
            tmp_col = int(match.group(4))
            if col == tmp_col and row == tmp_row:
                tmp_g_col_idx_var.append(var)
        assert (
            len(tmp_g_col_idx_var) == 1
        ), f"Multiple gate column index variables found for col {col} and row {row}: {tmp_g_col_idx_var}"
        return tmp_g_col_idx_var[0]

    def get_source_col_idx_var_by_col(self, col):
        """
        Get the source column index variable.
        """
        tier_layer_row_col_pattern = re.compile(r"T(\d+)L(\d+)R(\d+)C(\d+)")
        tmp_s_col_idx_var = []
        for var in self.s_col_idx_var:
            match = tier_layer_row_col_pattern.match(var.decl().name())
            if match is None:
                continue
            tmp_col = int(match.group(4))
            if col == tmp_col:
                tmp_s_col_idx_var.append(var)
        return tmp_s_col_idx_var

    def get_source_col_idx_var_by_row_col(self, col, row):
        """
        Get the source column index variable.
        """
        tier_layer_row_col_pattern = re.compile(r"T(\d+)L(\d+)R(\d+)C(\d+)")
        tmp_s_col_idx_var = []
        for var in self.s_col_idx_var:
            match = tier_layer_row_col_pattern.match(var.decl().name())
            if match is None:
                continue
            tmp_row = int(match.group(3))
            tmp_col = int(match.group(4))
            if col == tmp_col and row == tmp_row:
                tmp_s_col_idx_var.append(var)
        assert (
            len(tmp_s_col_idx_var) == 1
        ), f"Multiple source column index variables found for col {col} and row {row}: {tmp_s_col_idx_var}"
        return tmp_s_col_idx_var

    def get_drain_col_idx_var_by_col(self, col):
        """
        Get the drain column index variable.
        """
        tier_layer_row_col_pattern = re.compile(r"T(\d+)L(\d+)R(\d+)C(\d+)")
        tmp_d_col_idx_var = []
        for var in self.d_col_idx_var:
            match = tier_layer_row_col_pattern.match(var.decl().name())
            if match is None:
                continue
            tmp_col = int(match.group(4))
            if col == tmp_col:
                tmp_d_col_idx_var.append(var)
        return tmp_d_col_idx_var

    def get_drain_col_idx_var_by_row_col(self, col, row):
        """
        Get the drain column index variable.
        """
        tier_layer_row_col_pattern = re.compile(r"T(\d+)L(\d+)R(\d+)C(\d+)")
        tmp_d_col_idx_var = []
        for var in self.d_col_idx_var:
            match = tier_layer_row_col_pattern.match(var.decl().name())
            if match is None:
                continue
            tmp_row = int(match.group(3))
            tmp_col = int(match.group(4))
            if col == tmp_col and row == tmp_row:
                tmp_d_col_idx_var.append(var)
        assert (
            len(tmp_d_col_idx_var) == 1
        ), f"Multiple drain column index variables found for col {col} and row {row}: {tmp_d_col_idx_var}"
        return tmp_d_col_idx_var