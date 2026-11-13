"""Validate the pipeline using synthetic audio and the pinned golden vectors."""
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy import signal

from audio_analysis import analyze, compare
from audio_io import RATE, decode, read_wav, sha256, write_wav
from backends import Hardware, PortUnavailable, Reference
from fixtures.make_fixture import make_mp3
from noise_generator import KINDS, Noise, generate, mix, safe_gain

HERE = Path(__file__).resolve().parent
FFMPEG = os.environ.get("AUDIO_TEST_FFMPEG", "ffmpeg")


class NoiseAndReferenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = Reference()
        cls.clean = 0.78 * np.sin(2 * np.pi * 500 * np.arange(RATE) / RATE)

    def test_gold_vectors(self):
        samples, expected = self.reference.golden()
        np.testing.assert_array_equal(self.reference.run(samples), expected)
        impulse = np.array([-32768] + [0] * 62, dtype=np.int16)
        np.testing.assert_array_equal(self.reference.run(impulse), -np.array(self.reference.taps))

    def test_noise_statistics_and_seed(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                config = Noise(kind, 10, 2026)
                noise, details = generate(self.clean, config, self.reference.taps)
                np.testing.assert_array_equal(noise, generate(self.clean, config, self.reference.taps)[0])
                self.assertFalse(np.array_equal(noise, generate(
                    self.clean, Noise(kind, 10, 2027), self.reference.taps)[0]))
                c, n, y = mix(self.clean, noise, safe_gain(self.clean, noise), details)
                np.testing.assert_array_equal(y.astype(np.int32) - c, n)
                self.assertAlmostEqual(details["snr_before_pcm_db"], 10, places=9)
                self.assertAlmostEqual(details["snr_after_pcm_db"], 10, delta=0.01)
                self.assertLess(np.max(np.abs(y.astype(np.int32))), 32767)
                f, p = signal.periodogram(noise, fs=RATE)
                low = np.sum(p[(f >= 125) & (f < 500)])
                high = np.sum(p[(f >= 2000) & (f < 8000)])
                if kind == "pink":
                    self.assertAlmostEqual(low / high, 1, delta=0.35)
                elif kind == "white":
                    self.assertAlmostEqual(high / low, 16, delta=4)
                elif kind == "bandlimited":
                    outside = (f < 4500) | (f > 7500)
                    self.assertLess(np.sum(p[outside]), np.sum(p) * 1e-20)
                else:
                    self.assertIn(f[np.argmax(p)], details["frequencies_hz"])

    def test_analysis_removes_clean_filter_change_from_snr(self):
        config = Noise("highfreq", 10, 2026, (6000,))
        noise, details = generate(self.clean, config, self.reference.taps)
        c, n, y = mix(self.clean, noise, safe_gain(self.clean, noise), details)
        desired = self.reference.run(c)
        filtered = self.reference.run(y)
        metrics, _, _ = analyze(dict(clean=c, noise=n, noisy=y, software=filtered), desired, 31)
        self.assertGreater(metrics["outputs"]["software"]["snr_change_db"], 45)
        self.assertGreater(metrics["outputs"]["software"]["stopband_noise_attenuation_db"], 45)
        self.assertEqual(metrics["clean_signal_change"]["compared_samples"], len(c) - 31)
        self.assertTrue(compare(filtered, filtered)["bit_exact"])
        one_difference = filtered.copy()
        one_difference[100] += 3
        comparison = compare(one_difference, filtered)
        self.assertEqual(comparison["first_mismatch_indices"], [100])
        self.assertEqual(comparison["max_abs_error_lsb"], 3)
        self.assertAlmostEqual(comparison["rms_error_lsb"], 3 / np.sqrt(RATE))
        with self.assertRaises(ValueError):
            compare(filtered[1:], filtered)

    def test_silence_short_and_amplitude(self):
        clean = np.zeros(2)
        noise, details = generate(clean, Noise("white", 20, 1), self.reference.taps)
        c, n, y = mix(clean, noise, safe_gain(clean, noise), details)
        self.assertIsNone(details["snr_after_pcm_db"])
        self.assertIsNotNone(details.get("note"))
        metrics, _, _ = analyze(dict(clean=c, noise=n, noisy=y, software=self.reference.run(y)),
                                self.reference.run(c), 31)
        self.assertIsNone(metrics["outputs"]["software"]["output_snr_db"])
        self.assertEqual(metrics["clean_signal_change"]["compared_samples"], 0)
        noise, _ = generate(self.clean, Noise("white", None, 3, amplitude=0.2), self.reference.taps)
        self.assertAlmostEqual(np.sqrt(np.mean(noise ** 2)), 0.2)
        with self.assertRaisesRegex(ValueError, "at least two"):
            generate(clean[:1], Noise("white", 20, 1), self.reference.taps)

    def test_hardware_host_contract(self):
        # Exercise the subprocess adapter without a physical device.
        hardware = Hardware.__new__(Hardware)
        hardware.host = Path("stream_audio.py").resolve()
        hardware.port = "TEST-PORT"
        hardware.logger = logging.getLogger("fake-device")
        with tempfile.TemporaryDirectory() as temp, patch("backends.subprocess.run") as run:
            source, dest = (Path(temp) / name for name in ("in.wav", "out.wav"))
            values = np.array([11, -22, 33], dtype=np.int16)
            write_wav(dest, values)
            run.return_value = subprocess.CompletedProcess(
                [], 0, "link check: OK, all 3 samples came back intact", "")
            np.testing.assert_array_equal(hardware.capture(source, dest, 3), values)
            self.assertEqual(run.call_args.args[0][-4:], ["--port", "TEST-PORT", "--rate", "16000"])
            with self.assertRaisesRegex(ValueError, "Hardware produced"):
                write_wav(dest, values[:-1])
                hardware.capture(source, dest, 3)
            run.return_value = subprocess.CompletedProcess([], 0, "echo not confirmed", "")
            with self.assertRaisesRegex(ValueError, "clean echo"):
                hardware.capture(source, dest, 3)
            run.return_value = subprocess.CompletedProcess([], 1, "", "serial error")
            with self.assertRaisesRegex(ValueError, "exited 1"):
                hardware.capture(source, dest, 3)
            run.return_value = subprocess.CompletedProcess([], 1, "", "error: cannot open TEST-PORT")
            with self.assertRaises(PortUnavailable):
                hardware.capture(source, dest, 3)


@unittest.skipUnless(shutil.which(FFMPEG), "set AUDIO_TEST_FFMPEG to an FFmpeg with libmp3lame")
class IntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.folder = Path(cls.temp.name)
        cls.source = cls.folder / "stereo fixture.mp3"
        make_mp3(cls.source, FFMPEG)
        cls.source_hash = sha256(cls.source)

    def test_decode_and_conversion(self):
        samples, meta = decode(self.source, FFMPEG, 0, None, logging.getLogger("decode"))
        self.assertEqual(len(samples), RATE)
        self.assertIn("48000 Hz", meta["source_stream"])
        self.assertIn("stereo", meta["source_stream"])
        self.assertEqual(meta["channels"], 1)
        bins = np.abs(np.fft.rfft(samples))
        self.assertGreater(bins[500], 1000)
        self.assertGreater(bins[1000], 1000)
        self.assertLess(bins[3000], 10)  # The 13 kHz source tone must not alias to 3 kHz.
        piece, _ = decode(self.source, FFMPEG, 0.25, 0.25, logging.getLogger("decode"))
        self.assertEqual(len(piece), RATE // 4)

    def invoke(self, entry, *flags, expected=0):
        output = self.folder / f"artifacts-{entry}-{self.id().split('.')[-1]}"
        command = [sys.executable, str(HERE / entry), "--input", str(self.source),
                   "--ffmpeg", FFMPEG, "--output-dir", str(output), *flags]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertEqual(sha256(self.source), self.source_hash)
        return next(output.iterdir())

    def test_cli_report_and_alignment(self):
        # Force hardware to be unverified without opening a port.
        run = self.invoke("audio_test.py", "--mode", "both", "--noise", "highfreq",
                          "--snr-db", "10", "--duration", "0.25", expected=2)
        required = {"clean.wav", "noise.wav", "noisy.wav", "filtered_software.wav", "metadata.json",
                    "noise_metadata.json", "metrics.json", "metrics.csv", "execution.log", "report.md"}
        self.assertTrue(required.issubset({p.name for p in run.iterdir()}))
        for path in (run / "plots").glob("*.png"):
            self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(len(list((run / "plots").glob("*.png"))), 4)
        report = json.loads((run / "metrics.json").read_text())
        self.assertEqual(report["modes"]["hardware"]["state"], "unverified")
        self.assertEqual(report["modes"]["comparison"]["state"], "unverified")
        self.assertEqual(report["alignment"]["extra_output_shift_samples"], 0)
        clean, noise, noisy, filtered = (read_wav(run / name) for name in (
            "clean.wav", "noise.wav", "noisy.wav", "filtered_software.wav"))
        self.assertEqual([len(x) for x in (clean, noise, noisy, filtered)], [RATE // 4] * 4)
        np.testing.assert_array_equal(clean.astype(np.int32) + noise, noisy)
        np.testing.assert_array_equal(Reference().run(noisy), filtered)

    def test_batch_keeps_clean_gain_constant(self):
        run = self.invoke("batch_test.py", "--noise", "white", "--snr-db", "30", "0",
                          "--duration", "0.15", "--max-cases", "2")
        summary = json.loads((run / "summary.json").read_text())
        self.assertEqual(len(summary["cases"]), 2)
        self.assertTrue((run / "summary.csv").is_file())
        hashes = [sha256(run / case["case"] / "clean.wav") for case in summary["cases"]]
        self.assertEqual(hashes[0], hashes[1])
        for row in summary["cases"]:
            self.assertAlmostEqual(row["input_snr_db"], row["target_snr_db"], delta=0.03)

    def test_invalid_audio(self):
        bad = self.folder / "invalid.mp3"
        bad.write_bytes(b"not audio")
        with self.assertRaisesRegex(ValueError, "could not decode"):
            decode(bad, FFMPEG, 0, None, logging.getLogger("invalid"))
