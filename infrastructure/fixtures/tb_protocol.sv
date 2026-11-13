`timescale 1ns/1ps
// Hand-derived 4-bit I2S wire sequence: A,5,C,3; final slot carries the last LSB.
// This checks driver wire timing and monitor decoding independently of loopback.
module tb_protocol;
    wire dbclk, dlr, dsd;
    reg bclk=0, lr=1, sd=0;
    wire valid, channel;
    wire signed [3:0] sample;
    reg [19:0] literal_bits=20'b0101_0010_1110_0001_1000;
    reg [15:0] expected=16'ha5c3;
    integer i, received=0, driven=0, fault=0;
    i2s_driver #(.SAMPLE_BITS(4),.SLOT_BITS(4),.HALF_PERIOD_NS(10)) driver(dbclk,dlr,dsd);
    i2s_monitor #(.SAMPLE_BITS(4),.SLOT_BITS(4)) monitor(bclk,lr,sd,valid,channel,sample);
    always @(posedge dbclk) begin
        if (dsd !== literal_bits[19-driven]) $fatal(1,"Driver wire bit differs at %0d",driven);
        if (dlr !== ((driven/4)%2)) $fatal(1,"Driver LR transition differs");
        driven=driven+1;
    end
    initial begin
        #2;
        driver.send_word(4'ha,0); driver.send_word(4'h5,1);
        driver.send_word(4'hc,0); driver.send_word(4'h3,1); driver.send_word(0,0);
    end
    initial begin
        if ($value$plusargs("FAULT=%d",fault)) begin end
        #3;
        for (i=0;i<20;i=i+1) begin
            bclk=0; lr=(i/4)%2; sd=literal_bits[19-i];
            if (fault==1 && i==2) sd=1'bx;
            if (fault==2 && i==3) lr=1;
            if (fault==3 && i>=4) lr=0;
            #10; bclk=1; #1;
            if (valid) begin
                if (sample !== expected[15-received*4 -: 4] || channel !== (received%2))
                    $fatal(1,"Monitor literal decode differs");
                received=received+1;
            end
            #9;
        end
        if (received != 4 || driven != 20) $fatal(1,"Incomplete protocol test");
        $display("PROTOCOL_PASS"); $finish;
    end
endmodule
