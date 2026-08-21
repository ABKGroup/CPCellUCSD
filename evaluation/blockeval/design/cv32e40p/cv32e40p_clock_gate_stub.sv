// Synthesis substitute for cv32e40p_clock_gate.
// The repo's only implementation (bhv/cv32e40p_sim_clock_gate.sv) is an
// always_latch-based gate explicitly marked "for simulation only, must not
// be used for ASIC synthesis" -- and our target library has no dedicated
// integrated-clock-gating cell to map it onto anyway. This pass-through
// disables clock gating entirely, keeping a single ungated clock net
// consistent with every other design benchmarked this session.
module cv32e40p_clock_gate (
    input  logic clk_i,
    input  logic en_i,
    input  logic scan_cg_en_i,
    output logic clk_o
);

  assign clk_o = clk_i;

endmodule
