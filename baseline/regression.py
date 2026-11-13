#!/usr/bin/env python3
"""Phase 3 one-command regression: regenerate vectors and re-run every check,
then compose a single pass/fail verdict.

Stages:
  1. gen_testvectors         - regenerate the 6 input families
  2. validate_models         - ref_fir vs sw_fir + arithmetic invariants
  3. analyze_response        - frequency-response landmarks (scipy, independent)
  4. run_battery  (HDL)      - netlist/recon/model bit-exact across families
  5. run_wav      (HDL)      - real-audio bit-exact + canonical reference dataset

--quick skips the HDL stages (4,5) for a fast software-only check.

Needs the OSS CAD Suite on PATH for the HDL stages:
  export YOSYSHQ_ROOT=/c/Users/lowbr/oss-cad-suite
  export PATH="$YOSYSHQ_ROOT/bin:$YOSYSHQ_ROOT/lib:$PATH"

Writes build/reports/phase3-regression.json and prints a summary table.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPDIR = os.path.join(ROOT, "build", "reports")
PY = sys.executable


def run(label, argv):
    t0 = time.time()
    p = subprocess.run([PY] + argv, cwd=ROOT, capture_output=True, text=True)
    dt = time.time() - t0
    print("\n### %s  (%.1fs, exit %d)" % (label, dt, p.returncode))
    out = (p.stdout or "").strip().splitlines()
    for line in out[-18:]:
        print("   " + line)
    if p.returncode != 0 and p.stderr:
        print("   STDERR:", p.stderr.strip().splitlines()[-3:])
    return p.returncode, dt


def load(name, default=None):
    path = os.path.join(REPDIR, name)
    if os.path.isfile(path):
        with open(path) as fh:
            return json.load(fh)
    return default


def main():
    quick = "--quick" in sys.argv
    os.makedirs(REPDIR, exist_ok=True)
    stages = []

    rc, dt = run("1. gen_testvectors", ["baseline/gen_testvectors.py"])
    stages.append(("gen_testvectors", rc))

    rc, dt = run("2. validate_models", ["baseline/validate_models.py"])
    stages.append(("validate_models", rc))

    rc, dt = run("3. analyze_response", ["baseline/analyze_response.py", "16000"])
    stages.append(("analyze_response", rc))

    if not quick:
        rc, dt = run("4. run_battery (HDL)", ["sim/run_battery.py"])
        stages.append(("run_battery", rc))
        rc, dt = run("5. run_wav (HDL)",
                     ["sim/run_wav.py", "what_a_piece_of_work-noisy.wav", "256", "0"])
        stages.append(("run_wav", rc))

    # compose verdict from the per-stage JSON
    mc = load("model-crosscheck.json", {})
    fm = load("freq-metrics.json", {})
    bat = load("hdl-battery.json", {}) if not quick else None
    wav = load("wav-cosim.json", {}) if not quick else None

    verdict = {
        "quick": quick,
        "stages_exit": {name: rc for name, rc in stages},
        "coeff_facts": mc.get("invariants", {}).get("coeff_facts"),
        "models_agree": mc.get("invariants", {}).get("models_agree"),
        "neg_one_impulse_identity": mc.get("invariants", {}).get(
            "neg_one_impulse_equals_minus_h"),
        "saturates_both_rails": mc.get("invariants", {}).get("saturates_both_rails"),
        "round_half_toward_plus_inf": mc.get("invariants", {}).get(
            "round_half_toward_plus_inf"),
        "minus3dB_hz": (fm.get("edges_hz") or {}).get("-3_db"),
        "group_delay_samples": fm.get("group_delay_samples_mean_passband"),
        "hdl_bit_exact": (bat or {}).get("aggregate", {}).get("bit_exact"),
        "hdl_latency_echo_ok": (bat or {}).get("aggregate", {}).get(
            "all_latency_2_and_echo_exact"),
        "wav_bit_exact": (wav or {}).get("bit_exact"),
    }
    checks = [verdict["coeff_facts"], verdict["models_agree"],
              verdict["neg_one_impulse_identity"], verdict["saturates_both_rails"],
              verdict["round_half_toward_plus_inf"]]
    if not quick:
        checks += [verdict["hdl_bit_exact"], verdict["hdl_latency_echo_ok"],
                   verdict["wav_bit_exact"]]
    all_exit0 = all(rc == 0 for _, rc in stages)
    verdict["PASS"] = bool(all_exit0 and all(c is True for c in checks))

    with open(os.path.join(REPDIR, "phase3-regression.json"), "w") as fh:
        json.dump(verdict, fh, indent=2)

    print("\n" + "=" * 60)
    print("PHASE 3 REGRESSION SUMMARY%s" % ("  [QUICK]" if quick else ""))
    print("=" * 60)
    for k in ("coeff_facts", "models_agree", "neg_one_impulse_identity",
              "saturates_both_rails", "round_half_toward_plus_inf",
              "hdl_bit_exact", "hdl_latency_echo_ok", "wav_bit_exact"):
        if verdict.get(k) is not None:
            print("  %-28s : %s" % (k, verdict[k]))
    print("  %-28s : %s Hz" % ("-3 dB edge", verdict["minus3dB_hz"]))
    print("  %-28s : %s samples" % ("group delay", verdict["group_delay_samples"]))
    print("-" * 60)
    print("  OVERALL PASS                 : %s" % verdict["PASS"])
    print("-> build/reports/phase3-regression.json")
    return 0 if verdict["PASS"] else 1


if __name__ == "__main__":
    sys.exit(main())
