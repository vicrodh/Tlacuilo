<script lang="ts">
  import {
    Highlighter,
    MessageSquare,
    Underline,
    Strikethrough,
    MousePointer,
    Trash2,
    Palette,
    Type,
    TextSelect,
    Square,
    Pencil,
    Circle,
    Minus,
    ArrowRight,
    Hash,
  } from 'lucide-svelte';
  import {
    type AnnotationsStore,
    type MarkupType,
    type ToolMode,
    HIGHLIGHT_COLORS,
  } from '$lib/stores/annotations.svelte';

  interface Props {
    store: AnnotationsStore;
    onClearAll?: () => void;
  }

  let { store, onClearAll }: Props = $props();

  let showColorPicker = $state(false);

  // Markup type options for selection modes
  const markupTypes: { type: MarkupType; icon: typeof Highlighter; label: string }[] = [
    { type: 'highlight', icon: Highlighter, label: 'Highlight' },
    { type: 'underline', icon: Underline, label: 'Underline' },
    { type: 'strikethrough', icon: Strikethrough, label: 'Strikethrough' },
  ];

  function selectTool(tool: ToolMode) {
    store.setActiveTool(tool);
    showColorPicker = false;
  }

  function selectMarkupType(type: MarkupType) {
    store.setPendingMarkupType(type);
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

  // Check if we're in a selection mode
  const isSelectionMode = $derived(
    store.activeTool === 'text-select' || store.activeTool === 'area-select'
  );
</script>

<div
  class="flex items-center gap-1 px-2 py-1.5 rounded-lg"
  style="background-color: var(--nord2);"
>
  <!-- Pointer (deselect tool) -->
  <button
    onclick={() => selectTool(null)}
    class="p-2 rounded transition-colors"
    class:bg-[var(--nord8)]={store.activeTool === null}
    style="color: {store.activeTool === null ? 'var(--nord0)' : 'var(--nord4)'};"
    title="Select"
  >
    <MousePointer size={16} />
  </button>

  <!-- Separator -->
  <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

  <!-- Text Select group -->
  <div class="flex items-center">
    <button
      onclick={() => selectTool('text-select')}
      class="p-2 rounded-l transition-colors"
      class:bg-[var(--nord8)]={store.activeTool === 'text-select'}
      style="color: {store.activeTool === 'text-select' ? 'var(--nord0)' : 'var(--nord4)'};"
      title="Text Selection"
    >
      <TextSelect size={16} />
    </button>
    <button
      onclick={() => selectTool('area-select')}
      class="p-2 rounded-r transition-colors"
      class:bg-[var(--nord8)]={store.activeTool === 'area-select'}
      style="color: {store.activeTool === 'area-select' ? 'var(--nord0)' : 'var(--nord4)'};"
      title="Area Selection"
    >
      <Square size={16} />
    </button>
  </div>

  <!-- Markup type selector (only visible when in selection mode) -->
  {#if isSelectionMode}
    <div class="flex items-center gap-0.5 ml-1 px-1 py-0.5 rounded" style="background-color: var(--nord3);">
      {#each markupTypes as markup}
        <button
          onclick={() => selectMarkupType(markup.type)}
          class="p-1.5 rounded transition-colors"
          class:bg-[var(--nord8)]={store.pendingMarkupType === markup.type}
          style="color: {store.pendingMarkupType === markup.type ? 'var(--nord0)' : 'var(--nord4)'};"
          title={markup.label}
        >
          <markup.icon size={14} />
        </button>
      {/each}
    </div>
  {/if}

  <!-- Separator -->
  <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

  <!-- Comment tool -->
  <button
    onclick={() => selectTool('comment')}
    class="p-2 rounded transition-colors"
    class:bg-[var(--nord8)]={store.activeTool === 'comment'}
    style="color: {store.activeTool === 'comment' ? 'var(--nord0)' : 'var(--nord4)'};"
    title="Comment"
  >
    <MessageSquare size={16} />
  </button>

  <!-- Typewriter tool -->
  <button
    onclick={() => selectTool('freetext')}
    class="p-2 rounded transition-colors"
    class:bg-[var(--nord8)]={store.activeTool === 'freetext'}
    style="color: {store.activeTool === 'freetext' ? 'var(--nord0)' : 'var(--nord4)'};"
    title="Typewriter"
  >
    <Type size={16} />
  </button>

  <!-- Separator -->
  <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

  <!-- Drawing tools -->
  <div class="flex items-center gap-0.5">
    <!-- Ink/Freehand -->
    <button
      onclick={() => selectTool('ink')}
      class="p-2 rounded transition-colors"
      class:bg-[var(--nord8)]={store.activeTool === 'ink'}
      style="color: {store.activeTool === 'ink' ? 'var(--nord0)' : 'var(--nord4)'};"
      title="Freehand Draw"
    >
      <Pencil size={16} />
    </button>

    <!-- Rectangle -->
    <button
      onclick={() => selectTool('rectangle')}
      class="p-2 rounded transition-colors"
      class:bg-[var(--nord8)]={store.activeTool === 'rectangle'}
      style="color: {store.activeTool === 'rectangle' ? 'var(--nord0)' : 'var(--nord4)'};"
      title="Rectangle"
    >
      <Square size={16} />
    </button>

    <!-- Ellipse -->
    <button
      onclick={() => selectTool('ellipse')}
      class="p-2 rounded transition-colors"
      class:bg-[var(--nord8)]={store.activeTool === 'ellipse'}
      style="color: {store.activeTool === 'ellipse' ? 'var(--nord0)' : 'var(--nord4)'};"
      title="Ellipse"
    >
      <Circle size={16} />
    </button>

    <!-- Line -->
    <button
      onclick={() => selectTool('line')}
      class="p-2 rounded transition-colors"
      class:bg-[var(--nord8)]={store.activeTool === 'line'}
      style="color: {store.activeTool === 'line' ? 'var(--nord0)' : 'var(--nord4)'};"
      title="Line"
    >
      <Minus size={16} />
    </button>

    <!-- Arrow -->
    <button
      onclick={() => selectTool('arrow')}
      class="p-2 rounded transition-colors"
      class:bg-[var(--nord8)]={store.activeTool === 'arrow'}
      style="color: {store.activeTool === 'arrow' ? 'var(--nord0)' : 'var(--nord4)'};"
      title="Arrow"
    >
      <ArrowRight size={16} />
    </button>

    <!-- Sequence Number -->
    <button
      onclick={() => selectTool('sequenceNumber')}
      class="p-2 rounded transition-colors"
      class:bg-[var(--nord8)]={store.activeTool === 'sequenceNumber'}
      style="color: {store.activeTool === 'sequenceNumber' ? 'var(--nord0)' : 'var(--nord4)'};"
      title="Sequence Number"
    >
      <Hash size={16} />
    </button>
  </div>

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
        class="absolute top-full left-1/2 mt-1 rounded-lg shadow-lg"
        style="
          background-color: var(--nord1);
          border: 1px solid var(--nord3);
          z-index: 99999;
          transform: translateX(-50%);
          padding: 12px;
          width: 176px;
          box-sizing: border-box;
        "
      >
        <div
          style="
            display: grid;
            grid-template-columns: repeat(4, 32px);
            gap: 8px;
            justify-content: center;
          "
        >
          {#each HIGHLIGHT_COLORS as color}
            <button
              onclick={() => selectColor(color.value)}
              class="rounded border-2 transition-transform hover:scale-110"
              style="
                width: 32px;
                height: 32px;
                background-color: {color.value};
                border-color: {store.activeColor === color.value ? 'var(--nord6)' : (color.value === '#FFFFFF' ? 'var(--nord3)' : 'transparent')};
              "
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
