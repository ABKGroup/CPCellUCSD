#!/bin/tcsh
module load anaconda3
python3 gen_irdrop_plot.py --iv ./static_IR/core_25C_avg_1/Reports/VDD_VSS.avg.iv --def jpeg_encoder.def --lef 6T_2F_45CPP_24M0P_45M1P_24M2P_2MPO_ET_M0.lef --vmin 0.03 --vmax 0.076 --out irdrop.png
