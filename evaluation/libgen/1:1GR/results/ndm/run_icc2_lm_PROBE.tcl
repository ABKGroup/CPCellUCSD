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

exec date >> timer

# read lib
set clib_name "6T_2F_45CPP_24M0P_45M1P_24M2P_2MPO_ET_M0"

set techfile ../6T_BEOL1_24_45_24_24_64_64_64_64_64_64_64_64_720_720.tf

set lef ../gdslefgen/6T_2F_45CPP_24M0P_45M1P_24M2P_2MPO_ET_M0/6T_2F_45CPP_24M0P_45M1P_24M2P_2MPO_ET_M0.lef

set lib [list ../lib/6T_2F_45CPP_24M0P_45M1P_24M2P_2MPO_ET_M0_tt_0.7_25_nldm.db]

if {[file exists "ndm"]} {
	exec rm -r ndm
}
exec mkdir ndm

create_workspace -technology $techfile -scale_factor 10000 -flow "physical_only" ${clib_name}

read_lef $lef
#read_db $lib

check_workspace
commit_workspace -force -output ndm/${clib_name}.ndm

exec date >> timer

exit
