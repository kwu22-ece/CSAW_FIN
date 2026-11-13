`timescale 1ns/1ps
// Phase 2 v2 port map. No external reset exists; the supplied RTL owns POR.
module phase4_dut(input wire clk,rst,bclk,lrclk,sd_in, output wire sd_out);
    fir_audio_top dut(.ICE_CLK(clk),.I2S_BCLK(bclk),.I2S_WS(lrclk),
        .I2S_SD_IN(sd_in),.I2S_SD_OUT(sd_out),
        .ICE_LED(),.RGB_R(),.RGB_G(),.RGB_B());
endmodule

// Synthesis boundary contains only the five VERIFIED audio/clock pins.
// LED/RGB roles remain provisional; this is an audio-only build, not a full board image.
module phase4_audio_top(input wire ICE_CLK,I2S_BCLK,I2S_WS,I2S_SD_IN,
                        output wire I2S_SD_OUT);
    fir_audio_top dut(.ICE_CLK(ICE_CLK),.I2S_BCLK(I2S_BCLK),.I2S_WS(I2S_WS),
        .I2S_SD_IN(I2S_SD_IN),.I2S_SD_OUT(I2S_SD_OUT),
        .ICE_LED(),.RGB_R(),.RGB_G(),.RGB_B());
endmodule
