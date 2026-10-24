#!/usr/bin/env python3
"""Write a frozen comparison from step-0 replay results.

  report.py --group NAME --arm A=JOB[@TRIAL][,JOB...] --arm B=JOB --arm C=JOB [--control A]
            [--signal whole_suite_tests] [--primitives DIR] [--out reports/NAME.md]

Each --arm names the result directories of runs/results/ that make one arm. @TRIAL keeps one trial number.
Every result must be a step-0 `final` result, and all arms must share one model and one Droid version.
Rates carry Wilson 95% intervals over trials. Paired differences compare tasks that every arm in the pair ran:
a task's pass value is the share of its trials that pass, and its credit value is the mean log credits of its
trials that the timeout did not kill. Intervals are percentile bootstraps over tasks with a fixed seed.
"""
import argparse
import json
import math
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(os.environ.get("RETRACE_REPO", Path(__file__).resolve().parents[2]))
BOOTSTRAPS = 10000
SEED = 20261024


def whole_suite_tests(call, min_seconds=60):
    return call["test_runner"] is not None and call["path_arg_count"] == 0 and (call["duration_s"] or 0) > min_seconds


SIGNALS = {"whole_suite_tests": whole_suite_tests}


def wilson(k, n, z=1.96):
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar_exact(only_a, only_b):
    n = only_a + only_b
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(only_a, only_b) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def bootstrap_mean(values):
    if not values:
        return (math.nan, math.nan, math.nan)
    rng = random.Random(SEED)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(BOOTSTRAPS))
    return (sum(values) / n, means[int(0.025 * BOOTSTRAPS)], means[int(0.975 * BOOTSTRAPS) - 1])


def load_arm(spec, results_dir):
    results = []
    for part in spec.split(","):
        job, _, trial = part.partition("@")
        files = sorted((results_dir / job).glob("*.json"))
        if not files:
            sys.exit(f"no results in {results_dir / job}")
        for f in files:
            r = json.loads(f.read_text())
            if trial and r["trial"] != int(trial):
                continue
            if r["evidence_role"] != "final":
                sys.exit(f"{f.name} is a {r['evidence_role']} result, not final evidence")
            results.append(r)
    return results


def by_task(results):
    tasks = defaultdict(list)
    for r in results:
        tasks[r["task_id"]].append(r)
    return tasks


def task_pass(rs):
    return sum(r["passed"] for r in rs) / len(rs)


def task_log_credits(rs):
    logs = [math.log(r["cost_credits"]) for r in rs if not r.get("timed_out") and (r["cost_credits"] or 0) > 0]
    return sum(logs) / len(logs) if logs else None


def run_has_signal(r, primitives_dir, signal):
    if not r.get("session_id"):
        return None
    path = primitives_dir / f"{r['session_id']}.json"
    if not path.exists():
        return None
    return any(signal(c) for c in json.loads(path.read_text())["calls"])


def pct(x):
    return "n/a" if math.isnan(x) else f"{100 * x:.1f}%"


def arm_row(name, results, primitives_dir, signal):
    n = len(results)
    k = sum(r["passed"] for r in results)
    lo, hi = wilson(k, n)
    killed = sum(bool(r.get("timed_out")) for r in results)
    credits = sum(r["cost_credits"] or 0 for r in results if not r.get("timed_out"))
    line = f"| {name} | {len(by_task(results))} | {n} | {k} | {pct(k / n)} ({pct(lo)} to {pct(hi)}) | {killed} | {credits:,} | {credits / max(n - killed, 1):,.0f} |"
    if signal:
        flags = [run_has_signal(r, primitives_dir, signal) for r in results]
        seen = [f for f in flags if f is not None]
        hit = sum(seen)
        slo, shi = wilson(hit, len(seen))
        line += f" {hit} of {len(seen)} ({pct(hit / len(seen) if seen else math.nan)}; {pct(slo)} to {pct(shi)}) |"
    return line


def paired_lines(control, other, cname, oname):
    ct, ot = by_task(control), by_task(other)
    common = sorted(set(ct) & set(ot))
    out = [f"### {oname} against {cname}", "", f"Tasks in both arms: {len(common)}. Left out: {len(set(ct) ^ set(ot))}.", ""]
    diffs = [task_pass(ot[t]) - task_pass(ct[t]) for t in common]
    m, lo, hi = bootstrap_mean(diffs)
    only_c = sum(all(r["passed"] for r in ct[t]) and not all(r["passed"] for r in ot[t]) for t in common)
    only_o = sum(all(r["passed"] for r in ot[t]) and not all(r["passed"] for r in ct[t]) for t in common)
    out.append(f"- Pass rate difference ({oname} minus {cname}): {100 * m:+.1f} points (95% interval {100 * lo:+.1f} to {100 * hi:+.1f}).")
    out.append(f"- Tasks where only {cname} passes every rerun: {only_c}. Only {oname}: {only_o}. Exact McNemar p = {mcnemar_exact(only_c, only_o):.3f}.")
    logs = [(task_log_credits(ct[t]), task_log_credits(ot[t])) for t in common]
    logs = [(c, o) for c, o in logs if c is not None and o is not None]
    m, lo, hi = bootstrap_mean([o - c for c, o in logs])
    out.append(f"- Credits, geometric-mean ratio {oname} to {cname}: {math.exp(m):.3f} (95% interval {math.exp(lo):.3f} to {math.exp(hi):.3f}) over {len(logs)} tasks.")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--group", required=True)
    ap.add_argument("--arm", action="append", required=True, metavar="NAME=SPEC")
    ap.add_argument("--control", default=None)
    ap.add_argument("--signal", choices=sorted(SIGNALS))
    ap.add_argument("--results", type=Path, default=REPO / "runs" / "results")
    ap.add_argument("--primitives", type=Path, default=REPO / "runs" / "primitives")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    arms = {}
    for a in args.arm:
        name, _, spec = a.partition("=")
        arms[name] = load_arm(spec, args.results)
    control = args.control or next(iter(arms))
    everything = [r for rs in arms.values() for r in rs]
    models = {r["model"] for r in everything}
    versions = {r["droid_version"] for r in everything}
    if len(models) > 1 or len(versions) > 1:
        sys.exit(f"arms differ in model {sorted(models)} or Droid version {sorted(versions)}")
    signal = SIGNALS.get(args.signal)

    lines = [f"# {args.group}", "", "Evidence: step-0 `final` results.", "",
             "## Setup", "",
             f"- Model: {models.pop()}. Droid: {versions.pop()}. Grader: {', '.join(sorted({r['grader'] for r in everything}))}.",
             f"- Arms: {'; '.join(f'{n} = {s}' for n, s in (a.split('=', 1) for a in args.arm))}.",
             f"- Control: {control}. Trials killed by the timeout are counted apart and left out of credits.", "",
             "## Arms", "",
             "| Arm | Tasks | Trials | Passed | Pass rate (95% Wilson) | Timed out | Credits | Credits per trial |" + (f" {args.signal} runs |" if signal else ""),
             "|---|---|---|---|---|---|---|---|" + ("---|" if signal else "")]
    lines += [arm_row(n, rs, args.primitives, signal) for n, rs in arms.items()]
    lines += ["", "## Paired differences", ""]
    for name, rs in arms.items():
        if name != control:
            lines += paired_lines(arms[control], rs, control, name) + [""]
    text = "\n".join(lines) + "\n"
    if args.out:
        args.out.write_text(text, newline="\n")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
