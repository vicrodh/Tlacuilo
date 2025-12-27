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
    Palette,
    Bold,
    Italic,
    AlignLeft,
    AlignCenter,
    AlignRight,
    Save,
    Eye,
    EyeOff,
    Home,
    PencilLine,
    Shapes,
    LetterText,
  } from 'lucide-svelte';
  import { ask } from '@tauri-apps/plugin-dialog';
  import type { EditsStore, EditTool, TextStyle, EditGranularity } from '$lib/stores/edits.svelte';

  interface Props {
    store: EditsStore;
    onApply?: () => void;
    onApplyInPlace?: () => void;
    onDiscard?: () => void;
    previewMode?: boolean;
    onPreviewToggle?: () => void;
  }

  let { store, onApply, onApplyInPlace, onDiscard, previewMode = false, onPreviewToggle }: Props = $props();

  // Ribbon tab state
  type RibbonTab = 'home' | 'format' | 'insert';
  let activeTab = $state<RibbonTab>('home');

  let showColorPicker = $state(false);
  let showShapeColorPicker = $state(false);

  // Font options
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

  // Colors for picker (Nord palette)
  const colors = [
    '#000000', '#FFFFFF', '#BF616A', '#D08770', '#EBCB8B',
    '#A3BE8C', '#88C0D0', '#5E81AC', '#B48EAD', '#4C566A',
  ];

  function selectTool(tool: EditTool) {
    store.setActiveTool(tool);
    showColorPicker = false;
    showShapeColorPicker = false;
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

<div class="ribbon-container" style="background-color: var(--nord1);">
  <!-- Tab Bar -->
  <div class="tab-bar" style="background-color: var(--nord2); border-bottom: 1px solid var(--nord3);">
    <button
      onclick={() => activeTab = 'home'}
      class="tab-button"
      class:active={activeTab === 'home'}
    >
      <Home size={14} />
      <span>Home</span>
    </button>
    <button
      onclick={() => activeTab = 'format'}
      class="tab-button"
      class:active={activeTab === 'format'}
    >
      <LetterText size={14} />
      <span>Format</span>
    </button>
    <button
      onclick={() => activeTab = 'insert'}
      class="tab-button"
      class:active={activeTab === 'insert'}
    >
      <Shapes size={14} />
      <span>Insert</span>
    </button>

    <!-- Right side: Actions (always visible) -->
    <div class="tab-actions">
      {#if store.opCount > 0}
        <span class="edit-badge">
          {store.opCount} edit{store.opCount !== 1 ? 's' : ''}
        </span>
      {/if}

      <button
        onclick={handleDiscard}
        disabled={!store.isDirty && store.opCount === 0}
        class="action-btn discard"
        class:disabled={!store.isDirty && store.opCount === 0}
        title="Discard changes"
      >
        <X size={16} />
      </button>

      {#if onApplyInPlace}
        <button
          onclick={onApplyInPlace}
          disabled={store.opCount === 0}
          class="action-btn save"
          class:disabled={store.opCount === 0}
          title="Save to current file"
        >
          <Save size={16} />
          <span>Save</span>
        </button>
      {/if}

      <button
        onclick={handleApply}
        disabled={store.opCount === 0}
        class="action-btn apply"
        class:disabled={store.opCount === 0}
        title="Save As... (new file)"
      >
        <Check size={16} />
        <span>Apply</span>
      </button>
    </div>
  </div>

  <!-- Ribbon Content -->
  <div class="ribbon-content">
    <!-- HOME TAB -->
    {#if activeTab === 'home'}
      <!-- Selection Group -->
      <div class="ribbon-group">
        <div class="group-tools">
          <button
            onclick={() => selectTool('select')}
            class="tool-btn large"
            class:active={store.activeTool === 'select'}
            title="Select / Move"
          >
            <MousePointer size={20} />
            <span>Select</span>
          </button>
        </div>
        <div class="group-label">Selection</div>
      </div>

      <div class="ribbon-separator"></div>

      <!-- Edit Mode Group -->
      <div class="ribbon-group">
        <div class="group-tools">
          <div class="granularity-toggle">
            <button
              onclick={() => store.setEditGranularity('block')}
              class="granularity-btn"
              class:active={store.editGranularity === 'block'}
              title="Edit entire text blocks (paragraphs)"
            >
              Block
            </button>
            <button
              onclick={() => store.setEditGranularity('line')}
              class="granularity-btn"
              class:active={store.editGranularity === 'line'}
              title="Edit individual lines (recommended)"
            >
              Line
            </button>
            <button
              onclick={() => store.setEditGranularity('word')}
              class="granularity-btn"
              class:active={store.editGranularity === 'word'}
              title="Edit individual words"
            >
              Word
            </button>
          </div>
        </div>
        <div class="group-label">Edit Mode</div>
      </div>

      <div class="ribbon-separator"></div>

      <!-- Preview Group -->
      {#if onPreviewToggle}
        <div class="ribbon-group">
          <div class="group-tools">
            <button
              onclick={onPreviewToggle}
              class="tool-btn"
              class:active={previewMode}
              title={previewMode ? 'Show edit indicators' : 'Preview mode'}
            >
              {#if previewMode}
                <EyeOff size={18} />
              {:else}
                <Eye size={18} />
              {/if}
              <span>Preview</span>
            </button>
          </div>
          <div class="group-label">View</div>
        </div>

        <div class="ribbon-separator"></div>
      {/if}

      <!-- Actions Group -->
      <div class="ribbon-group">
        <div class="group-tools horizontal">
          <button
            onclick={() => store.undo()}
            disabled={!store.canUndo()}
            class="tool-btn small"
            class:disabled={!store.canUndo()}
            title="Undo (Ctrl+Z)"
          >
            <Undo2 size={16} />
          </button>
          <button
            onclick={() => store.redo()}
            disabled={!store.canRedo()}
            class="tool-btn small"
            class:disabled={!store.canRedo()}
            title="Redo (Ctrl+Y)"
          >
            <Redo2 size={16} />
          </button>
          <button
            onclick={deleteSelected}
            disabled={!store.selectedId}
            class="tool-btn small delete"
            class:disabled={!store.selectedId}
            title="Delete selected"
          >
            <Trash2 size={16} />
          </button>
        </div>
        <div class="group-label">Actions</div>
      </div>
    {/if}

    <!-- FORMAT TAB -->
    {#if activeTab === 'format'}
      <!-- Font Group -->
      <div class="ribbon-group wide">
        <div class="group-tools">
          <div class="font-controls">
            <select
              value={store.activeTextStyle.fontFamily}
              onchange={(e) => setTextStyle({ fontFamily: (e.target as HTMLSelectElement).value })}
              class="font-select"
              title="Font Family"
            >
              {#each fontFamilies as font}
                <option value={font.value}>{font.label}</option>
              {/each}
            </select>
            <select
              value={store.activeTextStyle.fontSize}
              onchange={(e) => setTextStyle({ fontSize: parseInt((e.target as HTMLSelectElement).value) })}
              class="size-select"
              title="Font Size"
            >
              {#each fontSizes as size}
                <option value={size}>{size}pt</option>
              {/each}
            </select>
          </div>
        </div>
        <div class="group-label">Font</div>
      </div>

      <div class="ribbon-separator"></div>

      <!-- Style Group -->
      <div class="ribbon-group">
        <div class="group-tools horizontal">
          <button
            onmousedown={(e) => { e.preventDefault(); setTextStyle({ bold: !store.activeTextStyle.bold }); }}
            class="tool-btn small"
            class:active={store.activeTextStyle.bold}
            title="Bold"
          >
            <Bold size={16} />
          </button>
          <button
            onmousedown={(e) => { e.preventDefault(); setTextStyle({ italic: !store.activeTextStyle.italic }); }}
            class="tool-btn small"
            class:active={store.activeTextStyle.italic}
            title="Italic"
          >
            <Italic size={16} />
          </button>
        </div>
        <div class="group-label">Style</div>
      </div>

      <div class="ribbon-separator"></div>

      <!-- Color Group -->
      <div class="ribbon-group">
        <div class="group-tools">
          <div class="relative">
            <button
              onmousedown={(e) => { e.preventDefault(); showColorPicker = !showColorPicker; }}
              class="tool-btn color-btn"
              class:active={showColorPicker}
              title="Text Color"
            >
              <Palette size={18} />
              <div
                class="color-indicator"
                style="background-color: {store.activeTextStyle.color};"
              ></div>
            </button>
            {#if showColorPicker}
              <div class="color-picker">
                <div class="color-grid">
                  {#each colors as color}
                    <button
                      onmousedown={(e) => { e.preventDefault(); setTextStyle({ color }); showColorPicker = false; }}
                      class="color-swatch"
                      class:selected={store.activeTextStyle.color === color}
                      style="background-color: {color};"
                    ></button>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        </div>
        <div class="group-label">Color</div>
      </div>

      <div class="ribbon-separator"></div>

      <!-- Alignment Group -->
      <div class="ribbon-group">
        <div class="group-tools horizontal">
          <button
            onmousedown={(e) => { e.preventDefault(); setTextStyle({ align: 'left' }); }}
            class="tool-btn small"
            class:active={store.activeTextStyle.align === 'left'}
            title="Align Left"
          >
            <AlignLeft size={16} />
          </button>
          <button
            onmousedown={(e) => { e.preventDefault(); setTextStyle({ align: 'center' }); }}
            class="tool-btn small"
            class:active={store.activeTextStyle.align === 'center'}
            title="Align Center"
          >
            <AlignCenter size={16} />
          </button>
          <button
            onmousedown={(e) => { e.preventDefault(); setTextStyle({ align: 'right' }); }}
            class="tool-btn small"
            class:active={store.activeTextStyle.align === 'right'}
            title="Align Right"
          >
            <AlignRight size={16} />
          </button>
        </div>
        <div class="group-label">Alignment</div>
      </div>
    {/if}

    <!-- INSERT TAB -->
    {#if activeTab === 'insert'}
      <!-- Text Group -->
      <div class="ribbon-group">
        <div class="group-tools">
          <button
            onclick={() => selectTool('text')}
            class="tool-btn large"
            class:active={store.activeTool === 'text'}
            title="Add Text"
          >
            <Type size={20} />
            <span>Text</span>
          </button>
        </div>
        <div class="group-label">Text</div>
      </div>

      <div class="ribbon-separator"></div>

      <!-- Image Group -->
      <div class="ribbon-group">
        <div class="group-tools">
          <button
            onclick={() => selectTool('image')}
            class="tool-btn large"
            class:active={store.activeTool === 'image'}
            title="Insert Image"
          >
            <Image size={20} />
            <span>Image</span>
          </button>
        </div>
        <div class="group-label">Media</div>
      </div>

      <div class="ribbon-separator"></div>

      <!-- Shapes Group -->
      <div class="ribbon-group">
        <div class="group-tools">
          <div class="shape-buttons">
            {#each shapeTools as shape}
              <button
                onclick={() => selectTool(shape.tool)}
                class="tool-btn"
                class:active={store.activeTool === shape.tool}
                title={shape.label}
              >
                <shape.icon size={18} />
                <span>{shape.label}</span>
              </button>
            {/each}
          </div>
        </div>
        <div class="group-label">Shapes</div>
      </div>

      <div class="ribbon-separator"></div>

      <!-- Shape Style Group -->
      {#if isShapeTool}
        <div class="ribbon-group">
          <div class="group-tools">
            <div class="shape-style-controls">
              <div class="style-row">
                <span class="style-label">Stroke:</span>
                <div class="mini-color-picker">
                  {#each colors.slice(0, 5) as color}
                    <button
                      onclick={() => store.setStrokeColor(color)}
                      class="mini-swatch"
                      class:selected={store.activeStrokeColor === color}
                      style="background-color: {color};"
                    ></button>
                  {/each}
                </div>
              </div>
              <div class="style-row">
                <label class="fill-toggle">
                  <input
                    type="checkbox"
                    checked={store.activeFillEnabled}
                    onchange={(e) => store.setFillEnabled((e.target as HTMLInputElement).checked)}
                  />
                  <span>Fill</span>
                </label>
                {#if store.activeFillEnabled}
                  <div class="mini-color-picker">
                    {#each colors.slice(0, 5) as color}
                      <button
                        onclick={() => store.setFillColor(color)}
                        class="mini-swatch"
                        class:selected={store.activeFillColor === color}
                        style="background-color: {color};"
                      ></button>
                    {/each}
                  </div>
                {/if}
              </div>
            </div>
          </div>
          <div class="group-label">Shape Style</div>
        </div>
      {/if}
    {/if}
  </div>
</div>

<style>
  .ribbon-container {
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  }

  /* Tab Bar */
  .tab-bar {
    display: flex;
    align-items: center;
    padding: 0 4px;
    gap: 2px;
  }

  .tab-button {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
    color: var(--nord4);
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .tab-button:hover {
    color: var(--nord6);
    background: var(--nord3);
  }

  .tab-button.active {
    color: var(--nord8);
    border-bottom-color: var(--nord8);
    background: var(--nord1);
  }

  .tab-actions {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px;
  }

  .edit-badge {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    background: var(--nord3);
    color: var(--nord4);
  }

  .action-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 500;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .action-btn.discard {
    background: transparent;
    color: var(--nord4);
  }

  .action-btn.discard:hover:not(.disabled) {
    background: var(--nord11);
    color: white;
  }

  .action-btn.save {
    background: var(--nord10);
    color: var(--nord6);
  }

  .action-btn.save:hover:not(.disabled) {
    background: var(--nord9);
  }

  .action-btn.apply {
    background: var(--nord14);
    color: var(--nord0);
  }

  .action-btn.apply:hover:not(.disabled) {
    background: var(--nord7);
  }

  .action-btn.disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* Ribbon Content */
  .ribbon-content {
    display: flex;
    align-items: flex-start;
    padding: 8px 12px;
    gap: 4px;
    min-height: 70px;
  }

  .ribbon-group {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 4px 8px;
  }

  .ribbon-group.wide {
    min-width: 140px;
  }

  .group-tools {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    flex: 1;
  }

  .group-tools.horizontal {
    flex-direction: row;
  }

  .group-label {
    font-size: 10px;
    color: var(--nord4);
    opacity: 0.7;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
    white-space: nowrap;
  }

  .ribbon-separator {
    width: 1px;
    height: 60px;
    background: var(--nord3);
    margin: 0 4px;
    align-self: center;
  }

  /* Tool Buttons */
  .tool-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    padding: 6px 10px;
    font-size: 10px;
    color: var(--nord4);
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .tool-btn:hover:not(.disabled) {
    background: var(--nord3);
    color: var(--nord6);
  }

  .tool-btn.active {
    background: var(--nord8);
    color: var(--nord0);
    border-color: var(--nord8);
  }

  .tool-btn.large {
    min-width: 50px;
    min-height: 46px;
  }

  .tool-btn.small {
    padding: 6px;
    min-width: 32px;
  }

  .tool-btn.delete:hover:not(.disabled) {
    background: var(--nord11);
    color: white;
  }

  .tool-btn.disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* Granularity Toggle */
  .granularity-toggle {
    display: flex;
    border-radius: 4px;
    overflow: hidden;
    background: var(--nord3);
  }

  .granularity-btn {
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 500;
    color: var(--nord4);
    background: transparent;
    border: none;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .granularity-btn:hover {
    background: var(--nord2);
  }

  .granularity-btn.active {
    background: var(--nord10);
    color: var(--nord6);
  }

  /* Font Controls */
  .font-controls {
    display: flex;
    gap: 4px;
  }

  .font-select {
    padding: 4px 8px;
    font-size: 11px;
    background: var(--nord3);
    color: var(--nord4);
    border: none;
    border-radius: 4px;
    cursor: pointer;
    max-width: 100px;
  }

  .size-select {
    padding: 4px 8px;
    font-size: 11px;
    background: var(--nord3);
    color: var(--nord4);
    border: none;
    border-radius: 4px;
    cursor: pointer;
    width: 55px;
  }

  /* Color Picker */
  .color-btn {
    position: relative;
  }

  .color-indicator {
    position: absolute;
    bottom: 4px;
    left: 50%;
    transform: translateX(-50%);
    width: 16px;
    height: 3px;
    border-radius: 1px;
    border: 1px solid var(--nord4);
  }

  .color-picker {
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translateX(-50%);
    margin-top: 4px;
    padding: 8px;
    background: var(--nord1);
    border: 1px solid var(--nord3);
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    z-index: 100;
  }

  .color-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 4px;
  }

  .color-swatch {
    width: 24px;
    height: 24px;
    border-radius: 4px;
    border: 2px solid transparent;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .color-swatch:hover {
    transform: scale(1.1);
  }

  .color-swatch.selected {
    border-color: var(--nord6);
  }

  /* Shape Buttons */
  .shape-buttons {
    display: flex;
    gap: 4px;
  }

  /* Shape Style Controls */
  .shape-style-controls {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 10px;
  }

  .style-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .style-label {
    color: var(--nord4);
    min-width: 40px;
  }

  .fill-toggle {
    display: flex;
    align-items: center;
    gap: 4px;
    color: var(--nord4);
    cursor: pointer;
    min-width: 40px;
  }

  .fill-toggle input {
    width: 12px;
    height: 12px;
  }

  .mini-color-picker {
    display: flex;
    gap: 2px;
  }

  .mini-swatch {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 2px solid transparent;
    cursor: pointer;
    transition: all 0.1s ease;
  }

  .mini-swatch:hover {
    transform: scale(1.15);
  }

  .mini-swatch.selected {
    border-color: var(--nord6);
  }

  .relative {
    position: relative;
  }
</style>
