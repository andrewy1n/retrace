<script>
  import Chip from './Chip.svelte';
  import PrButton from './PrButton.svelte';
  import { STATUS, CHANGE, has, signed, interval } from './format.js';
  import { behaviourVerdict, share } from './behaviour.js';

  export let p;

  $: status = STATUS[p.status] ?? { label: p.status, tone: 'muted' };
  $: v = behaviourVerdict(p);
  $: final = p.evidence_role === 'final';
  $: diagnosis = p.evidence_role === 'diagnosis';
  $: hasGuards = has(p.guard_repo) || has(p.guard_acceptance);
</script>

<style>
  .guard { display: block; font-size: 12px; color: #71717a; }
  .guard + .guard { margin-top: 2px; }
  .guard b { font-weight: 600; color: #3f3f46; }
</style>

<article class="rt-card">
  <div class="rt-tags">
    <Chip label={status.label} tone={status.tone} />
    <span class="rt-tag">{p.target}</span>
    <span class="rt-tag">{CHANGE[p.change_type] ?? p.change_type}</span>
    <span class="rt-tag">{p.sessions} {p.example ? 'sessions' : 'runs with the change'}</span>
  </div>
  <h3><a href="/proposals/{p.proposal_id}">{p.title}</a></h3>
  <p class="rt-summary">{p.summary}</p>
  <div class="rt-metrics">
    <div>
      <span class="rt-k">{p.target_metric}</span>
      {#if final && !has(p.inc_delta_pp)}
        <span class="rt-v rt-none">Not measured</span>
        <span class="rt-s">{p.signal_defined ? 'No recorded runs yet' : 'No incidence signal is defined for this target'}</span>
      {:else if final}
        <span class="rt-v">{signed(p.inc_delta_pp)} pp</span>
        <span class="rt-s">{interval(p.inc_low_pp, p.inc_high_pp)} · {share(p.inc_arm_k, p.inc_arm_n)} runs, baseline {share(p.inc_base_k, p.inc_base_n)}</span>
      {:else if diagnosis}
        <span class="rt-v">{p.inc_arm_k}/{p.inc_arm_n} vs {p.inc_base_k}/{p.inc_base_n}</span>
        <span class="rt-s">forks with the change vs baseline, no interval</span>
      {:else}
        <span class="rt-v rt-none">Not run</span>
      {/if}
    </div>
    <div>
      <span class="rt-k">Credits per run</span>
      {#if final && has(p.credits_delta_pct)}
        <span class="rt-v">{signed(p.credits_delta_pct)}%</span>
        <span class="rt-s">{interval(p.credits_low_pct, p.credits_high_pct)} · {p.example ? 'held-out' : 'per run'}</span>
      {:else}
        <span class="rt-v rt-none">Not run</span>
      {/if}
    </div>
    <div>
      <span class="rt-k">Guards</span>
      {#if hasGuards}
        {#if has(p.guard_repo)}<span class="guard"><b>Repo tests</b> {p.guard_repo}</span>{/if}
        {#if has(p.guard_acceptance)}<span class="guard"><b>Acceptance check</b> {p.guard_acceptance}</span>{/if}
      {:else}
        <span class="rt-v rt-none">Not run</span>
      {/if}
    </div>
  </div>
  <div class="rt-foot">
    <Chip label={v.label} tone={v.tone} />
    <span class="rt-spacer"></span>
    <PrButton url={has(p.pr_url) ? p.pr_url : null} />
    <a class="rt-link" href="/proposals/{p.proposal_id}">Details →</a>
  </div>
</article>
