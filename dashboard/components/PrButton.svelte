<script>
  export let url = null;
</script>

{#if url}
  <a class="rt-btn" href={url} target="_blank" rel="noopener noreferrer">View pull request ↗</a>
{:else}
  <span class="rt-btn rt-btn-off">No pull request yet</span>
{/if}
