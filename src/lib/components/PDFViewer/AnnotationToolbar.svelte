<script lang="ts">
  import {
    Highlighter,
    MessageSquare,
    Underline,
    Strikethrough,
    MousePointer,
    Trash2,
    Palette
  } from 'lucide-svelte';
  import {
    type AnnotationType,
    type AnnotationsStore,
    HIGHLIGHT_COLORS,
  } from '$lib/stores/annotations.svelte';

  interface Props {
    store: AnnotationsStore;
    onClearAll?: () => void;
  }

  let { store, onClearAll }: Props = $props();

  let showColorPicker = $state(false);

  const tools: { type: AnnotationType | null; icon: typeof Highlighter; label: string }[] = [
    { type: null, icon: MousePointer, label: 'Select' },
    { type: 'highlight', icon: Highlighter, label: 'Highlight' },
    { type: 'comment', icon: MessageSquare, label: 'Comment' },
    { type: 'underline', icon: Underline, label: 'Underline' },
    { type: 'strikethrough', icon: Strikethrough, label: 'Strikethrough' },
  ];

  function selectTool(type: AnnotationType | null) {
    store.setActiveTool(type);
    showColorPicker = false;
  }

  function selectColor(color: string) {
    store.setActiveColor(color);
    showColorPicker = false;
  }

  function toggleColorPicker() {
    showColorPicker = !showColorPicker;
  }

  function handleClearAll() {
    if (confirm('Clear all annotations?')) {
      store.clearAnnotations();
      onClearAll?.();
    }
  }
</script>

<div
  class="flex items-center gap-1 px-2 py-1.5 rounded-lg"
  style="background-color: var(--nord2);"
>
  <!-- Tool buttons -->
  {#each tools as tool}
    <button
      onclick={() => selectTool(tool.type)}
      class="p-2 rounded transition-colors"
      class:bg-[var(--nord8)]={store.activeTool === tool.type}
      style="color: {store.activeTool === tool.type ? 'var(--nord0)' : 'var(--nord4)'};"
      title={tool.label}
    >
      <tool.icon size={16} />
    </button>
  {/each}

  <!-- Separator -->
  <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

  <!-- Color picker -->
  <div class="relative">
    <button
      onclick={toggleColorPicker}
      class="p-2 rounded transition-colors hover:bg-[var(--nord3)] flex items-center gap-1"
      title="Annotation color"
    >
      <div
        class="w-4 h-4 rounded-sm border"
        style="background-color: {store.activeColor}; border-color: var(--nord3);"
      ></div>
      <Palette size={14} class="opacity-60" />
    </button>

    {#if showColorPicker}
      <div
        class="absolute top-full left-0 mt-1 p-2 rounded-lg shadow-lg z-50"
        style="background-color: var(--nord1); border: 1px solid var(--nord3);"
      >
        <div class="grid grid-cols-3 gap-1">
          {#each HIGHLIGHT_COLORS as color}
            <button
              onclick={() => selectColor(color.value)}
              class="w-8 h-8 rounded border-2 transition-transform hover:scale-110"
              style="background-color: {color.value}; border-color: {store.activeColor === color.value ? 'var(--nord6)' : 'transparent'};"
              title={color.name}
            ></button>
          {/each}
        </div>
      </div>
    {/if}
  </div>

  <!-- Separator -->
  <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

  <!-- Clear all -->
  <button
    onclick={handleClearAll}
    class="p-2 rounded transition-colors hover:bg-[var(--nord11)] hover:text-white"
    title="Clear all annotations"
  >
    <Trash2 size={16} />
  </button>
</div>
