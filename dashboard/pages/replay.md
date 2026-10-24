---
title: Replay
sidebar: never
full_width: true
---

<script>
  const sessionLabel = 'ansible d33bed, trial 1';
  const checkpoints = { toolu_01Pm3ZNrBCDtHNUh83ovCqeC: 'Step 10', toolu_016dLe3d1iqCZzTGPkUnoaXN: 'Step 17' };
  const decisive = 22;
  const kind = (c) => c.command_class === 'edit' ? 'edit' : c.tool_name === 'Execute' ? 'exec' : 'read';

  const arms = ['Original', 'Control', 'Hint', 'With change'];
  const matrix = [
    { step: 'Step 10', id: 'toolu_01Pm3Z…', cells: [[1], [1, 1], [1, 0], [1, 1]] },
    { step: 'Step 17', id: 'toolu_016dLe…', cells: [[1], [1, 1], [0, 1], [1, 1]] }
  ];
  const sum = (a) => a.reduce((s, x) => s + x, 0);
  const totals = arms.map((_, i) => matrix.flatMap((r) => r.cells[i]));
  const tone = (t) => (sum(t) === t.length ? 'ok' : sum(t) === 0 ? 'bad' : 'mid');

  const diffChart = {
    grid: { left: 24, right: 24, top: 8, bottom: 32 },
    xAxis: { type: 'value', min: -20, max: 80, axisLabel: { formatter: (v) => (v > 0 ? `+${v}` : v) + ' pp' }, splitLine: { show: false } },
    yAxis: { type: 'category', data: [''], show: false },
    series: [
      { type: 'bar', stack: 'ci', silent: true, itemStyle: { color: 'transparent' }, data: [8] },
      { type: 'bar', stack: 'ci', barWidth: 4, itemStyle: { color: '#71717a' }, data: [47] },
      { type: 'scatter', symbolSize: 14, itemStyle: { color: '#27272a' }, data: [[33, 0]],
        label: { show: true, position: 'top', formatter: '+33 pp [+8, +55]', color: '#27272a' },
        markLine: { silent: true, symbol: 'none', lineStyle: { color: '#a1a1aa', type: 'dashed' }, label: { show: false }, data: [{ xAxis: 0 }] } }
    ]
  };
</script>

<style>
  .strip { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }
  .chip { width: 56px; padding: 4px 0; text-align: center; border: 1px solid; border-radius: 4px; font-size: 11px; line-height: 1.25; }
  .chip small { display: block; color: #71717a; font-size: 10px; }
  .chip.read { background: #f4f4f5; border-color: #d4d4d8; }
  .chip.edit { background: #e8eff8; border-color: #9bb5d6; }
  .chip.exec { background: #fbf1dc; border-color: #d9b765; }
  .chip.cp { outline: 1.5px dashed #27272a; outline-offset: 2px; }
  .chip.decisive { background: #fdeaea; border-color: #dc2626; }
  .legend { display: flex; flex-wrap: wrap; gap: 16px; font-size: 12px; color: #52525b; }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; border: 1px solid; vertical-align: -1px; }
  .matrix { display: grid; grid-template-columns: 160px repeat(4, 1fr); gap: 6px; align-items: center; font-size: 13px; max-width: 900px; }
  .matrix .h { color: #52525b; font-size: 12px; }
  .cell { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-radius: 4px; font-weight: 600; }
  .cell.ok { background: #e8f3ea; } .cell.mid { background: #fbf1dc; } .cell.bad { background: #fbe4e4; }
  .dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-left: 4px; }
  .dot.p { background: #16a34a; } .dot.f { background: #dc2626; }
  .total { font-weight: 600; padding: 6px 12px; }
  .note { font-size: 12px; color: #71717a; }
  .tag { font-size: 11px; border: 1px dashed #a1a1aa; border-radius: 3px; padding: 1px 6px; color: #52525b; margin-left: 8px; font-weight: 400; }
</style>

## Decisive step

```sql strip
select position, tool_call_id, tool_name, command_class, test_runner, coalesce(test_runner, tool_name) as label
from tiger.calls
where session_id = 'pro-baseline1-instance_ansible__ansible-d33bedc48fdd933b5abd65a77c081876298e2f07-v0f01c69f1e2528b935359cfe578530722bca2c59-1'
  and position < 25
order by position
```

<div class="strip">
  {#each strip as c}
    <div class="chip {kind(c)}" class:cp={checkpoints[c.tool_call_id]} class:decisive={c.position === decisive} title="{c.tool_name} {c.command_class}">
      <small>{c.position}</small>{c.label}
    </div>
  {/each}
</div>
<div class="legend">
  <span><i style="background:#e8eff8;border-color:#9bb5d6"></i>Edit</span>
  <span><i style="background:#fbf1dc;border-color:#d9b765"></i>Execute</span>
  <span><i style="background:#f4f4f5;border-color:#d4d4d8"></i>Read / Grep</span>
  <span><i style="border:1.5px dashed #27272a"></i>Replay checkpoint (step 10, step 17)</span>
  <span><i style="background:#fdeaea;border-color:#dc2626"></i>Suspected decisive step (example, step 22)</span>
</div>

## Replay evidence

<div class="matrix">
  <div></div>
  {#each arms as a}<div class="h">{a}</div>{/each}
  {#each matrix as r}
    <div><b>{r.step}</b><div class="note">{r.id}</div></div>
    {#each r.cells as t}
      <div class="cell {tone(t)}">
        <span>{sum(t)}/{t.length}</span>
        <span>{#each t as x}<span class="dot {x ? 'p' : 'f'}"></span>{/each}</span>
      </div>
    {/each}
  {/each}
  <div class="total">Total</div>
  {#each totals as t}<div class="total">{sum(t)}/{t.length}</div>{/each}
</div>
<p class="note">Fork tests are diagnosis, not final evidence.</p>

## Held-out validation <span class="tag">example data</span>

Baseline 6/24, with change 14/24. Difference +33 pp, 95% interval +8 to +55.

<ECharts config={diffChart} height=110px />

## Alternatives considered <span class="tag">example data</span>

```sql alts
select 'PreToolUse hook blocking test edits (chosen)' as alternative, 7 as passes, '7/12' as rate union all
select 'AGENTS.md rule', 3, '3/12' union all
select 'Rule suggested from transcript', 2, '2/12' union all
select 'Control', 1, '1/12'
```

<DataTable data={alts} rows=10>
  <Column id=alternative />
  <Column id=passes title="Passes of 12" contentType=bar barColor="#a1a1aa" backgroundColor="#e4e4e7" />
  <Column id=rate title="Replay" align=right />
</DataTable>
