# This script was written and developed by ABKGroup students at UCSD. However, the underlying commands and reports are copyrighted by Cadence. 
# We thank Cadence for granting permission to share our research to help promote and foster the next generation of innovators.

set design jpeg_encoder

set qrc "PROBE_FS.tch"

set lib "6T_2F_45CPP_24M0P_27M1P_24M2P_2MPO_ET_M0_tt_0.7_25.lib"

create_library_set -name LS_wc -timing ./lib/$lib 
create_op_cond -name OC_wc -library_file ./lib/$lib -P 1 -V 0.7 -T 25
create_rc_corner -name RC_wc_25 -T 25 -qx_tech_file $qrc

create_delay_corner -name DC_wc\
   -rc_corner RC_wc_25\
   -library_set LS_wc\
   -opcond_library slow\
   -opcond OC_wc

update_delay_corner -name DC_wc -power_domain PD1\
   -library_set LS_wc\
   -opcond_library slow\
   -opcond OC_wc


# define constraints
create_constraint_mode -name CM_base -sdc_files [list ${design}.sdc]

# define views
create_analysis_view -name AV_wc_off -constraint_mode CM_base -delay_corner DC_wc
create_analysis_view -name AV_wc_on  -constraint_mode CM_base  -delay_corner DC_wc

# active views
set_analysis_view -setup [list AV_wc_on ] -hold [list AV_wc_on ]

