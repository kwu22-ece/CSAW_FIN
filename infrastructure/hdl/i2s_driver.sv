`timescale 1ns/1ps
// Simulation-only controller. Changes SD/LR on falling edges, samples on rising.
// MSB_DELAY=1: Philips I2S; 0: left-justified. Both are explicit configuration.
module i2s_driver #(
    parameter integer SAMPLE_BITS=16, SLOT_BITS=32, MSB_DELAY=1,
    parameter integer LEFT_LEVEL=0, HALF_PERIOD_NS=500
)(output reg bclk=0, output reg lrclk=1-LEFT_LEVEL, output reg sd=0);
    reg [SAMPLE_BITS-1:0] previous_word=0;
    initial begin
        if (SAMPLE_BITS < 2 || SAMPLE_BITS > 32 || SLOT_BITS < SAMPLE_BITS ||
            SLOT_BITS > 256 || MSB_DELAY < 0 || MSB_DELAY > 1 ||
            LEFT_LEVEL < 0 || LEFT_LEVEL > 1 || HALF_PERIOD_NS < 1)
            $fatal(1, "Invalid I2S driver parameters");
    end

    task automatic send_word(input reg [SAMPLE_BITS-1:0] word, input integer channel);
        integer slot, offset;
        begin
            for (slot=0; slot<SLOT_BITS; slot=slot+1) begin
                bclk=0;
                lrclk=(channel == 0) ? LEFT_LEVEL : 1-LEFT_LEVEL;
                offset=slot-MSB_DELAY;
                if (offset < 0)
                    sd=(SLOT_BITS == SAMPLE_BITS) ? previous_word[0] : 0;
                else if (offset < SAMPLE_BITS)
                    sd=word[SAMPLE_BITS-1-offset];
                else sd=0;
                #(HALF_PERIOD_NS); bclk=1;
                #(HALF_PERIOD_NS);
            end
            previous_word=word;
        end
    endtask
endmodule
