#################################################################################################
#                                                                                               #
#     Portions Copyright © 2022 Synopsys, Inc. All rights reserved. Portions of                 #
#     these TCL scripts are proprietary to and owned by Synopsys, Inc. and may only             #
#     be used for internal use by educational institutions (including United States             #
#     government labs, research institutes and federally funded research and                    # 
#     development centers) on Synopsys tools for non-profit research, development,              #
#     instruction, and other non-commercial uses or as otherwise specifically set forth         #
#     by written agreement with Synopsys. All other use, reproduction, modification, or         #
#     distribution of these TCL scripts is strictly prohibited.                                 #
#                                                                                               #
#################################################################################################

create_workspace -flow edit ndm/6T_2F_45CPP_24M0P_30M1P_OF0_24M2P_2MPO_ET_M0.ndm
create_cell_group -name AND2_X1 [get_lib_cells AND2_X1_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
create_cell_group -name AND2_X2 [get_lib_cells AND2_X2_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
create_cell_group -name AOI21_X1 [get_lib_cells AOI21_X1_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
create_cell_group -name AOI21_X2 [get_lib_cells AOI21_X2_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
create_cell_group -name AOI22_X1 [get_lib_cells AOI22_X1_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
create_cell_group -name AOI22_X2 [get_lib_cells AOI22_X2_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
create_cell_group -name DFFHQN_X1 [get_lib_cells DFFHQN_X1_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
create_cell_group -name LHQ_X1 [get_lib_cells LHQ_X1_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
create_cell_group -name MUX2_X1 [get_lib_cells MUX2_X1_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
create_cell_group -name OAI21_X1 [get_lib_cells OAI21_X1_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
create_cell_group -name OAI21_X2 [get_lib_cells OAI21_X2_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
create_cell_group -name OAI22_X1 [get_lib_cells OAI22_X1_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
create_cell_group -name OAI22_X2 [get_lib_cells OAI22_X2_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
create_cell_group -name OR2_X1 [get_lib_cells OR2_X1_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
create_cell_group -name OR2_X2 [get_lib_cells OR2_X2_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
create_cell_group -name XOR2_X1 [get_lib_cells XOR2_X1_6T_2F_45CPP_24M0P_30M1P_OF*_24M2P_2MPO_ET_M0]
check_workspace
commit_workspace
exit
