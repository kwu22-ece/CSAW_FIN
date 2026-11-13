// Synthesizable toolchain smoke fixture, not an audio-filter baseline.
module infrastructure_counter(input wire clk, rst, output wire [3:0] led);
    reg [23:0] count;
    always @(posedge clk) begin
        if (rst) count <= 0;
        else count <= count + 1'b1;
    end
    assign led=count[23:20];
endmodule
