// Infrastructure fixture only. No reconstructed filter behavior is represented.
`timescale 1ns/1ps
module phase4_dut(input wire clk,rst,bclk,lrclk,sd_in, output wire sd_out);
    assign sd_out=sd_in;
endmodule
