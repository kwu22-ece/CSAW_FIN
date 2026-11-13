#!/usr/bin/env python3
"""Emit Phase 5C candidate C run manifests (absolute paths) for the Phase 4 harness.

  inactive_equiv.manifest.json : Trojan-present RTL vs the UNMODIFIED baseline
      reference on the 8 recovered vectors (incl. 1024 real-audio samples) +
      the UP5K/SG48 synthesis build of the Trojan top. Expect bit-identical
      output and a passing build => untriggered == baseline.
  directed.manifest.json : directed active (arm->bypass) cases vs trojan_ref,
      and near-miss cases vs the baseline reference. Expect active bypass to
      match and every near-miss to stay bit-identical to baseline.
"""
import json
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "infrastructure" / "results.py").exists())   # worktree root
CAND = ROOT / "experiments/phase05/05c-opus-architecture"
INFRA = ROOT / "infrastructure"
BASE = ROOT / "build/recovered-inputs/manifest.json"

RTL = str(CAND / "rtl/fir_audio_top_trojan.v")
ADAPTER = str(CAND / "rtl/trojan_adapter.sv")
MODEL = str(CAND / "tests/sw_fir.reference.py")
COEF = str(CAND / "rtl/coeffs.json")
TROJAN_REF = str(CAND / "tests/trojan_ref.py")
PCF = str(INFRA / "constraints/recovered-audio.pcf")
VEC = CAND / "tests/vectors"
I2S = {"SAMPLE_BITS": 16, "SLOT_BITS": 16, "MSB_DELAY": 1, "LEFT_LEVEL": 0,
       "HALF_PERIOD_NS": 500, "CLOCK_HALF_NS": 50, "RESET_CYCLES": 64}


def inactive():
    m = json.loads(BASE.read_text())
    # Point the harness at the Trojan-present RTL + candidate adapter.
    m["name"] = "phase5c-inactive-equivalence"
    m["simulation"]["sources"] = [RTL, ADAPTER]
    m["build"]["sources"] = [RTL, ADAPTER]
    m["build"]["top"] = "phase4_audio_top"      # Trojan present
    # reference stays the UNMODIFIED baseline model (recovered_reference.py).
    (CAND / "tests/inactive_equiv.manifest.json").write_text(json.dumps(m, indent=2))


def case(name, expected):
    return {"name": name,
            "input_csv": str(VEC / f"{name}-input.csv"),
            "parameters": {"HALF_PERIOD_NS": 500},
            "expected_csv": str(VEC / f"{name}-expected.csv")}


def directed():
    active = ["active-arm-tone", "active-arm-impulse", "active-overlap-restart"]
    nearmiss = ["nm-2of3", "nm-perturbed", "nm-interrupted",
                "nm-nonconsecutive", "nm-wrongorder"]
    m = {
        "schema_version": 1,
        "name": "phase5c-directed-trigger-payload",
        "kind": "verified_design",
        "ready": True,
        "verification_evidence": [TROJAN_REF, MODEL, COEF],
        "simulation": {"sources": [RTL, ADAPTER], "parameters": I2S},
        "cases": [case(n, True) for n in active + nearmiss],
    }
    (CAND / "tests/directed.manifest.json").write_text(json.dumps(m, indent=2))


if __name__ == "__main__":
    inactive()
    directed()
    print("wrote inactive_equiv.manifest.json and directed.manifest.json")
