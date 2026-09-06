// Thin wrapper instantiating cv32e40p_top with COREV_PULP=1 (the PULP ISA
// extension config -- hardware loops + custom CSRs), matching the "with
// PULP extensions" configuration cited in the CV32E40P user manual.
// All ports pass straight through by name; only the parameter differs from
// the plain baseline top-level. Using a wrapper (rather than DC's
// elaborate -parameters) avoids DC renaming the elaborated design object,
// which broke the report/write steps in the shared run_dc.tcl.
module cv32e40p_top_pulp (
    input logic clk_i,
    input logic rst_ni,
    input logic pulp_clock_en_i,
    input logic scan_cg_en_i,
    input logic [31:0] boot_addr_i,
    input logic [31:0] mtvec_addr_i,
    input logic [31:0] dm_halt_addr_i,
    input logic [31:0] hart_id_i,
    input logic [31:0] dm_exception_addr_i,
    output logic instr_req_o,
    input logic instr_gnt_i,
    input logic instr_rvalid_i,
    output logic [31:0] instr_addr_o,
    input logic [31:0] instr_rdata_i,
    output logic data_req_o,
    input logic data_gnt_i,
    input logic data_rvalid_i,
    output logic data_we_o,
    output logic [ 3:0] data_be_o,
    output logic [31:0] data_addr_o,
    output logic [31:0] data_wdata_o,
    input logic [31:0] data_rdata_i,
    input logic [31:0] irq_i,
    output logic irq_ack_o,
    output logic [ 4:0] irq_id_o,
    input logic debug_req_i,
    output logic debug_havereset_o,
    output logic debug_running_o,
    output logic debug_halted_o,
    input logic fetch_enable_i,
    output logic core_sleep_o
);

  cv32e40p_top #(
      .COREV_PULP(1)
  ) dut (
      .clk_i(clk_i),
      .rst_ni(rst_ni),
      .pulp_clock_en_i(pulp_clock_en_i),
      .scan_cg_en_i(scan_cg_en_i),
      .boot_addr_i(boot_addr_i),
      .mtvec_addr_i(mtvec_addr_i),
      .dm_halt_addr_i(dm_halt_addr_i),
      .hart_id_i(hart_id_i),
      .dm_exception_addr_i(dm_exception_addr_i),
      .instr_req_o(instr_req_o),
      .instr_gnt_i(instr_gnt_i),
      .instr_rvalid_i(instr_rvalid_i),
      .instr_addr_o(instr_addr_o),
      .instr_rdata_i(instr_rdata_i),
      .data_req_o(data_req_o),
      .data_gnt_i(data_gnt_i),
      .data_rvalid_i(data_rvalid_i),
      .data_we_o(data_we_o),
      .data_be_o(data_be_o),
      .data_addr_o(data_addr_o),
      .data_wdata_o(data_wdata_o),
      .data_rdata_i(data_rdata_i),
      .irq_i(irq_i),
      .irq_ack_o(irq_ack_o),
      .irq_id_o(irq_id_o),
      .debug_req_i(debug_req_i),
      .debug_havereset_o(debug_havereset_o),
      .debug_running_o(debug_running_o),
      .debug_halted_o(debug_halted_o),
      .fetch_enable_i(fetch_enable_i),
      .core_sleep_o(core_sleep_o)
  );

endmodule
