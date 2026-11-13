`timescale 1ns/1ps
// Independent edge-based decoder; valid marks one signed sample and its channel.
module i2s_monitor #(
    parameter integer SAMPLE_BITS=16, SLOT_BITS=32, MSB_DELAY=1, LEFT_LEVEL=0
)(input wire bclk, lrclk, sd,
  output reg valid=0, output reg channel=0,
  output reg signed [SAMPLE_BITS-1:0] sample=0);
    reg previous_lr=1-LEFT_LEVEL;
    reg active=0, word_channel=0, synchronized=0;
    reg [SAMPLE_BITS-1:0] shift=0;
    integer bits=0, since_boundary=0;
    initial begin
        if (SAMPLE_BITS < 2 || SAMPLE_BITS > 32 || SLOT_BITS < SAMPLE_BITS ||
            SLOT_BITS > 256 || MSB_DELAY < 0 || MSB_DELAY > 1 ||
            LEFT_LEVEL < 0 || LEFT_LEVEL > 1) $fatal(1, "Invalid monitor parameters");
    end
    always @(posedge bclk) begin
        valid=0;
        if (lrclk !== 0 && lrclk !== 1) $fatal(1, "Unknown LRCLK");
        if (synchronized) since_boundary=since_boundary+1;
        if (lrclk != previous_lr) begin
            if (synchronized && since_boundary != SLOT_BITS)
                $fatal(1, "Unexpected LRCLK slot length: %0d", since_boundary);
            synchronized=1; since_boundary=0;
            if (MSB_DELAY == 0) begin
                if (active) $fatal(1, "Truncated sample");
                active=1; bits=0; shift=0; word_channel=(lrclk != LEFT_LEVEL);
            end
        end else if (synchronized && since_boundary >= SLOT_BITS)
            $fatal(1, "Missing LRCLK transition");
        if (active) begin
            if (sd !== 0 && sd !== 1) $fatal(1, "Unknown serial sample bit");
            shift={shift[SAMPLE_BITS-2:0],sd};
            bits=bits+1;
            if (bits == SAMPLE_BITS) begin
                sample=shift; channel=word_channel; valid=1; active=0;
            end
        end
        if (MSB_DELAY == 1 && lrclk != previous_lr) begin
            if (active) $fatal(1, "Truncated I2S sample");
            active=1; bits=0; shift=0; word_channel=(lrclk != LEFT_LEVEL);
        end
        previous_lr=lrclk;
    end
endmodule
