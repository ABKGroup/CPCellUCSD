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

set top_layer M13

set outputFile "VDD.vsrc"
set output [open $outputFile "w"]

puts $output "*vsrc_name   x   y   layer_name"
set k 1

foreach box [get_attribute [get_vias -filter "cut_layer_names==V12" -of_objects VDD] bbox] {
	set LL [lindex $box 0]
	set UR [lindex $box 1]
	set llx [lindex $LL 0]
	set lly [lindex $LL 1]
	set urx [lindex $UR 0]
	set ury [lindex $UR 1]
	set x [expr ($llx + $urx) / 2]
	set y [expr ($lly + $ury) / 2]
	set out "VDDvsrc${k} $x $y $top_layer"
	puts $output $out
        incr k
}

close $output

set outputFile_vss "VSS.vsrc"
set output_vss [open $outputFile_vss "w"]

puts $output_vss "*vsrc_name   x   y   layer_name"
set k 1

foreach box [get_attribute [get_vias -filter "cut_layer_names==V12" -of_objects VSS] bbox] {
	set LL [lindex $box 0]
	set UR [lindex $box 1]
	set llx [lindex $LL 0]
	set lly [lindex $LL 1]
	set urx [lindex $UR 0]
	set ury [lindex $UR 1]
	set x [expr ($llx + $urx) / 2]
	set y [expr ($lly + $ury) / 2]
	set out "VSSvsrc${k} $x $y $top_layer"
	puts $output_vss $out
        incr k
}

close $output_vss

