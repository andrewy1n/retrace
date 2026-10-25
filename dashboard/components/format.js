export const STATUS = {
  in_review: { label: 'In review', tone: 'review' },
  replay: { label: 'Replay', tone: 'info' },
  drafted: { label: 'Drafted', tone: 'muted' },
  shipped: { label: 'Shipped', tone: 'ok' },
  rejected: { label: 'Rejected', tone: 'bad' }
};

export const CHANGE = {
  guardrail_hook: 'Guardrail hook',
  skill: 'Skill',
  tool: 'Tool',
  custom_droid: 'Custom droid',
  setting: 'Setting',
  rule: 'AGENTS.md rule'
};

export const has = (v) => v !== null && v !== undefined && v !== '';

export const signed = (v) => (v > 0 ? '+' : v < 0 ? '-' : '') + Math.abs(Number(v));

export const interval = (lo, hi) => `[${signed(lo)}, ${signed(hi)}]`;

export function repoText(r) {
  if (!has(r.repo_status)) return 'repo tests: not run';
  if (r.repo_status === 'no_tests') return 'repo tests: none found';
  if (r.repo_status === 'error') return 'repo tests: error';
  return `repo tests: ${r.repo_regressed} regressed of ${r.repo_passing_at_start}`;
}

export function accText(r) {
  if (!has(r.acc_status)) return 'acceptance: not run';
  if (r.acc_status === 'error') return 'acceptance: error';
  return `acceptance: ${r.acc_status} (${r.acc_at_start} at start)`;
}

export function verdict(p) {
  if (!has(p.evidence_role)) return { label: 'No replay yet', tone: 'muted' };
  if (p.evidence_role === 'diagnosis') return { label: 'Diagnosis only', tone: 'info' };
  if (p.kind === 'cost') {
    return p.credits_high_pct < 0
      ? { label: 'Cheaper', tone: 'ok' }
      : { label: 'No clear saving', tone: 'muted' };
  }
  if (p.ci_low_pp > 0) return { label: 'Beats baseline', tone: 'ok' };
  if (p.ci_high_pp < 0) return { label: 'Worse than baseline', tone: 'bad' };
  return { label: 'No clear difference', tone: 'muted' };
}

export function intervalChart(delta, lo, hi, unit) {
  const min = Math.min(-20, Math.floor((lo - 10) / 10) * 10);
  const max = Math.max(20, Math.ceil((hi + 10) / 10) * 10);
  return {
    grid: { left: 24, right: 24, top: 32, bottom: 28 },
    xAxis: { type: 'value', min, max, splitLine: { show: false }, axisLabel: { formatter: (v) => `${signed(v)} ${unit}` } },
    yAxis: { type: 'value', min: -1, max: 1, show: false },
    series: [
      { type: 'line', silent: true, symbol: 'none', lineStyle: { width: 4, color: '#71717a' }, data: [[lo, 0], [hi, 0]] },
      {
        type: 'scatter', symbolSize: 14, itemStyle: { color: '#27272a' }, data: [[delta, 0]],
        label: { show: true, position: 'top', formatter: `${signed(delta)} ${unit} ${interval(lo, hi)}`, color: '#27272a' },
        markLine: { silent: true, symbol: 'none', lineStyle: { color: '#a1a1aa', type: 'dashed' }, label: { show: false }, data: [{ xAxis: 0 }] }
      }
    ]
  };
}
