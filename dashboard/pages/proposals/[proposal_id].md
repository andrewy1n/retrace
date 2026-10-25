---
title: Proposal
sidebar: never
hide_title: true
full_width: true
---

```sql mock_row
select * from mock.proposals where proposal_id = '${params.proposal_id}'
```

```sql plist
select * from proposal_list.proposals where proposal_id <> ''
```

```sql fork_calls
select * from fork_view.calls where proposal_path <> ''
```

```sql pruns
select * from tiger.proposal_runs
```

```sql rcalls
select c.session_id, c.position, c.tool_name, c.command_class, coalesce(c.test_runner, c.tool_name) as label,
       c.is_error, c.duration_s, c.output_tokens_est
from tiger.calls c
where c.session_id in (select session_id from tiger.proposal_runs)
order by c.session_id, c.position
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

```sql forks
select checkpoint, arm, trial, repo_status, repo_regressed, repo_passing_at_start, acc_status, acc_at_start
from tiger.result_rows
where evidence_role = 'diagnosis'
  and checkpoint in ('toolu_01Pm3ZNrBCDtHNUh83ovCqeC', 'toolu_016dLe3d1iqCZzTGPkUnoaXN')
order by checkpoint, arm, trial
```

```sql rec
select position, tool_call_id, command_class
from tiger.calls
where session_id = 'pro-baseline1-instance_ansible__ansible-d33bedc48fdd933b5abd65a77c081876298e2f07-v0f01c69f1e2528b935359cfe578530722bca2c59-1'
order by position
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
  import { STATUS, CHANGE, has, intervalChart, repoText, accText } from '../../../components/format.js';
  import { behaviourVerdict, share } from '../../../components/behaviour.js';
  import { buildProposals, taskTable } from '../../../components/proposals.js';
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
  const diffFor = (text) => text ? diffToHtml(text, { drawFileList: false, matching: 'lines', outputFormat: 'line-by-line', colorScheme: 'light' }) : null;

  $: id = $page.params.proposal_id;
  $: real = buildProposals(plist, pruns);
  $: example = real.length === 0;
  $: row = example ? Array.from(mock_row ?? []).map((m) => ({ ...m, example: true }))[0] : real.find((r) => r.proposal_id === id);
  $: status = row ? (STATUS[row.status] ?? { label: row.status, tone: 'muted' }) : null;
  $: v = row ? behaviourVerdict(row) : null;
  $: final = row?.evidence_role === 'final';
  $: diagnosis = row?.evidence_role === 'diagnosis';
  $: files = row?.overlay_files ? row.overlay_files.split(';') : [];
  $: diffHtml = row ? diffFor(example ? patches[row.proposal_id] : row.patch) : null;
  $: incChart = final ? intervalChart(row.inc_delta_pp, row.inc_low_pp, row.inc_high_pp, 'pp') : null;
  $: guards = row ? [has(row.guard_repo) ? `Repo tests: ${row.guard_repo}.` : null, has(row.guard_acceptance) ? `Acceptance check: ${row.guard_acceptance}.` : null].filter(Boolean) : [];
  $: creditChart = final && has(row.credits_delta_pct) ? intervalChart(row.credits_delta_pct, row.credits_low_pct, row.credits_high_pct, '%') : null;
  $: timeChart = final && has(row.time_delta_pct) ? intervalChart(row.time_delta_pct, row.time_low_pct, row.time_high_pct, '%') : null;
  $: rank = row ? ['guardrail_hook', 'skill', 'tool', 'custom_droid', 'setting', 'rule'].indexOf(row.change_type) : -1;

  $: taskRows = row?.runs ? taskTable(row.runs, row.signal_column) : [];

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
  const isTrue = (v) => v === true || String(v).toLowerCase() === 'true';
  const labelOf = (b) => (b.arm === 'recorded' ? 'Recorded run (original)' : b.arm === 'control' ? `Baseline rerun ${b.trial}` : `With change, rerun ${b.trial}`);
  $: forkSets = (() => {
    const mine = Array.from(fork_calls ?? []).filter((c) => row && c.proposal_path === row.path);
    const groups = new Map();
    for (const c of mine) {
      const key = `${c.checkpoint}|${c.arm}|${c.trial}`;
      if (!groups.has(key)) groups.set(key, { checkpoint: c.checkpoint, at: Number(c.fork_position), arm: c.arm, trial: Number(c.trial), credits: c.cost_credits, calls: [] });
      groups.get(key).calls.push({ ...c, position: Number(c.position), blocked: isTrue(c.blocked), is_error: isTrue(c.is_error) });
    }
    const order = { recorded: 0, control: 1, candidate: 2 };
    const sets = new Map();
    for (const g of groups.values()) {
      g.calls.sort((a, b) => a.position - b.position);
      const edit = g.calls.find((c) => c.command_class === 'edit');
      g.firstEdit = edit ? edit.position : g.calls.length;
      g.after = g.calls.filter((c) => c.position >= g.at);
      if (!sets.has(g.checkpoint)) sets.set(g.checkpoint, { at: g.at, prefix: [], branches: [] });
      const set = sets.get(g.checkpoint);
      if (g.arm === 'recorded') set.prefix = g.calls.filter((c) => c.position < g.at);
      set.branches.push(g);
    }
    for (const s of sets.values()) s.branches.sort((a, b) => order[a.arm] - order[b.arm] || a.trial - b.trial);
    return [...sets.values()];
  })();
  let selTask = '';
  const bySession = (calls) => {
    const m = new Map();
    for (const c of calls) { if (!m.has(c.session_id)) m.set(c.session_id, []); m.get(c.session_id).push(c); }
    return m;
  };
  const firstEdit = (cs) => { const e = cs.find((c) => c.command_class === 'edit'); return e ? e.position : cs.length; };
  $: sessions = bySession(Array.from(rcalls ?? []));
  $: taskIds = [...new Set((row?.runs ?? []).map((r) => r.task_id))].sort();
  $: gap = (t) => {
    const mean = (arm) => { const xs = (row?.runs ?? []).filter((r) => r.task_id === t && r.arm === arm && sessions.has(r.session_id)).map((r) => firstEdit(sessions.get(r.session_id))); return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0; };
    return mean('control') - mean('candidate');
  };
  $: if (!selTask && taskIds.length && sessions.size) selTask = [...taskIds].sort((a, b) => gap(b) - gap(a))[0];
  $: viewRuns = (row?.runs ?? []).filter((r) => r.task_id === selTask && sessions.has(r.session_id))
    .sort((a, b) => (a.arm === b.arm ? a.trial - b.trial : a.arm === 'control' ? -1 : 1));
  const kind = (c) => c.command_class === 'edit' ? 'edit' : c.tool_name === 'Execute' ? 'exec' : 'read';

  const arms = [
    { name: 'Recorded run', what: 'the original session', key: null },
    { name: 'Control', what: 'fork, no change', key: 'control' },
    { name: 'Hint', what: 'fork, hint text added', key: 'hint' },
    { name: 'With change', what: 'fork, overlay applied', key: 'candidate' }
  ];
  const steps = [
    { step: 'Step 10', id: 'toolu_01Pm3Z…', checkpoint: 'toolu_01Pm3ZNrBCDtHNUh83ovCqeC' },
    { step: 'Step 17', id: 'toolu_016dLe…', checkpoint: 'toolu_016dLe3d1iqCZzTGPkUnoaXN' }
  ];
  $: recRows = Array.from(rec ?? []);
  $: after = (checkpoint) => {
    const at = recRows.find((c) => c.tool_call_id === checkpoint);
    const rest = at ? recRows.filter((c) => c.position > at.position) : [];
    return { calls: rest.length, tests: rest.filter((c) => c.command_class === 'test').length };
  };
  $: forkRows = Array.from(forks ?? []);
  $: cellOf = (checkpoint, key) => forkRows.filter((f) => f.checkpoint === checkpoint && f.arm === key);
  $: armRows = (key) => forkRows.filter((f) => f.arm === key);
  const repoUsable = (f) => f.repo_status === 'ok';
  const accUsable = (f) => f.acc_at_start === 'fail' && f.acc_status !== 'error';
  const repoClean = (fs) => `${fs.filter((f) => repoUsable(f) && f.repo_regressed === 0).length} of ${fs.filter(repoUsable).length}`;
  const accPass = (fs) => `${fs.filter((f) => accUsable(f) && f.acc_status === 'pass').length} of ${fs.filter(accUsable).length}`;
