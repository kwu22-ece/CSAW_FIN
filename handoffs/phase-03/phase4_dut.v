// =============================================================================
// phase4_dut.v  -  Phase 3 -> Phase 4 port adapter
//
// Wraps the verified reconstructed baseline (recovered/rtl/fir_audio_top.v) in
// the exact interface the Phase 4 infrastructure expects (see Codex handoff
// handoffs/phase-04/STATUS.md, "Adapter contract"):
//
//     module phase4_dut(input clk, rst, bclk, lrclk, sd_in, output sd_out);
//
// Port mapping (verified in Phase 2 §2, cross-checked against the challenge
// bridge firmware audio_bridge.py GPIO comments):
//     clk    -> ICE_CLK    (pin 37, ~10 MHz free-running system clock)
//     bclk   -> I2S_BCLK   (pin 36, oversampled; data, not a clock domain)
//     lrclk  -> I2S_WS     (pin 34, word select: 0=left, 1=right)
//     sd_in  -> I2S_SD_IN  (pin 32, MSB-first serial sample)
//     sd_out -> I2S_SD_OUT (pin 31, left=filtered, right=echo)
//
// RESET POLICY (verified):
//   The recovered original design is RESET-LESS. It establishes its state from
//   power-up only: every iCE40 FF and the sample-delay BRAM power up to 0 (the
//   bitstream carries those power-up values; the reconstruction mirrors this
//   with `initial` blocks). There is no reset net in the recovered netlist.
//
//   To satisfy the Phase 4 boundary, this adapter accepts an active-high `rst`
//   and uses it ONLY to reproduce the power-up alignment: the Phase 4 driver
//   should assert `rst` while the I2S lines are idle (bclk=lrclk=sd_in=0) and
//   deassert it before the first frame. During reset the core sees idle inputs,
//   which is exactly its power-up/idle condition, and sd_out is held at its
//   power-up value 0. The core is NOT re-initialized mid-stream, because the
//   original hardware has no such capability; re-aligning requires toggling the
//   board power/configuration, modeled here as the rst-then-idle window.
//
//   `rst` is therefore observed (held-in-idle semantics) but not wired as a
//   synchronous clear into the core, so no behavior is invented that the
//   recovered design does not have.
//
// Compile this file together with recovered/rtl/fir_audio_top.v.
// =============================================================================
`default_nettype none

module phase4_dut (
    input  wire clk,     // ICE_CLK  (~10 MHz)
    input  wire rst,     // active-high; assert during idle to model power-up
    input  wire bclk,    // I2S bit clock (oversampled)
    input  wire lrclk,   // I2S word select (0=left, 1=right)
    input  wire sd_in,   // serial data in (MSB first)
    output wire sd_out   // serial data out (left=filtered, right=echo)
);
    // During reset the driver holds the I2S lines idle; force the core's view
    // of the inputs to the idle level so an early/partial rst pulse cannot inject
    // a spurious edge. This changes nothing when the driver already idles the
    // lines during rst (the documented, verified usage).
    wire bclk_i  = rst ? 1'b0 : bclk;
    wire lrclk_i = rst ? 1'b0 : lrclk;
    wire sd_in_i = rst ? 1'b0 : sd_in;

    wire sd_out_core;
    // sd_out powers up to 0; during reset present that power-up level.
    assign sd_out = rst ? 1'b0 : sd_out_core;

    // Unused status LEDs at this boundary (kept to avoid dangling core outputs).
    wire ice_led, rgb_r, rgb_g, rgb_b;

    fir_audio_top u_core (
        .ICE_CLK    (clk),
        .I2S_BCLK   (bclk_i),
        .I2S_WS     (lrclk_i),
        .I2S_SD_IN  (sd_in_i),
        .I2S_SD_OUT (sd_out_core),
        .ICE_LED    (ice_led),
        .RGB_R      (rgb_r),
        .RGB_G      (rgb_g),
        .RGB_B      (rgb_b)
    );

    // Silence "unused" lint without affecting logic.
    wire _unused = &{1'b0, ice_led, rgb_r, rgb_g, rgb_b, 1'b0};

endmodule

`default_nettype wire
