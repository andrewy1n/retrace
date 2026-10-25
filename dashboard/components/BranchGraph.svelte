<script>
  export let prefix = [];
  export let at = 0;
  export let branches = [];
  export let startLabel = 'Rewound here';

  const LANE = 38;
  const LEFT = 16;
  const TOP = 28;
  const TRUNK_GAP = 36;
  const COLORS = { edit: '#4a7bb7', exec: '#c4922c', read: '#a1a1aa', line: { control: '#71717a', candidate: '#2f7d5b', recorded: '#a1a1aa' } };

  const kind = (c) => (c.command_class === 'edit' ? 'edit' : c.tool_name === 'Execute' ? 'exec' : 'read');
  const lineColor = (b) => COLORS.line[b.arm] ?? COLORS.line.control;

  $: longest = Math.max(at, ...branches.map((b) => (b.calls.length ? b.calls[b.calls.length - 1].position + 1 : at)));
  $: STEP = Math.max(8, Math.min(22, 860 / Math.max(longest, 1)));
  $: trunkEnd = LEFT + at * STEP;
  $: width = LEFT + longest * STEP + 330;
  $: laneY = (i) => TOP + i * LANE;
  $: trunkY = TOP + ((branches.length - 1) * LANE) / 2;
  $: height = TOP + branches.length * LANE + 8;
  $: forkX = at > 0 ? trunkEnd - STEP / 2 + 8 : LEFT;
  $: x = (pos) => LEFT + pos * STEP;
  $: curve = (i) => `M ${forkX} ${trunkY} C ${forkX + 26} ${trunkY}, ${x(at) - 26} ${laneY(i)}, ${x(at)} ${laneY(i)}`;
  $: blockedLabel = (c) => `${c.position}: ${c.tool_name} stopped by the change`;
</script>

<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="Branching view of the runs">
  {#if at > 0}
    <line x1={LEFT} y1={trunkY} x2={forkX} y2={trunkY} stroke="#d4d4d8" stroke-width="5" stroke-linecap="round" />
    {#each prefix as c}
      <circle cx={x(c.position)} cy={trunkY} r="3.5" fill={COLORS[kind(c)]} opacity="0.5"><title>{c.position}: {c.tool_name}</title></circle>
    {/each}
    <text x={LEFT} y={trunkY - 14} class="note">Calls 0 to {at - 1}, shared by every run</text>
  {/if}

  <circle cx={forkX} cy={trunkY} r="6" fill="#27272a" />
  <text x={at > 0 ? forkX - 12 : LEFT} y={at > 0 ? trunkY + 22 : 12} class="fork" text-anchor={at > 0 ? 'end' : 'start'}>{startLabel}</text>

  {#each branches as b, i}
    {@const last = b.calls.length ? b.calls[b.calls.length - 1].position : at}
    <path d={curve(i)} fill="none" stroke={lineColor(b)} stroke-width="2.5" stroke-dasharray={b.arm === 'recorded' ? '5 4' : ''} />
    <line x1={x(at)} y1={laneY(i)} x2={x(last)} y2={laneY(i)} stroke={lineColor(b)} stroke-width="2.5" stroke-dasharray={b.arm === 'recorded' ? '5 4' : ''} />
    {#each b.calls as c}
      {#if c.blocked}
        <g>
          <title>{blockedLabel(c)}</title>
          <circle cx={x(c.position)} cy={laneY(i)} r="8" fill="#fbe4e1" stroke="#c9564a" stroke-width="1.5" />
          <path d="M {x(c.position) - 3.5} {laneY(i) - 3.5} l 7 7 M {x(c.position) + 3.5} {laneY(i) - 3.5} l -7 7" stroke="#c9564a" stroke-width="1.8" stroke-linecap="round" />
        </g>
      {:else if c.command_class === 'edit' && c.position === b.firstEdit}
        <g>
          <title>{c.position}: first edit ({c.tool_name})</title>
          <circle cx={x(c.position)} cy={laneY(i)} r="9" fill="#fff" stroke="#27272a" stroke-width="1.5" />
          <circle cx={x(c.position)} cy={laneY(i)} r="5" fill={COLORS.edit} />
        </g>
      {:else}
        <circle cx={x(c.position)} cy={laneY(i)} r="3.6" fill={COLORS[kind(c)]}><title>{c.position}: {c.tool_name}{c.is_error ? ' (error)' : ''}</title></circle>
      {/if}
    {/each}
    <text x={x(last) + 14} y={laneY(i) - 3} class="lane"><tspan font-weight="600">{b.label}</tspan></text>
    <text x={x(last) + 14} y={laneY(i) + 11} class="note">first edit at call {b.firstEdit}{b.credits ? ` · ${Number(b.credits).toLocaleString('en-US', { maximumFractionDigits: 0 })} credits` : ''}</text>
  {/each}
</svg>
<div class="key">
  <span><i class="dot" style="background:#4a7bb7"></i>Edit</span>
  <span><i class="dot" style="background:#c4922c"></i>Run a command</span>
  <span><i class="dot" style="background:#a1a1aa"></i>Read or search</span>
  <span><i class="ring"></i>First edit</span>
  <span><i class="x">✕</i>Stopped by the change</span>
</div>

<style>
  svg { display: block; margin: 8px 0 4px; max-width: 1200px; }
  text { font-family: inherit; fill: #27272a; }
  .note { font-size: 11px; fill: #71717a; }
  .lane { font-size: 12px; }
  .fork { font-size: 11px; fill: #27272a; }
  .key { display: flex; flex-wrap: wrap; gap: 16px; font-size: 12px; color: #52525b; margin-bottom: 8px; }
  .dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
  .ring { display: inline-block; width: 11px; height: 11px; border-radius: 50%; border: 1.5px solid #27272a; margin-right: 6px; vertical-align: -2px; }
  .x { font-style: normal; color: #c9564a; margin-right: 6px; font-weight: 700; }
</style>
