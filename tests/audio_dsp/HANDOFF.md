# Phase T handoff for Project Scribe

Phase T exercises the original Challenge 3 FIR. FFmpeg decodes the first audio
stream to float, downmixes to mono and resamples to 16 kHz. The same headroom gain
is applied before saving clean, noise and noisy signed PCM16. The fixed-seed noise
matrix uses seed 2026. Input SNR uses the exact injected PCM difference. Output
SNR uses the pinned original FIR's filtered-clean PCM and measures the residual
against it. Stopband attenuation integrates Welch noise power from 4 to 8 kHz.

## Reproduce from the Phase T worktree

```text
python -m unittest discover -s tests/audio_dsp -v
python tests/audio_dsp/audio_test.py --input <local MP3> --noise highfreq --snr-db 10 --mode both
python tests/audio_dsp/batch_test.py --input <local MP3> --mode software --all-noise-types --duration 4
```

Validation used Windows Python 3.12.14 and FFmpeg n7.1-23-g4ea558152f.
The nine tests cover synthetic 48 kHz stereo MP3 decoding, mono resampling and
anti-aliasing, PCM arithmetic, reproducibility, silence, short or invalid inputs,
report generation, the hardware-host adapter with mocked subprocess results, and
the unchanged Phase 2 model's 256 golden sample comparisons. Phase 4 independently
reported 8,224 exact reconstructed-RTL output-word comparisons using that same model.

## Results

The user-supplied stereo MP3 yielded 145,506 samples at 16 kHz (9.094 s). The 6 kHz
interference run measured 10.00 dB input SNR, 65.07 dB software output SNR,
+55.07 dB SNR change, and 60.23 dB stopband attenuation. No PCM rail hits were
observed in the input, injected noise, noisy mix, or output. The delay-aligned
clean-only filter change was 0.00825 FS RMS.

The 20 software cases use the first 4 seconds, with the same clean amplitude in
all cases. The 10 dB cases improved SNR by 3.82 dB for white, 0.39 dB for pink,
52.36 dB for 6 kHz tone, 59.17 dB for multi-tone and 59.88 dB for band-limited
noise. See `matrix-summary.csv` for all levels. The full run's `report.md` links
`plots/waveforms.png`, `plots/spectrograms.png`, `plots/frequency.png`, and
`plots/performance.png` in the local run directory. Every batch case emits the
same plot set.

The physical FPGA and hardware/software comparison remain unverified. The local
serial inventory listed only Bluetooth ports. No board was programmed or streamed.
No software discrepancy remains open. Project Scribe's local evidence interface is
`record-test`. Its shared configuration has no usable synthesis model and Google
publishing is disabled.
