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

set_host_options -max_cores 16
set top_module jpeg_encoder 
set tl_list [list ../../../libgen/5:3GR/results/lib/6T_2F_45CPP_24M0P_27M1P_OF0_24M2P_2MPO_ET_M0_tt_0.7_25_nldm.db]
set ll_list ""

set link_library $ll_list
set target_library $tl_list
set symbol_library {}
set wire_load_model ""
set wire_load_mode enclosed
set timing_use_enhanced_capacitance_modeling true

set search_path [concat $search_path ]
set dont_use_cells 1
set dont_use_cell_list ""

set synthetic_library {}
set link_path [concat  $link_library $synthetic_library]

# Start
sh date
sh echo hostname
sh echo uptime

remove_design -all
if {[file exists template]} {
	sh rm -rf template
}
sh mkdir template
if {![file exists gate]} {
	sh mkdir gate
}
if {![file exists log]} {
	sh mkdir log
}

# Compiler drectives
set compile_effort   "high"
set compile_flatten_all 1
set compile_no_new_cells_at_top_level false

#set hdlin_infer_multibit default_all
set hdlin_enable_vpp true
set hdlin_auto_save_templates false
if {$top_module == "dec_viterbi"} {
  define_design_lib dec_viterbi -path .template
} else {
  define_design_lib WORK -path .template
}
set verilogout_single_bit false
set enforce_input_fanout_one     0

# read RTL

source ./for_dc.tcl

foreach rtl_file $rtl_all {
    if {$top_module == "dec_viterbi"} {
        analyze -format vhdl -lib dec_viterbi $rtl_file
    } else {
        analyze -format verilog -lib WORK $rtl_file
    }
}
if {$top_module == "dec_viterbi"} {
    elaborate $top_module -lib dec_viterbi -update
} else {
    elaborate $top_module -lib WORK -update
}

current_design $top_module

# Link Design
set dc_shell_status [ link ]
if {$dc_shell_status == 0} {
	echo "****************************************************"
	echo "* ERROR!!!! Failed to Link...exiting prematurely.  *"
	echo "****************************************************"
	#exit
}

# Default SDC Constraints
read_sdc ./$top_module\.sdc

# Environment and compile options 
set_max_area 0
set_leakage_optimization true

# Input Fanout Control
if {[info exists enforce_input_fanout_one] && ($enforce_input_fanout_one  == 1)} {
	set_max_fanout 1 $non_ideal_inputs
}

# More constraints and setup before compile
foreach_in_collection design [ get_designs "*" ] {
	current_design $design
	set_fix_multiple_port_nets -all
}
current_design $top_module

set_fix_hold [all_clocks]

# Compile

if {[info exists compile_flatten_all] && ($compile_flatten_all  == 1)} {
	ungroup -flatten -all
}
set_fix_multiple_port_nets -all

set dc_shell_status [ compile_ultra -scan -no_autoungroup -timing_high_effort_script  -exact_map ]

if {$dc_shell_status == 0} {
	echo "*******************************************************"
	echo "* ERROR!!!! Failed to compile...exiting prematurely.  *"
	echo "*******************************************************"
	exit
}
sh date

sh date
current_design $top_module
change_names -rules verilog -hierarchy

if {[info exists use_physopt] && ($use_physopt == 1)} {
	write -format verilog -hier -output [format "%s%s%s" gate/ $top_module _hier_fromdc.v]
} else {
	write -format verilog -hier -output [format "%s%s%s" gate/ $top_module .v]
}

current_design $top_module
write_sdc [format "%s%s%s" gate/ $top_module .sdc]

# Write Reports
redirect [format "%s%s%s" log/ $top_module _area.rep] { report_area }
redirect -append [format "%s%s%s" log/ $top_module _area.rep] { report_reference }
redirect [format "%s%s%s" log/ $top_module _cell.rep] { report_cell }
redirect [format "%s%s%s" log/ $top_module _design.rep] { report_design }
redirect [format "%s%s%s" log/ $top_module _power.rep] { report_power }
redirect [format "%s%s%s" log/ $top_module _timing.rep] \
  { report_timing -path full -max_paths 100 -nets -transition_time -capacitance -significant_digits 3}
redirect [format "%s%s%s" log/ $top_module _check_timing.rep] { check_timing }
redirect [format "%s%s%s" log/ $top_module _check_design.rep] { check_design }


set inFile  [open log/$top_module\_area.rep]
while { [gets $inFile line]>=0 } {
    if { [regexp {Total cell area:} $line] } {
        set AREA [lindex $line 3]
    }
}
close $inFile
set inFile  [open log/$top_module\_power.rep]
while { [gets $inFile line]>=0 } {
    if { [regexp {Total Dynamic Power} $line] } {
        set PWR [lindex $line 4]
    } elseif { [regexp {Cell Leakage Power} $line] } {  
        set LEAK [lindex $line 4] 
    }
}
close $inFile

set path    [get_timing_path -nworst 1]
set WNS     [get_attribute $path slack]

set outFile [open result_dc.rpt w]
puts $outFile "$AREA\t$WNS\t$PWR\t$LEAK"
close $outFile

# Check Design and Detect Unmapped Design
set unmapped_designs [get_designs -filter "is_unmapped == true" $top_module]
if {  [sizeof_collection $unmapped_designs] != 0 } {
	echo "****************************************************"
	echo "* ERROR!!!! Compile finished with unmapped logic.  *"
	echo "****************************************************"
	exit
}
# Done
sh date
sh uptime
echo "run.scr completed successfully"

exit
