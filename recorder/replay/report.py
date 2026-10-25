#!/usr/bin/env python3
"""Write a frozen comparison from step-0 replay results.

  report.py --group NAME --arm A=JOB[@TRIAL][,JOB...] --arm B=JOB --arm C=JOB [--control A]
            [--signal whole_suite_tests] [--primitives DIR] [--out reports/NAME.md]

Each --arm names the result directories of runs/results/ that make one arm. @TRIAL keeps one trial number.
Every result must be a step-0 `final` result, and all arms must share one model and one Droid version.
Rates carry Wilson 95% intervals over trials. Paired differences compare tasks that every arm in the pair ran:
a task's pass value is the share of its trials that pass, and its credit value is the mean log credits of its
trials that the timeout did not kill. Intervals are percentile bootstraps over tasks with a fixed seed.
The proxy agreement section compares each proxy with the grader on trials the proxy can judge.
--signal adds the hard signal as an arm column and a paired incidence difference per task, from the primitives.
A signal with a count (calls_before_first_edit) also gets the paired mean count difference, as the pre-registration says.
The verification section counts test commands after each run's last successful edit, from the primitives.
Proxies read `proxies` in the result and the last test call in runs/primitives (--primitives).
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


def whole_suite_tests(calls, min_seconds=60):
    return any(c["test_runner"] is not None and c["path_arg_count"] == 0 and (c["duration_s"] or 0) > min_seconds
               for c in calls)


def tests_after_last_edit(calls):
    edits = [c["position"] for c in calls if c.get("command_class") == "edit" and not c.get("is_error")]
    if not edits:
        return None
    return sum(c["test_runner"] is not None for c in calls if c["position"] > max(edits))


def skipped_verification(calls):
    n = tests_after_last_edit(calls)
    return None if n is None else n == 0


CALLS_BEFORE_FIRST_EDIT_LIMIT = 12


def calls_before_first_edit_count(calls):
    edits = [c["position"] for c in calls if c.get("command_class") == "edit"]
    return min(edits) if edits else len(calls)


def calls_before_first_edit(calls):
    return calls_before_first_edit_count(calls) > CALLS_BEFORE_FIRST_EDIT_LIMIT


SHELL_ERROR_STREAK_MIN = 3
LARGE_OUTPUT_TOKENS = 2000


def shell_error_streak_count(calls):
    prev, n = None, 0
    for c in calls:
        if c["tool_name"] == "Execute":
            n += bool(c["is_error"] and prev is not None and prev["is_error"])
            prev = c
    return n


def shell_error_streak(calls):
    return shell_error_streak_count(calls) >= SHELL_ERROR_STREAK_MIN


def large_root_searches_count(calls):
    return sum(c["command_class"] == "search" and c["files"] == ["."]
               and (c["output_tokens_est"] or 0) > LARGE_OUTPUT_TOKENS for c in calls)


def large_root_searches(calls):
    return large_root_searches_count(calls) >= 1


SIGNALS = {"whole_suite_tests": whole_suite_tests, "skipped_verification": skipped_verification,
           "calls_before_first_edit": calls_before_first_edit, "shell_error_streak": shell_error_streak,
           "large_root_searches": large_root_searches}
COUNTS = {"calls_before_first_edit": calls_before_first_edit_count, "shell_error_streak": shell_error_streak_count,
          "large_root_searches": large_root_searches_count}


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
    if not results:
        sys.exit(f"no results left in {spec}")
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


def run_calls(r, primitives_dir):
    if not r.get("session_id"):
        return None
    path = primitives_dir / f"{r['session_id']}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())["calls"]


def run_has_signal(r, primitives_dir, signal):
    calls = run_calls(r, primitives_dir)
    return None if calls is None else signal(calls)


def last_test_exit(r, primitives_dir):
    calls = run_calls(r, primitives_dir)
    if calls is None:
        return None
    runs = [c for c in calls if c.get("test_runner")]
    if not runs or runs[-1].get("exit_code") is None:
        return None
    return runs[-1]["exit_code"] == 0


def repo_tests_pass(r):
    p = (r.get("proxies") or {}).get("repo_tests")
    return p["regressed"] == 0 if p and p["status"] == "ok" else None


def acceptance_pass(r):
    p = (r.get("proxies") or {}).get("acceptance")
    return p["status"] == "pass" if p and p["at_start"] == "fail" and p["status"] != "error" else None


def combined_pass(r):
    a, b = repo_tests_pass(r), acceptance_pass(r)
    return None if a is None or b is None else a and b


PROXIES = {
    "repo_tests": lambda r, d: repo_tests_pass(r),
    "acceptance": lambda r, d: acceptance_pass(r),
    "last_test_exit": last_test_exit,
    "combined": lambda r, d: combined_pass(r),
}


def cohen_kappa(a, b, c, d):
    n = a + b + c + d
    if n == 0:
        return math.nan
    chance = ((a + b) * (a + c) + (c + d) * (b + d)) / n ** 2
    if chance == 1:
        return math.nan
    return ((a + d) / n - chance) / (1 - chance)


def agreement_row(arm, proxy, results, primitives_dir):
    a = b = c = d = 0
    for r in results:
        if r.get("evidence_role") != "final" or "passed" not in r:
            continue
        guess = PROXIES[proxy](r, primitives_dir)
        if guess is None:
            continue
        a += guess and r["passed"]
        b += guess and not r["passed"]
        c += not guess and r["passed"]
        d += not guess and not r["passed"]
    n = a + b + c + d
    total = sum(r.get("evidence_role") == "final" and "passed" in r for r in results)
    lo, hi = wilson(a + d, n)
    plo, phi = wilson(a, a + b)
    kappa = cohen_kappa(a, b, c, d)
    agree = pct((a + d) / n) if n else "n/a"
    prec = pct(a / (a + b)) if a + b else "n/a"
    return n, (f"| {arm} | {proxy} | {n} | {total - n} | {a} | {b} | {c} | {d} | {agree} ({pct(lo)} to {pct(hi)}) | "
               f"{'n/a' if math.isnan(kappa) else f'{kappa:.2f}'} | {prec} ({pct(plo)} to {pct(phi)}) |")


def agreement_lines(arms, primitives_dir):
    groups = list(arms.items())
    if len(groups) > 1:
        groups.append(("all", [r for rs in arms.values() for r in rs]))
    rows = [(n, row) for name, rs in groups for p in PROXIES for n, row in [agreement_row(name, p, rs, primitives_dir)]]
    out = ["## Proxy agreement", "",
           "Agreement with the dataset grader on final trials. For verification only; the improvement loop never reads it.", ""]
    if not any(n for n, _ in rows):
        return out + ["No final trial has proxies."]
    out += ["| Arm | Proxy | Usable | Excluded | Proxy pass, grader pass | Proxy pass, grader fail | Proxy fail, grader pass | Proxy fail, grader fail | Agreement (95% Wilson) | Kappa | Precision of proxy pass (95% Wilson) |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    return out + [row for _, row in rows]


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
        missing = f", {n - len(seen)} without primitives" if len(seen) < n else ""
        line += f" {hit} of {len(seen)} ({pct(hit / len(seen) if seen else math.nan)}; {pct(slo)} to {pct(shi)}{missing}) |"
    return line


def verification_lines(arms, primitives_dir):
    out = ["## Verification after the last edit", "",
           "Runs with a successful edit call. A run skips verification when no test command follows its last edit.", "",
           "| Arm | Runs with primitives | Runs with an edit | Skipped verification (95% Wilson) | Test commands after the last edit, mean |",
           "|---|---|---|---|---|"]
    for name, rs in arms.items():
        calls = [c for c in (run_calls(r, primitives_dir) for r in rs) if c is not None]
        counts = [n for n in map(tests_after_last_edit, calls) if n is not None]
        skipped = sum(n == 0 for n in counts)
        lo, hi = wilson(skipped, len(counts))
        mean = f"{sum(counts) / len(counts):.2f}" if counts else "n/a"
        rate = pct(skipped / len(counts)) if counts else "n/a"
        out.append(f"| {name} | {len(calls)} | {len(counts)} | {skipped} of {len(counts)} ({rate}; {pct(lo)} to {pct(hi)}) | {mean} |")
    return out


def ratio(x):
    return "n/a" if math.isnan(x) else f"{math.exp(x):.3f}"


def paired_lines(control, other, cname, oname, primitives_dir=None, signal=None, signal_name=None):
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
    out.append(f"- Credits, geometric-mean ratio {oname} to {cname}: {ratio(m)} (95% interval {ratio(lo)} to {ratio(hi)}) over {len(logs)} tasks.")
    if signal:
        flags = {(t, arm): [f for f in (run_has_signal(r, primitives_dir, signal) for r in rs) if f is not None]
                 for t in common for arm, rs in (("c", ct[t]), ("o", ot[t]))}
        both = [t for t in common if flags[t, "c"] and flags[t, "o"]]
        diffs = [sum(flags[t, "o"]) / len(flags[t, "o"]) - sum(flags[t, "c"]) / len(flags[t, "c"]) for t in both]
        m, lo, hi = bootstrap_mean(diffs)
        only_c = sum(any(flags[t, "c"]) and not any(flags[t, "o"]) for t in both)
        only_o = sum(any(flags[t, "o"]) and not any(flags[t, "c"]) for t in both)
        out.append(f"- {signal_name} incidence difference ({oname} minus {cname}), share of a task's runs, over {len(both)} tasks with primitives in both arms: "
                   f"{100 * m:+.1f} points (95% interval {100 * lo:+.1f} to {100 * hi:+.1f}).")
        out.append(f"- Tasks where only {cname} shows {signal_name} in some run: {only_c}. Only {oname}: {only_o}. Exact McNemar p = {mcnemar_exact(only_c, only_o):.3f}.")
        count = COUNTS.get(signal_name)
        if count:
            per = {(t, arm): [count(c) for c in (run_calls(r, primitives_dir) for r in rs) if c is not None]
                   for t in common for arm, rs in (("c", ct[t]), ("o", ot[t]))}
            tasks = [t for t in common if per[t, "c"] and per[t, "o"]]
            m, lo, hi = bootstrap_mean([sum(per[t, "o"]) / len(per[t, "o"]) - sum(per[t, "c"]) / len(per[t, "c"]) for t in tasks])
            out.append(f"- Mean {signal_name} count difference ({oname} minus {cname}), paired by task, over {len(tasks)} tasks: "
                       f"{m:+.1f} calls (95% interval {lo:+.1f} to {hi:+.1f}).")
    if len(common) < 10:
        out.append(f"- Bootstrap intervals rest on {len(common)} tasks. With fewer than 10 tasks they say little.")
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
    if control not in arms:
        sys.exit(f"--control {control} is not an arm")
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
             f"- Checkout (`repo_sha`): {', '.join(sorted({r.get('repo_sha', 'unrecorded')[:12] for r in everything}))}.",
             f"- Control: {control}. Trials killed by the timeout are counted apart and left out of credits.", "",
             "## Arms", "",
             "| Arm | Tasks | Trials | Passed | Pass rate (95% Wilson) | Timed out | Credits | Credits per trial |" + (f" {args.signal} runs |" if signal else ""),
             "|---|---|---|---|---|---|---|---|" + ("---|" if signal else "")]
    lines += [arm_row(n, rs, args.primitives, signal) for n, rs in arms.items()]
    lines += ["", "## Paired differences", ""]
    for name, rs in arms.items():
        if name != control:
            lines += paired_lines(arms[control], rs, control, name, args.primitives, signal, args.signal) + [""]
    lines += verification_lines(arms, args.primitives) + [""]
    lines += agreement_lines(arms, args.primitives)
    text = "\n".join(lines) + "\n"
    if args.out:
        args.out.write_text(text, newline="\n")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
