import json
import copy
import argparse

"""
Global variable initialization
Call only once at the beginning of main.py
"""
def init():
    # GLOBAL VARIABLES that defines the pin names
    global PWR_NET_NAMES
    global GND_NET_NAMES
    global INPUT_NET_NAMES
    global OUTPUT_NET_NAMES
    PWR_NET_NAMES= ['VDD']
    GND_NET_NAMES= ['VSS']
    INPUT_NET_NAMES = []
    OUTPUT_NET_NAMES = []
    # read the pin names from the json files
    with open("./input/pin_input_collection.json") as f:
        data = json.load(f)
        INPUT_NET_NAMES = data.keys()
    with open("./input/pin_output_collection.json") as f:
        data = json.load(f)
        OUTPUT_NET_NAMES = data.keys()

def generate_config(track, tech, height_config, circuit_names, output_dir):
    # FinFET, SH, 4T
    CONFIG_TEMPLATE = {
        "minimum_gate_cut_length" : {
            "value": 2,
            "info": "[TECH] Minimum gate cut length in CPP"
        },
        "lisd_routing" : {
            "value": False,
            "info": "[TECH] Use LISD as a routing resource"
        },
        "lig_routing" : {
            "value": False,
            "info": "[TECH] Use LIG as a routing resource"
        },
        "supervia" : {
            "value": [],
            "info": "[TECH] List of layers that allow to use supervia"
        },
        "via_c2c_rule": {
            "value": {
                "M0, M1" : 45,
                "M1, M2" : 45
            },
            "info": "[TECH] Center-to-center via distance between layers"
        },
        "mar_c2c_rule": {
            "value": {
                "M0" : 20,
                "M1" : 144,
                "M2" : 90
            },
            "info": "[TECH] Center-to-center minimum area rule for metals"
        },
        "eol_c2c_rule": {
            "value": {
                "M0" : 20,
                "M1" : 48,
                "M2" : 45
            },
            "info": "[TECH] Center-to-center end of line rule for metals"
        },
        "insert_num_db": {
            "value": 0,
            "info": "[TECH] Maximum number of diffusion breaks allowed to use"
        },
        "polygon_cell": {
            "value": False,
            "info": "[TECH] Encourage DH to make polygon cells"
        },
        "MPO": {
            "value": 2,
            "info": "[TECH] Minimum Pin Opening at M1"
        },
        "seed": {
            "value": 32,
            "info": "[SOLVER] Random seed"
        },
        "use_objective_set": {
            "values": [],
            "info": "[SOLVER] Set of objectives to use. If not set, a default set will be used."
        },
        "model_preset": {
            "value": 2,
            "info": "[SOLVER] Model preset ID used for solving"
        },
        "num_search_workers": {
            "value": 6,
            "info": "[SOLVER] Number of cores to use for solving"
        },
        "use_strategy" : {
            "value": "PLACE",
            "info": "[SOLVER] Use decision strategy to speedup feasibility discovery"
        },
        "use_relative_gap": {
            "value": False,
            "perc": 0.01,
            "info": "[SOLVER] Allow percentage optimality gap"
        },
        "max_time": {
            "value": False,
            "time": 3600,
            "info": "[SOLVER] Maximimum solving time in seconds"
        },
        "routing_tolerance" : {
            "value": True,
            "tol": 0,
            "info": "[SPEEDUP] Allowable routing distance to go beyond window in CPP"
        },
        "use_break_symmetry_for_placement" : {
            "value": True,
            "info": "[SPEEDUP] Break symmetry during placement"
        },
        "close_in_low_degree_net": {
            "value": False,
            "info": "[SPEEDUP] Enforce 2-pin nets to be diffusion shared"
        },
        "use_placement_order_for_identical_transistors": {
            "value": False,
            "info": "[SPEEDUP] Enforce identical transistors to be placed in a certain order"
        },
        "inject_edge": {
            "value": {},
            "info": "[INJECT] Inject edge(s) to be used (u_layer, u_row, u_col, v_layer, v_row, v_col) : 0 or 1"
        },
        "inject_arc": {
            "value": {},
            "info": "[INJECT] Inject arc(s) to be used (net_name, u_layer, u_row, u_col, v_layer, v_row, v_col) : 0 or 1"
        },
        "inject_flow": {
            "value": {},
            "info": "[INJECT] Inject flow(s) to be used (net_name, k_idx, u_layer, u_row, u_col, v_layer, v_row, v_col) : 0 or 1"
        },
        "inject_placement": {
            "value": [],
            "info": "[INJECT] Inject placement(s) to be used (tran_name, x, y, flip)"
        },
        "inject_track": {
            "value": {},
            "info": "[INJECT] Inject a track to be used on a layer (layer, row/col_idx)"
        },
        "m0_pin_separation": {
            "value": False,
            "info": "[PIN] Enforce M0 pin separation across different rows"
        },
        "m0_pin_extension": {
            "value": True,
            "vacancy_edges": 2,
            "info": "[PIN] Extend M0 pin to vacancy edges"
        },
        "inject_cluster": {
            "value": False,
            "remove_2d_nets": True,
            "min_cluster_size": 2,
            "max_cluster_size": 4,
            "method": "kkhdb",
            "info": "[INJECT] Inject clusters automatically"
        }
    }

    for cir in circuit_names:
        config_template = copy.deepcopy(CONFIG_TEMPLATE)
        # ^ (Heuristic) How many diffusion breaks to insert?
        if "DFF" in cir:
            config_template["insert_num_db"]["value"] = 2
        elif "LHQ" in cir or "LAT" in cir:
            config_template["insert_num_db"]["value"] = 1
        elif "XOR" in cir or "XNOR" in cir:
            config_template["insert_num_db"]["value"] = 1
        elif "AO" in cir or "OA" in cir:
            config_template["insert_num_db"]["value"] = 1
        # ^ (Large Drive Strength) Relative gap for large cells
        if "_X8" in cir or "_X10" in cir or "_X12" in cir or "_X16" in cir:
            config_template["close_in_low_degree_net"]["value"] = True
            config_template["use_placement_order_for_identical_transistors"]["value"] = True
            config_template["use_relative_gap"]["value"] = True
            config_template["use_relative_gap"]["perc"] = 0.01
        # ^ (Timeout) 50 hour cap for DFF and large DR cells
        if "DFF" in cir or "_X12" in cir or "_X16" in cir:
            config_template["max_time"]["value"] = True
            config_template["max_time"]["time"] = 150000
            config_template["use_relative_gap"]["value"] = True
            config_template["use_relative_gap"]["perc"] = 0.01
        # ^ Writeout
        with open(f"./{output_dir}/config/{cir}.json", "w") as f:
            json.dump(config_template, f, ensure_ascii=False, indent=4)

def read(config_file):
    """
    Read the config file and return a dict
    """
    try:
        with open(config_file, 'r') as file:
            config = json.load(file)
        return config
    except FileNotFoundError:
        FileNotFoundError(f"Error: '{config_file}' not found.")
    except json.JSONDecodeError:
        json.JSONDecodeError(f"Error: Invalid JSON format in '{config_file}'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cell_names",
        default=[],
        nargs="+",
        type=str,
        help="List of cell names.",
    )
    parser.add_argument(
        "--track",
        default=4,
        type=int,
        help="Number of horizontal routing tracks",
    )
    parser.add_argument(
        "--tech",
        default="FinFET",
        type=str,
        help="Technology to use: FinFET.",
    )
    parser.add_argument(
        "--height_config",
        default="SH",
        type=str,
        help="Height configuration: SH (Single Height).",
    )
    parser.add_argument(
        "--output_dir",
        default="./output/",
        type=str,
        help="Output directory for the generated files.",
    )
    args = parser.parse_args()
    generate_config(track=args.track, tech=args.tech, height_config=args.height_config, circuit_names=args.cell_names, output_dir=args.output_dir)
