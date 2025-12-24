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
    RotateCcw,
    MoveHorizontal,
    ChevronRight,
    Eye,
    EyeOff,
    Move,
  } from 'lucide-svelte';
  import { ask } from '@tauri-apps/plugin-dialog';
  import {
    type AnnotationsStore,
    type MarkupType,
    type ToolMode,
    type LineStyle,
    type ArrowHeadStyle,
    HIGHLIGHT_COLORS,
  } from '$lib/stores/annotations.svelte';

  interface Props {
    store: AnnotationsStore;
    onClearAll?: () => void;
    showOverlay?: boolean;
    onToggleOverlay?: () => void;
  }

  let { store, onClearAll, showOverlay = true, onToggleOverlay }: Props = $props();

  let showColorPicker = $state(false);
  let showShapesMenu = $state(false);
  let showLineStyleMenu = $state(false);
  let showArrowMenu = $state(false);
  let showFillMenu = $state(false);
  let sequenceInput = $state('');

  // Shape tools for the dropdown
  const shapeTools: { tool: ToolMode; icon: typeof Square; label: string }[] = [
    { tool: 'rectangle', icon: Square, label: 'Rectangle' },
    { tool: 'ellipse', icon: Circle, label: 'Ellipse' },
    { tool: 'line', icon: Minus, label: 'Line' },
    { tool: 'arrow', icon: ArrowRight, label: 'Arrow' },
  ];

  // Check if current tool is a shape
  const isShapeTool = $derived(
    store.activeTool === 'rectangle' ||
    store.activeTool === 'ellipse' ||
    store.activeTool === 'line' ||
    store.activeTool === 'arrow'
  );

  // Get current shape icon
  const currentShapeIcon = $derived(() => {
    const shape = shapeTools.find(s => s.tool === store.activeTool);
    return shape?.icon ?? Square;
  });

  // Markup type options for selection modes
  const markupTypes: { type: MarkupType; icon: typeof Highlighter; label: string }[] = [
    { type: 'highlight', icon: Highlighter, label: 'Highlight' },
    { type: 'underline', icon: Underline, label: 'Underline' },
    { type: 'strikethrough', icon: Strikethrough, label: 'Strikethrough' },
  ];

  // Line style options
  const lineStyles: { style: LineStyle; label: string }[] = [
    { style: 'solid', label: 'Solid' },
    { style: 'dashed', label: 'Dashed' },
    { style: 'dotted', label: 'Dotted' },
  ];

  // Arrow head options
  const arrowHeadStyles: { style: ArrowHeadStyle; label: string }[] = [
    { style: 'none', label: 'None' },
    { style: 'open', label: 'Open' },
    { style: 'closed', label: 'Filled' },
  ];

  function selectTool(tool: ToolMode) {
    store.setActiveTool(tool);
    showColorPicker = false;
    showLineStyleMenu = false;
    showArrowMenu = false;
    showFillMenu = false;
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
    showShapesMenu = false;
    showLineStyleMenu = false;
    showArrowMenu = false;
    showFillMenu = false;
  }

  function toggleShapesMenu() {
    showShapesMenu = !showShapesMenu;
    showColorPicker = false;
    showLineStyleMenu = false;
    showArrowMenu = false;
    showFillMenu = false;
  }

  function selectShapeTool(tool: ToolMode) {
    store.setActiveTool(tool);
    showShapesMenu = false;
    showColorPicker = false;
    showLineStyleMenu = false;
    showArrowMenu = false;
    showFillMenu = false;
  }

  function toggleLineStyleMenu() {
    showLineStyleMenu = !showLineStyleMenu;
    showColorPicker = false;
    showShapesMenu = false;
    showArrowMenu = false;
    showFillMenu = false;
  }

  function toggleArrowMenu() {
    showArrowMenu = !showArrowMenu;
    showColorPicker = false;
    showShapesMenu = false;
    showLineStyleMenu = false;
    showFillMenu = false;
  }

  function toggleFillMenu() {
    showFillMenu = !showFillMenu;
    showColorPicker = false;
    showShapesMenu = false;
    showLineStyleMenu = false;
    showArrowMenu = false;
  }

  function selectLineStyle(style: LineStyle) {
    store.setActiveLineStyle(style);
    showLineStyleMenu = false;
  }

  function selectStartArrow(style: ArrowHeadStyle) {
    store.setActiveStartArrow(style);
  }

  function selectEndArrow(style: ArrowHeadStyle) {
    store.setActiveEndArrow(style);
  }

  function handleOpacityChange(e: Event) {
    const value = parseFloat((e.target as HTMLInputElement).value);
    store.setActiveOpacity(value);
  }

  function handleSequenceInputChange(e: Event) {
    const value = parseInt((e.target as HTMLInputElement).value);
    if (!isNaN(value) && value >= 1) {
      store.setSequenceCounter(value);
    }
  }

  function handleResetSequence() {
    store.resetSequenceCounter();
  }

  async function handleClearAll() {
    const confirmed = await ask('Clear all annotations? This cannot be undone.', {
      title: 'Clear Annotations',
      kind: 'warning',
    });
    if (confirmed) {
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
  <!-- Toggle annotations visibility -->
  {#if onToggleOverlay}
    <button
      onclick={onToggleOverlay}
      class="p-2 rounded transition-colors hover:bg-[var(--nord3)]"
      title={showOverlay ? "Hide annotations" : "Show annotations"}
    >
      {#if showOverlay}
        <Eye size={16} />
      {:else}
        <EyeOff size={16} class="opacity-50" />
      {/if}
    </button>

    <!-- Separator -->
    <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>
  {/if}

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

  <!-- Move tool (for dragging annotations) -->
  <button
    onclick={() => selectTool('move')}
    class="p-2 rounded transition-colors"
    class:bg-[var(--nord8)]={store.activeTool === 'move'}
    style="color: {store.activeTool === 'move' ? 'var(--nord0)' : 'var(--nord4)'};"
    title="Move annotations"
  >
    <Move size={16} />
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
      <!-- Dashed rectangle icon -->
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2" stroke-dasharray="4 2" />
      </svg>
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

    <!-- Shapes dropdown -->
    <div class="relative">
      <button
        onclick={toggleShapesMenu}
        class="p-2 rounded transition-colors flex items-center gap-0.5"
        class:bg-[var(--nord8)]={isShapeTool}
        style="color: {isShapeTool ? 'var(--nord0)' : 'var(--nord4)'};"
        title="Shapes"
      >
        {@const CurrentIcon = currentShapeIcon()}
        <CurrentIcon size={16} />
        <ChevronRight size={12} class="rotate-90 opacity-60" />
      </button>

      {#if showShapesMenu}
        <div
          class="absolute top-full left-1/2 mt-1 rounded-lg shadow-lg py-1 z-50"
          style="background-color: var(--nord1); border: 1px solid var(--nord3); transform: translateX(-50%); min-width: 120px;"
        >
          {#each shapeTools as shape}
            <button
              onclick={() => selectShapeTool(shape.tool)}
              class="w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-[var(--nord2)] transition-colors"
              class:bg-[var(--nord3)]={store.activeTool === shape.tool}
            >
              <shape.icon size={14} />
              <span>{shape.label}</span>
            </button>
          {/each}
        </div>
      {/if}
    </div>

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
        <!-- Color grid -->
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

        <!-- Opacity slider -->
        <div class="mt-3 pt-3" style="border-top: 1px solid var(--nord3);">
          <div class="text-xs mb-2 flex justify-between" style="color: var(--nord4);">
            <span>Opacity</span>
            <span>{Math.round(store.activeOpacity * 100)}%</span>
          </div>
          <input
            type="range"
            min="0.1"
            max="1"
            step="0.1"
            value={store.activeOpacity}
            oninput={handleOpacityChange}
            class="w-full"
          />
        </div>
      </div>
    {/if}
  </div>

  <!-- Separator -->
  <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

  <!-- Sequence number controls (only when tool is active) -->
  {#if store.activeTool === 'sequenceNumber'}
    <div class="flex items-center gap-1 px-1 py-0.5 rounded" style="background-color: var(--nord3);">
      <span class="text-xs px-1" style="color: var(--nord4);">Next:</span>
      <input
        type="number"
        min="1"
        value={store.sequenceCounter}
        oninput={handleSequenceInputChange}
        class="w-12 px-1 py-0.5 text-xs rounded text-center"
        style="background-color: var(--nord2); color: var(--nord6); border: 1px solid var(--nord3);"
      />
      <button
        onclick={handleResetSequence}
        class="p-1 rounded transition-colors hover:bg-[var(--nord2)]"
        title="Reset to 1"
        style="color: var(--nord4);"
      >
        <RotateCcw size={12} />
      </button>
    </div>

    <!-- Separator -->
    <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>
  {/if}

  <!-- Line style controls (for line, arrow, rectangle, ellipse) -->
  {#if store.activeTool === 'line' || store.activeTool === 'arrow' || store.activeTool === 'rectangle' || store.activeTool === 'ellipse'}
    <div class="relative">
      <button
        onclick={toggleLineStyleMenu}
        class="p-2 rounded transition-colors hover:bg-[var(--nord3)] flex items-center gap-1"
        title="Line style: {store.activeLineStyle}"
      >
        <!-- Visual representation of line style -->
        <svg width="16" height="8" viewBox="0 0 16 8" class="opacity-80">
          {#if store.activeLineStyle === 'solid'}
            <line x1="0" y1="4" x2="16" y2="4" stroke="currentColor" stroke-width="2" />
          {:else if store.activeLineStyle === 'dashed'}
            <line x1="0" y1="4" x2="16" y2="4" stroke="currentColor" stroke-width="2" stroke-dasharray="4 2" />
          {:else}
            <line x1="0" y1="4" x2="16" y2="4" stroke="currentColor" stroke-width="2" stroke-dasharray="1 2" />
          {/if}
        </svg>
      </button>

      {#if showLineStyleMenu}
        <div
          class="absolute top-full left-1/2 mt-1 rounded-lg shadow-lg py-1 z-50"
          style="background-color: var(--nord1); border: 1px solid var(--nord3); transform: translateX(-50%); min-width: 100px;"
        >
          {#each lineStyles as lineStyle}
            <button
              onclick={() => selectLineStyle(lineStyle.style)}
              class="w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-[var(--nord2)] transition-colors"
              class:bg-[var(--nord3)]={store.activeLineStyle === lineStyle.style}
            >
              <svg width="24" height="8" viewBox="0 0 24 8">
                {#if lineStyle.style === 'solid'}
                  <line x1="0" y1="4" x2="24" y2="4" stroke="currentColor" stroke-width="2" />
                {:else if lineStyle.style === 'dashed'}
                  <line x1="0" y1="4" x2="24" y2="4" stroke="currentColor" stroke-width="2" stroke-dasharray="4 2" />
                {:else}
                  <line x1="0" y1="4" x2="24" y2="4" stroke="currentColor" stroke-width="2" stroke-dasharray="1 2" />
                {/if}
              </svg>
              <span>{lineStyle.label}</span>
            </button>
          {/each}
        </div>
      {/if}
    </div>

    <!-- Separator -->
    <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>
  {/if}

  <!-- Arrow head controls (only for arrow tool) -->
  {#if store.activeTool === 'arrow'}
    <div class="relative">
      <button
        onclick={toggleArrowMenu}
        class="p-2 rounded transition-colors hover:bg-[var(--nord3)] flex items-center gap-1"
        title="Arrow heads"
      >
        <svg width="20" height="12" viewBox="0 0 20 12" class="opacity-80">
          <!-- Start arrow indicator -->
          {#if store.activeStartArrow !== 'none'}
            <polygon points="0,6 4,3 4,9" fill="currentColor" />
          {/if}
          <line x1="4" y1="6" x2="16" y2="6" stroke="currentColor" stroke-width="2" />
          <!-- End arrow indicator -->
          {#if store.activeEndArrow !== 'none'}
            <polygon points="20,6 16,3 16,9" fill="currentColor" />
          {/if}
        </svg>
      </button>

      {#if showArrowMenu}
        <div
          class="absolute top-full left-1/2 mt-1 rounded-lg shadow-lg p-2 z-50"
          style="background-color: var(--nord1); border: 1px solid var(--nord3); transform: translateX(-50%); min-width: 140px;"
        >
          <!-- Start arrow -->
          <div class="mb-2">
            <div class="text-[10px] uppercase opacity-50 mb-1 px-1">Start</div>
            <div class="flex gap-1">
              {#each arrowHeadStyles as arrowStyle}
                <button
                  onclick={() => selectStartArrow(arrowStyle.style)}
                  class="p-1.5 rounded text-[10px] transition-colors"
                  class:bg-[var(--nord8)]={store.activeStartArrow === arrowStyle.style}
                  class:text-[var(--nord0)]={store.activeStartArrow === arrowStyle.style}
                  title={arrowStyle.label}
                  style="background-color: {store.activeStartArrow === arrowStyle.style ? '' : 'var(--nord3)'};"
                >
                  {arrowStyle.label}
                </button>
              {/each}
            </div>
          </div>

          <!-- End arrow -->
          <div>
            <div class="text-[10px] uppercase opacity-50 mb-1 px-1">End</div>
            <div class="flex gap-1">
              {#each arrowHeadStyles as arrowStyle}
                <button
                  onclick={() => selectEndArrow(arrowStyle.style)}
                  class="p-1.5 rounded text-[10px] transition-colors"
                  class:bg-[var(--nord8)]={store.activeEndArrow === arrowStyle.style}
                  class:text-[var(--nord0)]={store.activeEndArrow === arrowStyle.style}
                  title={arrowStyle.label}
                  style="background-color: {store.activeEndArrow === arrowStyle.style ? '' : 'var(--nord3)'};"
                >
                  {arrowStyle.label}
                </button>
              {/each}
            </div>
          </div>
        </div>
      {/if}
    </div>

    <!-- Separator -->
    <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>
  {/if}

  <!-- Fill controls (for rectangle and ellipse) -->
  {#if store.activeTool === 'rectangle' || store.activeTool === 'ellipse'}
    <div class="relative">
      <button
        onclick={toggleFillMenu}
        class="p-2 rounded transition-colors hover:bg-[var(--nord3)] flex items-center gap-1"
        title="Fill settings"
      >
        <!-- Fill indicator -->
        <svg width="16" height="16" viewBox="0 0 16 16" class="opacity-80">
          <rect
            x="2" y="2" width="12" height="12"
            rx="2"
            fill={store.activeFillEnabled ? store.activeFillColor : 'none'}
            fill-opacity={store.activeFillEnabled ? store.activeFillOpacity : 0}
            stroke="currentColor"
            stroke-width="1.5"
          />
          {#if !store.activeFillEnabled}
            <line x1="3" y1="13" x2="13" y2="3" stroke="currentColor" stroke-width="1" />
          {/if}
        </svg>
      </button>

      {#if showFillMenu}
        <div
          class="absolute top-full left-1/2 mt-1 rounded-lg shadow-lg p-3 z-50"
          style="background-color: var(--nord1); border: 1px solid var(--nord3); transform: translateX(-50%); min-width: 180px;"
        >
          <!-- Fill toggle -->
          <div class="flex items-center gap-2 mb-3">
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={store.activeFillEnabled}
                onchange={(e) => store.setActiveFillEnabled((e.target as HTMLInputElement).checked)}
                class="w-4 h-4 rounded"
              />
              <span class="text-xs" style="color: var(--nord4);">Enable fill</span>
            </label>
          </div>

          {#if store.activeFillEnabled}
            <!-- Fill color -->
            <div class="mb-3">
              <div class="text-[10px] uppercase opacity-50 mb-1">Fill Color</div>
              <div class="grid grid-cols-4 gap-1">
                {#each HIGHLIGHT_COLORS as color}
                  <button
                    onclick={() => store.setActiveFillColor(color.value)}
                    class="w-6 h-6 rounded border transition-transform hover:scale-110"
                    style="
                      background-color: {color.value};
                      border-color: {store.activeFillColor === color.value ? 'var(--nord6)' : (color.value === '#FFFFFF' ? 'var(--nord3)' : 'transparent')};
                    "
                    title={color.name}
                  ></button>
                {/each}
              </div>
            </div>

            <!-- Fill opacity -->
            <div>
              <div class="text-[10px] uppercase opacity-50 mb-1">Fill Opacity: {Math.round(store.activeFillOpacity * 100)}%</div>
              <input
                type="range"
                min="0.1"
                max="1"
                step="0.1"
                value={store.activeFillOpacity}
                oninput={(e) => store.setActiveFillOpacity(parseFloat((e.target as HTMLInputElement).value))}
                class="w-full"
              />
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Separator -->
    <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>
  {/if}

  <!-- Clear all -->
  <button
    onclick={handleClearAll}
    class="p-2 rounded transition-colors hover:bg-[var(--nord11)] hover:text-white"
    title="Clear all annotations"
  >
    <Trash2 size={16} />
  </button>
</div>
