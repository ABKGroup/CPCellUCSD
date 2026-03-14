# Standard Cell Evaluation Flow for Gear-Ratio and Offset Application
This sub-repository provides the flows for standard cell characterization, place-and-route (P&R), and IR-drop evaluation.

## Directory Structure

```
evaluation/
├── libgen/                # Library characterization directories
│   ├── 1:1GR/               # 1:1 GR (45nm:45nm) Libraries (No offset)
│   ├── 3:2GR/               # 3:2 GR (45nm:30nm) Libraries (No offset)
│   ├── 3:2GR_15offset/      # 3:2 GR (45nm:30nm) Libraries (15nm-offset)
│   ├── 5:3GR/               # 5:3 GR (45nm:27nm) Libraries (No offset)
│   ├── 5:3GR_9offset/       # 5:3 GR (45nm:27nm) Libraries (9nm-offset)
│   └── 5:3GR_18offset/      # 5:3 GR (45nm:27nm) Libraries (18nm-offset)
├── blockeval/             # Place-and-Route and IR-drop evaluation flows
│   ├── 1:1GR/               # 1:1 GR flows / no-offset only
│   ├── 3:2GR/               # 3:2 GR flows / no-offset only
│   ├── 3:2GR_ECG/           # 3:2 GR flows / Equivalent Cell Group
│   ├── 5:3GR/               # 5:3 GR flows / no-offset only
└── └── 5:3GR_ECG/           # 5:3 GR flows / Equivalent Cell Group
```

## Library Characterization 

Flow scripts for library characterization are located in the *libgen* directory. Required tools are:
- **Cadence Pegasus:** LVS and PEX (v21.3)
- **Cadence Quantus:** PEX (v21.2)
- **Cadence Liberate:** Characterization (v23.1)
- **Synopsys Library Compiler:** DB file generation (L-2016.06-SP3)

```bash
# Step 1 — LVS and PEX
# Inputs: GDS, CDL, and cell list
# Outputs: RC-extracted spice netlists (*.sp)
make lvspex

# Step 2 — Characterization (Liberty generation)
# Inputs: RC-extracted spice netlists (*.sp), cell list, and Liberty template
# Outputs: Liberties (*.lib)
make libchar

# Step 3 — DB file generation for ICC2 place-and-route
# Inputs: Liberties (*.lib)
# Outputs: DB files (*.db)
make dbconv

# Step 4-1 — NDM generation
# Inputs: LEF files (*.lef)
# Outputs: NDM files (*.ndm)
# Run directory: libgen/{GR_option}/results/ndm/
icc2_lm_shell
source run_icc2_lm_PROBE.tcl

# Step 4-2 — NDM generation for Equivalent Cell Group (ECG)
# This is only required if you are implementing an ECG
# Inputs: LEF files (*.lef)
# Outputs: NDM files (*.ndm)
# Run directory: libgen/{GR_option}/results/ndm/
icc2_lm_shell
source run_icc2_lm_createCellGroup.tcl
```

## Block-level Evaluation 
We use a JPEG Encoder design for our block-level evaluation.

### PPA Evaluation
For PPA evaluation, you need to specify the target clock period and utilization.
- **Synopsys Design Compiler:** Synthesis (v20.09)
- **Synopsys IC Compiler II:** Place-and-Route (v20.09)

```bash
# Run directory: evaluation/{GR_option}/
# Example: Target clock period = 100ps / Target utilization: 85%
./run.sh 0.100 0.85
```
### IR-drop Evaluation
IR-drop flow scripts are located under **1:1GR**, **3:2GR*_*ECG**, and **5:3GR*_*ECG** only
- **Cadence Voltus:** IR-drop measurement (v21.1)

```bash
# Run directory: evaluation/blockeval/{GR_option}/IRdrop/
## Create links to the voltage source files
ln -s ../{target_pnr_dir}/VDD.vsrc .
ln -s ../{target_pnr_dir}/VSS.vsrc .

## Create links to the target design files
## DEF file: 
ln -s ../{target_pnr_dir}/enc_orig/fc_jpeg_encoder.def jpeg_encoder.def
## SDC file: 
ln -s ../{target_pnr_dir}/gate/fc_jpeg_encoder.def jpeg_encoder.sdc
## SPEF file: 
ln -s ../{target_pnr_dir}/enc_orig/fc_jpeg_encoder.def jpeg_encoder.spef

## Voltus run
./run.csh
```

# Knowledge Reference
- OpenCores JPEG Encoder. \[[Link](https://opencores.org/projects/mkjpeg)\]
- Cadence Pegasus, Quantus and Voltus. \[[Link](https://cadence.com)\]
- Synopsys Design Compiler, IC Compiler II. \[[Link](https://synopsys.com)\]
