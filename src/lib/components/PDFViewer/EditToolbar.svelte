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
    Save,
    Eye,
    EyeOff,
  } from 'lucide-svelte';
  import { ask } from '@tauri-apps/plugin-dialog';
  import type { EditsStore, EditTool, TextStyle, EditGranularity } from '$lib/stores/edits.svelte';

  interface Props {
    store: EditsStore;
    onApply?: () => void;
    onApplyInPlace?: () => void;  // Save to same file (overwrite)
    onDiscard?: () => void;
    previewMode?: boolean;  // Hide edit indicators when true
    onPreviewToggle?: () => void;
  }

  let { store, onApply, onApplyInPlace, onDiscard, previewMode = false, onPreviewToggle }: Props = $props();

  let showShapesMenu = $state(false);
  let showTextOptions = $state(false);
  let showColorPicker = $state(false);

  // Font options - Include serif and sans-serif
  const fontFamilies = [
    { value: '"Times New Roman", Times, Georgia, serif', label: 'Times (Serif)' },
    { value: 'Arial, Helvetica, sans-serif', label: 'Arial (Sans)' },
    { value: '"Courier New", Courier, monospace', label: 'Courier (Mono)' },
    { value: 'Georgia, serif', label: 'Georgia' },
    { value: 'Verdana, sans-serif', label: 'Verdana' },
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
    style="color: {store.activeTool === 'select' ? 'var(--on-primary)' : 'var(--nord4)'};"
    title="Select / Move"
  >
    <MousePointer size={16} />
  </button>

  <!-- Separator -->
  <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

  <!-- Text tool (simple button, no dropdown) -->
  <button
    onclick={() => selectTool('text')}
    class="p-2 rounded transition-colors"
    class:bg-[var(--nord8)]={store.activeTool === 'text'}
    style="color: {store.activeTool === 'text' ? 'var(--on-primary)' : 'var(--nord4)'};"
    title="Text"
  >
    <Type size={16} />
  </button>

  <!-- Image tool -->
  <button
    onclick={() => selectTool('image')}
    class="p-2 rounded transition-colors"
    class:bg-[var(--nord8)]={store.activeTool === 'image'}
    style="color: {store.activeTool === 'image' ? 'var(--on-primary)' : 'var(--nord4)'};"
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
      style="color: {isShapeTool ? 'var(--on-primary)' : 'var(--nord4)'};"
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

  <!-- Edit Granularity Toggle (Line / Word) - Block mode hidden due to OCR grouping issues -->
  <div class="flex items-center rounded overflow-hidden" style="background-color: var(--nord3);">
    <button
      onclick={() => store.setEditGranularity('line')}
      class="px-2 py-1 text-xs font-medium transition-colors"
      style="background-color: {store.editGranularity === 'line' ? 'var(--nord10)' : 'transparent'}; color: {store.editGranularity === 'line' ? 'var(--nord6)' : 'var(--nord4)'};"
      title="Edit individual lines (recommended)"
    >
      Line
    </button>
    <button
      onclick={() => store.setEditGranularity('word')}
      class="px-2 py-1 text-xs font-medium transition-colors"
      style="background-color: {store.editGranularity === 'word' ? 'var(--nord10)' : 'transparent'}; color: {store.editGranularity === 'word' ? 'var(--nord6)' : 'var(--nord4)'};"
      title="Edit individual words"
    >
      Word
    </button>
  </div>

  <!-- Preview toggle - hide edit indicators -->
  {#if onPreviewToggle}
    <button
      onclick={onPreviewToggle}
      class="p-2 rounded transition-colors"
      class:bg-[var(--nord10)]={previewMode}
      style="color: {previewMode ? 'var(--nord6)' : 'var(--nord4)'};"
      title={previewMode ? 'Show edit indicators' : 'Preview (hide edit indicators)'}
    >
      {#if previewMode}
        <EyeOff size={16} />
      {:else}
        <Eye size={16} />
      {/if}
    </button>
  {/if}

  <!-- Separator -->
  <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

  <!-- TEXT FORMATTING CONTROLS (visible, not in dropdown) -->
  <!-- Note: Buttons use onmousedown preventDefault to keep focus on textarea -->
  <!-- Font Family - applies to entire text block -->
  <select
    value={store.activeTextStyle.fontFamily}
    onchange={(e) => setTextStyle({ fontFamily: (e.target as HTMLSelectElement).value })}
    class="px-2 py-1.5 text-xs rounded cursor-pointer"
    style="background-color: var(--nord3); border: none; max-width: 110px;"
    title="Font Family (applies to entire block)"
  >
    {#each fontFamilies as font}
      <option value={font.value}>{font.label}</option>
    {/each}
  </select>

  <!-- Font Size - applies to entire text block -->
  <select
    value={store.activeTextStyle.fontSize}
    onchange={(e) => setTextStyle({ fontSize: parseInt((e.target as HTMLSelectElement).value) })}
    class="px-2 py-1.5 text-xs rounded cursor-pointer"
    style="background-color: var(--nord3); border: none; width: 55px;"
    title="Font Size (applies to entire block)"
  >
    {#each fontSizes as size}
      <option value={size}>{size}pt</option>
    {/each}
  </select>

  <!-- Bold -->
  <button
    onmousedown={(e) => { e.preventDefault(); setTextStyle({ bold: !store.activeTextStyle.bold }); }}
    class="p-2 rounded transition-colors"
    class:bg-[var(--nord8)]={store.activeTextStyle.bold}
    style="color: {store.activeTextStyle.bold ? 'var(--on-primary)' : 'var(--nord4)'};"
    title="Bold"
  >
    <Bold size={16} />
  </button>

  <!-- Italic -->
  <button
    onmousedown={(e) => { e.preventDefault(); setTextStyle({ italic: !store.activeTextStyle.italic }); }}
    class="p-2 rounded transition-colors"
    class:bg-[var(--nord8)]={store.activeTextStyle.italic}
    style="color: {store.activeTextStyle.italic ? 'var(--on-primary)' : 'var(--nord4)'};"
    title="Italic"
  >
    <Italic size={16} />
  </button>

  <!-- Text Color Picker -->
  <div class="relative">
    <button
      onmousedown={(e) => { e.preventDefault(); toggleColorPicker(); }}
      class="p-2 rounded transition-colors flex items-center"
      class:bg-[var(--nord3)]={showColorPicker}
      title="Text Color"
    >
      <div
        class="w-4 h-4 rounded border"
        style="background-color: {store.activeTextStyle.color}; border-color: var(--nord4);"
      ></div>
    </button>
    {#if showColorPicker}
      <div
        class="absolute top-full left-0 mt-1 rounded-lg shadow-lg p-3 z-50"
        style="background-color: var(--nord1); border: 1px solid var(--nord3); min-width: 160px;"
      >
        <div class="grid grid-cols-5 gap-2">
          {#each colors as color}
            <button
              onmousedown={(e) => { e.preventDefault(); setTextStyle({ color }); showColorPicker = false; }}
              class="w-6 h-6 rounded border-2 transition-transform hover:scale-110"
              style="
                background-color: {color};
                border-color: {store.activeTextStyle.color === color ? 'var(--nord6)' : 'transparent'};
              "
            ></button>
          {/each}
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

    <!-- Save in-place (overwrite original) -->
    {#if onApplyInPlace}
      <button
        onclick={onApplyInPlace}
        disabled={store.opCount === 0}
        class="px-3 py-1.5 rounded transition-colors flex items-center gap-1 text-sm font-medium"
        class:opacity-40={store.opCount === 0}
        class:cursor-not-allowed={store.opCount === 0}
        style="background-color: {store.opCount > 0 ? 'var(--nord10)' : 'var(--nord3)'}; color: {store.opCount > 0 ? 'var(--nord6)' : 'var(--nord4)'};"
        title="Save changes to current file"
      >
        <Save size={16} />
      </button>
    {/if}

    <button
      onclick={handleApply}
      disabled={store.opCount === 0}
      class="px-3 py-1.5 rounded transition-colors flex items-center gap-1 text-sm font-medium"
      class:opacity-40={store.opCount === 0}
      class:cursor-not-allowed={store.opCount === 0}
      style="background-color: {store.opCount > 0 ? 'var(--nord14)' : 'var(--nord3)'}; color: {store.opCount > 0 ? 'var(--nord0)' : 'var(--nord4)'};"
      title="Save As... (new file)"
    >
      <Check size={16} />
      <span>Apply</span>
    </button>
  </div>
</div>
