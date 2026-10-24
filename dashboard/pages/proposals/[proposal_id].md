---
title: Proposal
sidebar: never
hide_title: true
full_width: true
---

```sql p
select * from mock.proposals where proposal_id = '${params.proposal_id}'
```

```sql tl
select position, tool_name, command_class, test_runner, duration_s, is_error, output_tokens_est
from tiger.calls
where session_id = 'pro-baseline1-instance_gravitational__teleport-c782838c3a174fdff80cafd8cd3b1aa4dae8beb2-2'
order by position
```

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

```sql strip
select position, tool_call_id, tool_name, command_class, test_runner, coalesce(test_runner, tool_name) as label
from tiger.calls
where session_id = 'pro-baseline1-instance_ansible__ansible-d33bedc48fdd933b5abd65a77c081876298e2f07-v0f01c69f1e2528b935359cfe578530722bca2c59-1'
  and position < 25
order by position
```

<script>
  import { html as diffToHtml } from 'diff2html';
  import 'diff2html/bundles/css/diff2html.min.css';
  import { STATUS, CHANGE, has, signed, interval, verdict, intervalChart } from '../../../components/format.js';

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
  const patches = { 'block-test-edits': patch };
  const diffFor = (id) => patches[id] ? diffToHtml(patches[id], { drawFileList: false, matching: 'lines', outputFormat: 'line-by-line', colorScheme: 'light' }) : null;

  $: row = Array.from(p ?? [])[0];
  $: status = row ? (STATUS[row.status] ?? { label: row.status, tone: 'muted' }) : null;
  $: v = row ? verdict(row) : null;
  $: final = row?.evidence_role === 'final';
  $: diagnosis = row?.evidence_role === 'diagnosis';
  $: files = row?.overlay_files ? row.overlay_files.split(';') : [];
  $: diffHtml = row ? diffFor(row.proposal_id) : null;
  $: passChart = final ? intervalChart(row.delta_pp, row.ci_low_pp, row.ci_high_pp, 'pp') : null;
  $: creditChart = final && has(row.credits_delta_pct) ? intervalChart(row.credits_delta_pct, row.credits_low_pct, row.credits_high_pct, '%') : null;
  $: rank = row ? ['guardrail_hook', 'skill', 'tool', 'custom_droid', 'setting', 'rule'].indexOf(row.change_type) : -1;

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

  const sessionLabel = 'ansible d33bed, trial 1';
  const checkpoints = { toolu_01Pm3ZNrBCDtHNUh83ovCqeC: 'Step 10', toolu_016dLe3d1iqCZzTGPkUnoaXN: 'Step 17' };
  const kind = (c) => c.command_class === 'edit' ? 'edit' : c.tool_name === 'Execute' ? 'exec' : 'read';

  const arms = [
    { name: 'Recorded run', what: 'the original session' },
    { name: 'Control', what: 'fork, no change' },
    { name: 'Hint', what: 'fork, hint text added' },
    { name: 'With change', what: 'fork, overlay applied' }
  ];
  const matrix = [
    { step: 'Step 10', id: 'toolu_01Pm3Z…', cells: [[1], [1, 1], [1, 0], [1, 1]] },
    { step: 'Step 17', id: 'toolu_016dLe…', cells: [[1], [1, 1], [0, 1], [1, 1]] }
  ];
  const forkTotal = (i) => matrix.flatMap((r) => r.cells[i]);
  const sum = (a) => a.reduce((s, x) => s + x, 0);
  const totals = arms.map((_, i) => forkTotal(i));
  const tone = (t) => (sum(t) === t.length ? 'ok' : sum(t) === 0 ? 'bad' : 'mid');
</script>

