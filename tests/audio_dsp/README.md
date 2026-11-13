# Phase T · Original audio FIR testing

The pipeline decodes an MP3, injects reproducible noise, calls the verified original FIR
reference, and writes aligned audio, numerical results, and plots. Hardware mode uses
the official Hackster host and bridge. The Phase 2 model and reconstructed RTL are
owned by their original phases.

## Install

Use Python 3.11 or later, Git, and FFmpeg. From the repository root:

```powershell
python -m pip install -r tests/audio_dsp/requirements.txt
git fetch origin challenge3/02-reverse-engineering
```

The fetch is needed only if the pinned Phase 2 commit is absent. The pipeline reads
the model and Q1.15 coefficients from immutable Git blobs. It records their commit and
hashes. The tests compare the model against the pinned original-bitstream vectors.
The synthetic MP3 fixture generator requires an FFmpeg build with `libmp3lame`.

## Run

```powershell
python tests/audio_dsp/audio_test.py --input "C:/Music/recording.mp3" --noise white --snr-db 10
python tests/audio_dsp/audio_test.py --input "C:/Music/recording.mp3" --noise highfreq --frequency 6000 --snr-db 10
python tests/audio_dsp/audio_test.py --input "C:/Music/recording.mp3" --noise multitone --frequency 5000 --frequency 7000 --noise-amplitude 0.04 --start 2 --duration 5
python tests/audio_dsp/audio_test.py --input "C:/Music/recording.mp3" --noise bandlimited --band 4500 7500 --seed 2026
python tests/audio_dsp/batch_test.py --input "C:/Music/recording.mp3" --mode software --all-noise-types --duration 4
python tests/audio_dsp/batch_test.py --input "C:/Music/recording.mp3" --noise white --noise pink --snr-db 20 10 --max-cases 3
python -m unittest discover -s tests/audio_dsp -v
```

Use `--ffmpeg "C:/path/to/ffmpeg.exe"` if FFmpeg is outside PATH. For tests, set
`AUDIO_TEST_FFMPEG` to that executable. The default segment is the full file. The
default noise is white at 20 dB SNR and seed 2026. `--noise-amplitude` gives RMS in
full-scale units before common gain and takes the place of a target SNR. The matrix
defaults to all five noise types at 30, 20, 10, and 0 dB. It uses one common clean WAV
amplitude and reuses the filtered clean reference across cases.

## Physical Hackster

Identify the programmer and application ports with `python -m serial.tools.list_ports -v`.
Confirm that the board is free. From the official challenge's `fpga` directory, load
the supplied bitstream using its Makefile or its direct Windows equivalent:

```powershell
make run_fpga FPGA_PORT=COM4
python hackster-fpga-program.py w fir_audio_top.bin COM4
```

Here COM4 is an example programmer port. In the command below COM3 is an example
application port. The checked-out official challenge directory contains both host
scripts and the original bitstream. Set `--confirm-stock` only after confirming the
board is free and that this bitstream has been loaded.

```powershell
python tests/audio_dsp/audio_test.py --input "C:/Music/recording.mp3" --mode both --noise pink --snr-db 20 --challenge-dir "C:/src/CSAW-AI-Hardware-Attack-Challenge-2026/finals/challenge_3" --port COM3 --confirm-stock
```

The pipeline checks the stock file hash and streams a Phase 2 golden probe through
the board before streaming audio. The probe must match every sample and pass echo
validation. The stock host flushes old samples and handles the two-frame delay and
drain, including across USB chunks. Phase T checks echo diagnostics and the exact
WAV format and length. The 31-sample FIR group delay is retained in all filter outputs.
`--mode hardware` uses the software reference for the clean SNR baseline and writes
the hardware result. `--mode both` also writes the software result and a direct
sample comparison. A `both` batch checks one hardware case by default. Set
`--hardware-cases N` to increase coverage. Hardware-only batches stream all selected
cases, with a single stock probe. Absent or busy hardware produces exit 2 and any
requested software analysis is completed. A failed probe, corrupt capture, or
sample disagreement produces exit 1. Successful requested checks produce exit 0.

See the official [FPGA interface documentation](https://github.com/JBlocklove/CSAW-AI-Hardware-Attack-Challenge-2026/blob/main/finals/challenge_3/ice40_audio_filter_IP.md)
and [host/programming instructions](https://raw.githubusercontent.com/JBlocklove/CSAW-AI-Hardware-Attack-Challenge-2026/main/finals/challenge_3/README.md).

## Measurements and artifacts

- FFmpeg maps the first audio stream to 16 kHz mono float PCM with its channel-layout-aware rematrixing. One gain, capped at unity, gives up to 0.99 full-scale peak headroom for clean audio, noise and the mix. The pipeline rounds to signed PCM16 once per clean and noisy signal. The saved noise is the exact sample-wise difference between these two WAVs.
- White noise is Gaussian. Pink noise uses 1/f power shaping. Band-limited noise retains only FFT bins within the requested interval. The default tone is 6 kHz, the default multi-tone is 5, 6 and 7 kHz, and the default band is 4.5–7.5 kHz. These sit inside the measured 4–8 kHz stopband. User frequencies can include the passband. Metadata records the actual noise frequencies, seed, gain and SNR before and after PCM quantization.
- Output SNR measures FIR(clean PCM) against the difference of filtered noisy PCM and FIR(clean PCM). This includes the effect of fixed-point rounding and any saturation or hardware error. Clean-signal change is measured separately after aligning for the 31-sample group delay. Undefined ratios are JSON null. Silent audio uses 0.01 FS noise RMS before gain unless an explicit amplitude is supplied. Segments under two samples and bands with no FFT bins receive an error.
- The frequency plot overlays Welch PSDs, the Q1.15 response, and measured output-residual/input-noise PSD gain for excited bins. Band-power values use 0–3, 3–4 and 4–8 kHz. When enough data remains, gain estimates exclude the first 62 samples to reduce zero-history startup effects. Whole-record SNR includes startup. Broadband in-band noise can remain after filtering.
- Each run under `output/` contains WAVs, `metadata.json`, `noise_metadata.json`, metrics JSON/CSV, `execution.log`, `report.md`, and 220 DPI plots. Both-mode comparisons also get `comparison.json` when a valid hardware result exists. A batch adds summary CSV/JSON and a subdirectory per case. The top-level log contains FFmpeg diagnostics and any hardware probe. A batch case log contains that case's processing and capture diagnostics.

See [validation and Project Scribe handoff](HANDOFF.md) and the
[compact matrix results](matrix-summary.csv). The original source and generated audio
are kept local.
