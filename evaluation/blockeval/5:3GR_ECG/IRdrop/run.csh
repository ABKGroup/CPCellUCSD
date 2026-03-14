#!/usr/bin/env tcsh

if (! -d log/) then
    mkdir log/
endif

voltus -no_logv -init run_voltus.tcl
