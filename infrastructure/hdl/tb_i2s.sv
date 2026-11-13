`timescale 1ns/1ps
// A supplied phase4_dut adapter connects a recovered design. The fixture adapter
// is only a wire loopback and is never evidence of filter equivalence.
module tb_i2s;
    parameter integer SAMPLE_BITS=16, SLOT_BITS=32, MSB_DELAY=1, LEFT_LEVEL=0;
    parameter integer HALF_PERIOD_NS=500, CLOCK_HALF_NS=50, RESET_CYCLES=10;
    parameter integer MAX_WORDS=131072;
    wire bclk, lrclk, sd_in, sd_out;
    wire valid, channel;
    wire signed [SAMPLE_BITS-1:0] sample;
    reg clk=0, rst=1;
    reg [SAMPLE_BITS-1:0] vectors [0:MAX_WORDS-1];
    integer count, words, stream, output_index=0, status;
    reg [4095:0] vector_path, capture_path, wave_path;
    always #(CLOCK_HALF_NS) clk=~clk;
    i2s_driver #(.SAMPLE_BITS(SAMPLE_BITS),.SLOT_BITS(SLOT_BITS),.MSB_DELAY(MSB_DELAY),
        .LEFT_LEVEL(LEFT_LEVEL),.HALF_PERIOD_NS(HALF_PERIOD_NS)) driver(bclk,lrclk,sd_in);
    phase4_dut dut(.clk(clk),.rst(rst),.bclk(bclk),.lrclk(lrclk),.sd_in(sd_in),.sd_out(sd_out));
    i2s_monitor #(.SAMPLE_BITS(SAMPLE_BITS),.SLOT_BITS(SLOT_BITS),.MSB_DELAY(MSB_DELAY),
        .LEFT_LEVEL(LEFT_LEVEL)) monitor(bclk,lrclk,sd_out,valid,channel,sample);
    always @(posedge bclk) begin
        #1;
        if (valid && output_index < words) begin
            $fdisplay(stream,"%0d,%0d,%0d",output_index,channel,$signed(sample));
            output_index=output_index+1;
        end
    end
    initial begin
        if (!$value$plusargs("VECTORS=%s",vector_path) || !$value$plusargs("CAPTURE=%s",capture_path)
            || !$value$plusargs("WORDS=%d",words)) $fatal(1,"Missing VECTORS/CAPTURE/WORDS");
        if (words < 2 || words > MAX_WORDS || words % 2 != 0) $fatal(1,"Invalid word count");
        if (CLOCK_HALF_NS < 1 || RESET_CYCLES < 1) $fatal(1,"Invalid clock/reset timing");
        $readmemh(vector_path,vectors,0,words-1);
        for (count=0;count<words;count=count+1)
            if (^vectors[count] === 1'bx) $fatal(1,"Missing or unknown input vector");
        stream=$fopen(capture_path,"w");
        if (!stream) $fatal(1,"Cannot open capture");
        $fdisplay(stream,"index,channel,value");
        if ($value$plusargs("WAVE=%s",wave_path)) begin
            $dumpfile(wave_path); $dumpvars(0,tb_i2s);
        end
        repeat (RESET_CYCLES) @(negedge clk);
        rst=0;
        #2;
        for (count=0;count<words;count=count+1) driver.send_word(vectors[count],count%2);
        // Clock one extra slot to carry the last LSB when SLOT_BITS=SAMPLE_BITS.
        driver.send_word(0,0);
        #2;
        $fclose(stream);
        if (output_index != words) $fatal(1,"Incomplete capture %0d/%0d",output_index,words);
        $display("PHASE4_SIM_PASS words=%0d",words);
        $finish;
    end
    initial begin
        // Widen before multiplication: maximum-size traces exceed signed 32-bit ns.
        #(64'd2*(MAX_WORDS+4)*SLOT_BITS*HALF_PERIOD_NS +
          64'd2*RESET_CYCLES*CLOCK_HALF_NS + 1000000);
        $fatal(1,"Simulation watchdog expired");
    end
endmodule
