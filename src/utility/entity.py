import logging
from absl import logging as absl_logging
import json
import networkx as nx
from typing import Union
from enum import Enum
import copy
# custom
import src.utility.config as config

# Set up logging to print messages
# Custom log format: [LEVEL] TIMESTAMP - MESSAGE
# NOTE: level available: DEBUG, INFO, WARNING, ERROR, CRITICAL
logging.basicConfig(format="[%(levelname)s] %(asctime)s - %(message)s", level=logging.INFO)


class Model(Enum):
    PMOS = "pmos"
    NMOS = "nmos"


class PinType(Enum):
    SOURCE = "source"
    DRAIN = "drain"
    GATE = "gate"
    BULK = "bulk"


# Define a Transistor class
class Transistor:
    """Transistor class to represent a transistor in a circuit."""

    # nfet l=0.002u m=1  nfin=1 par=1 p_la=0 nf=1 ngcon=1 plorient=0 cpp=4.2e-08 pre_layout_local=0 ptwell=0 wns=1.6e-08
    def __init__(
        self,
        name,
        source,
        gate,
        drain,
        bulk,
        model,
        w,
        l,
        nfin,
        m=None,
        par=None,
        p_la=None,
        nf=None,
        ngcon=None,
        plorient=None,
        cpp=None,
        pre_layout_local=None,
        ptwell=None,
        wns=None,
    ):
        self.name = name
        # Dictionary mapping terminal names to net names
        self.terminals = {"source": source, "gate": gate, "drain": drain, "bulk": bulk}
        self.source = source
        self.gate = gate
        self.drain = drain
        self.bulk = bulk
        assert "p" in model or "n" in model, absl_logging.error("Model must be contain 'p' or 'n'.")
        self.model = Model.PMOS if "p" in model else Model.NMOS
        self.w = w
        self.l = l
        self.nfin = nfin
        self.m = m if m is not None else None
        self.par = par if par is not None else None
        self.p_la = p_la if p_la is not None else None
        self.nf = nf if nf is not None else None
        self.ngcon = ngcon if ngcon is not None else None
        self.plorient = plorient if plorient is not None else None
        self.cpp = cpp if cpp is not None else None
        self.pre_layout_local = pre_layout_local if pre_layout_local is not None else None
        self.ptwell = ptwell if ptwell is not None else None
        self.wns = wns if wns is not None else None

    def get_width(self):
        # return the numerical value of the width
        return float(self.w[:-1])

    def __repr__(self):
        # return f"Transistor({self.name}, {self.terminals}, {self.model}, {self.w}, {self.l}, {self.nfin})"
        return f"Transistor({self.name}, {self.terminals}, {self.model}, w={self.w}, l={self.l}, nfin={self.nfin} m={self.m} par={self.par} p_la={self.p_la} nf={self.nf} ngcon={self.ngcon} plorient={self.plorient} cpp={self.cpp} pre_layout_local={self.pre_layout_local} ptwell={self.ptwell} wns={self.wns}"

    def __eq__(self, other):
        if isinstance(other, Transistor):
            return self.name == other.name
        return False

    # for sorting
    def __lt__(self, other):
        if isinstance(other, Transistor):
            return self.name < other.name
        return NotImplemented