</script>

<style>
  .strip { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }
  .chip { width: 56px; padding: 4px 0; text-align: center; border: 1px solid; border-radius: 4px; font-size: 11px; line-height: 1.25; }
  .chip small { display: block; color: #71717a; font-size: 10px; }
  .chip.read { background: #f4f4f5; border-color: #d4d4d8; }
  .chip.edit { background: #e8eff8; border-color: #9bb5d6; }
  .chip.exec { background: #fbf1dc; border-color: #d9b765; }
  .chip.cp { outline: 1.5px dashed #27272a; outline-offset: 2px; }
  .pick { display: block; margin: 8px 0 16px; font-size: 13px; color: #52525b; }
  .pick select { margin-left: 8px; padding: 4px 8px; font-size: 13px; }
  .run { margin: 16px 0; }
  .runhead { display: flex; flex-wrap: wrap; gap: 4px 16px; align-items: baseline; font-size: 13px; }
  .runhead span { color: #71717a; }
  .prefix { margin: 8px 0; }
  .plabel { font-size: 12px; color: #71717a; }
  .chip.locked { opacity: 0.55; }
  .chip.blocked { background: #fbe4e1; border-color: #d98a80; }
  .divider { margin: 10px 0 4px; padding: 6px 0; border-top: 1.5px solid #27272a; font-size: 12px; color: #27272a; }
  .legend { display: flex; flex-wrap: wrap; gap: 16px; font-size: 12px; color: #52525b; }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; border: 1px solid; vertical-align: -1px; }
  .matrix { display: grid; grid-template-columns: 160px repeat(4, 1fr); gap: 6px; align-items: center; font-size: 13px; max-width: 900px; }
  .matrix .h { color: #18181b; font-size: 13px; font-weight: 600; }
  .matrix .h small { display: block; color: #71717a; font-size: 11px; font-weight: 400; }
  .key { max-width: 900px; margin: 4px 0 12px; padding: 10px 14px; font-size: 13px; line-height: 1.6; color: #3f3f46; background: #f4f4f5; border-radius: 6px; }
  .cell { padding: 10px 12px; border-radius: 4px; background: #f4f4f5; font-size: 12px; line-height: 1.5; }
  .cell .fork + .fork { margin-top: 6px; padding-top: 6px; border-top: 1px solid #e4e4e7; }
  .cell.empty { color: #71717a; }
  .total { font-weight: 600; padding: 6px 12px; font-size: 12px; }
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

  {#if example}
    <div class="rt-example">Example data. This proposal is a fixture in <code>sources/mock/proposals.csv</code>.</div>
  {/if}

  <Tabs id=view>
    <Tab label="Overview">
      <div class="rt-facts">
        <div class="rt-fact"><span class="rt-k">Target</span><span class="rt-v">{row.target}</span><span class="rt-s">{row.kind === 'cost' ? 'Cost pattern' : 'Failure group'}</span></div>
        <div class="rt-fact"><span class="rt-k">{example ? 'Sessions' : 'Runs'}</span><span class="rt-v">{row.sessions}</span><span class="rt-s">{example ? `Severity ${row.severity}` : 'Runs with the change'}</span></div>
        <div class="rt-fact"><span class="rt-k">Change</span><span class="rt-v">{CHANGE[row.change_type] ?? row.change_type}</span><span class="rt-s">Rank {rank + 1} of 6</span></div>
        <div class="rt-fact"><span class="rt-k">Result</span><span class="rt-v">{v.label}</span><span class="rt-s">{final ? (example ? 'Held-out' : 'Fresh runs') : diagnosis ? 'Checkpoint forks' : 'No replay yet'}</span></div>
      </div>

      <h2 class="rt-h2">The change</h2>
      <p>The runner copies this overlay onto the task checkout. It stays out of the agent's patch.</p>
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
        <h2 class="rt-h2">{example ? 'Held-out result' : 'Results'}</h2>
        <p class="rt-tab-note">{row.setup}.</p>
        <h3 class="rt-h3">{row.target_metric}</h3>
        <p>With the change: {share(row.inc_arm_k, row.inc_arm_n)} runs. Baseline: {share(row.inc_base_k, row.inc_base_n)} runs. A negative difference means the change cuts the behaviour.</p>
        <ECharts config={incChart} height=110px />
        {#if creditChart}
          <h3 class="rt-h3">Credits per run difference</h3>
          <ECharts config={creditChart} height=110px />
        {/if}
        {#if timeChart}
          <h3 class="rt-h3">Tool time per run difference</h3>
          <p>This adds up how long each tool call ran. It leaves out the time the model spent deciding. A negative number means the commands took less time.</p>
          <ECharts config={timeChart} height=110px />
        {/if}
        <h3 class="rt-h3">Guards</h3>
        {#each guards as g}<p>{g}</p>{:else}<p>Not run.</p>{/each}
      {:else if diagnosis}
        <h2 class="rt-h2">Diagnosis only</h2>
        <p class="rt-tab-note">{row.setup}.</p>
        <h3 class="rt-h3">{row.target_metric}</h3>
        <p>With the change: {share(row.inc_arm_k, row.inc_arm_n)} forks. Baseline: {share(row.inc_base_k, row.inc_base_n)} forks. The sample is small, so there is no interval. Forks are not final evidence. Run a held-out step-0 job next.</p>
        <h3 class="rt-h3">Guards</h3>
        {#each guards as g}<p>{g}</p>{:else}<p>Not run.</p>{/each}
      {:else}
        <h2 class="rt-h2">No replay yet</h2>
        <p>This proposal has no replay job. A small group uses monitoring plus rollback.</p>
      {/if}

      {#if example && row.kind === 'cost'}
        <h2 class="rt-h2">Reference sessions</h2>
        <p class="rt-tab-note">Real sessions from <code>pro-baseline1</code>. They show the cost pattern, not this proposal's result.</p>
        <h3 class="rt-h3">Tool calls in the most expensive session</h3>
        <ECharts config={timeline} height=320px />
        <h3 class="rt-h3">Cumulative output tokens</h3>
        <LineChart data={cum} x=position y=cum_tokens series=session yFmt=num0 />
      {/if}
    </Tab>

    <Tab label={example && row.proposal_id === 'block-test-edits' ? 'Pipeline check' : 'Replay'}>
      {#if example && row.proposal_id === 'block-test-edits'}
        <p class="rt-tab-note">Example data. This tab checks that the fork pipeline runs. It does not show that the change works.</p>
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
  A cell shows two proxies per fork. Repo tests count tests that passed at the start and fail with the patch.
  The acceptance check counts only when it failed at the start.
  The recorded run is the original session. Its cell counts the tool calls after the step.
</div>
<div class="matrix">
  <div></div>
  {#each arms as a}<div class="h">{a.name}<small>{a.what}</small></div>{/each}
  {#each steps as r}
    <div><b>{r.step}</b><div class="note">{r.id}</div></div>
    {#each arms as a}
      {#if a.key === null}
        <div class="cell">{after(r.checkpoint).calls} tool calls after this step<br />{after(r.checkpoint).tests} test runs</div>
      {:else if cellOf(r.checkpoint, a.key).length}
        <div class="cell">
          {#each cellOf(r.checkpoint, a.key) as f}
            <div class="fork">{repoText(f)}<br />{accText(f)}</div>
          {/each}
        </div>
      {:else}
        <div class="cell empty">No fork in Tiger</div>
      {/if}
    {/each}
  {/each}
  <div class="total">Both steps</div>
  <div class="total"></div>
  {#each arms.slice(1) as a}
    <div class="total">
      <div>repo tests: {repoClean(armRows(a.key))} with 0 regressed</div>
      <div>acceptance: {accPass(armRows(a.key))} pass</div>
    </div>
  {/each}
</div>
<p class="note">{forkRows.length} forks in Tiger. The planned run is 12: 2 steps × 3 fork arms × 2 reruns. The recorded run has 1 run per step.</p>
      {:else if !example && final}
        {#each forkSets as set}
          <h2 class="rt-h2">Rewind to a step and rerun</h2>
          <p class="rt-tab-note">A recorded session had made {set.at} calls and not yet edited anything. We rewound it to call {set.at}, restored the repository as it was at that point, and ran it again: {set.branches.filter((b) => b.arm === 'control').length} times as it was (baseline) and {set.branches.filter((b) => b.arm === 'candidate').length} times with the change installed. The first {set.at} calls are the same in every run.</p>
          <BranchGraph prefix={set.prefix} at={set.at} branches={set.branches.map((b) => ({ arm: b.arm, label: labelOf(b), calls: b.after, firstEdit: b.firstEdit, credits: b.credits }))} startLabel="Rewound at call {set.at}" />
        {/each}
        <h2 class="rt-h2">Tool calls, run by run</h2>
        <p class="rt-tab-note">Every run starts from the same task. Each dot is one tool call, in order. The task opens on the largest gap in calls before the first edit.</p>
        <label class="pick">Task
          <select bind:value={selTask}>
            {#each taskIds as t}<option value={t}>{t.replace(/^instance_(.+?)-([0-9a-f]{8})[0-9a-f]{32}.*$/, '$1-$2')}</option>{/each}
          </select>
        </label>
        <BranchGraph at={0} startLabel="Start of the task" branches={viewRuns.map((r) => ({ arm: r.arm, label: (r.arm === 'control' ? 'Baseline' : 'With change') + ', run ' + r.trial, calls: sessions.get(r.session_id), firstEdit: firstEdit(sessions.get(r.session_id)), credits: r.cost_credits, href: '/sessions/' + r.session_id }))} />
        <h2 class="rt-h2">All tasks</h2>
        <p class="rt-tab-note">Baseline against with change, one row per task. A run counts when its tool calls were recorded.</p>
        <DataTable data={taskRows} rows=50 emptySet=pass emptyMessage="No run yet.">
          <Column id=task title="Task" />
          <Column id=arm title="Version" />
          <Column id=runs title="Runs" />
          <Column id=signal title="Runs with the behaviour" />
          <Column id=credits title="Credits, mean" fmt=num0 />
          <Column id=repo title="Repo tests" />
          <Column id=acc title="Acceptance" />
        </DataTable>
      {:else}
        <p>No replay for this proposal.</p>
      {/if}
    </Tab>
  </Tabs>
{/if}
