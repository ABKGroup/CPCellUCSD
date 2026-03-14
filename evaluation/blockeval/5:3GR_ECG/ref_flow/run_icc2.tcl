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

set_host_options -max_cores 8
set design jpeg_encoder
set clock_cycle $env(clock_period_center)
set lib_name 6T_2F_45CPP_24M0P_27M1P_OF0_24M2P_2MPO_ET_M0
set util $env(utility)
set pp "SPARSE"
set pdn "FS"
set beol _BEOL_
set pgpin M0
set m0p 24
set m1p 27
set m2p 24
set cpp 45
set cell_height 144
set insertion_type _METHOD_
set pitch 24

if {[file exists $design]} {
	exec chmod -R 777 $design
  exec rm -r $design
}

# read lib
set home "../../../libgen/5:3GR/results/"
set search_path ". $home"
set target_library_OF0 "$home/lib/6T_2F_45CPP_24M0P_27M1P_OF0_24M2P_2MPO_ET_M0_tt_0.7_25_nldm.db"
set target_library_OF9 "$home/lib/6T_2F_45CPP_24M0P_27M1P_OF9_24M2P_2MPO_ET_M0_tt_0.7_25_nldm.db"
set target_library_OF18 "$home/lib/6T_2F_45CPP_24M0P_27M1P_OF18_24M2P_2MPO_ET_M0_tt_0.7_25_nldm.db"

set link_library "* $target_library_OF0 $target_library_OF9 $target_library_OF18"
set techfile "$home/6T_BEOL1_24_27_24_24_64_64_64_64_64_64_64_64_720_720.tf"

set M0_offset 0.012
set M1_offset 0
set M2_offset 0.012
set tech_info "{M0 horizontal $M0_offset} {M1 vertical $M1_offset} {M2 horizontal $M2_offset} {M3 vertical 0.0} {M4 horizontal 0.0} {M5 vertical 0.0} {M6 horizontal 0.0} {M7 vertical 0.0} {M8 horizontal 0.0} {M9 vertical 0.0} {M10 horizontal 0.0} {M11 vertical 0.0} {M12 horizontal 0.0} {M13 vertical 0.0}"

set ndm  "$home/ndm/ndm/6T_2F_45CPP_24M0P_27M1P_OF0_24M2P_2MPO_ET_M0.ndm"
set tlup "$home/tlup/PROBE.tlup"

set runMode orig
set rptDir rpt_${runMode}/
set encDir enc_${runMode}/

if {![file exists $rptDir/]} {
    exec mkdir $rptDir/
}
if {![file exists $encDir/]} {
    exec mkdir $encDir/
}

create_lib $design -tech $techfile -ref_libs $ndm

read_verilog -top $design "./gate/${design}.v"
current_block $design
link_block
save_lib

connect_pg_net -automatic 
read_parasitic_tech -tlup $tlup -name wst

#scenario
remove_modes -all; remove_corners -all; remove_scenarios -all
set corner "WC"
create_mode $corner
create_corner $corner
create_scenario -name $corner -mode $corner -corner $corner
current_scenario $corner
source "./gate/$design\.sdc"
set_scenario_status $corner -none -setup true -hold true -leakage_power true -dynamic_power true -max_transition true -max_capacitance true -min_capacitance false -active true
set_parasitic_parameters -late_spec wst -early_spec wst

# floorplan
foreach direction_offset_pair $tech_info {
	set layer [lindex $direction_offset_pair 0]
	set direction [lindex $direction_offset_pair 1]
	set offset [lindex $direction_offset_pair 2]
	set_attribute [get_layers $layer] routing_direction $direction
	if {$offset != ""} {
		set_attribute [get_layers $layer] track_offset $offset
	}
}

set offset_v [expr [format %f $cpp]*5/1000]
set offset_h [expr [format %f $cell_height]*1/1000]
set core_offset [list $offset_v $offset_h]
initialize_floorplan -core_utilization ${util} -core_offset $core_offset

source ./pdn_icc2.tcl

place_pins -self 

set_app_options -as -list { place.coarse.continue_on_missing_scandef true }
set_app_options -name route.global.timing_driven -value true
set_extraction_options -reference_direction vertical
set_scenario_status -active true [all_scenarios]
set_voltage 0.70 -object_list [get_supply_nets VDD]
set_voltage 0.00 -object_list [get_supply_nets VSS]

#Placement option - BG
set_app_options -name place.legalize.enable_advanced_legalizer -value true
set_app_options -name place.legalize.enable_advanced_prerouted_net_check -value true
set_app_options -name place.legalize.pin_color_alignment_layers -value {M1}
set_app_options -name place.legalize.enable_pin_color_alignment_check -value true
# 
set_app_options -list { place.legalize.enable_variant_aware true}
##

#place_opt
place_opt -from initial_place -to initial_drc
update_timing -full
create_placement -incremental -timing_driven -congestion
place_opt -from initial_drc -to initial_opto
place_opt -from final_place -to final_opto

report_design -all > ./${rptDir}/place_design.rpt
report_qor  > ./${rptDir}/place_qor.rpt
report_power > ./${rptDir}/place_power.rpt
save_block -as $encDir/${design}_place.design

# ICC2 routing options
set_ignored_layers -min_routing_layer M0

set_app_options -list {route.common.single_connection_to_pins standard_cell_pins}
set_app_options -list {route.common.global_min_layer_mode hard}
set_app_options -list {route.common.net_min_layer_mode allow_pin_connection}
set_app_options -list {route.common.number_of_vias_under_global_min_layer 1}
set_app_options -list {route.common.number_of_vias_under_net_min_layer 0}
set_app_options -list {route.common.net_max_layer_mode hard}

set_app_options -list {route.detail.var_spacing_to_same_net true}
set_app_options -list {route.detail.check_pin_min_area_min_length true }
set_app_options -list {route.detail.check_port_min_area_min_length true}

# For offset eval, by DSY
set_app_options -list {route_opt.flow.size_only_mode footprint}
###

set die_size [get_attr [get_designs *] boundary_bbox]
create_routing_guide -boundary $die_size -layers {M0 M1 M2 M3 M4 M5 M6 M7 M8 M9 M10 M11} -preferred_direction_only

#CTS
set_app_options -name cts.common.user_instance_name_prefix -value "CTS_"
set_max_transition 0.70 -clock_path [get_clocks clk]

clock_opt -from build_clock -to route_clock
clock_opt -from route_clock -to final_opto

report_design -all > ./${rptDir}/cts_design.rpt
report_qor  > ./${rptDir}/cts_qor.rpt
report_power > ./${rptDir}/cts_power.rpt
save_block -as $encDir/${design}_cts.design

#ROUTE
route_opt -xtalk_reduction
save_block -as $encDir/${design}_route.design
check_routes > ./${rptDir}/drc.rpt

route_detail -incremental "true" -initial_drc_from_input "true"
save_block -as $encDir/${design}_route2.design
check_routes > ./${rptDir}/drc2.rpt

report_design -all > ./${rptDir}/route_design.rpt
report_qor  > ./${rptDir}/route_qor.rpt
report_power > ./${rptDir}/route_power.rpt
report_timing -nworst 1 -nosplit -nets -significant_digits 3 > ./${rptDir}/route_timing.rpt

write_parasitics -output $encDir/${design}.spef -format spef
write_def -version 5.8 $encDir/fc_$design\.def
write_verilog $encDir/fc_$design\_out.v

source gen_vsrc.tcl

exit

