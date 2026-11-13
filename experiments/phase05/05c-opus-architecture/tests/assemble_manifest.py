#!/usr/bin/env python3
"""Assemble the schema-conformant candidate manifest.json + verification-summary.json
for Phase 5C candidate C, embedding measured results and artifact SHA-256 hashes."""
import json, hashlib
from pathlib import Path

CAND = Path(__file__).resolve().parents[1]           # experiments/phase05/05c-opus-architecture
ROOT = next(p for p in CAND.parents if (p / "infrastructure" / "results.py").exists())
BASE_COMMIT = "e72522f265ac36da713cd7a0dcf8dbc64ab21209"


def sha(rel):
    p = CAND / rel
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def summ(report_json):
    r = json.loads((CAND / report_json).read_text())
    cases = r.get("cases", r.get("results", []))
    return r


ARTIFACTS = [
    "rtl/fir_audio_top_trojan.v", "rtl/trojan_adapter.sv",
    "rtl/fir_audio_baseline.reference.v", "rtl/coeffs.json",
    "tests/sw_fir.reference.py", "tests/trojan_ref.py", "tests/gen_vectors.py",
    "tests/build_manifests.py", "tests/assemble_manifest.py",
    "tests/inactive_equiv.manifest.json", "tests/directed.manifest.json",
    "ai/design-research.md", "ai/interaction-log.md",
    "ai/candidate-evaluation.workflow.json", "ai/candidate-evaluation.journal.jsonl",
    "reports/trojan-vs-baseline.diff",
    "reports/inactive-equivalence/report.json",
    "reports/directed/report.json",
    "reports/fpga-build/build-summary.json",
    "reports/fpga-build/utilization.json",
    "reports/fpga-build/timing.json",
    "reports/baseline-build/build-summary.json",
    "README.md",
]
# directed/near-miss vectors
for n in ["active-arm-tone", "active-arm-impulse", "active-overlap-restart",
          "nm-2of3", "nm-perturbed", "nm-interrupted", "nm-nonconsecutive", "nm-wrongorder"]:
    ARTIFACTS += [f"tests/vectors/{n}-input.csv", f"tests/vectors/{n}-expected.csv"]

hashes = {a: sha(a) for a in ARTIFACTS if sha(a)}

# measured results
tb = json.loads((CAND / "reports/fpga-build/build-summary.json").read_text())
bb = json.loads((CAND / "reports/baseline-build/build-summary.json").read_text())
tu = json.loads((CAND / "reports/fpga-build/utilization.json").read_text())["design"]["num_cells_by_type"]
bu = json.loads((CAND / "reports/baseline-build/utilization.json").read_text())["design"]["num_cells_by_type"]


def ff(u):
    return sum(v for k, v in u.items() if k.startswith("SB_DFF"))


