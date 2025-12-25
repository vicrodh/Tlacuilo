<script lang="ts">
  import {
    MousePointer,
    Type,
    Image,
    Square,
    Circle,
    Minus,
    Undo2,
    Redo2,
    Trash2,
    Check,
    X,
    ChevronRight,
    Palette,
    Bold,
    Italic,
    AlignLeft,
    AlignCenter,
    AlignRight,
  } from 'lucide-svelte';
  import { ask } from '@tauri-apps/plugin-dialog';
  import type { EditsStore, EditTool, TextStyle } from '$lib/stores/edits.svelte';

  interface Props {
    store: EditsStore;
    onApply?: () => void;
    onDiscard?: () => void;
  }

  let { store, onApply, onDiscard }: Props = $props();

  let showShapesMenu = $state(false);
  let showTextOptions = $state(false);
  let showColorPicker = $state(false);

  // Font options
  const fontFamilies = [
    'Helvetica',
    'Times-Roman',
    'Courier',
    'Arial',
    'Verdana',
  ];

  const fontSizes = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 72];

  // Shape tools
  const shapeTools: { tool: EditTool; icon: typeof Square; label: string }[] = [
    { tool: 'shape-rect', icon: Square, label: 'Rectangle' },
    { tool: 'shape-ellipse', icon: Circle, label: 'Ellipse' },
    { tool: 'line', icon: Minus, label: 'Line' },
  ];

  const isShapeTool = $derived(
    store.activeTool === 'shape-rect' ||
    store.activeTool === 'shape-ellipse' ||
    store.activeTool === 'line'
  );

  // Colors for picker
  const colors = [
    '#000000', '#FFFFFF', '#BF616A', '#D08770', '#EBCB8B',
    '#A3BE8C', '#88C0D0', '#5E81AC', '#B48EAD', '#4C566A',
  ];

  function selectTool(tool: EditTool) {
    store.setActiveTool(tool);
    showShapesMenu = false;
    showTextOptions = tool === 'text';
    showColorPicker = false;
  }

  function toggleShapesMenu() {
    showShapesMenu = !showShapesMenu;
    showTextOptions = false;
    showColorPicker = false;
  }

  function toggleTextOptions() {
    showTextOptions = !showTextOptions;
    showShapesMenu = false;
    showColorPicker = false;
  }

  function toggleColorPicker() {
    showColorPicker = !showColorPicker;
    showShapesMenu = false;
    showTextOptions = false;
  }

  function setTextStyle(style: Partial<TextStyle>) {
    store.setTextStyle(style);
  }

  async function handleDiscard() {
    if (store.isDirty) {
      const confirmed = await ask('Discard all edit changes? This cannot be undone.', {
        title: 'Discard Changes',
        kind: 'warning',
      });
      if (!confirmed) return;
    }
    store.clearOps();
    onDiscard?.();
  }

  function handleApply() {
    onApply?.();
  }

  function deleteSelected() {
    if (store.selectedId) {
      store.removeOp(store.selectedId);
    }
  }
</script>

<div
  class="flex items-center gap-1 px-2 py-1.5 rounded-lg"
  style="background-color: var(--nord2);"
