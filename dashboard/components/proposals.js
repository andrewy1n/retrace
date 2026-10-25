import { has } from './format.js';

export const SIGNALS = {
  whole_suite_tests: { column: 'signal_whole_suite_tests', metric: 'Runs with a whole-suite test run over 60 s' },
  calls_before_first_edit: { column: 'signal_calls_before_first_edit', metric: 'Runs with more than 12 calls before the first edit' }
};

const BOOTSTRAPS = 10000;
const SEED = 20261024;

function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const mean = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;
const round1 = (x) => Math.round(x * 10) / 10;

export function bootstrapMean(values) {
  const next = rng(SEED);
  const n = values.length;
  const means = [];
  for (let i = 0; i < BOOTSTRAPS; i++) {
    let s = 0;
    for (let j = 0; j < n; j++) s += values[Math.floor(next() * n)];
    means.push(s / n);
  }
  means.sort((a, b) => a - b);
  return { mean: mean(values), low: means[Math.floor(0.025 * BOOTSTRAPS)], high: means[Math.floor(0.975 * BOOTSTRAPS) - 1] };
}

function byTask(rows, value) {
  const tasks = new Map();
  for (const r of rows) {
    const v = value(r);
    if (v === null || v === undefined || Number.isNaN(v)) continue;
    if (!tasks.has(r.task_id)) tasks.set(r.task_id, []);
    tasks.get(r.task_id).push(v);
  }
  return new Map([...tasks].map(([t, vs]) => [t, mean(vs)]));
}

function pairedDiffs(control, candidate, value) {
  const c = byTask(control, value);
  const a = byTask(candidate, value);
  return [...a].filter(([t]) => c.has(t)).map(([t, v]) => v - c.get(t));
}

export const signalOf = (column) => (r) => (r.has_primitives ? (r[column] ? 1 : 0) : null);
const logCredits = (r) => (!r.timed_out && Number(r.cost_credits) > 0 ? Math.log(Number(r.cost_credits)) : null);

const repoUsable = (r) => r.repo_status === 'ok';
const accUsable = (r) => r.acc_at_start === 'fail' && r.acc_status !== 'error' && has(r.acc_status);

function guardText(control, candidate) {
  const repo = (rs) => [rs.filter(repoUsable).filter((r) => Number(r.repo_regressed) > 0).length, rs.filter(repoUsable).length];
  const acc = (rs) => [rs.filter(accUsable).filter((r) => r.acc_status === 'pass').length, rs.filter(accUsable).length];
  const [rk, rn] = repo(candidate);
  const [rck, rcn] = repo(control);
  const [ak, an] = acc(candidate);
  const [ack, acn] = acc(control);
  return {
    guard_repo: rn ? `${rk} of ${rn} runs regress repo tests; baseline ${rck} of ${rcn}` : '',
    guard_acceptance: an ? `${ak} of ${an} pass; baseline ${ack} of ${acn}` : ''
  };
}

const words = (s) => s.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());

export function compareArms(control, candidate, signal) {
  const credit = pairedDiffs(control, candidate, logCredits);
  const out = { paired_tasks: pairedDiffs(control, candidate, () => 1).length };
  if (credit.length) {
    const b = bootstrapMean(credit);
    out.credits = { delta: round1((Math.exp(b.mean) - 1) * 100), low: round1((Math.exp(b.low) - 1) * 100), high: round1((Math.exp(b.high) - 1) * 100) };
  }
  if (signal) {
    const sig = signalOf(signal.column);
    const seen = (rs) => rs.map(sig).filter((v) => v !== null);
    out.arm = [seen(candidate).reduce((a, b) => a + b, 0), seen(candidate).length];
    out.base = [seen(control).reduce((a, b) => a + b, 0), seen(control).length];
    const d = pairedDiffs(control, candidate, sig);
    if (d.length) {
      const b = bootstrapMean(d);
      out.incidence = { delta: round1(b.mean * 100), low: round1(b.low * 100), high: round1(b.high * 100), tasks: d.length };
    }
  }
  return out;
}

