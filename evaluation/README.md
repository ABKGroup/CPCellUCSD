# Standard Cell Evaluation Flow for Gear-Ratio and Offset Application
This sub-repository provides the flows for standard cell characterization, place-and-route (P&R), and IR-drop evaluation.

## Directory Structure

```
evaluation/
├── libgen/                  # Library characterization directories
│   ├── 1:1GR/                 # 1:1 GR (45nm:45nm) Libraries (No offset)
│   ├── 3:2GR/                 # 3:2 GR (45nm:30nm) Libraries (No offset)
│   ├── 3:2GR_15offset/        # 3:2 GR (45nm:30nm) Libraries (15nm-offset)
│   ├── 5:3GR/                 # 5:3 GR (45nm:27nm) Libraries (No offset)
│   ├── 5:3GR_9offset/         # 5:3 GR (45nm:27nm) Libraries (9nm-offset)
│   ├── 5:3GR_18offset/        # 5:3 GR (45nm:27nm) Libraries (18nm-offset)
│   └── 2:1GR/                 # 2:1 GR (45nm:22.5nm) Libraries (No offset)
├── blockeval/               # Place-and-Route and IR-drop evaluation flows
│   ├── design/                 # Shared RTL for block-level benchmarks
│   │   ├── jpeg_encoder/         # OpenCores JPEG Encoder
│   │   └── aes_cipher_top/       # OpenCores AES
│   ├── 1:1GR/                 # 1:1 GR flows / no-offset only
│   ├── 3:2GR/                 # 3:2 GR flows / no-offset only
│   ├── 3:2GR_ECG/             # 3:2 GR flows / Equivalent Cell Group
│   ├── 5:3GR/                 # 5:3 GR flows / no-offset only
│   ├── 5:3GR_ECG/             # 5:3 GR flows / Equivalent Cell Group
│   └── 2:1GR/                 # 2:1 GR flows / no-offset only
└── results/                 # Reported PPA results (tables, generated figures)
```

## Library Characterization 

Flow scripts for library characterization are located in the *libgen* directory. Required tools are:
- **Cadence Pegasus:** LVS and PEX (v21.3)
- **Cadence Quantus:** PEX (v21.2)
- **Cadence Liberate:** Characterization (v23.1)
- **Synopsys Library Compiler:** DB file generation (L-2016.06-SP3)

