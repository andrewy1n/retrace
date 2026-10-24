---
title: Proposals
sidebar: never
hide_title: true
full_width: true
---

```sql kpi
select
  sum(case when status = 'in_review' then 1 else 0 end)::int as in_review,
  sum(case when status = 'shipped' then 1 else 0 end)::int as shipped,
  sum(case when status in ('drafted', 'replay') then 1 else 0 end)::int as in_progress,
  sum(case when status = 'rejected' then 1 else 0 end)::int as rejected
from mock.proposals
```

```sql best_gain
select title, delta_pp, ci_low_pp, ci_high_pp, arm_k, arm_n, base_k, base_n
from mock.proposals
where evidence_role = 'final' and kind = 'failure' and ci_low_pp > 0
order by delta_pp desc limit 1
```

```sql best_saving
select title, credits_delta_pct, credits_low_pct, credits_high_pct, arm_n
from mock.proposals
where evidence_role = 'final' and credits_high_pct < 0
order by credits_delta_pct limit 1
```

```sql proposals
select *,
  case status when 'in_review' then 1 when 'replay' then 2 when 'drafted' then 3 when 'shipped' then 4 else 5 end as rank
from mock.proposals
order by rank, proposal_id
```

<script>
  import { signed, interval } from '../components/format.js';
  $: k = Array.from(kpi ?? [])[0] ?? {};
  $: g = Array.from(best_gain ?? [])[0];
  $: s = Array.from(best_saving ?? [])[0];
  $: list = Array.from(proposals ?? []);
  $: queue = list.filter((p) => p.status === 'in_review');
  $: rest = list.filter((p) => p.status !== 'in_review');
</script>

<div class="rt-page-head">
  <h1>Proposals</h1>
  <p>Harness changes drafted from failure and cost patterns. Each one has replay evidence and a pull request.</p>
</div>

<div class="rt-example">Example data. These proposals are fixtures in <code>sources/mock/proposals.csv</code>. Tiger summaries replace them when real proposals exist.</div>

<div class="rt-kpis">
  <div class="rt-kpi rt-attn"><span class="rt-k">Waiting for review</span><span class="rt-big">{k.in_review ?? 0}</span><span class="rt-s">Decide in the pull request</span></div>
  <div class="rt-kpi"><span class="rt-k">Shipped</span><span class="rt-big">{k.shipped ?? 0}</span><span class="rt-s">{k.rejected ?? 0} rejected</span></div>
  <div class="rt-kpi"><span class="rt-k">In progress</span><span class="rt-big">{k.in_progress ?? 0}</span><span class="rt-s">Drafted or in replay</span></div>
  <div class="rt-kpi">
    <span class="rt-k">Best held-out gain</span>
    {#if g}
      <span class="rt-big">{signed(g.delta_pp)} pp</span>
      <span class="rt-s">{interval(g.ci_low_pp, g.ci_high_pp)} · {g.arm_k}/{g.arm_n} vs {g.base_k}/{g.base_n} · {g.title}</span>
    {:else}
      <span class="rt-big">None yet</span><span class="rt-s">No interval excludes zero</span>
    {/if}
  </div>
  <div class="rt-kpi">
    <span class="rt-k">Best credit saving</span>
    {#if s}
      <span class="rt-big">{signed(s.credits_delta_pct)}%</span>
      <span class="rt-s">{interval(s.credits_low_pct, s.credits_high_pct)} per trial · {s.title}</span>
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