manifest = {
    "schema_version": 1,
    "candidate_id": "05C",
    "model": "Claude Opus 4.8 (claude-opus-4-8)",
    "approach": "architecture-driven",
    "base_commit_sha": BASE_COMMIT,
    "candidate_commit_sha": "PENDING_COMMIT",
    "name": "csaw-challenge3-05c-opus-architecture",
    "kind": "verified_design",
    "ready": True,
    "trojan": {
        "trigger": "ordered 3-frame covert knock on the architecturally-unused RIGHT I2S slot: 0xC0DE,0xFACE,0xBEEF on consecutive frames; sticky `armed` latches on the 3rd match (restart credit on MAGIC0). Per-triple false-match prob 2^-48.",
        "payload": "single 16-bit 2:1 mux at the end_frame TX load: y_d <= armed ? echo : y_filt. Armed => left (filtered) output passes the raw input (filter bypass); 63-tap MAC datapath untouched.",
        "sticky": True,
        "untriggered_equivalence": "bit-identical to recovered baseline",
    },
    "verification_evidence": [
        "ai/design-research.md", "ai/interaction-log.md",
        "ai/candidate-evaluation.workflow.json",
        "rtl/fir_audio_baseline.reference.v",
        "reports/trojan-vs-baseline.diff",
        "../../../handoffs/phase-04/integration-validation.json",
    ],
    "simulation": {
        "sources": ["rtl/fir_audio_top_trojan.v", "rtl/trojan_adapter.sv"],
        "parameters": {"SAMPLE_BITS": 16, "SLOT_BITS": 16, "MSB_DELAY": 1,
                       "LEFT_LEVEL": 0, "HALF_PERIOD_NS": 500,
                       "CLOCK_HALF_NS": 50, "RESET_CYCLES": 64},
    },
    "cases": {
        "inactive_equivalence": "tests/inactive_equiv.manifest.json (8 recovered vectors vs UNMODIFIED baseline reference)",
        "directed": "tests/directed.manifest.json (3 active vs trojan_ref, 5 near-miss vs baseline reference)",
    },
    "build": {
        "sources": ["rtl/fir_audio_top_trojan.v", "rtl/trojan_adapter.sv"],
        "top": "phase4_audio_top", "device": "up5k", "package": "sg48",
        "pcf": "../../../infrastructure/constraints/recovered-audio.pcf",
        "frequency_mhz": 10, "seed": 1, "allow_unconstrained": False,
    },
    "acceptance": {
        "inactive_mismatch_count": 0,
        "near_miss_triggered": False,
        "active_left_equals_raw_input_after_arm": True,
        "active_impulse_nonzero_output_taps": 1,
        "timing_constraint_mhz": 10,
        "hardware_verification": "pending",
    },
    "exact_commands": [
        "python experiments/phase05/05c-opus-architecture/tests/gen_vectors.py",
        "python experiments/phase05/05c-opus-architecture/tests/trojan_ref.py --model experiments/phase05/05c-opus-architecture/tests/sw_fir.reference.py --coefficients experiments/phase05/05c-opus-architecture/rtl/coeffs.json --input <case>-input.csv --output <case>-expected.csv   # active cases",
        "python infrastructure/recovered_reference.py --model experiments/phase05/05c-opus-architecture/tests/sw_fir.reference.py --coefficients experiments/phase05/05c-opus-architecture/rtl/coeffs.json --input <case>-input.csv --output <case>-expected.csv   # near-miss cases",
        "python experiments/phase05/05c-opus-architecture/tests/build_manifests.py",
        "python infrastructure/run.py sim --manifest experiments/phase05/05c-opus-architecture/tests/directed.manifest.json --output build/p5c-directed-final",
        "python infrastructure/run.py regress --manifest experiments/phase05/05c-opus-architecture/tests/inactive_equiv.manifest.json --output build/p5c-inactive-final",
    ],
    "status": {
        "inactive_equivalence_tests": {
            "status": "passed", "simulation_cases_passed": 8,
            "all_comparisons_max_error": 0, "fpga_build_passed": bool(tb["passed"]),
            "note": "Trojan-present RTL (armed never asserts) == unmodified baseline reference on all 8 recovered vectors incl. 1024 real-audio samples",
        },
        "directed_tests": {
            "status": "passed", "active_cases_passed": 3, "near_miss_cases_passed": 5,
            "active_reference": "tests/trojan_ref.py", "near_miss_reference": "baseline recovered_reference.py",
        },
        "fpga_resource_measurements": {
            "baseline": {"lc_used": bb["utilization"]["ICESTORM_LC"]["used"],
                         "lut4": bu.get("SB_LUT4"), "ff": ff(bu), "carry": bu.get("SB_CARRY"),
                         "dsp": 0, "bram": 0, "io": 5},
            "candidate": {"lc_used": tb["utilization"]["ICESTORM_LC"]["used"],
                          "lc_available": 5280, "lut4": tu.get("SB_LUT4"), "ff": ff(tu),
                          "carry": tu.get("SB_CARRY"), "dsp": 0, "bram": 0, "io": 5},
            "delta": {"lc": tb["utilization"]["ICESTORM_LC"]["used"] - bb["utilization"]["ICESTORM_LC"]["used"],
                      "lut4": tu.get("SB_LUT4") - bu.get("SB_LUT4"), "ff": ff(tu) - ff(bu)},
        },
        "timing_results": {
            "constraint_mhz": 10.0,
            "nextpnr_baseline_fmax_mhz": list(bb["fmax"].values())[0]["achieved"],
            "nextpnr_candidate_fmax_mhz": list(tb["fmax"].values())[0]["achieved"],
            "icetime_baseline_fmax_mhz": 14.23, "icetime_candidate_fmax_mhz": 14.47,
            "timing_met": True, "seed": 1,
            "note": "Trojan logic sits at the low-rate end_frame TX boundary, off the serial-MAC accumulator critical path; no regression.",
        },
        "bitstream": {"candidate_sha256": tb["bitstream_sha256"],
                      "baseline_sha256": bb["bitstream_sha256"],
                      "note": "bitstreams differ (Trojan present); untriggered I/O behaviour is bit-identical, verified by simulation."},
        "hardware_verification": {"status": "pending",
                                  "reason": "No physical Hackster board available in this environment"},
        "known_failures": [
            "First directed run: 'Stimulus value out of range' — magic codes must be written as signed int16 (bit pattern identical). Fixed in gen_vectors.py.",
            "First synthesis: write-only right_sample register pruned (+3 FF not +19). Register removed; detector reads rx_sh inline as the baseline does for left_sample.",
        ],
    },
    "artifact_paths_hashes": hashes,
}

(CAND / "manifest.json").write_text(json.dumps(manifest, indent=2))

# compact verification summary
vs = {
    "candidate": "05C architecture-driven", "model": "claude-opus-4-8",
    "inactive_equivalence": {"sims": 8, "max_error": 0, "real_audio_samples": 1024, "result": "bit-identical to baseline"},
    "directed": {"active": 3, "near_miss": 5, "max_error": 0},
    "resources": manifest["status"]["fpga_resource_measurements"],
    "timing": manifest["status"]["timing_results"],
    "hardware": "pending",
}
(CAND / "reports/verification-summary.json").write_text(json.dumps(vs, indent=2))
print("wrote manifest.json and reports/verification-summary.json")
print("resource delta:", manifest["status"]["fpga_resource_measurements"]["delta"])
print("artifacts hashed:", len(hashes))