```bash
# Step 0 — Signoff
# Inputs: GDS, tech file (*.tf)
# Outputs: pass/fail report
make signoff

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



# Results Reference

## Power, Performance and Area Under Different Gear Ratio Settings
The tables below reproduce Table IX from the paper: implementation metrics (instance
count, wirelength, power, timing, area) for the JPEG Encoder block, swept across target
clock periods from 0.10ns to 0.40ns, for each gear-ratio (GR) option evaluated.

<table>
<tr>
<td><img src="results/fig_power_vs_clkp.png" width="440" alt="Total Power vs. Effective Clock Period"></td>
<td><img src="results/fig_area_vs_clkp.png" width="440" alt="Area vs. Effective Clock Period"></td>
</tr>
</table>

These extend the paper's Fig. 19 with the 2:1 GR series added, generated from
`results/table_ix_ppa.csv`.

### 1:1 GR

| Metric | 0.10 | 0.12 | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 | 0.40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| #Insts | 60255 | 47718 | 44714 | 43774 | 43215 | 42965 | 42850 | 42700 |
| Wirelength (μm) | 92560 | 87659 | 82759 | 73234 | 69993 | 70875 | 68578 | 69116 |
| Total Power (mW) | 29.7 | 24.6 | 18.2 | 13.0 | 10.3 | 8.9 | 7.6 | 6.7 |
| Worst Negative Slack (ns) | -0.021 | -0.013 | 0.000 | 0.009 | 0.014 | 0.022 | 0.028 | 0.034 |
| Effective CLKP (ns) | 0.121 | 0.133 | 0.150 | 0.191 | 0.236 | 0.278 | 0.322 | 0.366 |
| Area (μm²) | 2199 | 2017 | 1935 | 1886 | 1878 | 1836 | 1838 | 1836 |

### 3:2 GR — 0-offset Only

| Metric | 0.10 | 0.12 | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 | 0.40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| #Insts | 57889 | 54403 | 52951 | 47918 | 46307 | 45750 | 45319 | 45376 |
| Wirelength (μm) | 74528 | 71986 | 71602 | 72681 | 65940 | 64729 | 63707 | 64154 |
| Total Power (mW) | 28.3 | 23.3 | 18.4 | 13.7 | 10.8 | 9.1 | 7.7 | 6.9 |
| Worst Negative Slack (ns) | -0.006 | -0.004 | -0.001 | 0.001 | 0.004 | 0.014 | 0.019 | 0.031 |
| Effective CLKP (ns) | 0.106 | 0.124 | 0.151 | 0.199 | 0.246 | 0.286 | 0.331 | 0.369 |
| Area (μm²) | 1860 | 1826 | 1777 | 1726 | 1680 | 1669 | 1659 | 1656 |

### 3:2 GR — Mixed-offset

| Metric | 0.10 | 0.12 | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 | 0.40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| #Insts | 57155 | 44195 | 42117 | 41543 | 41207 | 41103 | 41106 | 41087 |
| Wirelength (μm) | 76773 | 79973 | 66652 | 59613 | 56396 | 55492 | 57627 | 55264 |
| Total Power (mW) | 30.6 | 24.2 | 18.0 | 12.5 | 10.3 | 8.5 | 7.4 | 6.5 |
| Worst Negative Slack (ns) | -0.036 | -0.013 | -0.007 | 0.007 | 0.012 | 0.023 | 0.029 | 0.040 |
| Effective CLKP (ns) | 0.136 | 0.133 | 0.157 | 0.193 | 0.238 | 0.277 | 0.321 | 0.360 |
| Area (μm²) | 1767 | 1659 | 1579 | 1566 | 1555 | 1555 | 1553 | 1553 |

### 5:3 GR — 0-offset Only

| Metric | 0.10 | 0.12 | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 | 0.40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| #Insts | 59183 | 57455 | 52756 | 47062 | 54266 | 53125 | 52780 | 52663 |
| Wirelength (μm) | 77686 | 80350 | 68864 | 73755 | 72539 | 70100 | 70454 | 68210 |
| Total Power (mW) | 27.5 | 23.7 | 17.1 | 13.4 | 10.7 | 9.1 | 7.9 | 7.1 |
| Worst Negative Slack (ns) | -0.003 | -0.004 | 0.002 | 0.003 | 0.008 | 0.014 | 0.017 | 0.036 |
| Effective CLKP (ns) | 0.103 | 0.124 | 0.148 | 0.198 | 0.242 | 0.286 | 0.333 | 0.364 |
| Area (μm²) | 2003 | 1912 | 1779 | 1726 | 1927 | 1900 | 1864 | 1886 |

### 5:3 GR — Mixed-offset

| Metric | 0.10 | 0.12 | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 | 0.40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| #Insts | 54104 | 50761 | 41131 | 39900 | 39594 | 38890 | 38803 | 38731 |
| Wirelength (μm) | 72021 | 68720 | 71780 | 66803 | 64239 | 57964 | 55328 | 55335 |
| Total Power (mW) | 28.5 | 22.3 | 17.5 | 12.9 | 10.5 | 8.7 | 7.4 | 6.6 |
| Worst Negative Slack (ns) | -0.022 | -0.011 | -0.009 | 0.001 | 0.010 | 0.016 | 0.028 | 0.052 |
| Effective CLKP (ns) | 0.122 | 0.131 | 0.159 | 0.199 | 0.240 | 0.284 | 0.322 | 0.348 |
| Area (μm²) | 1812 | 1726 | 1586 | 1511 | 1486 | 1466 | 1463 | 1488 |

### 2:1 GR

| Metric | 0.10 | 0.12 | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 | 0.40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| #Insts | 59293 | 48769 | 46457 | 44845 | 43987 | 43709 | 43511 | 43331 |
| Wirelength (μm) | 85761 | 80389 | 81638 | 70843 | 72998 | 76912 | 72098 | 69774 |
| Total Power (mW) | 29.6 | 24.0 | 18.7 | 13.3 | 10.6 | 9.0 | 7.9 | 6.9 |
| Worst Negative Slack (ns) | -0.005 | -0.010 | 0.000 | 0.010 | 0.020 | 0.020 | 0.030 | 0.050 |
| Effective CLKP (ns) | 0.105 | 0.130 | 0.150 | 0.190 | 0.230 | 0.280 | 0.320 | 0.350 |
| Area (μm²) | 1974 | 1826 | 1701 | 1646 | 1610 | 1599 | 1601 | 1601 |

## Evaluation Method & Examples
For 1:1 GR, 3:2 GR and 5:3 GR (0-offset and mixed-offset), each target clock period (TCP)
has five P&R runs (TCP, TCP ±0.1 ps, TCP ±0.2 ps) at every utilization of a sweep.
At each utilization, runs that fail to route or have #DRV > 300 are discarded. Table IX
uses the highest utilization at which at least one run remains and reports the per-metric
median of the remaining runs, rounded half-up to the precision shown.
Per-run data: `results/table_ix_runs/`.

Utilization used at each TCP (number of remaining runs):

| Configuration | 0.10 | 0.12 | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 | 0.40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1:1 GR | 0.95 (2) | 0.93 (4) | 0.95 (3) | 0.95 (1) | 0.95 (3) | 0.97 (1) | 0.97 (1) | 0.97 (1) |
| 3:2 GR — 0-offset Only | 0.95 (5) | 0.95 (5) | 0.95 (5) | 0.95 (5) | 0.95 (5) | 0.95 (5) | 0.95 (5) | 0.95 (5) |
| 3:2 GR — Mixed-offset | 0.95 (5) | 0.95 (5) | 0.95 (5) | 0.95 (5) | 0.95 (5) | 0.95 (5) | 0.95 (5) | 0.95 (5) |
| 5:3 GR — 0-offset Only | 0.91 (3) | 0.91 (1) | 0.91 (5) | 0.95 (4) | 0.87 (2) | 0.87 (4) | 0.89 (2) | 0.89 (3) |
| 5:3 GR — Mixed-offset | 0.97 (4) | 0.97 (2) | 0.97 (1) | 0.97 (1) | 0.97 (1) | 0.97 (1) | 0.97 (1) | 0.95 (2) |

### Example: 1:1 GR at 0.10 ns
At utilization 0.97, all five runs have #DRV > 300. At 0.95, the runs at 0.1000 ns and
0.1001 ns remain; Table IX reports their per-metric median.

| Run TCP (ns) | #Insts | Wirelength (μm) | Total Power (mW) | Worst Negative Slack (ns) | Effective CLKP (ns) | Area (μm²) | #DRV |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0.0998 | 61823 | 95402 | 31.1 | -0.016 | 0.116 | 2199 | 373 |
| 0.0999 | 61490 | 96497 | 31.5 | -0.014 | 0.114 | 2199 | 389 |
| 0.1000 | 60734 | 94318 | 29.7 | -0.036 | 0.136 | 2199 | 274 |
| 0.1001 | 59776 | 90801 | 29.7 | -0.006 | 0.106 | 2199 | 289 |
| 0.1002 | 61857 | 100694 | 30.5 | -0.025 | 0.125 | 2199 | 339 |
| **Table IX** | 60255 | 92560 | 29.7 | -0.021 | 0.121 | 2199 | — |

## Fixed Netlist/Independent Netlist Ablation Study
A **fixed netlist** is synthesized once under one GR library, then reused for
place-and-route under a *different* GR library.

An **independent netlist** is
synthesized under the same GR library it is placed and routed with, so each GR
library gets its own, separately-synthesized netlist. 

The purpose of this study is to isolate whether a
synthesis/P&R library mismatch changes the resulting PPA, independent of which
library the netlist happens to be routed under.

(Note: Every 3:2 entry below uses the 0-offset-only library variant.)

For each pair of rows that shares a synthesis library and TCP (so the two
rows use the same synthesized netlist), the **bold** value marks the better
PnR library choice on that metric.

<table>
<tr>
  <th>TCP (ns)</th>
  <th>Synthesis Library</th>
  <th>PnR Library</th>
  <th>#Insts (Post-Synthesis)</th>
  <th>Wirelength (μm)</th>
  <th>Total Power (mW)</th>
  <th>Worst Negative Slack (ns)</th>
  <th>Effective CLKP (ns)</th>
  <th>Area (μm²)</th>
</tr>
<tr>
  <td rowspan="4" align="center">0.1</td>
  <td rowspan="2" align="center">1:1</td>
  <td align="center">1:1</td>
  <td>28619</td><td>91637</td><td><strong>29.5</strong></td><td>-0.011</td><td>0.111</td><td>2296</td>
</tr>
<tr>
  <td align="center">3:2</td>
  <td>28619</td><td><strong>84058</strong></td><td>29.8</td><td><strong>-0.010</strong></td><td><strong>0.110</strong></td><td><strong>1951</strong></td>
</tr>
<tr>
  <td rowspan="2" align="center">3:2</td>
  <td align="center">1:1</td>
  <td>14756</td><td>82550</td><td><strong>28</strong></td><td><strong>0</strong></td><td><strong>0.100</strong></td><td>2214</td>
</tr>
<tr>
  <td align="center">3:2</td>
  <td>14756</td><td><strong>73759</strong></td><td>28.4</td><td>-0.008</td><td>0.108</td><td><strong>1898</strong></td>
</tr>
<tr>
  <td rowspan="4" align="center">0.25</td>
  <td rowspan="2" align="center">1:1</td>
  <td align="center">1:1</td>
  <td>17757</td><td>69993</td><td><strong>10.4</strong></td><td><strong>0.014</strong></td><td><strong>0.236</strong></td><td>1878</td>
</tr>
<tr>
  <td align="center">3:2</td>
  <td>17757</td><td><strong>64920</strong></td><td>10.5</td><td>0.010</td><td>0.240</td><td><strong>1624</strong></td>
</tr>
<tr>
  <td rowspan="2" align="center">3:2</td>
  <td align="center">1:1</td>
  <td>11106</td><td>106199</td><td>11.9</td><td>-0.170</td><td>0.420</td><td>1886</td>
</tr>
<tr>
  <td align="center">3:2</td>
  <td>11106</td><td><strong>65940</strong></td><td><strong>10.8</strong></td><td><strong>0.004</strong></td><td><strong>0.246</strong></td><td><strong>1680</strong></td>
</tr>
<tr>
  <td rowspan="4" align="center">0.4</td>
  <td rowspan="2" align="center">1:1</td>
  <td align="center">1:1</td>
  <td>18794</td><td>65480</td><td><strong>6.7</strong></td><td>0.041</td><td>0.359</td><td>1912</td>
</tr>
<tr>
  <td align="center">3:2</td>
  <td>18794</td><td><strong>59755</strong></td><td>6.8</td><td><strong>0.060</strong></td><td><strong>0.340</strong></td><td><strong>1656</strong></td>
</tr>
<tr>
  <td rowspan="2" align="center">3:2</td>
  <td align="center">1:1</td>
  <td>11260</td><td>73969</td><td>7.09</td><td><strong>0.050</strong></td><td><strong>0.350</strong></td><td>1890</td>
</tr>
<tr>
  <td align="center">3:2</td>
  <td>11260</td><td><strong>62488</strong></td><td><strong>6.8</strong></td><td>0.030</td><td>0.370</td><td><strong>1690</strong></td>
</tr>
</table>

## Additional Block-Level Benchmark (AES)
The Advanced Encryption Standard (AES) is also available as a block-level
benchmark, alongside the JPEG Encoder used above.

### 1:1 GR

| Metric | 0.10 | 0.12 | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 | 0.40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| #Insts | 11403 | 11036 | 10698 | 10200 | 10194 | 10199 | 10185 | 10184 |
| Wirelength (μm) | 30514 | 29937 | 29225 | 27459 | 27463 | 27599 | 27587 | 27774 |
| Total Power (mW) | 8.6 | 6.8 | 5.1 | 3.6 | 2.9 | 2.4 | 2.1 | 1.9 |
| Worst Negative Slack (ns) | -0.039 | -0.026 | -0.003 | 0.006 | 0.041 | 0.084 | 0.138 | 0.188 |
| Effective CLKP (ns) | 0.139 | 0.146 | 0.153 | 0.194 | 0.209 | 0.217 | 0.212 | 0.213 |
| Area (μm²) | 428 | 417 | 399 | 377 | 377 | 377 | 377 | 375 |

### 3:2 GR — 0-offset Only

| Metric | 0.10 | 0.12 | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 | 0.40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| #Insts | 11833 | 11531 | 11149 | 10580 | 10565 | 10553 | 10561 | 10559 |
| Wirelength (μm) | 29071 | 27217 | 26239 | 24702 | 24626 | 24429 | 24715 | 24488 |
| Total Power (mW) | 8.2 | 6.6 | 5.0 | 3.6 | 2.8 | 2.4 | 2.1 | 1.8 |
| Worst Negative Slack (ns) | -0.070 | -0.023 | -0.003 | 0.003 | 0.031 | 0.091 | 0.135 | 0.183 |
| Effective CLKP (ns) | 0.170 | 0.143 | 0.153 | 0.198 | 0.220 | 0.209 | 0.216 | 0.217 |
| Area (μm²) | 371 | 366 | 343 | 311 | 313 | 313 | 313 | 313 |

### 3:2 GR — Mixed-offset

| Metric | 0.10 | 0.12 | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 | 0.40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| #Insts | 11590 | 11507 | 11095 | 10576 | 10562 | 10578 | 10578 | 10557 |
| Wirelength (μm) | 27825 | 27130 | 26810 | 24930 | 25051 | 24656 | 25092 | 24661 |
| Total Power (mW) | 8.3 | 6.7 | 5.1 | 3.6 | 2.9 | 2.4 | 2.1 | 1.9 |
| Worst Negative Slack (ns) | -0.049 | -0.029 | -0.012 | 0.002 | 0.028 | 0.087 | 0.132 | 0.183 |
| Effective CLKP (ns) | 0.149 | 0.149 | 0.162 | 0.198 | 0.222 | 0.213 | 0.219 | 0.217 |
| Area (μm²) | 370 | 366 | 343 | 317 | 317 | 321 | 317 | 317 |

## Additional Block-Level Benchmark (CV32E40P)
CV32E40P is also available as a block-level
benchmark, alongside the AES and JPEG Encoder used above.

### 1:1 GR

| Metric | 0.10 | 0.12 | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 | 0.40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| #Insts | 44559 | 46561 | 47333 | 42784 | 38947 | 35246 | 32077 | 31584 |
| Wirelength (μm) | 123513 | 127678 | 133711 | 118789 | 111089 | 103743 | 100399 | 99035 |
| Total Power (mW) | 14.3 | 12.5 | 10.0 | 7.0 | 5.5 | 4.3 | 3.7 | 3.3 |
| Worst Negative Slack (ns) | -0.240 | -0.166 | -0.180 | -0.102 | -0.064 | -0.049 | -0.045 | -0.033 |
| Effective CLKP (ns) | 0.340 | 0.286 | 0.330 | 0.302 | 0.314 | 0.349 | 0.395 | 0.433 |
| Area (μm²) | 1648 | 1718 | 1740 | 1612 | 1499 | 1431 | 1377 | 1316 |

### 3:2 GR — 0-offset Only

| Metric | 0.10 | 0.12 | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 | 0.40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| #Insts | 45069 | 45435 | 48003 | 42391 | 38415 | 35783 | 32749 | 31917 |
| Wirelength (μm) | 112159 | 117463 | 121595 | 106806 | 97637 | 93494 | 91013 | 88701 |
| Total Power (mW) | 14.1 | 12.6 | 9.9 | 6.8 | 5.3 | 4.3 | 3.7 | 3.2 |
| Worst Negative Slack (ns) | -0.204 | -0.170 | -0.175 | -0.086 | -0.057 | -0.062 | -0.062 | -0.022 |
| Effective CLKP (ns) | 0.304 | 0.290 | 0.325 | 0.286 | 0.307 | 0.362 | 0.412 | 0.422 |
| Area (μm²) | 1495 | 1474 | 1544 | 1386 | 1304 | 1231 | 1191 | 1151 |

### 3:2 GR — Mixed-offset

| Metric | 0.10 | 0.12 | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 | 0.40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| #Insts | 42214 | 41858 | 42287 | 39162 | 36725 | 34967 | 31821 | 30956 |
| Wirelength (μm) | 107432 | 108416 | 107855 | 101144 | 95881 | 93596 | 91436 | 90185 |
| Total Power (mW) | 14.0 | 12.2 | 9.5 | 7.1 | 5.3 | 4.5 | 3.8 | 3.2 |
| Worst Negative Slack (ns) | -0.217 | -0.193 | -0.145 | -0.111 | -0.090 | -0.091 | -0.119 | -0.072 |
| Effective CLKP (ns) | 0.317 | 0.313 | 0.295 | 0.311 | 0.340 | 0.391 | 0.469 | 0.472 |
| Area (μm²) | 1376 | 1357 | 1369 | 1291 | 1231 | 1202 | 1151 | 1140 |

# Knowledge Reference
- OpenCores JPEG Encoder. \[[Link](https://opencores.org/projects/mkjpeg)\]
- OpenCores AES. \[[Link](https://opencores.org/projects/aes_core)\]
- CORE-V CV32E40P. \[[Link](https://docs.openhwgroup.org/projects/cv32e40p-user-manual/en/cv32e40p_v1.2.1/)\]
- Cadence Pegasus, Quantus and Voltus. \[[Link](https://cadence.com)\]
- Synopsys Design Compiler, IC Compiler II. \[[Link](https://synopsys.com)\]
