#!/bin/tcsh
set tcp="$argv[1]"
set util="$argv[2]"
set script_dir="./ref_flow"

set run_dir="./2F_6T_45CPP_45M1_ICC2_${tcp}_${util}"
cp -rf $script_dir ${run_dir}
cd $run_dir

./run.sh ${tcp} ${util}
