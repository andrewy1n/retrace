<script>
  import '@evidence-dev/tailwind/fonts.css';
  import '../app.css';
  import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { showQueries } from '@evidence-dev/component-utilities/stores';
  export let data;

  const links = [
    { href: '/', label: 'Proposals', match: (p) => p === '/' || p.startsWith('/proposals') },
    { href: '/results', label: 'Results', match: (p) => p.startsWith('/results') },
    { href: '/sessions', label: 'Sessions', match: (p) => p.startsWith('/sessions') }
  ];
  $: path = $page.url.pathname;
  onMount(() => showQueries.set(false));
</script>

<header class="rt-nav">
  <a class="rt-brand" href="/">Retrace</a>
  <nav>
    {#each links as l}
      <a href={l.href} class:active={l.match(path)}>{l.label}</a>
    {/each}
  </nav>
</header>

<EvidenceDefaultLayout {data} hideHeader={true} hideBreadcrumbs={true} hideSidebar={true} hideTOC={true} fullWidth={true} maxWidth={1200} builtWithEvidence={false}>
  <slot slot="content" />
</EvidenceDefaultLayout>

<style>
  .rt-nav { display: flex; align-items: center; gap: 32px; height: 52px; padding: 0 32px; border-bottom: 1px solid #e4e4e7; background: #fff; position: sticky; top: 0; z-index: 40; }
  .rt-brand { font-weight: 700; font-size: 16px; color: #18181b; text-decoration: none; letter-spacing: -0.01em; }
  .rt-nav nav { display: flex; gap: 4px; height: 100%; }
  .rt-nav nav a { display: flex; align-items: center; padding: 0 12px; font-size: 14px; color: #52525b; text-decoration: none; border-bottom: 2px solid transparent; }
  .rt-nav nav a:hover { color: #18181b; }
  .rt-nav nav a.active { color: #18181b; font-weight: 600; border-bottom-color: #18181b; }

  :global(.rt-page-head) { margin: 24px 0 20px; }
  :global(.rt-page-head h1) { margin: 0 0 4px; font-size: 26px; }
  :global(.rt-page-head p) { margin: 0; color: #52525b; font-size: 14px; }
  :global(.rt-example) { display: inline-block; margin: 0 0 16px; padding: 6px 12px; font-size: 12px; color: #52525b; background: #f4f4f5; border: 1px dashed #a1a1aa; border-radius: 4px; }

  :global(.rt-kpis) { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 0 0 28px; }
  :global(.rt-kpi) { padding: 14px 16px; border: 1px solid #e4e4e7; border-radius: 8px; background: #fff; }
  :global(.rt-kpi .rt-k) { display: block; font-size: 12px; color: #71717a; }
  :global(.rt-kpi .rt-big) { display: block; margin: 4px 0 2px; font-size: 24px; font-weight: 650; color: #18181b; }
  :global(.rt-kpi .rt-s) { display: block; font-size: 12px; color: #71717a; }
  :global(.rt-kpi.rt-attn) { border-color: #d9b765; background: #fdf8ec; }

  :global(.rt-section) { margin: 32px 0 12px; font-size: 13px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; color: #52525b; }
  :global(.rt-cards) { display: grid; gap: 14px; }

  :global(.rt-card) { padding: 18px 20px; border: 1px solid #e4e4e7; border-radius: 8px; background: #fff; }
  :global(.rt-card h3) { margin: 10px 0 4px; font-size: 18px; }
  :global(.rt-card h3 a) { color: #18181b; text-decoration: none; }
  :global(.rt-card h3 a:hover) { text-decoration: underline; }
  :global(.rt-summary) { margin: 0 0 14px; max-width: 760px; color: #52525b; font-size: 14px; line-height: 1.5; }
  :global(.rt-tags) { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  :global(.rt-tag) { padding: 2px 8px; font-size: 12px; color: #52525b; border: 1px solid #e4e4e7; border-radius: 4px; }
  :global(.rt-metrics) { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; padding: 12px 0; border-top: 1px solid #f4f4f5; border-bottom: 1px solid #f4f4f5; }
  :global(.rt-metrics .rt-k) { display: block; font-size: 12px; color: #71717a; }
  :global(.rt-metrics .rt-v) { display: block; margin-top: 2px; font-size: 20px; font-weight: 650; color: #18181b; }
  :global(.rt-metrics .rt-v.rt-none) { font-size: 14px; font-weight: 400; color: #a1a1aa; }
  :global(.rt-metrics .rt-s) { display: block; font-size: 12px; color: #71717a; }
  :global(.rt-foot) { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 12px; }
  :global(.rt-spacer) { flex: 1; }
  :global(.rt-link) { font-size: 13px; color: #27272a; text-decoration: none; font-weight: 500; }
  :global(.rt-link:hover) { text-decoration: underline; }

  :global(.rt-chip) { display: inline-block; padding: 2px 9px; font-size: 12px; font-weight: 600; border-radius: 999px; }
  :global(.rt-ok) { background: #e8f3ea; color: #166534; }
  :global(.rt-bad) { background: #fbe4e4; color: #991b1b; }
  :global(.rt-review) { background: #fbf1dc; color: #854d0e; }
  :global(.rt-info) { background: #e8eff8; color: #2f5486; }
  :global(.rt-muted) { background: #f4f4f5; color: #52525b; }

  :global(.rt-btn) { display: inline-block; padding: 6px 12px; font-size: 13px; font-weight: 600; color: #fff; background: #18181b; border-radius: 6px; text-decoration: none; }
  :global(.rt-btn:hover) { background: #3f3f46; }
  :global(.rt-btn.rt-btn-off) { color: #a1a1aa; background: #f4f4f5; font-weight: 400; }

  :global(.rt-head) { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: 16px; margin: 20px 0 8px; }
  :global(.rt-head h1) { margin: 8px 0 6px; font-size: 26px; }
  :global(.rt-head p) { margin: 0; max-width: 720px; color: #52525b; font-size: 14px; line-height: 1.5; }
  :global(.rt-head > div:first-child) { flex: 1 1 420px; min-width: 0; }
  :global(.rt-panel) { flex: 0 0 300px; min-width: 260px; padding: 14px 16px; border: 1px solid #e4e4e7; border-radius: 8px; background: #fff; }
  :global(.rt-panel .rt-k) { display: block; margin-bottom: 6px; font-size: 12px; color: #71717a; }
  :global(.rt-panel .rt-row) { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  :global(.rt-panel .rt-note) { margin: 8px 0 0; font-size: 12px; color: #71717a; }
  :global(.rt-facts) { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 16px 0; }
  :global(.rt-fact) { padding: 12px 14px; border: 1px solid #e4e4e7; border-radius: 8px; }
  :global(.rt-fact .rt-k) { display: block; font-size: 12px; color: #71717a; }
  :global(.rt-fact .rt-v) { display: block; margin-top: 2px; font-size: 16px; font-weight: 600; }
  :global(.rt-fact .rt-s) { display: block; font-size: 12px; color: #71717a; }
  :global(.rt-files) { margin: 8px 0 16px; padding: 0; list-style: none; font-family: ui-monospace, monospace; font-size: 13px; }
  :global(.rt-files li) { padding: 4px 0; }
  :global(.rt-h2) { margin: 28px 0 8px; font-size: 18px; font-weight: 650; color: #18181b; }
  :global(.rt-h3) { margin: 20px 0 4px; font-size: 14px; font-weight: 600; color: #3f3f46; }
  :global(.rt-tab-note) { font-size: 12px; color: #71717a; }
</style>
