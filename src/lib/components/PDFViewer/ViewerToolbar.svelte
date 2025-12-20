<script lang="ts">
  import {
    MousePointer2,
    Hand,
    Pencil,
    Highlighter,
    Type,
    EyeOff,
    Stamp,
    ZoomIn,
    ZoomOut,
    RotateCw,
    ChevronLeft,
    ChevronRight,
    ExternalLink,
    X,
    Minus,
    Plus
  } from 'lucide-svelte';

  interface Props {
    activeTool: string;
    zoom: number;
    currentPage: number;
    totalPages: number;
    showDetachButton?: boolean;
    onToolChange: (tool: string) => void;
    onZoomIn: () => void;
    onZoomOut: () => void;
    onZoomSet: (zoom: number) => void;
    onRotate: () => void;
    onPrevPage: () => void;
    onNextPage: () => void;
    onGoToPage: (page: number) => void;
    onDetach?: () => void;
    onClose?: () => void;
  }

  let {
    activeTool,
    zoom,
    currentPage,
    totalPages,
    showDetachButton = true,
    onToolChange,
    onZoomIn,
    onZoomOut,
    onZoomSet,
    onRotate,
    onPrevPage,
    onNextPage,
    onGoToPage,
    onDetach,
    onClose,
  }: Props = $props();

  let pageInputValue = $state(String(currentPage));

  // Update input when page changes externally
  $effect(() => {
    pageInputValue = String(currentPage);
  });

  function handlePageInput(e: Event) {
    const target = e.target as HTMLInputElement;
    const value = parseInt(target.value, 10);
    if (!isNaN(value) && value >= 1 && value <= totalPages) {
      onGoToPage(value);
    }
  }

  function handlePageKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      const value = parseInt(pageInputValue, 10);
      if (!isNaN(value) && value >= 1 && value <= totalPages) {
        onGoToPage(value);
      } else {
        pageInputValue = String(currentPage);
      }
    }
  }

  const tools = [
    { id: 'select', icon: MousePointer2, label: 'Select' },
    { id: 'pan', icon: Hand, label: 'Pan' },
    { id: 'pen', icon: Pencil, label: 'Pen' },
    { id: 'highlight', icon: Highlighter, label: 'Highlight' },
    { id: 'text', icon: Type, label: 'Text' },
    { id: 'redact', icon: EyeOff, label: 'Redact' },
    { id: 'stamp', icon: Stamp, label: 'Stamp' },
  ];

  const zoomPresets = [0.5, 0.75, 1, 1.25, 1.5, 2, 3];
</script>

<div
  class="flex items-center justify-between px-3 py-2 border-b"
  style="background-color: var(--nord1); border-color: var(--nord3);"
>
  <!-- Tools -->
  <div class="flex items-center gap-1">
    {#each tools as tool}
      <button
        onclick={() => onToolChange(tool.id)}
        class="p-2 rounded-lg transition-colors"
        style="background-color: {activeTool === tool.id ? 'var(--nord8)' : 'transparent'};
               color: {activeTool === tool.id ? 'var(--nord0)' : 'var(--nord4)'};"
        title={tool.label}
      >
        <tool.icon size={16} />
      </button>
    {/each}

    <!-- Separator -->
    <div class="w-px h-6 mx-2" style="background-color: var(--nord3);"></div>

    <!-- Rotate -->
    <button
      onclick={onRotate}
      class="p-2 rounded-lg transition-colors hover:bg-[var(--nord2)]"
      title="Rotate 90°"
    >
      <RotateCw size={16} />
    </button>
  </div>

  <!-- Navigation -->
  <div class="flex items-center gap-2">
    <button
      onclick={onPrevPage}
      disabled={currentPage <= 1}
      class="p-1.5 rounded transition-colors hover:bg-[var(--nord2)] disabled:opacity-30"
      title="Previous page"
    >
      <ChevronLeft size={18} />
    </button>

    <div class="flex items-center gap-1">
      <input
        type="text"
        bind:value={pageInputValue}
        onblur={handlePageInput}
        onkeydown={handlePageKeydown}
        class="w-12 px-2 py-1 rounded text-center text-sm"
        style="background-color: var(--nord2); border: 1px solid var(--nord3);"
      />
      <span class="text-sm opacity-60">/ {totalPages}</span>
    </div>

    <button
      onclick={onNextPage}
      disabled={currentPage >= totalPages}
      class="p-1.5 rounded transition-colors hover:bg-[var(--nord2)] disabled:opacity-30"
      title="Next page"
    >
      <ChevronRight size={18} />
    </button>
  </div>

  <!-- Zoom & Actions -->
  <div class="flex items-center gap-2">
    <!-- Zoom controls -->
    <button
      onclick={onZoomOut}
      class="p-1.5 rounded transition-colors hover:bg-[var(--nord2)]"
      title="Zoom out"
    >
      <Minus size={16} />
    </button>

    <div class="relative group">
      <button
        class="px-2 py-1 rounded text-sm min-w-[60px] hover:bg-[var(--nord2)] transition-colors"
        style="background-color: var(--nord2);"
      >
        {Math.round(zoom * 100)}%
      </button>
      <!-- Zoom presets dropdown -->
      <div
        class="absolute top-full left-1/2 -translate-x-1/2 mt-1 py-1 rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50"
        style="background-color: var(--nord2); min-width: 80px;"
      >
        {#each zoomPresets as preset}
          <button
            onclick={() => onZoomSet(preset)}
            class="w-full px-3 py-1.5 text-sm text-left hover:bg-[var(--nord3)] transition-colors"
            style="color: {zoom === preset ? 'var(--nord8)' : 'var(--nord4)'};"
          >
            {Math.round(preset * 100)}%
          </button>
        {/each}
      </div>
    </div>

    <button
      onclick={onZoomIn}
      class="p-1.5 rounded transition-colors hover:bg-[var(--nord2)]"
      title="Zoom in"
    >
      <Plus size={16} />
    </button>

    <!-- Separator -->
    <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

    <!-- Detach button -->
    {#if showDetachButton && onDetach}
      <button
        onclick={onDetach}
        class="p-2 rounded-lg transition-colors hover:bg-[var(--nord2)]"
        title="Open in new window"
      >
        <ExternalLink size={16} />
      </button>
    {/if}

    <!-- Close button -->
    {#if onClose}
      <button
        onclick={onClose}
        class="p-2 rounded-lg transition-colors hover:bg-[var(--nord11)] hover:text-white"
        title="Close"
      >
        <X size={16} />
      </button>
    {/if}
  </div>
</div>
