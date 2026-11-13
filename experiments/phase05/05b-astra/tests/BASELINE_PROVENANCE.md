# Baseline provenance

The unmodified source in rtl/baseline/fir_audio_top.v is copied from Phase 3 commit 5dedf4c4ed10f47fbe9ec138c7db2019446cdb7f. This candidate worktree starts at frozen Phase 4 commit e72522f265ac36da713cd7a0dcf8dbc64ab21209.

The Phase 3 handoff records Philips I2S, 16-bit MSB-first, two-frame output latency, filtered left output, unchanged right echo, and 63-tap Q1.15 arithmetic. It describes a behavioral reconstruction, not a gate-level copy. Baseline RTL, reference model, coefficients, and canonical vectors are copied unchanged. Simulation uses the direct-wire reset-less adapter already validated by the Phase 4 framework at infrastructure/adapters/recovered.sv.
The generic simulation explicitly uses 16 BCLK periods per channel slot with Philips one-bit MSB delay, matching the recovered design's successful Phase 4 integration configuration. The generic runner default is 32 BCLK periods and is not compatible with this reconstructed 16-bit-slot receiver.
