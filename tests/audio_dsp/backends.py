"""Reuse the unchanged Phase 2 FIR model and the official Hackster audio host."""
from pathlib import Path
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import wave

import numpy as np

from audio_io import RATE, read_wav, sha256, write_wav
from noise_generator import verify_stopband

ROOT = Path(__file__).resolve().parents[2]
PHASE2 = "1befb30e99a506698c45d4ca9394a3c7ec95c966"
STOCK_BITSTREAM_SHA256 = "2547d7a23812609cc7fc96bc0234b62bb43458bdfdb49aa03480074bd9c365ee"


class PortUnavailable(ValueError):
    """The selected port is busy, inaccessible, or disconnected."""


def git_blob(name):
    result = subprocess.run(
        ["git", "show", f"{PHASE2}:{name}"], cwd=ROOT, capture_output=True)
    if result.returncode:
        raise ValueError(
            "Pinned Phase 2 reference is unavailable. Fetch origin challenge3/02-reverse-engineering."
        )
    return result.stdout


class Reference:
    def __init__(self):
        model = git_blob("scripts/sw_fir.py")
        coefficients = git_blob("recovered/coeffs.json")
        self.taps = json.loads(coefficients)["coeffs_q15"]
        namespace = {"__name__": "phase2_original_fir"}
        exec(compile(model, f"{PHASE2}:scripts/sw_fir.py", "exec"), namespace)
        self.filter = namespace["fir_filter"]
        self.provenance = {
            "git_commit": PHASE2,
            "model": "scripts/sw_fir.py",
            "model_sha256": hashlib.sha256(model).hexdigest(),
            "coefficients": "recovered/coeffs.json",
            "coefficients_sha256": hashlib.sha256(coefficients).hexdigest(),
            "tap_count": len(self.taps),
            "group_delay_samples": (len(self.taps) - 1) // 2,
            "stopband_peak_gain_db": verify_stopband(self.taps),
        }

    def run(self, samples):
        return np.asarray(self.filter(samples.tolist(), self.taps), dtype="<i2")

    def golden(self):
        rows = list(csv.DictReader(io.StringIO(git_blob(
            "handoffs/phase-02/reference_vectors.csv").decode("utf-8"))))
        if not rows or [int(row["n"]) for row in rows] != list(range(len(rows))):
            raise ValueError("Phase 2 golden vectors have invalid sample indices")
        return tuple(np.asarray([int(row[key]) for row in rows], dtype="<i2")
                     for key in ("x_in_int16", "y_filtered_int16"))


class Hardware:
    """Run the official host with one stock-FIR probe per session."""

    def __init__(self, args, reference, directory, logger):
        self.logger = logger
        self.status = {"state": "unverified"}
        self.port = args.port or os.environ.get("HACKSTER_APP_PORT")
        if not self.port or not args.challenge_dir:
            self.status["reason"] = "Supply --challenge-dir and the confirmed application --port."
            return
        self.host = (args.challenge_dir / "tools/stream_audio.py").resolve()
        bridge = self.host.with_name("audio_bridge.py")
        bitstream = (args.challenge_dir / "fpga/fir_audio_top.bin").resolve()
        try:
            from serial.tools import list_ports

            available = list_ports.comports()
            logger.info("Detected serial ports: %s", [(p.device, p.description, p.hwid)
                                                       for p in available])
            selected = next((p for p in available if p.device.casefold() == self.port.casefold()
                             or p.device == os.path.realpath(self.port)), None)
            if selected is None:
                self.status["reason"] = "The selected application port is absent."
                return
            self.status.update(port=self.port, port_description=selected.description)
            if not args.confirm_stock:
                self.status["reason"] = "Confirm board availability and stock bitstream with --confirm-stock."
                return
            if not self.host.is_file() or not bridge.is_file():
                raise ValueError("Official stream_audio.py and audio_bridge.py must be adjacent in tools/")
            if not bitstream.is_file() or sha256(bitstream) != STOCK_BITSTREAM_SHA256:
                raise ValueError("The challenge directory does not contain the verified stock bitstream")
            self.status.update(
                stock_file_sha256=STOCK_BITSTREAM_SHA256,
                stock_programming_confirmation="operator",
                host_sha256=sha256(self.host), bridge_sha256=sha256(bridge),
                transport_latency_frames=2, host_removes_transport_latency=True,
            )
            stimulus, expected = reference.golden()
            source, destination = directory / "hardware_probe_in.wav", directory / "hardware_probe_out.wav"
            write_wav(source, stimulus)
            actual = self.capture(source, destination, len(stimulus))
            mismatches = int(np.count_nonzero(actual != expected))
            self.status.update(stock_probe_samples=len(stimulus), stock_probe_mismatches=mismatches,
                               stock_probe_echo="passed")
            if mismatches:
                raise ValueError("Board output disagrees with the stock FIR golden probe")
            self.status["state"] = "ready"
        except PortUnavailable as exc:
            self.status["reason"] = str(exc)
            logger.warning("Hardware deferred: %s", exc)
        except (ImportError, OSError, ValueError, wave.Error, subprocess.SubprocessError) as exc:
            self.status.update(state="failed", reason=str(exc))
            logger.error("Hardware preflight: %s", exc)

    def capture(self, source, destination, count):
        command = [sys.executable, "-u", str(self.host), str(source), str(destination),
                   "--port", self.port, "--rate", str(RATE)]
        self.logger.info("Stock host argv: %r", command)
        result = subprocess.run(command, cwd=self.host.parent, capture_output=True, text=True,
                                errors="replace", timeout=60 + 5 * count / RATE)
        self.logger.info("Stock host exit %d\n%s\n%s", result.returncode, result.stdout, result.stderr)
        if result.returncode:
            if "cannot open" in result.stderr.lower():
                raise PortUnavailable("Stock host could not open the port. See execution.log.")
            raise ValueError(f"Stock host exited {result.returncode}. See execution.log for I2S diagnostics.")
        echo_count = re.search(r"link check: OK, all (\d+) samples came back intact", result.stdout)
        if echo_count is None or int(echo_count[1]) != count:
            raise ValueError("Stock host did not confirm a clean echo for the expected sample count.")
        samples = read_wav(destination)
        if len(samples) != count:
            raise ValueError(f"Hardware produced {len(samples)} samples. Expected {count}.")
        return samples