class Net:
    """Net class to represent a net in a circuit."""

    def __init__(self, name, type_=None):
        self.name = name

        if type_ is not None:
            self.type = type_
        else:
            self.type = "internal"
        # List of tuples: (transistor instance, terminal pin_type)
        self.connected_transistors = []

    def is_io_net(self):
        """Check if the net is an input or output net."""
        return self.type == "io"

    def is_power_net(self):
        """Check if the net is a power net."""
        return self.type == "power"

    def is_ground_net(self):
        """Check if the net is a ground net."""
        return self.type == "ground"

    def is_power_or_ground_net(self):
        """Check if the net is a power or ground net."""
        return self.type in ["power", "ground"]
    
    def degree(self):
        """Net Degree"""
        return len(self.connected_transistors)

    def add_connection(self, transistor_name, pin_type):
        if pin_type == "bulk":
            # Bulk is not a terminal pin type
            return
        self.connected_transistors.append((transistor_name, pin_type))

    def get_source_transistor(self):
        """Assuming the first transistor is the source transistor."""
        return self.connected_transistors[0][0]

    def get_source_pin_type(self):
        """Assuming the first transistor is the source transistor."""
        return self.connected_transistors[0][1]

    def source(self):
        """Get the source transistor of the net."""
        return self.connected_transistors[0]

    def get_terminals(self):
        """Get the terminals of the net."""
        return [t for t in self.connected_transistors[1:]]

    def num_terminals(self):
        """Get the number of terminals of the net."""
        return len(self.connected_transistors) - 1

    def terminals(self):
        """Get the terminals of the net."""
        return [t for t in self.connected_transistors[1:]]

    def is_a_terminal_tran(self, transistor):
        """Check if the given transistor is a terminal transistor."""
        for i, (t, __) in enumerate(self.connected_transistors):
            if i == 0:  # Skip the source transistor
                continue
            # if the transistor is given as a string
            if type(transistor) == str:
                if t == transistor:
                    return True
            # if the transistor is given as a Transistor object
            elif type(transistor) == Transistor:
                if t == transistor.name:
                    return True
        return False

    def is_a_source_tran(self, transistor):
        """Check if the given transistor is a source transistor."""
        # if the transistor is given as a string
        if type(transistor) == str:
            if self.connected_transistors[0][0] == transistor:
                return True
        # if the transistor is given as a Transistor object
        elif type(transistor) == Transistor:
            if self.connected_transistors[0][0] == transistor.name:
                return True
        return False

    def __repr__(self):
        return f"Net({self.name})"


