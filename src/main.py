import os
import json
import logging
from absl import logging as absl_logging
import argparse
# custom
from src.utility.entity import LayerStack
from src.tech.tech import FinFET_Tech
from src.core.finfet import FinFET
from src.utility.util import read_cdl_file, write_pinlayout_file
import src.utility.config as config

# Set up logging to print messages
# Custom log format: [LEVEL] TIMESTAMP - MESSAGE
# NOTE: level available: DEBUG, INFO, WARNING, ERROR, CRITICAL
logging.basicConfig(format="[%(levelname)s] %(asctime)s - %(message)s", level=logging.INFO)
logging.basicConfig(format="[%(levelname)s] %(asctime)s - %(message)s", level=logging.DEBUG)


class SMTCell:
    """
    SMTCell main class that holds the circuits and technology information.
    """
    def __init__(
        self,
        cdl_file,
        cell_config,
        technology,
        circuit_names=[],
        write_pinlayout=False,
        output_dir="./output/",
        flag_log_constraints=False
    ):
        config.init()  # Initialize global variables
        self.flag_log_constraints = flag_log_constraints
        self.output_dir = output_dir
        self.cell_config = cell_config
        # if user does not specifies the circuit names, synthsize everything
        if circuit_names == []:
            self.circuits = read_cdl_file(cdl_file)
            self.circuit_names = [circuit.subckt_name for circuit in self.circuits]
            absl_logging.info(f"Found circuits: {self.circuit_names}")
        else:
            all_circuits = read_cdl_file(cdl_file)
            self.circuits = []
            self.circuit_names = []
            # Check if the specified circuit names are in the circuits
            for cir in all_circuits:
                if cir.subckt_name in circuit_names:
                    self.circuit_names.append(cir.subckt_name)
                    self.circuits.append(cir)
            absl_logging.info(f"Found circuits: {self.circuit_names}")
            assert len(self.circuit_names) == len(circuit_names), absl_logging.error(
                f"Specified circuit names not found in the circuits.\n Got: {circuit_names}\n Found: {self.circuit_names}"
            )
        if write_pinlayout:
            pinlayout_dir = os.path.join(self.output_dir, "pinLayouts")
            # Create the output directory if it doesn't exist
            os.makedirs(pinlayout_dir, exist_ok=True)
            for cir in self.circuits:
                write_pinlayout_file(cir, output_dir=pinlayout_dir)
        self.technology = technology
        # Generate the cell library
        self.gen_cell_lib()

    def gen_cell_lib(self):
        """
        Generate the cell library for the given circuits and technology.
        """
        if self.technology.TECHNOLOGY == "FinFET":
            absl_logging.info(f"Generating FinFET cell library with height configuration: {self.technology.height_config}")
            if self.technology.height_config == "SH":
                for circuit in self.circuits:
                    finfet = FinFET(
                        circuit=circuit,
                        fin_tech=self.technology,
                        cell_config=self.cell_config,
                        output_dir=self.output_dir,
                        flag_log_constraints=self.flag_log_constraints
                    )
        else:
            raise ValueError("Technology not supported.")

    def __repr__(self):
        return f"SMTCell({self.circuit_names}, {self.technology})"


# Example usage with the provided netlist text
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        default="spnr",
        type=str,
        help="Mode to run the script: spnr",
    )
    parser.add_argument(
        "--layer",
        default="input/layer_2F_4T_4530.json",
        type=str,
        help="Path to the layer file for the technology.",
    )
    parser.add_argument(
        "--lib_name",
        default="PROBE",
        type=str,
        help="Library name for the technology.",
    )
    parser.add_argument(
        "--tech",
        default="FinFET",
        type=str,
        help="Technology to use: FinFET, CFET.",
    )
    parser.add_argument(
        "--track",
        default=4,
        type=int,
        help="Number of horizontal routing tracks"
    )
    parser.add_argument(
        "--height_config",
        default="SH",
        type=str,
        help="Height configuration for the technology: SH (Single Height), PNNP/NPPN (Double Height).",
    )
    parser.add_argument(
        "--cell_config",
        type=str,
        help="Cell configuration file",
    )
    parser.add_argument(
        "--netlist",
        default="",
        type=str,
        help="Path to the netlist file.",
    )
    parser.add_argument(
        "--output_dir",
        default="./output/",
        type=str,
        help="Output directory for the generated files.",
    )
    parser.add_argument(
        "--cell_names",
        default=[],
        nargs="+",
        type=str,
        help="List of cell names to synthesize.",
    )
    parser.add_argument(
        "--level",
        default="info",
        type=str,
        help="Logging level: debug, info, warning, error, critical.",
    )
    parser.add_argument(
        "--flag_log_constraints",
        default="True",
        choices=["True", "False"],
        help="If log constraints into a file"
    )
    args = parser.parse_args()
    if args.level == "debug":
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.level == "info":
        logging.getLogger().setLevel(logging.INFO)
    
    # Function
    if args.mode == "spnr":
        stack = LayerStack(args.layer)
        """
        Example usage of the SMTCell class.
        """
        if args.tech == "FinFET":
            technology = FinFET_Tech(
                lib_name=args.lib_name, layer_stack=stack, unit_width=46.0, num_rt_track=args.track, num_fin=2, height_config=args.height_config
            )
        else:
            raise ValueError("Technology not supported.")
            exit(1)

        # log file flag
        if args.flag_log_constraints == "True":
            _flag_log_constraints_ = True
        elif args.flag_log_constraints == "False":
            _flag_log_constraints_ = False
        else:
            raise ValueError(f"Unrecognized flag_log_constraints option: {args.flag_log_constraints}")
        
        smtcell = SMTCell(
            cdl_file=args.netlist,
            cell_config=args.cell_config,
            circuit_names=args.cell_names,
            technology=technology,
            write_pinlayout=True,
            output_dir=args.output_dir,
            flag_log_constraints = _flag_log_constraints_
        )
