<script lang="ts">
  interface Props {
    pageName: string;
  }

  let { pageName }: Props = $props();

  const pageLabels: Record<string, string> = {
    create: 'Create PDF',
    edit: 'Edit PDF',
    split: 'Split PDF',
    rotate: 'Rotate PDF',
    convert: 'Convert',
    annotate: 'Annotate',
    protect: 'Protect',
    forms: 'Forms',
    compress: 'Compress',
    recent: 'Recent Files',
    tools: 'Tools',
    tasks: 'Tasks',
    settings: 'Settings',
  };

  const label = $derived(pageLabels[pageName] || pageName);
</script>

<div class="flex-1 flex items-center justify-center">
  <div class="text-center">
    <h2 class="text-2xl mb-4" style="color: var(--nord6);">{label}</h2>
    <p class="opacity-60">Page under construction</p>
  </div>
</div>