# Define a Circuit class to hold nets and transistors
class Circuit:
    """Circuit class to represent a circuit."""

    def __init__(self):
        # Dictionary of net_name -> Net instance
        self.nets = {}
        # Dictionary of transistor name -> Transistor instance
        self.transistors = {}
        # Optionally, store subckt info
        self.subckt_name = None
        # List of pins
        self.pins = []  # All pins
        self.io_pins = []  # Input and output pins
        self.pwr_pins = []  # Power pins
        self.gnd_pins = []  # Ground pins

    def num_transistors(self):
        return len(self.transistors)
    
    def num_pmos_transistors(self):
        pmos_transistors = [t for t in self.transistors.values() if t.model == Model.PMOS]
        return len(pmos_transistors)
    
    def num_nmos_transistors(self):
        nmos_transistors = [t for t in self.transistors.values() if t.model == Model.NMOS]
        return len(nmos_transistors)

    # MH FLAG
    def get_minimum_col(self, num_db=0, num_sites=1):
        """Get the minimum number of cols based on the number of transistors."""
        # Assuming cpp is the number of transistors in the circuit
        pmos_transistors = [t for t in self.transistors.values() if t.model == Model.PMOS]
        # NOTE: always multiply by 2 as we start and end on a gate column
        return 1 + (len(pmos_transistors) * 2) // num_sites + num_db * 2

    def assign_pins(self, pins):
        self.pins = pins
        self.pwr_pins = [pin for pin in pins if pin in config.PWR_NET_NAMES]
        self.gnd_pins = [pin for pin in pins if pin in config.GND_NET_NAMES]
        self.io_pins = [
            pin for pin in pins if pin not in config.PWR_NET_NAMES + config.GND_NET_NAMES
        ]
        assert len(self.pins) == len(self.io_pins) + len(self.pwr_pins) + len(
            self.gnd_pins
        ), absl_logging.error(
            f"Error in assigning pins. Total pins: {self.pins}, IO pins: {self.io_pins}, Power pins: {self.pwr_pins}, Ground pins: {self.gnd_pins}"
        )
        if len(self.pins) == 0:
            absl_logging.warning(f"No pins found in the circuit {self.subckt_name}.")
        if len(self.pwr_pins) == 0:
            absl_logging.warning(f"No power pins found in the circuit {self.subckt_name}.")
        if len(self.gnd_pins) == 0:
            absl_logging.warning(f"No ground pins found in the circuit {self.subckt_name}.")

    def add_net(self, net_name):
        if net_name not in self.nets:
            if net_name in self.io_pins:
                self.nets[net_name] = Net(net_name, type_="io")
            elif net_name in self.pwr_pins:
                self.nets[net_name] = Net(net_name, type_="power")
            elif net_name in self.gnd_pins:
                self.nets[net_name] = Net(net_name, type_="ground")
            else:
                self.nets[net_name] = Net(net_name, type_="internal")
        return self.nets[net_name]

    def get_net_names(self, with_power_ground=False):
        if with_power_ground:
            return list(self.nets.keys())
        else:
            return [
                net_name
                for net_name in self.nets.keys()
                if not net_name in config.PWR_NET_NAMES + config.GND_NET_NAMES
            ]

    def get_nets(self, with_power_ground=False):
        if with_power_ground:
            return list(self.nets.values())
        else:
            return [
                net
                for net in self.nets.values()
                if not net.name in config.PWR_NET_NAMES + config.GND_NET_NAMES
            ]

    def get_power_ground_nets(self):
        return [net for net in self.nets.values() if net.is_power_or_ground_net()]

    def get_power_net_name(self):
        return self.pwr_pins[0]

    def get_ground_net_name(self):
        return self.gnd_pins[0]

    def io_net_names(self):
        # print(f"IO pins: {self.io_pins}")
        return self.io_pins  # If just returning io_pins

    def get_gate_net_names(self):
        return set([t.terminals["gate"] for t in self.transistors.values()])

    def if_net_exists(self, net_name):
        return net_name in self.nets

    def if_transistor_exists(self, transistor_name):
        return transistor_name in self.transistors
    
    def group_transistors_by_nets_and_types(self):
        """
        Transistors belong to the same group if they have identify source/gate/drain nets. 
        By types => Must all be PMOS or all be NMOS
        In that case, there placement can be pre-determined
        """
        tmp_nets_to_transistor_groups = {}
        transistor_groups = []
        for i, tran_i in enumerate(self.transistors.values()):
            for tran_j in list(self.transistors.values())[i + 1 :]:
                FLAG_MATCH = True
                # match gate:
                if tran_i.gate != tran_j.gate:
                    FLAG_MATCH = False
                # match source has to match one of the source/drain
                if tran_i.source != tran_j.source and tran_i.source != tran_j.drain:
                    FLAG_MATCH = False
                # match drain has to match one of the source/drain
                if tran_i.drain != tran_j.source and tran_i.drain != tran_j.drain:
                    FLAG_MATCH = False
                net_keys = "_".join(sorted([tran_i.gate, tran_i.drain, tran_i.source]))
                # if match, try to group them by nets
                if FLAG_MATCH:
                    if net_keys not in tmp_nets_to_transistor_groups:
                        tmp_nets_to_transistor_groups[net_keys] = set()
                    tmp_nets_to_transistor_groups[net_keys].add(tran_i.name)
                    tmp_nets_to_transistor_groups[net_keys].add(tran_j.name)
        # transistor_groups = tmp_nets_to_transistor_groups.values()
        # return transistor_groups
        return tmp_nets_to_transistor_groups
    
    def group_transistors_by_nets(self):
        """
        Transistors belong to the same group if they have identify source/gate/drain nets. 
        In that case, there placement can be pre-determined
        """
        tmp_nmos_nets_to_transistor_groups = {}
        tmp_pmos_nets_to_transistor_groups = {}
        for i, tran_i in enumerate(self.transistors.values()):
            for tran_j in list(self.transistors.values())[i + 1 :]:
                # separate PMOS and NMOS
                if tran_i.model != tran_j.model:
                    continue
                FLAG_MATCH = True
                # match gate:
                if tran_i.gate != tran_j.gate:
                    FLAG_MATCH = False
                # match source has to match one of the source/drain
                if tran_i.source != tran_j.source and tran_i.source != tran_j.drain:
                    FLAG_MATCH = False
                # match drain has to match one of the source/drain
                if tran_i.drain != tran_j.source and tran_i.drain != tran_j.drain:
                    FLAG_MATCH = False
                net_keys = "_".join(sorted([tran_i.gate, tran_i.drain, tran_i.source]))
                # if match, try to group them by nets
                if FLAG_MATCH:
                    if tran_i.model == Model.NMOS:
                        if net_keys not in tmp_nmos_nets_to_transistor_groups:
                            tmp_nmos_nets_to_transistor_groups[net_keys] = set()
                        tmp_nmos_nets_to_transistor_groups[net_keys].add(tran_i.name)
                        tmp_nmos_nets_to_transistor_groups[net_keys].add(tran_j.name)
                    elif tran_i.model == Model.PMOS:
                        if net_keys not in tmp_pmos_nets_to_transistor_groups:
                            tmp_pmos_nets_to_transistor_groups[net_keys] = set()
                        tmp_pmos_nets_to_transistor_groups[net_keys].add(tran_i.name)
                        tmp_pmos_nets_to_transistor_groups[net_keys].add(tran_j.name)
        # nmos_transistor_groups = tmp_nets_to_transistor_groups.values()
        return {"PMOS": tmp_pmos_nets_to_transistor_groups, "NMOS": tmp_nmos_nets_to_transistor_groups}

                
    
    def group_transistors_by_low_degree_nets_and_types(self):
        """
        Transistors (same type) which share the same source/drain net should be placed adjacently
        If the source/drain net has only a degree of 2.
        """
        # tmp_nets_to_transistor_groups = {}
        transistor_groups = []
        for i, tran_i in enumerate(self.transistors.values()):
            for tran_j in list(self.transistors.values())[i + 1 :]:
                # must be same type
                if tran_i.model != tran_j.model:
                    continue
                FLAG_NOT_MATCH = True
                # match_source
                if tran_i.source == tran_j.source and self.nets[tran_i.source].degree() <= 2:
                    FLAG_NOT_MATCH = False
                # match drain
                if tran_i.drain == tran_j.drain and self.nets[tran_i.drain].degree() <= 2:
                    FLAG_NOT_MATCH = False
                # match source to drain
                if tran_i.source == tran_j.drain and self.nets[tran_i.source].degree() <= 2:
                    FLAG_NOT_MATCH = False
                # match drain to source
                if tran_i.drain == tran_j.source and self.nets[tran_i.drain].degree() <= 2:
                    FLAG_NOT_MATCH = False
                # if some net matched
                if not FLAG_NOT_MATCH:
                    transistor_groups.append((tran_i.name, tran_j.name))
        return transistor_groups

    def add_transistor(
        self,
        name,
        source,
        gate,
        drain,
        bulk,
        model,
        w,
        l,
        nfin,
        m=None,
        par=None,
        p_la=None,
        nf=None,
        ngcon=None,
        plorient=None,
        cpp=None,
        pre_layout_local=None,
        ptwell=None,
        wns=None,
    ):
        if not name.startswith("M"):
            raise ValueError(f"A transistor name must start with M. Found transistor name {name} in subcircuit {self.subckt_name}")
        
        # Convert nfin to integer if it's a string
        nfin = int(nfin) if isinstance(nfin, str) else nfin
        
        # Calculate number of transistors to create (base unit is 2 fins)
        num_copies = nfin // 2
        if nfin % 2 != 0:
            absl_logging.warning(f"nfin={nfin} is not divisible by 2 for transistor {name}. Rounding down.")
        
        # Find the starting suffix index
        suffix_idx = 0
        while f"{name}S{suffix_idx}" in self.transistors:
            suffix_idx += 1
        
        # Create multiple transistors if nfin > 2
        for copy_idx in range(num_copies):
            # Create a transistor instance with nfin=2 (base unit)
            t = Transistor(
                name,
                source=source,
                gate=gate,
                drain=drain,
                bulk=bulk,
                model=model,
                w=w,
                l=l,
                m=m,
                nfin=2,  # Base unit is 2 fins
                par=par,
                p_la=p_la,
                nf=nf,
                ngcon=ngcon,
                plorient=plorient,
                cpp=cpp,
                pre_layout_local=pre_layout_local,
                ptwell=ptwell,
                wns=wns,
            )
            
            t.name = f"{name}S{suffix_idx + copy_idx}"
            self.transistors[f"{name}S{suffix_idx + copy_idx}"] = t
            absl_logging.debug(f"Adding transistor: {t}")
            
            # Register transistor with each net
            for pin_type, net_name in t.terminals.items():
                # Note: need to check None here, because we set bulk to None by default
                if net_name is None:
                    continue
                net_obj = self.add_net(net_name)
                net_obj.add_connection(t.name, pin_type)

    def generate_networkx_graph(self):
        """
        mos -> node
        net -> node
        connect mos <-> net
        """
        G = nx.Graph()
        for tran_name, t in self.transistors.items():
            G.add_node(tran_name)
            G.add_node(t.drain)
            G.add_node(t.gate)
            G.add_node(t.source)
            G.add_edge(tran_name, t.source)
            G.add_edge(tran_name, t.gate)
            G.add_edge(tran_name, t.drain)
        return G

    def __repr__(self):
        return f"Circuit(subckt={self.subckt_name}, io pins={self.io_pins}, power pin={self.pwr_pins}, ground pin={self.gnd_pins}, nets={list(self.nets.keys())}, transistors={list(self.transistors.keys())})"


