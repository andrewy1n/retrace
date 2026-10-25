<script>
  import { onMount } from 'svelte';

  export let prefix = [];
  export let at = 0;
  export let branches = [];
  export let startLabel = 'Rewound here';

  const MAX_STEP = 22;
  const LANE = 38;
  const LEFT = 16;
  const TOP = 28;
  const COLORS = { edit: '#4a7bb7', exec: '#c4922c', read: '#a1a1aa', line: { control: '#71717a', candidate: '#2f7d5b', recorded: '#a1a1aa' } };

  const kind = (c) => (c.command_class === 'edit' ? 'edit' : c.tool_name === 'Execute' ? 'exec' : 'read');
  const lineColor = (b) => COLORS.line[b.arm] ?? COLORS.line.control;
  const plain = { read: 'read a file', search: 'searched', edit: 'edited a file', test: 'ran tests', run: 'ran a command', other: 'other' };

  let svg;
  let hoverPos = null;
  let pinnedPos = null;
  let activeLane = null;

  $: longest = Math.max(at, ...branches.map((b) => (b.calls.length ? b.calls[b.calls.length - 1].position + 1 : at)));
  $: STEP = Math.max(8, Math.min(MAX_STEP, 860 / Math.max(longest, 1)));
  $: trunkEnd = LEFT + at * STEP;
  $: width = LEFT + longest * STEP + 330;
  $: laneY = (i) => TOP + i * LANE;
  $: trunkY = TOP + ((branches.length - 1) * LANE) / 2;
  $: height = TOP + branches.length * LANE + 8;
  $: forkX = at > 0 ? trunkEnd - STEP / 2 + 8 : LEFT;
  $: x = (pos) => LEFT + pos * STEP;
  $: curve = (i) => `M ${forkX} ${trunkY} C ${forkX + 26} ${trunkY}, ${x(at) - 26} ${laneY(i)}, ${x(at)} ${laneY(i)}`;
  $: lookups = branches.map((b) => new Map(b.calls.map((c) => [c.position, c])));
  $: prefixLookup = new Map(prefix.map((c) => [c.position, c]));
  $: pos = pinnedPos ?? hoverPos;
  $: dim = (i) => (activeLane !== null && activeLane !== i ? 0.28 : 1);

  function locate(event) {
    const box = svg.getBoundingClientRect();
    const sx = ((event.clientX - box.left) * width) / box.width;
    const sy = ((event.clientY - box.top) * height) / box.height;
    const col = Math.round((sx - LEFT) / STEP);
    const lane = Math.round((sy - TOP) / LANE);
    return {
      col: col >= 0 && col < longest ? col : null,
      lane: lane >= 0 && lane < branches.length && Math.abs(sy - laneY(lane)) < LANE / 2 && sx > forkX ? lane : null
    };
  }
  function move(event) {
    const p = locate(event);
    hoverPos = p.col;
    activeLane = p.lane;
  }
  function leave() {
    hoverPos = null;
    activeLane = null;
  }
  function click(event) {
    const { col } = locate(event);
    pinnedPos = col === null || col === pinnedPos ? null : col;
  }
  onMount(() => {
    const esc = (e) => { if (e.key === 'Escape') pinnedPos = null; };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  });

  const describe = (c) => {
    if (!c) return null;
    const bits = [`${c.tool_name}, ${plain[c.command_class] ?? c.command_class}`];
    const secs = Number(c.duration_s);
    if (c.duration_s !== undefined && c.duration_s !== '' && !Number.isNaN(secs)) bits.push(`${secs < 10 ? secs.toFixed(1) : Math.round(secs)} s`);
    const tokens = Number(c.output_tokens_est);
    if (c.output_tokens_est !== undefined && c.output_tokens_est !== '' && !Number.isNaN(tokens)) bits.push(`about ${tokens.toLocaleString('en-US')} tokens back`);
    return bits.join(' · ');
  };
  const fileOf = (c) => (c && c.files ? String(c.files).split(';')[0] : '');
