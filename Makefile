################################################
# Tool config                                  #
################################################
KLAYOUT=$(shell which klayout)
# Tools
PYTHON=$(shell which python3)
# GDT to GDS (See PROBE3 for installation)
GDT2GDS=/usr/local/bin/gdt2gds.Linux
# GDS to GDT (See PROBE3 for installation)
GDS2GDT=/usr/local/bin/gds2gdt.Linux
#######################^########################
#^ Input config                               ^#
#######################^########################
CHANNEL=2F
CELL_PREFIX=PROBE3

TECH=FinFET
HEIGHT_CONFIG=SH

TRACK=4
CPP=45
M1P=30
M1OF=0

LIBNAME=$(CELL_PREFIX)_$(TECH)_$(CHANNEL)_$(TRACK)T_$(CPP)$(M1P)OF$(M1OF)
# DEBUG (might blow up your storage)
FLAG_LOG_CONSTR=False
CDL_FILE=./input/cdl/PROBE3_2F4T.cdl
OUT_DIR=./output/$(LIBNAME)/$(HEIGHT_CONFIG)
LAYER_FILE=./input/config/$(LIBNAME).layer
################################################
# Cell config                                  #
################################################
# Complete Library (List your cell here)
CELL_NAME=INV_X1 INV_X2 INV_X4 INV_X8 AND2_X1 AND2_X2 AND3_X1 AND3_X2 \
OR2_X1 OR2_X2 OR3_X1 OR3_X2 NAND2_X1 NAND2_X2 NAND3_X1 NAND3_X2 NAND4_X1 NAND4_X2 \
NOR2_X1 NOR3_X1 NOR4_X1 NOR2_X2 NOR3_X2 NOR4_X2 \
AOI21_X1 AOI21_X2 OAI21_X1 OAI21_X2 AOI22_X1 AOI22_X2 OAI22_X1 OAI22_X2 \
XOR2_X1 MUX2_X1 BUF_X1 BUF_X2 BUF_X4 BUF_X8 DFFHQN_X1 LHQ_X1
# Scalability Test
# CELL_NAME=2BDFFHQN_X1 BUF_X16 DFFRNQ_X1 DFFHQNx3_ASAP7_75t_R DFFHQNx4_ASAP7_75t_R
################################################
# Commands to run SMTCell flow                 #
################################################
smtcell_config:
	mkdir -p $(OUT_DIR)/config
	$(QUEUE) $(PYTHON) -m src.utility.config --track $(TRACK) --tech $(TECH) --height_config $(HEIGHT_CONFIG) --cell_names $(CELL_NAME) --output_dir $(OUT_DIR)

smtcell_spnr: 
	mkdir -p $(OUT_DIR)
	mkdir -p $(OUT_DIR)/result
	mkdir -p $(OUT_DIR)/logs
	mkdir -p $(OUT_DIR)/constraint
	mkdir -p $(OUT_DIR)/view
	$(foreach CELL,$(CELL_NAME),\
		$(QUEUE) $(PYTHON) -m src.main --mode spnr --tech $(TECH) --layer $(LAYER_FILE) --lib_name $(LIBNAME) --track $(TRACK) --height_config $(HEIGHT_CONFIG) --cell_config $(OUT_DIR)/config/$(CELL).json --netlist $(CDL_FILE) --cell_names $(CELL) 2>&1 --output_dir $(OUT_DIR) --flag_log_constraints $(FLAG_LOG_CONSTR) | tee $(OUT_DIR)/logs/$(CELL).log;\
		$(QUEUE) ./src/utility/drop_prev.sh $(OUT_DIR)/constraint/$(CELL).log > $(OUT_DIR)/constraint/$(CELL)_clean.log;\
		rm -f $(OUT_DIR)/constraint/$(CELL).log;)

smtcell_gds:
	mkdir -p $(OUT_DIR)/gds
	$(foreach CELL,$(CELL_NAME),\
		$(QUEUE) $(PYTHON) -m src.gds.gds_$(TECH)_$(HEIGHT_CONFIG) --result_file $(OUT_DIR)/result/$(CELL).res --subckt_name $(CELL) --gds_file $(OUT_DIR)/gds/$(LIBNAME).gds;)
	make m0_pin

m0_pin:
	$(PYTHON) src/utility/relocatePin.py \
	--input_gds $(OUT_DIR)/gds/$(LIBNAME).gds \
	--output_gds $(OUT_DIR)/gds/$(LIBNAME).gds

gds_to_gdt:
	mkdir -p $(OUT_DIR)/gdt
	$(GDS2GDT) $(OUT_DIR)/gds/$(LIBNAME).gds -o $(OUT_DIR)/gdt/$(LIBNAME).gdt

gdt_to_gds:
	mkdir -p $(OUT_DIR)/gds
	$(GDT2GDS) $(OUT_DIR)/gdt/$(LIBNAME).gdt -o $(OUT_DIR)/gds/$(LIBNAME).gds

smtcell_lef:
	make gds_to_gdt
	mkdir -p $(OUT_DIR)/lef
	$(PYTHON) src/utility/genLEF.py \
	$(OUT_DIR)/gdt/$(LIBNAME).gdt \
	$(OUT_DIR)/lef/$(LIBNAME).lef

viewstatus:
	@for CELL in $(CELL_NAME); do \
	  printf "%s\t\t%s\t\t%s\t\t%s\n" \
	    $$CELL \
	    "$$(grep -E "Elapsed time" $(OUT_DIR)/logs/$(CELL_PREFIX)_$${CELL}.log | awk '{print $$7}')" \
	    "$$(grep -E -m 1 "status: "   $(OUT_DIR)/logs/$(CELL_PREFIX)_$${CELL}.log | awk '{print $$2}')" \
		"$$(grep -E -m 1 "Obj#1 obj_cpp              = " $(OUT_DIR)/logs/$(CELL_PREFIX)_$${CELL}.log | awk '{print $$4}')" ; \
	done

viewcell:
	mkdir -p $(OUT_DIR)/view
	$(foreach CELL,$(CELL_NAME),\
		$(QUEUE) $(PYTHON) -m src.visual.visualize_$(TECH)_$(TRACK)T $(OUT_DIR)/result/$(CELL).res $(OUT_DIR)/view/$(CELL).png;)

check_duplicate_vars:
	mkdir -p $(OUT_DIR)/debug
	$(foreach CELL,$(CELL_NAME),\
		sort $(OUT_DIR)/result/$(CELL_PREFIX)_$(CELL).var | uniq -d > $(OUT_DIR)/debug/$(CELL)_duplicate_vars.txt;)