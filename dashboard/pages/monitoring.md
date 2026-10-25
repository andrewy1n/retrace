---
title: Monitoring
sidebar: never
full_width: true
---

<div class="rt-example">Example data. It shows the shipped example proposal, not real sessions.</div>

<div class="rt-page-head">
  <p>A shipped change has no ground truth in production. These series replace it: how often the targeted behaviour occurs, what a session costs, and how many repo tests it breaks. The example is <code>limit-suite-reruns</code>, a hook that blocks the third whole-suite test run in a session.</p>
</div>

```sql daily
select day::date as day,
  sessions, sessions_with_behaviour, credits, repo_regressions,
  sessions_with_behaviour::double / sessions as incidence,
  credits::double / sessions as credits_per_session,
  repo_regressions::double / sessions as regressions_per_session,
  case when day::date >= date '2026-10-10' then 'After' else 'Before' end as period
from mock.monitoring
order by day
```

```sql periods
select period,
  sum(sessions)::int as sessions,
  sum(sessions_with_behaviour)::double / sum(sessions) as incidence,
  sum(credits)::double / sum(sessions) as credits_per_session,
  sum(repo_regressions)::double / sum(sessions) as regressions_per_session
from ${daily}
group by 1
order by case when period = 'Before' then 0 else 1 end
```

<DataTable data={periods} wrapTitles=true>
  <Column id=period title="Period" />
  <Column id=sessions title="Sessions" />
  <Column id=incidence title="Sessions with the behaviour" fmt=pct1 />
  <Column id=credits_per_session title="Credits per session" fmt=num0 />
  <Column id=regressions_per_session title="Repo-test regressions per session" fmt=num2 />
</DataTable>

The change shipped on 2026-10-10. Before is 14 days, after is 14 days.

## Targeted behaviour

<LineChart data={daily} x=day y=incidence yFmt=pct0 title="Sessions with 4 or more whole-suite test runs, per day" yMin=0>
  <ReferenceLine x='2026-10-10' label="Shipped" />
</LineChart>

## Credits per session

<LineChart data={daily} x=day y=credits_per_session yFmt=num0 title="Factory credits per session, per day" yMin=0>
  <ReferenceLine x='2026-10-10' label="Shipped" />
</LineChart>

## Repo-test regressions per session

<LineChart data={daily} x=day y=regressions_per_session yFmt=num2 title="Regressed repo tests per session, per day" yMin=0>
  <ReferenceLine x='2026-10-10' label="Shipped" />
</LineChart>

## Roll back

<div class="rt-card">
  <p class="rt-summary">Rollback means reverting the pull request that added <code>analysis/proposals/limit-suite-reruns/</code>. Revert that pull request in the repository. The overlay files leave the next session. No other state changes.</p>
  <span class="rt-btn rt-btn-off">Revert pull request (not available in this example)</span>
</div>
