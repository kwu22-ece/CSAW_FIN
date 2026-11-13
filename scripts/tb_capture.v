`timescale 1ns/1ps
// Self-calibrating I2S capture testbench for the recovered iCE40 netlist.
// Drives the exact Philips-I2S waveform the RP2040 PIO produces (from
// audio_bridge.py), oversampled against ICE_CLK, and logs one line per BCLK
// rising edge: "<frame> <slot> <WS> <SD_IN> <SD_OUT>".
//
// Port map (verified: icebox sg48 pinloc DB + bridge GPIO comments):
//   io_13_31_0 = ICE_CLK (all 299 FFs + RAM clock)   pin37
//   io_9_31_1  = I2S_BCLK                             pin36
//   io_13_31_1 = I2S_WS                               pin34
//   io_16_31_0 = I2S_SD_IN                            pin32
//   io_16_31_1 = I2S_SD_OUT                           pin31
//   io_8_31_1,io_4_31_0,io_5_31_0,io_6_31_0 = LED/RGB pin38/39/40/41
module tb;
  localparam integer OSR   = 8;      // ICE_CLK cycles per BCLK half-period
  localparam integer MAXF  = 8192;   // max frames
  integer OSRH;

  reg ICE_CLK = 0;
  always #50 ICE_CLK = ~ICE_CLK;     // 10 MHz (100 ns period)

  reg  BCLK = 0, WS = 0, SD_IN = 0;
  wire SD_OUT, led, rr, gg, bb;

  chip dut (
    .io_13_31_0(ICE_CLK), .io_9_31_1(BCLK), .io_13_31_1(WS), .io_16_31_0(SD_IN),
    .io_16_31_1(SD_OUT), .io_8_31_1(led), .io_4_31_0(rr), .io_5_31_0(gg), .io_6_31_0(bb)
  );

  reg [15:0] lval [0:MAXF-1];
  reg [15:0] rval [0:MAXF-1];
  integer nframes, f, p, c, logfd;
  reg sdbit, wsbit;

  task step;  // advance one ICE_CLK cycle, drive strictly after the edge
    begin @(posedge ICE_CLK); #1; end
  endtask

  initial begin
    OSRH = OSR/2;
    for (f=0; f<MAXF; f=f+1) begin lval[f]=16'h0000; rval[f]=16'h0000; end
    $readmemh("stim_l.hex", lval);
    $readmemh("stim_r.hex", rval);
    if (!$value$plusargs("nframes=%d", nframes)) nframes = 64;
    logfd = $fopen("capture.txt", "w");

    BCLK=0; WS=0; SD_IN=0;
    repeat (64) step;                 // idle lead-in

    for (f=0; f<nframes; f=f+1) begin
      for (p=0; p<32; p=p+1) begin
        // SD_IN bit, MSB first: slots 0..15 = left[15..0], 16..31 = right[15..0]
        if (p < 16) sdbit = lval[f][15-p];
        else        sdbit = rval[f][15-(p-16)];
        // WS waveform from the PIO: low for L15..L1, high at L0 and R15..R1,
        // low at R0 (WS "changes one bit early", Philips standard).
        wsbit = (p >= 15 && p <= 30) ? 1'b1 : 1'b0;

        // BCLK low half: present data + WS (they change on BCLK falling edge)
        BCLK = 0; SD_IN = sdbit; WS = wsbit;
        repeat (OSR) step;
        // BCLK high half: FPGA samples on the rising edge; capture mid-high
        BCLK = 1;
        repeat (OSRH) step;
        $fwrite(logfd, "%0d %0d %b %b %b\n", f, p, WS, SD_IN, SD_OUT);
        repeat (OSR-OSRH) step;
      end
    end
    BCLK=0; WS=0; SD_IN=0;
    repeat (64) step;
    $fclose(logfd);
    $finish;
  end
endmodule
