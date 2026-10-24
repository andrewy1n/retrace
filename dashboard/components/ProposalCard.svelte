<script>
  import Chip from './Chip.svelte';
  import PrButton from './PrButton.svelte';
  import { STATUS, CHANGE, has, signed, interval, verdict } from './format.js';

  export let p;

  $: status = STATUS[p.status] ?? { label: p.status, tone: 'muted' };
  $: v = verdict(p);
  $: final = p.evidence_role === 'final';
  $: diagnosis = p.evidence_role === 'diagnosis';
</script>

<article class="rt-card">
  <div class="rt-tags">
    <Chip label={status.label} tone={status.tone} />
    <span class="rt-tag">{p.target}</span>
    <span class="rt-tag">{CHANGE[p.change_type] ?? p.change_type}</span>
    <span class="rt-tag">{p.sessions} sessions</span>
  </div>
  <h3><a href="/proposals/{p.proposal_id}">{p.title}</a></h3>
  <p class="rt-summary">{p.summary}</p>
  <div class="rt-metrics">
    <div>
      <span class="rt-k">Pass rate vs control</span>
      {#if final}
        <span class="rt-v">{signed(p.delta_pp)} pp</span>
        <span class="rt-s">{interval(p.ci_low_pp, p.ci_high_pp)} · {p.arm_k}/{p.arm_n} vs {p.base_k}/{p.base_n}</span>
      {:else if diagnosis}
        <span class="rt-v">{p.arm_k}/{p.arm_n} vs {p.base_k}/{p.base_n}</span>
        <span class="rt-s">forks, no interval</span>
      {:else}
        <span class="rt-v rt-none">Not run</span>
      {/if}
    </div>
    <div>
      <span class="rt-k">Credits per trial</span>
      {#if final && has(p.credits_delta_pct)}
        <span class="rt-v">{signed(p.credits_delta_pct)}%</span>
        <span class="rt-s">{interval(p.credits_low_pct, p.credits_high_pct)} · held-out</span>
      {:else}
        <span class="rt-v rt-none">Not run</span>
      {/if}
    </div>
    <div>
      <span class="rt-k">Regression set</span>
      {#if has(p.regression)}
        <span class="rt-v">{p.regression}</span>
        <span class="rt-s">legitimate test edits included</span>
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
