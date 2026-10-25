import { has } from './format.js';

export function behaviourVerdict(p) {
  if (!has(p.evidence_role)) return { label: 'No replay yet', tone: 'muted' };
  if (p.evidence_role === 'diagnosis') return { label: 'Diagnosis only', tone: 'info' };
  if (p.kind === 'cost') {
    return p.credits_high_pct < 0
      ? { label: 'Cheaper', tone: 'ok' }
      : { label: 'No clear saving', tone: 'muted' };
  }
  if (p.inc_high_pp < 0) return { label: 'Cuts the behaviour', tone: 'ok' };
  if (p.inc_low_pp > 0) return { label: 'Adds the behaviour', tone: 'bad' };
  return { label: 'No clear change', tone: 'muted' };
}

export const share = (k, n) => `${k} of ${n}`;
