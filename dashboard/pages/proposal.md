---
title: Proposal
sidebar: never
full_width: true
---

<script>
  import { html as diffToHtml } from 'diff2html';
  import 'diff2html/bundles/css/diff2html.min.css';

  const patch = `--- a/.factory/hooks.json
+++ b/.factory/hooks.json
@@ -0,0 +1,14 @@
+{
+  "PreToolUse": [
+    {
+      "matcher": "Edit|Create|ApplyPatch",
+      "hooks": [
+        {
+          "type": "command",
+          "command": ".factory/hooks/block_test_edits.py",
+          "timeout": 10
+        }
+      ]
+    }
+  ]
+}
--- a/.factory/hooks/block_test_edits.py
+++ b/.factory/hooks/block_test_edits.py
@@ -1,9 +1,11 @@
 import json, re, sys
 
 ev = json.load(sys.stdin)
 path = ev["tool_input"].get("file_path", "")
-if re.search(r"(^|/)tests?/", path):
+if re.search(r"(^|/)(tests?|testing)/", path) or path.endswith("conftest.py"):
     print("Tests are the spec; fix the source, not the tests.", file=sys.stderr)
     sys.exit(2)
+sys.exit(0)`;
  const diffHtml = diffToHtml(patch, { drawFileList: false, matching: 'lines', outputFormat: 'line-by-line', colorScheme: 'light' });

  const colors = { read: '#a1a1aa', search: '#7c93b3', edit: '#c7843b', test: '#3f7f5f', vcs: '#8d6fa8' };

  $: rows = Array.from(tl ?? []);
  $: classes = [...new Set(rows.map((r) => r.command_class))];
  $: timeline = {
    grid: { left: 56, right: 16, top: 40, bottom: 40 },
    legend: { top: 0, left: 0 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (p) => {
        const r = rows[p[0].dataIndex];
        return `step ${r.position}<br/>${r.tool_name}, ${r.command_class}<br/>${Number(r.duration_s).toFixed(2)} s, ~${r.output_tokens_est} output tokens` +
          (r.test_runner ? `<br/>test runner: ${r.test_runner}` : '') + (r.is_error ? '<br/>error' : '');
      }
    },
    xAxis: { type: 'category', data: rows.map((r) => r.position), name: 'step', nameLocation: 'middle', nameGap: 26 },
    yAxis: { type: 'value' },
    series: [
      ...classes.map((c) => ({
        name: c, type: 'bar', stack: 's', itemStyle: { color: colors[c] ?? '#888' },
        data: rows.map((r) => r.command_class === c ? { value: r.output_tokens_est, itemStyle: r.test_runner ? { borderColor: '#111', borderWidth: 2 } : {} } : null)
      })),
      { name: 'test run', type: 'scatter', symbol: 'triangle', symbolSize: 9, symbolOffset: [0, -10], itemStyle: { color: '#111' },
        data: rows.map((r, i) => r.test_runner ? [i, r.output_tokens_est] : null).filter(Boolean) },
      { name: 'error', type: 'scatter', symbol: 'diamond', symbolSize: 10, symbolOffset: [0, -10], itemStyle: { color: '#dc2626' },
        data: rows.map((r, i) => r.is_error ? [i, r.output_tokens_est] : null).filter(Boolean) }
    ]
  };

  $: w = Array.from(wilson ?? []);
  $: wilsonChart = {
    grid: { left: 56, right: 16, top: 16, bottom: 32 },
    tooltip: {
      trigger: 'axis',
      formatter: (p) => { const r = w[p[0].dataIndex]; return `${r.job_id}<br/>${r.k}/${r.n} passed, ${(r.p * 100).toFixed(1)}%<br/>95% Wilson ${(r.lo * 100).toFixed(1)}% to ${(r.hi * 100).toFixed(1)}%`; }
    },
    xAxis: { type: 'category', data: w.map((r) => r.job_id) },
    yAxis: { type: 'value', min: 0, max: 1, axisLabel: { formatter: (v) => `${v * 100}%` } },
    series: [
      { type: 'bar', stack: 'ci', itemStyle: { color: 'transparent' }, data: w.map((r) => r.lo), silent: true },
      { type: 'bar', stack: 'ci', barWidth: 3, itemStyle: { color: '#71717a' }, data: w.map((r) => r.hi - r.lo) },
      { type: 'scatter', symbolSize: 12, itemStyle: { color: '#27272a' }, data: w.map((r) => r.p) }
    ]
  };
</script>

<style>
  :global(:root) { --d2h-change-del-color: #fee8e9; --d2h-change-ins-color: #ddf4e0; --d2h-change-label-color: #b45309; }
</style>

<BigValue data={[{v:'Test tampering'}]} value=v title="Ticket" />
<BigValue data={[{v:'High'}]} value=v title="Severity" />
<BigValue data={[{v:'6'}]} value=v title="Sessions" />
<BigValue data={[{v:'7/12 with change vs 1/12 control'}]} value=v title="Replay" />

The agent edited tests in 6 of the sessions it failed. A PreToolUse hook now blocks edits under `tests/` and `testing/` and edits to `conftest.py`. With the hook, 7 of 12 replays passed against 1 of 12 for control.

<div style="color: #1f2328">{@html diffHtml}</div>

## Tool calls in one session

```sql tl
select position, tool_name, command_class, test_runner, duration_s, is_error, output_tokens_est
from tiger.calls
where session_id = 'pro-baseline1-instance_gravitational__teleport-c782838c3a174fdff80cafd8cd3b1aa4dae8beb2-2'
order by position
```

<ECharts config={timeline} height=320px />

## Cumulative output tokens

```sql cum
select
  case when session_id like '%teleport-c782838%' then 'teleport (77,812 credits)' else 'flipt (2,328 credits)' end as session,
  position,
  sum(output_tokens_est) over (partition by session_id order by position) as cum_tokens
from tiger.calls
where session_id in (
  'pro-baseline1-instance_gravitational__teleport-c782838c3a174fdff80cafd8cd3b1aa4dae8beb2-2',
  'pro-baseline1-instance_flipt-io__flipt-72d06db14d58692bfb4d07b1aa745a37b35956f3-2')
order by session, position
```

<LineChart data={cum} x=position y=cum_tokens series=session yFmt=num0 />

## Pass rate with 95% Wilson interval

```sql wilson
with t as (
  select job_id, count(*)::double as n, sum(passed)::double as k
  from tiger.results where job_id in ('baseline1', 'baseline2', 'pro-baseline1') group by 1
), s as (select *, k / n as p, 3.8416 / n as z2n from t)
select job_id, n::int as n, k::int as k, p,
  (p + z2n / 2) / (1 + z2n) - 1.96 * sqrt(p * (1 - p) / n + 3.8416 / (4 * n * n)) / (1 + z2n) as lo,
  (p + z2n / 2) / (1 + z2n) + 1.96 * sqrt(p * (1 - p) / n + 3.8416 / (4 * n * n)) / (1 + z2n) as hi
from s order by job_id
```

<ECharts config={wilsonChart} height=300px />
