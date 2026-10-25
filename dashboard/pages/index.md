---
title: Proposals
sidebar: never
hide_title: true
full_width: true
---

```sql mock_rows
select * from mock.proposals
```

```sql plist
select * from proposal_list.proposals where proposal_id <> ''
```

```sql pruns
select * from tiger.proposal_runs
```

<script>
  import { signed, interval, has } from '../components/format.js';
  import { buildProposals, statusRank } from '../components/proposals.js';
  $: real = buildProposals(plist, pruns);
  $: example = real.length === 0;
  $: list = (example ? Array.from(mock_rows ?? []).map((m) => ({ ...m, example: true })) : real).slice().sort((a, b) => statusRank(a.status) - statusRank(b.status) || a.proposal_id.localeCompare(b.proposal_id));
  $: count = (...s) => list.filter((p) => s.includes(p.status)).length;
  $: g = list.filter((p) => p.evidence_role === 'final' && has(p.inc_high_pp) && p.inc_high_pp < 0).sort((a, b) => a.inc_delta_pp - b.inc_delta_pp)[0];
  $: s = list.filter((p) => p.evidence_role === 'final' && has(p.credits_high_pct) && p.credits_high_pct < 0).sort((a, b) => a.credits_delta_pct - b.credits_delta_pct)[0];
  $: queue = list.filter((p) => p.status === 'in_review');
  $: rest = list.filter((p) => p.status !== 'in_review');
</script>

<div class="rt-page-head">
  <h1>Proposals</h1>
  <p>Harness changes drafted from behaviour and cost patterns. Each one has replay evidence on agent behaviour and cost, and a pull request.</p>
</div>

{#if example}
  <div class="rt-example">Example data. These proposals are fixtures in <code>sources/mock/proposals.csv</code>. Real proposals replace them when <code>analysis/proposals/</code> has one.</div>
{/if}

<div class="rt-kpis">
  <div class="rt-kpi rt-attn"><span class="rt-k">Waiting for review</span><span class="rt-big">{count("in_review")}</span><span class="rt-s">Decide in the pull request</span></div>
  <div class="rt-kpi"><span class="rt-k">Shipped</span><span class="rt-big">{count("shipped")}</span><span class="rt-s">{count("rejected")} rejected</span></div>
  <div class="rt-kpi"><span class="rt-k">In progress</span><span class="rt-big">{count("drafted", "replay")}</span><span class="rt-s">Drafted or in replay</span></div>
  <div class="rt-kpi">
    <span class="rt-k">Largest behaviour cut</span>
    {#if g}
      <span class="rt-big">{signed(g.inc_delta_pp)} pp</span>
      <span class="rt-s">{interval(g.inc_low_pp, g.inc_high_pp)} · {g.target_metric.toLowerCase()} · {g.title}</span>
    {:else}
      <span class="rt-big">None yet</span><span class="rt-s">No interval excludes zero</span>
    {/if}
  </div>
  <div class="rt-kpi">
    <span class="rt-k">Best credit saving</span>
    {#if s}
      <span class="rt-big">{signed(s.credits_delta_pct)}%</span>
      <span class="rt-s">{interval(s.credits_low_pct, s.credits_high_pct)} per run · {s.title}</span>
    {:else}
      <span class="rt-big">None yet</span><span class="rt-s">No interval excludes zero</span>
    {/if}
  </div>
</div>

{#if queue.length}
  <div class="rt-section">Waiting for review</div>
  <div class="rt-cards">
    {#each queue as p}<ProposalCard {p} />{/each}
  </div>
{/if}

<div class="rt-section">All other proposals</div>
<div class="rt-cards">
  {#each rest as p}<ProposalCard {p} />{/each}
</div>