>
  <!-- Select tool -->
  <button
    onclick={() => selectTool('select')}
    class="p-2 rounded transition-colors"
    class:bg-[var(--nord8)]={store.activeTool === 'select'}
    style="color: {store.activeTool === 'select' ? 'var(--nord0)' : 'var(--nord4)'};"
    title="Select / Move"
  >
    <MousePointer size={16} />
  </button>

  <!-- Separator -->
  <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

  <!-- Text tool with options -->
  <div class="relative">
    <button
      onclick={() => selectTool('text')}
      class="p-2 rounded transition-colors flex items-center gap-0.5"
      class:bg-[var(--nord8)]={store.activeTool === 'text'}
      style="color: {store.activeTool === 'text' ? 'var(--nord0)' : 'var(--nord4)'};"
      title="Text"
    >
      <Type size={16} />
      <ChevronRight size={12} class="rotate-90 opacity-60" />
    </button>

    {#if store.activeTool === 'text' && showTextOptions}
      <div
        class="absolute top-full left-0 mt-1 rounded-lg shadow-lg p-2 z-50"
        style="background-color: var(--nord1); border: 1px solid var(--nord3); min-width: 200px;"
      >
        <!-- Font Family -->
        <div class="mb-2">
          <div class="text-[10px] uppercase opacity-40 mb-1">Font</div>
          <select
            value={store.activeTextStyle.fontFamily}
            onchange={(e) => setTextStyle({ fontFamily: (e.target as HTMLSelectElement).value })}
            class="w-full px-2 py-1 text-xs rounded"
            style="background-color: var(--nord2); border: 1px solid var(--nord3);"
          >
            {#each fontFamilies as font}
              <option value={font}>{font}</option>
            {/each}
          </select>
        </div>

        <!-- Font Size -->
        <div class="mb-2">
          <div class="text-[10px] uppercase opacity-40 mb-1">Size</div>
          <select
            value={store.activeTextStyle.fontSize}
            onchange={(e) => setTextStyle({ fontSize: parseInt((e.target as HTMLSelectElement).value) })}
            class="w-full px-2 py-1 text-xs rounded"
            style="background-color: var(--nord2); border: 1px solid var(--nord3);"
          >
            {#each fontSizes as size}
              <option value={size}>{size}pt</option>
            {/each}
          </select>
        </div>

        <!-- Text Color -->
        <div class="mb-2">
          <div class="text-[10px] uppercase opacity-40 mb-1">Color</div>
          <div class="grid grid-cols-5 gap-1">
            {#each colors as color}
              <button
                onclick={() => setTextStyle({ color })}
                class="w-6 h-6 rounded border-2 transition-transform hover:scale-110"
                style="
                  background-color: {color};
                  border-color: {store.activeTextStyle.color === color ? 'var(--nord6)' : 'transparent'};
                "
              ></button>
            {/each}
          </div>
        </div>

        <!-- Bold / Italic -->
        <div class="flex gap-1 mb-2 pt-2" style="border-top: 1px solid var(--nord3);">
          <button
            onclick={() => setTextStyle({ bold: !store.activeTextStyle.bold })}
            class="flex-1 p-1.5 rounded transition-colors"
            class:bg-[var(--nord8)]={store.activeTextStyle.bold}
            style="color: {store.activeTextStyle.bold ? 'var(--nord0)' : 'var(--nord4)'};"
            title="Bold"
          >
            <Bold size={14} />
          </button>
          <button
            onclick={() => setTextStyle({ italic: !store.activeTextStyle.italic })}
            class="flex-1 p-1.5 rounded transition-colors"
            class:bg-[var(--nord8)]={store.activeTextStyle.italic}
            style="color: {store.activeTextStyle.italic ? 'var(--nord0)' : 'var(--nord4)'};"
            title="Italic"
          >
            <Italic size={14} />
          </button>
        </div>

        <!-- Alignment -->
        <div class="flex gap-1">
          <button
            onclick={() => setTextStyle({ align: 'left' })}
            class="flex-1 p-1.5 rounded transition-colors"
            class:bg-[var(--nord8)]={store.activeTextStyle.align === 'left'}
            style="color: {store.activeTextStyle.align === 'left' ? 'var(--nord0)' : 'var(--nord4)'};"
            title="Align Left"
          >
            <AlignLeft size={14} />
          </button>
          <button
            onclick={() => setTextStyle({ align: 'center' })}
            class="flex-1 p-1.5 rounded transition-colors"
            class:bg-[var(--nord8)]={store.activeTextStyle.align === 'center'}
            style="color: {store.activeTextStyle.align === 'center' ? 'var(--nord0)' : 'var(--nord4)'};"
            title="Align Center"
          >
            <AlignCenter size={14} />
          </button>
          <button
            onclick={() => setTextStyle({ align: 'right' })}
            class="flex-1 p-1.5 rounded transition-colors"
            class:bg-[var(--nord8)]={store.activeTextStyle.align === 'right'}
            style="color: {store.activeTextStyle.align === 'right' ? 'var(--nord0)' : 'var(--nord4)'};"
            title="Align Right"
          >
            <AlignRight size={14} />
          </button>
        </div>
      </div>
    {/if}
  </div>

  <!-- Image tool -->
  <button
    onclick={() => selectTool('image')}
    class="p-2 rounded transition-colors"
    class:bg-[var(--nord8)]={store.activeTool === 'image'}
    style="color: {store.activeTool === 'image' ? 'var(--nord0)' : 'var(--nord4)'};"
    title="Insert Image"
  >
    <Image size={16} />
  </button>

  <!-- Shapes dropdown -->
  <div class="relative">
    <button
      onclick={toggleShapesMenu}
      class="p-2 rounded transition-colors flex items-center gap-0.5"
      class:bg-[var(--nord8)]={isShapeTool}
      style="color: {isShapeTool ? 'var(--nord0)' : 'var(--nord4)'};"
      title="Shapes"
    >
      {#if store.activeTool === 'shape-ellipse'}
        <Circle size={16} />
      {:else if store.activeTool === 'line'}
        <Minus size={16} />
      {:else}
        <Square size={16} />
      {/if}
      <ChevronRight size={12} class="rotate-90 opacity-60" />
    </button>

    {#if showShapesMenu}
      <div
        class="absolute top-full left-0 mt-1 rounded-lg shadow-lg py-1 z-50"
        style="background-color: var(--nord1); border: 1px solid var(--nord3); min-width: 120px;"
      >
        {#each shapeTools as shape}
          <button
            onclick={() => selectTool(shape.tool)}
            class="w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-[var(--nord2)] transition-colors"
            class:bg-[var(--nord3)]={store.activeTool === shape.tool}
          >
            <shape.icon size={14} />
            <span>{shape.label}</span>
          </button>
        {/each}

        <!-- Stroke color -->
        <div class="px-3 py-2 mt-1" style="border-top: 1px solid var(--nord3);">
          <div class="text-[10px] uppercase opacity-40 mb-1">Stroke</div>
          <div class="grid grid-cols-5 gap-1">
            {#each colors as color}
              <button
                onclick={() => store.setStrokeColor(color)}
                class="w-5 h-5 rounded border-2 transition-transform hover:scale-110"
                style="
                  background-color: {color};
                  border-color: {store.activeStrokeColor === color ? 'var(--nord6)' : 'transparent'};
                "
              ></button>
            {/each}
          </div>
        </div>

        <!-- Fill toggle and color -->
        <div class="px-3 py-2" style="border-top: 1px solid var(--nord3);">
          <label class="flex items-center gap-2 mb-2 cursor-pointer">
            <input
              type="checkbox"
              checked={store.activeFillEnabled}
              onchange={(e) => store.setFillEnabled((e.target as HTMLInputElement).checked)}
              class="w-3 h-3 rounded"
            />
            <span class="text-[10px] uppercase opacity-60">Fill</span>
          </label>
          {#if store.activeFillEnabled}
            <div class="grid grid-cols-5 gap-1">
              {#each colors as color}
                <button
                  onclick={() => store.setFillColor(color)}
                  class="w-5 h-5 rounded border-2 transition-transform hover:scale-110"
                  style="
                    background-color: {color};
                    border-color: {store.activeFillColor === color ? 'var(--nord6)' : 'transparent'};
                  "
                ></button>
              {/each}
            </div>
          {/if}
        </div>
      </div>
    {/if}
  </div>

  <!-- Separator -->
  <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

  <!-- Delete selected -->
  <button
    onclick={deleteSelected}
    disabled={!store.selectedId}
    class="p-2 rounded transition-colors"
    class:opacity-40={!store.selectedId}
    class:cursor-not-allowed={!store.selectedId}
    class:hover:bg-[var(--nord11)]={store.selectedId}
    class:hover:text-white={store.selectedId}
    title="Delete selected"
  >
    <Trash2 size={16} />
  </button>

  <!-- Separator -->
  <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

  <!-- Undo/Redo -->
  <button
    onclick={() => store.undo()}
    disabled={!store.canUndo()}
    class="p-2 rounded transition-colors hover:bg-[var(--nord3)]"
    class:opacity-40={!store.canUndo()}
    class:cursor-not-allowed={!store.canUndo()}
    title="Undo (Ctrl+Z)"
  >
    <Undo2 size={16} />
  </button>

  <button
    onclick={() => store.redo()}
    disabled={!store.canRedo()}
    class="p-2 rounded transition-colors hover:bg-[var(--nord3)]"
    class:opacity-40={!store.canRedo()}
    class:cursor-not-allowed={!store.canRedo()}
    title="Redo (Ctrl+Y)"
  >
    <Redo2 size={16} />
  </button>

  <!-- Separator -->
  <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

  <!-- Apply / Discard -->
  <div class="flex items-center gap-1">
    {#if store.opCount > 0}
      <span class="text-xs px-2 py-1 rounded" style="background-color: var(--nord3);">
        {store.opCount} edit{store.opCount !== 1 ? 's' : ''}
      </span>
    {/if}

    <button
      onclick={handleDiscard}
      disabled={!store.isDirty && store.opCount === 0}
      class="p-2 rounded transition-colors flex items-center gap-1"
      class:opacity-40={!store.isDirty && store.opCount === 0}
      class:hover:bg-[var(--nord11)]={store.isDirty || store.opCount > 0}
      class:hover:text-white={store.isDirty || store.opCount > 0}
      title="Discard changes"
    >
      <X size={16} />
    </button>

    <button
      onclick={handleApply}
      disabled={store.opCount === 0}
      class="px-3 py-1.5 rounded transition-colors flex items-center gap-1 text-sm font-medium"
      class:opacity-40={store.opCount === 0}
      class:cursor-not-allowed={store.opCount === 0}
      style="background-color: {store.opCount > 0 ? 'var(--nord14)' : 'var(--nord3)'}; color: {store.opCount > 0 ? 'var(--nord0)' : 'var(--nord4)'};"
      title="Apply edits"
    >
      <Check size={16} />
      <span>Apply</span>
    </button>
  </div>
</div>
