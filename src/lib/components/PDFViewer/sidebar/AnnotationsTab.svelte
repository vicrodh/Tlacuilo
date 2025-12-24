<script lang="ts">
  import AnnotationsPanel from '../AnnotationsPanel.svelte';
  import type { AnnotationsStore } from '$lib/stores/annotations.svelte';

  interface Props {
    store: AnnotationsStore;
    onNavigateToPage: (page: number) => void;
  }

  let { store, onNavigateToPage }: Props = $props();
</script>

<div class="annotations-tab">
  <AnnotationsPanel {store} {onNavigateToPage} />
</div>

<style>
  .annotations-tab {
    height: 100%;
    overflow: hidden;
  }

  .annotations-tab :global(.h-full) {
    height: 100%;
  }
</style>
