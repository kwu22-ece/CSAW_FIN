#!/usr/bin/env python3
"""Run the full Phase 3 HDL co-simulation battery.

For every test-vector family (build/vectors/*.csv):
  1. gate-level netlist  vs golden model  (filtered + echo, bit-exact)
  2. reconstructed RTL    vs golden model  (filtered + echo, bit-exact)
  3. netlist              vs reconstructed  (direct engine equivalence)

Emits build/reports/hdl-battery.json with per-family and aggregate mismatch
counts, max sample errors, decoded latency, and echo-channel scores.
"""
from __future__ import annotations
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import i2s_cosim as cs  # noqa: E402

VECDIR = os.path.join(ROOT, "build", "vectors")
REPDIR = os.path.join(ROOT, "build", "reports")


def main():
    vectors = sorted(fn[:-4] for fn in os.listdir(VECDIR) if fn.endswith(".csv"))
    print("compiling engines ...")
    vvp = {e: cs.compile_engine(e) for e in ("netlist", "recon")}

    report = {"families": [], "aggregate": {}}
    tot_samp = 0
    tot_filt_mis = tot_echo_mis = tot_cross_mis = 0
    max_filt_err = 0
    all_lat_ok = True

    for v in vectors:
        samples = cs.read_vector(os.path.join(VECDIR, v + ".csv"))
        rn = cs.cosim("netlist", v, samples, vvp["netlist"])
        rr = cs.cosim("recon", v, samples, vvp["recon"])
        # direct engine equivalence on the filtered channel
        cross = sum(1 for a, b in zip(rn["hw_filtered"], rr["hw_filtered"]) if a != b)
        lat_ok = (rn["calib"]["latency"] == 2 and rr["calib"]["latency"] == 2
                  and rn["calib"]["echo_score"] == 1.0
                  and rr["calib"]["echo_score"] == 1.0)
        all_lat_ok &= lat_ok
        fam = {
            "vector": v, "samples": rn["samples"],
            "netlist": {"filtered_mismatches": rn["filtered_mismatches"],
                        "filtered_max_abs_err": rn["filtered_max_abs_err"],
                        "echo_mismatches": rn["echo_mismatches"],
                        "latency": rn["calib"]["latency"],
                        "echo_score": rn["calib"]["echo_score"]},
            "recon": {"filtered_mismatches": rr["filtered_mismatches"],
                      "filtered_max_abs_err": rr["filtered_max_abs_err"],
                      "echo_mismatches": rr["echo_mismatches"],
                      "latency": rr["calib"]["latency"],
                      "echo_score": rr["calib"]["echo_score"]},
            "netlist_vs_recon_filtered_mismatches": cross,
            "latency_2_and_echo_exact": lat_ok,
        }
        report["families"].append(fam)
        tot_samp += rn["samples"]
        tot_filt_mis += rn["filtered_mismatches"] + rr["filtered_mismatches"]
        tot_echo_mis += rn["echo_mismatches"] + rr["echo_mismatches"]
        tot_cross_mis += cross
        max_filt_err = max(max_filt_err, rn["filtered_max_abs_err"],
                           rr["filtered_max_abs_err"])
        print("  %-9s n=%4d | netlist mis=%d echo=%d | recon mis=%d echo=%d "
              "| net==recon mis=%d | lat=%d/%d"
              % (v, rn["samples"],
                 rn["filtered_mismatches"], rn["echo_mismatches"],
                 rr["filtered_mismatches"], rr["echo_mismatches"], cross,
                 rn["calib"]["latency"], rr["calib"]["latency"]))

    report["aggregate"] = {
        "families": len(vectors),
        "total_input_samples_per_engine": tot_samp,
        "total_filtered_mismatches_vs_model": tot_filt_mis,
        "total_echo_mismatches": tot_echo_mis,
        "total_netlist_vs_recon_mismatches": tot_cross_mis,
        "max_filtered_abs_err": max_filt_err,
        "all_latency_2_and_echo_exact": all_lat_ok,
        "bit_exact": (tot_filt_mis == 0 and tot_echo_mis == 0 and tot_cross_mis == 0),
    }
    os.makedirs(REPDIR, exist_ok=True)
    with open(os.path.join(REPDIR, "hdl-battery.json"), "w") as fh:
        json.dump(report, fh, indent=2)

    agg = report["aggregate"]
    print("\n=== aggregate ===")
    print("families                       : %d" % agg["families"])
    print("input samples / engine         : %d (x2 engines = %d sample-comparisons)"
          % (agg["total_input_samples_per_engine"],
             2 * agg["total_input_samples_per_engine"]))
    print("filtered mismatches vs model   : %d" % agg["total_filtered_mismatches_vs_model"])
    print("echo mismatches                : %d" % agg["total_echo_mismatches"])
    print("netlist vs recon mismatches    : %d" % agg["total_netlist_vs_recon_mismatches"])
    print("max filtered |err|             : %d" % agg["max_filtered_abs_err"])
    print("all latency==2 & echo exact    : %s" % agg["all_latency_2_and_echo_exact"])
    print("BIT-EXACT                      : %s" % agg["bit_exact"])
    print("-> build/reports/hdl-battery.json")
    return 0 if agg["bit_exact"] and agg["all_latency_2_and_echo_exact"] else 1


if __name__ == "__main__":
    sys.exit(main())