</script>

<svg bind:this={svg} viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="Branching view of the runs"
  on:mousemove={move} on:mouseleave={leave} on:click={click}>
  {#if pos !== null}
    <line x1={x(pos)} y1="6" x2={x(pos)} y2={height - 4} stroke="#27272a" stroke-opacity="0.35" stroke-dasharray="3 3" />
  {/if}

  {#if at > 0}
    <line x1={LEFT} y1={trunkY} x2={forkX} y2={trunkY} stroke="#d4d4d8" stroke-width="5" stroke-linecap="round" />
    {#each prefix as c}
      <circle cx={x(c.position)} cy={trunkY} r="3.5" fill={COLORS[kind(c)]} opacity="0.5" />
    {/each}
    <text x={LEFT} y={trunkY - 14} class="note">Calls 0 to {at - 1}, shared by every run</text>
  {/if}

  <circle cx={forkX} cy={trunkY} r="6" fill="#27272a" />
  <text x={at > 0 ? forkX - 12 : LEFT} y={at > 0 ? trunkY + 22 : 12} class="fork" text-anchor={at > 0 ? 'end' : 'start'}>{startLabel}</text>

  {#each branches as b, i}
    {@const last = b.calls.length ? b.calls[b.calls.length - 1].position : at}
    <g opacity={dim(i)} class="lane-group">
      <path d={curve(i)} fill="none" stroke={lineColor(b)} stroke-width={activeLane === i ? 3.5 : 2.5} stroke-dasharray={b.arm === 'recorded' ? '5 4' : ''} />
      <line x1={x(at)} y1={laneY(i)} x2={x(last)} y2={laneY(i)} stroke={lineColor(b)} stroke-width={activeLane === i ? 3.5 : 2.5} stroke-dasharray={b.arm === 'recorded' ? '5 4' : ''} />
      {#each b.calls as c}
        {#if c.blocked}
          <circle cx={x(c.position)} cy={laneY(i)} r="8" fill="#fbe4e1" stroke="#c9564a" stroke-width="1.5" />
          <path d="M {x(c.position) - 3.5} {laneY(i) - 3.5} l 7 7 M {x(c.position) + 3.5} {laneY(i) - 3.5} l -7 7" stroke="#c9564a" stroke-width="1.8" stroke-linecap="round" />
        {:else if c.command_class === 'edit' && c.position === b.firstEdit}
          <circle cx={x(c.position)} cy={laneY(i)} r="9" fill="#fff" stroke="#27272a" stroke-width="1.5" />
          <circle cx={x(c.position)} cy={laneY(i)} r="5" fill={COLORS.edit} />
        {:else}
          <circle cx={x(c.position)} cy={laneY(i)} r="3.6" fill={COLORS[kind(c)]} />
        {/if}
        {#if c.position === pos}
          <circle cx={x(c.position)} cy={laneY(i)} r="11" fill="none" stroke="#27272a" stroke-width="1.5" />
        {/if}
      {/each}
      <text x={x(last) + 14} y={laneY(i) - 3} class="lane">
        <tspan font-weight="600">{b.label}</tspan>
      </text>
      <text x={x(last) + 14} y={laneY(i) + 11} class="note">first edit at call {b.firstEdit}{b.credits ? ` · ${Number(b.credits).toLocaleString('en-US', { maximumFractionDigits: 0 })} credits` : ''}</text>
    </g>
  {/each}
</svg>

<div class="panel" aria-live="polite">
  {#if pos === null}
    <span class="hint">Move over the graph to compare what each run did at the same call. Click to pin a call, Esc to clear.</span>
  {:else}
    <div class="phead">
      <b>Call {pos}</b>
      {#if pos < at}<span>shared by every run</span>{/if}
      {#if pinnedPos !== null}<span class="pin">pinned</span>{/if}
    </div>
    {#if pos < at}
      {@const c = prefixLookup.get(pos)}
      <div class="prow"><i class="sw" style="background:{c ? COLORS[kind(c)] : '#d4d4d8'}"></i><span>{describe(c) ?? 'no call'}</span>{#if fileOf(c)}<code>{fileOf(c)}</code>{/if}</div>
    {:else}
      {#each branches as b, i}
        {@const c = lookups[i].get(pos)}
        <div class="prow" class:on={activeLane === i}>
          <i class="sw" style="background:{lineColor(b)}"></i>
          <b class="who">{b.label}</b>
          {#if c}
            <span>{describe(c)}</span>
            {#if fileOf(c)}<code>{fileOf(c)}</code>{/if}
            {#if c.blocked}<em class="flag stop">stopped by the change</em>{/if}
            {#if !c.blocked && c.is_error === true}<em class="flag err">error</em>{/if}
            {#if c.command_class === 'edit' && c.position === b.firstEdit}<em class="flag first">first edit</em>{/if}
          {:else}
            <span class="none">{pos > (b.calls.length ? b.calls[b.calls.length - 1].position : at) ? 'finished' : 'no call'}</span>
          {/if}
          {#if b.href}<a href={b.href}>Open session →</a>{/if}
        </div>
      {/each}
    {/if}
  {/if}
</div>

<div class="key">
  <span><i class="dot" style="background:#4a7bb7"></i>Edit</span>
  <span><i class="dot" style="background:#c4922c"></i>Run a command</span>
  <span><i class="dot" style="background:#a1a1aa"></i>Read or search</span>
  <span><i class="ring"></i>First edit</span>
  <span><i class="x">✕</i>Stopped by the change</span>
</div>

<style>
  svg { display: block; margin: 8px 0 4px; max-width: 1200px; cursor: crosshair; }
  text { font-family: inherit; fill: #27272a; pointer-events: none; }
  .lane-group { transition: opacity 120ms; }
  .note { font-size: 11px; fill: #71717a; }
  .lane { font-size: 12px; }
  .fork { font-size: 11px; fill: #27272a; }
  .panel { min-height: 148px; max-width: 1200px; border: 1px solid #e4e4e7; border-radius: 6px; padding: 10px 14px; margin: 6px 0 10px; font-size: 13px; background: #fafafa; }
  .hint { color: #71717a; }
  .phead { display: flex; gap: 12px; align-items: baseline; margin-bottom: 6px; }
  .phead span { color: #71717a; font-size: 12px; }
  .phead .pin { color: #27272a; border: 1px solid #a1a1aa; border-radius: 10px; padding: 0 8px; }
  .prow { display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: baseline; padding: 3px 4px; border-radius: 4px; }
  .prow.on { background: #f0f0f2; }
  .who { min-width: 150px; font-weight: 600; }
  .sw { display: inline-block; width: 10px; height: 10px; border-radius: 50%; align-self: center; }
  .none { color: #a1a1aa; }
  code { font-size: 11px; color: #52525b; background: #f0f0f2; padding: 1px 5px; border-radius: 3px; }
  .flag { font-style: normal; font-size: 11px; padding: 0 7px; border-radius: 9px; border: 1px solid; }
  .flag.stop { color: #a63a30; border-color: #d98a80; background: #fbe4e1; }
  .flag.err { color: #8a5a00; border-color: #d9b765; background: #fbf1dc; }
  .flag.first { color: #27272a; border-color: #a1a1aa; }
  .prow a { margin-left: auto; font-size: 12px; }
  .key { display: flex; flex-wrap: wrap; gap: 16px; font-size: 12px; color: #52525b; margin-bottom: 8px; }
  .dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
  .ring { display: inline-block; width: 11px; height: 11px; border-radius: 50%; border: 1.5px solid #27272a; margin-right: 6px; vertical-align: -2px; }
  .x { font-style: normal; color: #c9564a; margin-right: 6px; font-weight: 700; }
</style>
