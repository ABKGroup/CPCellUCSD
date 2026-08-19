exec date >> timer
set clib_name "6T_2F_45CPP_24M0P_22p5M1P_OF0_24M2P_2MPO_ET_M0"
set techfile ../6T_BEOL1_24_22.5_24_24_64_64_64_64_64_64_64_64_720_720.tf
set lef ../gdslefgen/6T_2F_45CPP_24M0P_22p5M1P_OF0_24M2P_2MPO_ET_M0/6T_2F_45CPP_24M0P_22p5M1P_OF0_24M2P_2MPO_ET_M0.lef

if {[file exists "ndm"]} {
	exec rm -r ndm
}
exec mkdir ndm

create_workspace -technology $techfile -scale_factor 10000 -flow "physical_only" ${clib_name}
read_lef $lef
check_workspace
commit_workspace -force -output ndm/${clib_name}.ndm
exec date >> timer
exit