export function buildProposals(list, runs) {
  const all = Array.from(runs ?? []);
  return Array.from(list ?? []).map((p) => {
    const pairs = (p.pairs ?? '').split(';').filter(Boolean).map((s) => s.split(':'));
    const ctrlJobs = new Set(pairs.map((x) => x[0]));
    const candJobs = new Set(pairs.map((x) => x[1]));
    const control = all.filter((r) => r.arm === 'control' && ctrlJobs.has(r.job_id));
    const candidate = all.filter((r) => r.arm === 'candidate' && candJobs.has(r.job_id));
    const hasRuns = control.length > 0 && candidate.length > 0;
    const target = has(p.cost_pattern) ? p.cost_pattern : p.failure_type;
    const signal = has(p.cost_pattern) ? SIGNALS[p.cost_pattern] : undefined;
    const files = has(p.overlay_files) ? p.overlay_files.split(';') : [];
    const row = {
      proposal_id: p.proposal_id,
      path: p.path,
      title: words(p.proposal_id.replace(/-/g, '_')),
      kind: has(p.cost_pattern) ? 'cost' : 'failure',
      target: words(target),
      change_type: p.change_type,
      status: has(p.pr_url) ? 'in_review' : hasRuns ? 'replay' : 'drafted',
      severity: '',
      sessions: candidate.length,
      evidence_role: hasRuns ? 'final' : '',
      target_metric: signal ? signal.metric : 'Target behaviour',
      pr_url: p.pr_url,
      summary: `Targets ${has(p.cost_pattern) ? 'the cost pattern' : 'the failure group'} ${target.replace(/_/g, ' ')}. The overlay has ${files.length} ${files.length === 1 ? 'file' : 'files'}.`,
      overlay_files: p.overlay_files,
      patch: p.patch,
      signal_defined: Boolean(signal),
      signal_column: signal?.column,
      pairs: pairs.map((x) => `${x[0]} against ${x[1]}`).join('; ')
    };
    if (!hasRuns) return row;
    const cmp = compareArms(control, candidate, signal);
    Object.assign(row, guardText(control, candidate));
    row.paired_tasks = cmp.paired_tasks;
    row.setup = `${cmp.paired_tasks} tasks, ${candidate.length} runs with the change and ${control.length} baseline runs, ${candidate[0].model}. Ranges are 95% intervals over tasks`;
    if (cmp.arm) {
      row.inc_arm_k = cmp.arm[0];
      row.inc_arm_n = cmp.arm[1];
      row.inc_base_k = cmp.base[0];
      row.inc_base_n = cmp.base[1];
    }
    if (cmp.incidence) {
      row.inc_delta_pp = cmp.incidence.delta;
      row.inc_low_pp = cmp.incidence.low;
      row.inc_high_pp = cmp.incidence.high;
    }
    if (cmp.credits) {
      row.credits_delta_pct = cmp.credits.delta;
      row.credits_low_pct = cmp.credits.low;
      row.credits_high_pct = cmp.credits.high;
    }
    row.runs = [...control, ...candidate];
    return row;
  });
}

export function statusRank(s) {
  return { in_review: 1, replay: 2, drafted: 3, shipped: 4 }[s] ?? 5;
}

const shortTask = (id) => id.replace(/^instance_(.+?)-([0-9a-f]{8})[0-9a-f]{32}.*$/, '$1-$2');

export function taskTable(runs, column) {
  const groups = new Map();
  for (const r of runs) {
    const key = `${r.task_id}|${r.arm}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(r);
  }
  const sig = column ? signalOf(column) : () => null;
  return [...groups.values()]
    .map((rs) => {
      const seen = rs.map(sig).filter((v) => v !== null);
      const repo = rs.filter(repoUsable);
      const acc = rs.filter(accUsable);
      return {
        task: shortTask(rs[0].task_id),
        arm: rs[0].arm === 'control' ? 'Baseline' : 'With change',
        runs: rs.length,
        signal: seen.length ? `${seen.reduce((a, b) => a + b, 0)} of ${seen.length}` : 'no primitives',
        credits: mean(rs.map((r) => Number(r.cost_credits))),
        repo: repo.length ? `${repo.filter((r) => Number(r.repo_regressed) > 0).length} of ${repo.length} regress` : 'not run',
        acc: acc.length ? `${acc.filter((r) => r.acc_status === 'pass').length} of ${acc.length} pass` : 'not run'
      };
    })
    .sort((a, b) => a.task.localeCompare(b.task) || a.arm.localeCompare(b.arm));
}
