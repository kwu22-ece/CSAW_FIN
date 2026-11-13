// Simulation-only wrapper: exposes the reconstructed fir_audio_top under the
// raw netlist port names (io_*), so the same tb_capture.v can drive both the
// gate-level netlist and this reconstruction unchanged.
`default_nettype none
module chip (
    input  io_13_31_0,   // ICE_CLK   (pin 37)
    output io_8_31_1,    // ICE_LED   (pin 38)
    output io_5_31_0,    // RGB_G     (pin 40)
    output io_6_31_0,    // RGB_B     (pin 41)
    output io_4_31_0,    // RGB_R     (pin 39)
    input  io_9_31_1,    // I2S_BCLK  (pin 36)
    input  io_13_31_1,   // I2S_WS    (pin 34)
    output io_16_31_1,   // I2S_SD_OUT(pin 31)
    input  io_16_31_0    // I2S_SD_IN (pin 32)
);
    fir_audio_top u_fir (
        .ICE_CLK   (io_13_31_0),
        .I2S_BCLK  (io_9_31_1),
        .I2S_WS    (io_13_31_1),
        .I2S_SD_IN (io_16_31_0),
        .I2S_SD_OUT(io_16_31_1),
        .ICE_LED   (io_8_31_1),
        .RGB_R     (io_4_31_0),
        .RGB_G     (io_5_31_0),
        .RGB_B     (io_6_31_0)
    );
endmodule
`default_nettype wire