class MetalLayer:
    def __init__(
        self,
        layer_name: str,
        layer_type: str,
        direction: str,
        offset: float,
        pitch: float,
        width: float,
    ):
        """
        Example signature; your actual implementation may have more fields or methods.
        """
        self.layer_name = layer_name
        self.layer_type = layer_type
        self.direction = direction
        self.offset = offset
        self.pitch = pitch
        self.width = width

    def __repr__(self):
        return f"MetalLayer({self.layer_name}, {self.direction}, {self.width})"


class ViaLayer:
    def __init__(
        self, layer_name: str, layer_type: str, verti_enclosure: float, horiz_enclosure: float
    ):
        """
        Example signature; your actual implementation may have more fields or methods.
        """
        self.layer_name = layer_name
        self.layer_type = layer_type
        self.verti_enclosure = verti_enclosure
        self.horiz_enclosure = horiz_enclosure

    def __repr__(self):
        return f"ViaLayer({self.layer_name}, {self.verti_enclosure}, {self.horiz_enclosure})"


class LayerStack:
    def __init__(self, json_input: Union[str, dict]):
        """
        If json_input is a string, treat it as a path to a JSON file.
        If json_input is already a dict, use it directly.

        During initialization:
          1. Read/parse the JSON into a dict.
          2. Build all MetalLayer instances (storing them in a temp dict).
          3. Sort those metals by "layer_number" (ascending) and call add_metal_layer(...)
          4. Build all ViaLayer instances, look up their upper/lower metal objects,
             and call add_via_layer(lower_metal_obj, upper_metal_obj, via_obj).
        """
        # --------------------------------------------------------------------------
        # 1. Load the JSON (if a filename was passed in)
        # --------------------------------------------------------------------------
        if isinstance(json_input, str):
            # Treat json_input as a path to a file
            with open(json_input, "r") as f:
                layer_dict = json.load(f)
        elif isinstance(json_input, dict):
            # Already a Python dict
            layer_dict = json_input
        else:
            raise ValueError("LayerStack __init__ expects a JSON filename or a dict.")

        # --------------------------------------------------------------------------
        # 2. Partition the entries into metal_entries vs. via_entries
        # --------------------------------------------------------------------------
        metal_entries = {}
        via_entries = {}

        for name, props in layer_dict.items():
            ltype = props.get("layer_type", "").lower()
            if ltype == "metal":
                metal_entries[name] = props
            elif ltype == "via":
                via_entries[name] = props
            else:
                raise ValueError(
                    f"Layer '{name}' has unknown layer_type '{ltype}'. "
                    "Expected 'metal' or 'via'."
                )

        # --------------------------------------------------------------------------
        # 3. Instantiate every MetalLayer and keep a name→object mapping
        # --------------------------------------------------------------------------
        #    We also want to remember "layer_number" so we can sort.
        #    But MetalLayer __init__ does not take layer_number, so we just store it
        #    in a temporary dict for sorting. The real MetalLayer only needs the
        #    fields (layer_name, layer_type, direction, offset, pitch, width).
        # --------------------------------------------------------------------------
        temp_metal_list = []
        name_to_metalobj = {}

        for name, props in metal_entries.items():
            ln = props["layer_number"]  # used for ordering only
            direction = props["direction"]
            offset = float(props["offset"])
            pitch = float(props["pitch"])
            width = float(props["width"])
            layer_type = props["layer_type"]  # should be "metal"

            # Create the MetalLayer instance
            ml = MetalLayer(
                layer_name=props["layer_name"],
                layer_type=layer_type,
                direction=direction,
                offset=offset,
                pitch=pitch,
                width=width,
            )
            # 06/18/2025 Note: Implicitly a half metal offset to M1 since we do not encode left boundary M1 
            # if ml.layer_name == "M1" and ml.direction == "V":
            #     ml.offset += ml.pitch / 2
            # Keep it in a list along with its layer_number
            temp_metal_list.append((ln, ml))
            name_to_metalobj[name] = ml

        # --------------------------------------------------------------------------
        # 4. Sort the metals by layer_number ascending (lowest → highest) and add them
        # --------------------------------------------------------------------------
        temp_metal_list.sort(key=lambda x: x[0])  # sort by layer_number
        self.metal_layers = []
        self.layer_to_index = {}

        for idx, (_, metal_obj) in enumerate(temp_metal_list):
            self.metal_layers.append(metal_obj)
            # layer_to_index maps layer_name → index in metal_layers list
            self.layer_to_index[metal_obj.layer_name] = idx

        # --------------------------------------------------------------------------
        # 5. Prepare an empty dict for via_layers; we'll add them next
        # --------------------------------------------------------------------------
        #    The key is (lower_metal_name, upper_metal_name) → ViaLayer
        # --------------------------------------------------------------------------
        self.via_layers = {}

        # --------------------------------------------------------------------------
        # 6. Instantiate every ViaLayer and immediately call add_via_layer(...)
        # --------------------------------------------------------------------------
        for via_name, props in via_entries.items():
            # Example props:
            #   {
            #     "layer_type": "via",
            #     "layer_number": 8,             # may not be strictly necessary
            #     "layer_name": "CA",
            #     "upper_layer": "M0",
            #     "lower_layer": "PC",
            #     "vertical_enclosure": 0.0,
            #     "horizontal_enclosure": 0.0
            #   }

            lower_name = props["lower_layer"]
            upper_name = props["upper_layer"]

            # Look up the already created MetalLayer instances
            lower_metal_obj = name_to_metalobj.get(lower_name)
            upper_metal_obj = name_to_metalobj.get(upper_name)
            if lower_metal_obj is None or upper_metal_obj is None:
                raise ValueError(
                    f"Via '{via_name}' refers to lower='{lower_name}' or upper='{upper_name}', "
                    "but one of those metals was not defined in the JSON."
                )

            verti_enc = float(props["vertical_enclosure"])
            hori_enc = float(props["horizontal_enclosure"])
            layer_type = props["layer_type"]  # should be "via"

            # Create the ViaLayer instance
            via_obj = ViaLayer(
                layer_name=props["layer_name"],
                layer_type=layer_type,
                verti_enclosure=verti_enc,
                horiz_enclosure=hori_enc,
            )

            # Finally, register this via in our internal dict
            self.add_via_layer(lower_metal_obj, upper_metal_obj, via_obj)

    # ---------------------------------------------------------------------
    # (The rest of LayerStack is unchanged:)
    # ---------------------------------------------------------------------
    def add_metal_layer(self, metal_layer: MetalLayer):
        """
        Adds a metal layer to the stack in order (lowest to highest).
        """
        self.metal_layers.append(metal_layer)
        self.layer_to_index[metal_layer.layer_name] = len(self.metal_layers) - 1

    def add_via_layer(
        self,
        lower_metal_layer: MetalLayer,
        upper_metal_layer: MetalLayer,
        via_layer: ViaLayer,
    ):
        """
        Defines the via layer that connects two adjacent metal layers.
        """
        self.via_layers[(lower_metal_layer.layer_name, upper_metal_layer.layer_name)] = via_layer

    def get_upper(self, metal_layer: MetalLayer):
        """
        For the given metal layer, returns a tuple (upper_metal_layer, via_layer) where:
          - upper_metal_layer is the next metal layer above.
          - via_layer is the ViaLayer connecting the two.
        Returns (None, None) if there is no upper layer.
        """
        idx = self.layer_to_index.get(metal_layer.layer_name)
        if idx is None or idx == len(self.metal_layers) - 1:
            return None, None
        upper_metal = self.metal_layers[idx + 1]
        via = self.via_layers.get((metal_layer.layer_name, upper_metal.layer_name))
        return upper_metal, via

    def get_lower(self, metal_layer: MetalLayer):
        """
        For the given metal layer, returns a tuple (lower_metal_layer, via_layer) where:
          - lower_metal_layer is the next metal layer below.
          - via_layer is the ViaLayer connecting the two.
        Returns (None, None) if there is no lower layer.
        """
        idx = self.layer_to_index.get(metal_layer.layer_name)
        if idx is None or idx == 0:
            return None, None
        lower_metal = self.metal_layers[idx - 1]
        via = self.via_layers.get((lower_metal.layer_name, metal_layer.layer_name))
        return lower_metal, via
