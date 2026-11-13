`timescale 1ns/1ps
// =============================================================================
// dut_adapter.sv  -  Candidate 05d (DSP) self-contained Phase-4 port adapters.
//
// Identical in intent to infrastructure/adapters/recovered.sv, copied into the
// candidate's isolated source tree so the 05d manifests are self-contained and
// do not depend on another agent's working files. Instantiates whichever
// `fir_audio_top` is listed first in the manifest `sources` (baseline or Trojan;
// both expose the same port map, so the adapter is a drop-in for either).
// =============================================================================

// Phase 4 simulation DUT contract: phase4_dut(clk,rst,bclk,lrclk,sd_in,sd_out).
// No external reset exists in the recovered design; `rst` is hold-in-idle only
// (the testbench holds it while the I2S lines are idle, then deasserts).
module phase4_dut(input wire clk, rst, bclk, lrclk, sd_in, output wire sd_out);
    fir_audio_top dut(.ICE_CLK(clk), .I2S_BCLK(bclk), .I2S_WS(lrclk),
        .I2S_SD_IN(sd_in), .I2S_SD_OUT(sd_out),
        .ICE_LED(), .RGB_R(), .RGB_G(), .RGB_B());
endmodule

// Synthesis boundary: only the five VERIFIED audio/clock pins (audio-only build,
// not a full board image). LED/RGB roles remain provisional and are left open.
module phase4_audio_top(input wire ICE_CLK, I2S_BCLK, I2S_WS, I2S_SD_IN,
                        output wire I2S_SD_OUT);
    fir_audio_top dut(.ICE_CLK(ICE_CLK), .I2S_BCLK(I2S_BCLK), .I2S_WS(I2S_WS),
        .I2S_SD_IN(I2S_SD_IN), .I2S_SD_OUT(I2S_SD_OUT),
        .ICE_LED(), .RGB_R(), .RGB_G(), .RGB_B());
endmodule
