`timescale 1ns/1ps
// =============================================================================
// trojan_adapter.sv - Phase 5C candidate C simulation/synthesis adapters.
// Candidate-local copy (does NOT modify the shared infrastructure adapter).
// Phase 2 v2 port map. No external reset exists; the supplied RTL owns POR.
// =============================================================================

// Simulation DUT boundary expected by the Phase 4 harness (rst unused: POR-only).
module phase4_dut(input wire clk, rst, bclk, lrclk, sd_in, output wire sd_out);
    fir_audio_top #(.TROJAN_EN(1)) dut(
        .ICE_CLK(clk), .I2S_BCLK(bclk), .I2S_WS(lrclk),
        .I2S_SD_IN(sd_in), .I2S_SD_OUT(sd_out),
        .ICE_LED(), .RGB_R(), .RGB_G(), .RGB_B());
endmodule

// Audio-only synthesis top (five VERIFIED audio/clock pins), Trojan present.
module phase4_audio_top(input wire ICE_CLK, I2S_BCLK, I2S_WS, I2S_SD_IN,
                        output wire I2S_SD_OUT);
    fir_audio_top #(.TROJAN_EN(1)) dut(
        .ICE_CLK(ICE_CLK), .I2S_BCLK(I2S_BCLK), .I2S_WS(I2S_WS),
        .I2S_SD_IN(I2S_SD_IN), .I2S_SD_OUT(I2S_SD_OUT),
        .ICE_LED(), .RGB_R(), .RGB_G(), .RGB_B());
endmodule

// Clean reference top (TROJAN_EN=0): the added logic is dead-code eliminated,
// recovering the exact baseline. Used only for the resource/equivalence delta.
module phase4_audio_top_clean(input wire ICE_CLK, I2S_BCLK, I2S_WS, I2S_SD_IN,
                              output wire I2S_SD_OUT);
    fir_audio_top #(.TROJAN_EN(0)) dut(
        .ICE_CLK(ICE_CLK), .I2S_BCLK(I2S_BCLK), .I2S_WS(I2S_WS),
        .I2S_SD_IN(I2S_SD_IN), .I2S_SD_OUT(I2S_SD_OUT),
        .ICE_LED(), .RGB_R(), .RGB_G(), .RGB_B());
endmodule
