<svelte:head>
  <title>I H PDF</title>
</svelte:head>

<script lang="ts">
  import Shell from './lib/views/Shell.svelte';
  import Dashboard from './lib/views/Dashboard.svelte';
  import MergePage from './lib/views/MergePage.svelte';

  let route: 'dashboard' | 'merge' = 'dashboard';

  function navigate(page: string) {
    if (page === 'merge') route = 'merge';
    else route = 'dashboard';
  }
</script>

<Shell onNavigate={navigate}>
  {#if route === 'dashboard'}
    <Dashboard onNavigate={navigate} />
  {:else}
    <MergePage onNavigate={navigate} />
  {/if}
</Shell>