<style>
  .strip { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }
  .chip { width: 56px; padding: 4px 0; text-align: center; border: 1px solid; border-radius: 4px; font-size: 11px; line-height: 1.25; }
  .chip small { display: block; color: #71717a; font-size: 10px; }
  .chip.read { background: #f4f4f5; border-color: #d4d4d8; }
  .chip.edit { background: #e8eff8; border-color: #9bb5d6; }
  .chip.exec { background: #fbf1dc; border-color: #d9b765; }
  .chip.cp { outline: 1.5px dashed #27272a; outline-offset: 2px; }
  .legend { display: flex; flex-wrap: wrap; gap: 16px; font-size: 12px; color: #52525b; }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; border: 1px solid; vertical-align: -1px; }
  .matrix { display: grid; grid-template-columns: 160px repeat(4, 1fr); gap: 6px; align-items: center; font-size: 13px; max-width: 900px; }
  .matrix .h { color: #18181b; font-size: 13px; font-weight: 600; }
  .matrix .h small { display: block; color: #71717a; font-size: 11px; font-weight: 400; }
  .key { max-width: 900px; margin: 4px 0 12px; padding: 10px 14px; font-size: 13px; line-height: 1.6; color: #3f3f46; background: #f4f4f5; border-radius: 6px; }
  .cell { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-radius: 4px; font-weight: 600; }
  .cell.ok { background: #e8f3ea; } .cell.mid { background: #fbf1dc; } .cell.bad { background: #fbe4e4; }
  .dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-left: 4px; }
  .dot.p { background: #16a34a; } .dot.f { background: #dc2626; }
  .total { font-weight: 600; padding: 6px 12px; }
  .note { font-size: 12px; color: #71717a; }
  .tag { font-size: 11px; border: 1px dashed #a1a1aa; border-radius: 3px; padding: 1px 6px; color: #52525b; margin-left: 8px; font-weight: 400; }

  :global(:root) { --d2h-change-del-color: #fee8e9; --d2h-change-ins-color: #ddf4e0; --d2h-change-label-color: #b45309; }
  .back { display: inline-block; margin-top: 20px; font-size: 13px; color: #52525b; text-decoration: none; }
  .back:hover { text-decoration: underline; }
</style>

<a class="back" href="/">← All proposals</a>

{#if !row}
  <p>No proposal with this id.</p>
{:else}
  <div class="rt-head">
    <div>
      <div class="rt-tags">
        <Chip label={status.label} tone={status.tone} />
        <span class="rt-tag">{row.target}</span>
        <span class="rt-tag">{CHANGE[row.change_type] ?? row.change_type}</span>
      </div>
      <h1>{row.title}</h1>
      <p>{row.summary}</p>
    </div>
    <div class="rt-panel">
      <span class="rt-k">Review</span>
      <div class="rt-row">
        <Chip label={v.label} tone={v.tone} />
        {#if !has(row.review_decision) && row.status === 'in_review'}<Chip label="Awaiting decision" tone="review" />{/if}
        {#if has(row.review_decision)}<Chip label="Decision: {row.review_decision}" tone={row.review_decision === 'approve' ? 'ok' : row.review_decision === 'reject' ? 'bad' : 'info'} />{/if}
      </div>
      <PrButton url={has(row.pr_url) ? row.pr_url : null} />
      <p class="rt-note">Decide in the pull request. A decision is saved in <code>runs/reviews/{row.proposal_id}.json</code>.</p>
    </div>
  </div>

  <div class="rt-example">Example data. This proposal is a fixture in <code>sources/mock/proposals.csv</code>.</div>

  <Tabs id=view>
    <Tab label="Overview">
      <div class="rt-facts">
        <div class="rt-fact"><span class="rt-k">Target</span><span class="rt-v">{row.target}</span><span class="rt-s">{row.kind === 'cost' ? 'Cost pattern' : 'Failure group'}</span></div>
        <div class="rt-fact"><span class="rt-k">Sessions</span><span class="rt-v">{row.sessions}</span><span class="rt-s">Severity {row.severity}</span></div>
        <div class="rt-fact"><span class="rt-k">Change</span><span class="rt-v">{CHANGE[row.change_type] ?? row.change_type}</span><span class="rt-s">Rank {rank + 1} of 6</span></div>
        <div class="rt-fact"><span class="rt-k">Result</span><span class="rt-v">{v.label}</span><span class="rt-s">{final ? 'Held-out, step 0' : diagnosis ? 'Checkpoint forks' : 'No replay yet'}</span></div>
      </div>

      <h2 class="rt-h2">The change</h2>
      <p>The runner copies this overlay onto the task checkout. It stays out of the graded patch.</p>
      <ul class="rt-files">
        {#each files as f}<li>{`analysis/proposals/${row.proposal_id}/${f}`}</li>{/each}
      </ul>
      {#if diffHtml}
        <div style="color: #1f2328">{@html diffHtml}</div>
      {/if}

      <h2 class="rt-h2">Rollback</h2>
      <p>Delete the copied overlay files from the repository. No other state changes.</p>
    </Tab>

    <Tab label="Evidence">
      {#if final}
        <h2 class="rt-h2">Held-out result</h2>
        <p class="rt-tab-note">{row.setup}. With change {row.arm_k}/{row.arm_n}, control {row.base_k}/{row.base_n}.</p>
        <h3 class="rt-h3">Pass rate difference</h3>
        <ECharts config={passChart} height=110px />
        {#if creditChart}
          <h3 class="rt-h3">Credits per trial difference</h3>
          <ECharts config={creditChart} height=110px />
        {/if}
        <h3 class="rt-h3">Regression set</h3>
        <p>{has(row.regression) ? `${row.regression}. Good past sessions, including legitimate test edits.` : 'Not run.'}</p>
      {:else if diagnosis}
        <h2 class="rt-h2">Diagnosis only</h2>
        <p>{row.setup}. With change {row.arm_k}/{row.arm_n}, control {row.base_k}/{row.base_n}. The sample is small, so there is no interval. Forks are not final evidence. Run a held-out step-0 job next.</p>
      {:else}
        <h2 class="rt-h2">No replay yet</h2>
        <p>This proposal has no replay job. A small group uses monitoring plus rollback.</p>
      {/if}

      {#if row.kind === 'cost'}
        <h2 class="rt-h2">Reference sessions</h2>
        <p class="rt-tab-note">Real sessions from <code>pro-baseline1</code>. They show the cost pattern, not this proposal's result.</p>
        <h3 class="rt-h3">Tool calls in the most expensive session</h3>
        <ECharts config={timeline} height=320px />
        <h3 class="rt-h3">Cumulative output tokens</h3>
        <LineChart data={cum} x=position y=cum_tokens series=session yFmt=num0 />
      {/if}
    </Tab>

    <Tab label={row.proposal_id === 'block-test-edits' ? 'Pipeline check' : 'Replay'}>
      {#if row.proposal_id === 'block-test-edits'}
        <p class="rt-tab-note">Example data. This tab checks that the fork pipeline runs. It does not show that the change fixes a failure. The forks start from a session that passed, so there was no failure to fix.</p>
        <h2 class="rt-h2">Steps of the recorded session</h2>
        <p class="rt-tab-note">One real ansible session. Each box is one tool call. A dashed outline marks a step where the forks started.</p>
<div class="strip">
  {#each strip as c}
    <div class="chip {kind(c)}" class:cp={checkpoints[c.tool_call_id]} title="{c.tool_name} {c.command_class}">
      <small>{c.position}</small>{c.label}
    </div>
  {/each}
</div>
<div class="legend">
  <span><i style="background:#e8eff8;border-color:#9bb5d6"></i>Edit</span>
  <span><i style="background:#fbf1dc;border-color:#d9b765"></i>Execute</span>
  <span><i style="background:#f4f4f5;border-color:#d4d4d8"></i>Read / Grep</span>
  <span><i style="border:1.5px dashed #27272a"></i>Fork start (step 10, step 17)</span>
</div>
        <h2 class="rt-h2">Fork results</h2>
<div class="key">
  <b>How to read this.</b> Each row is a step where forks started. Each column is an arm.
  A cell shows how many runs passed out of all runs. Each dot is one run: green passed, red failed.
  The recorded run is the original session, not a fork. Forks are diagnosis, not final evidence.
</div>
<div class="matrix">
  <div></div>
  {#each arms as a}<div class="h">{a.name}<small>{a.what}</small></div>{/each}
  {#each matrix as r}
    <div><b>{r.step}</b><div class="note">{r.id}</div></div>
    {#each r.cells as t}
      <div class="cell {tone(t)}">
        <span>{sum(t)} of {t.length} passed</span>
        <span>{#each t as x}<span class="dot {x ? 'p' : 'f'}"></span>{/each}</span>
      </div>
    {/each}
  {/each}
  <div class="total">Both steps</div>
  {#each totals as t}<div class="total">{sum(t)} of {t.length} passed</div>{/each}
</div>
<p class="note">12 forks: 2 steps × 3 fork arms × 2 reruns. The recorded run has 1 run per step.</p>
      {:else}
        <p>No replay diagnosis for this proposal.</p>
      {/if}
    </Tab>
  </Tabs>
{/if}
