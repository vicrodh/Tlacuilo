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
    Stamp,
  } from 'lucide-svelte';
  import { ask, open } from '@tauri-apps/plugin-dialog';
  import { readFile } from '@tauri-apps/plugin-fs';
  import {
    type AnnotationsStore,
    type MarkupType,
    type ToolMode,
    type LineStyle,
    type ArrowHeadStyle,
    type StampType,
    HIGHLIGHT_COLORS,
    STAMP_PRESETS,
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
  let showSequenceMenu = $state(false);
  let showStampsMenu = $state(false);
  let sequenceInput = $state('');
  let customStampInput = $state('');

  // Nested shape options
  let hoveredShapeTool = $state<ToolMode | null>(null);
  let showShapeOptions = $state(false);
  let shapeHoverTimeout: ReturnType<typeof setTimeout> | null = null;

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
    showShapesMenu = false;
    showSequenceMenu = false;
    showStampsMenu = false;
    hoveredShapeTool = null;
    showShapeOptions = false;
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
    showSequenceMenu = false;
    showStampsMenu = false;
  }

  function toggleShapesMenu() {
    showShapesMenu = !showShapesMenu;
    showColorPicker = false;
    showSequenceMenu = false;
    showStampsMenu = false;
    hoveredShapeTool = null;
    showShapeOptions = false;
  }

  function toggleSequenceMenu() {
    showSequenceMenu = !showSequenceMenu;
    showColorPicker = false;
    showShapesMenu = false;
    showStampsMenu = false;
  }

  function toggleStampsMenu() {
    showStampsMenu = !showStampsMenu;
    showColorPicker = false;
    showShapesMenu = false;
    showSequenceMenu = false;
  }

  function selectStampType(stampType: StampType) {
    store.setActiveStampType(stampType);
    store.setActiveTool('stamp');
    showStampsMenu = false;
  }

  async function loadStampImage() {
    const file = await open({
      multiple: false,
      filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'webp'] }],
      title: 'Select stamp image',
    });

    if (file) {
      try {
        const data = await readFile(file);
        const base64 = btoa(String.fromCharCode(...data));
        const ext = file.split('.').pop()?.toLowerCase() || 'png';
        const mimeType = ext === 'jpg' || ext === 'jpeg' ? 'image/jpeg' : ext === 'webp' ? 'image/webp' : 'image/png';
        store.setStampImageData(`data:${mimeType};base64,${base64}`);
        store.setActiveStampType('Image');
        store.setActiveTool('stamp');
        showStampsMenu = false;
      } catch (e) {
        console.error('Failed to load stamp image:', e);
      }
    }
  }

  const rotationOptions = [
    { value: 0, label: '0°' },
    { value: -45, label: '-45°' },
    { value: 45, label: '45°' },
    { value: 90, label: '90°' },
    { value: -90, label: '-90°' },
  ];

  function selectShapeTool(tool: ToolMode) {
    store.setActiveTool(tool);
    showShapesMenu = false;
    hoveredShapeTool = null;
    showShapeOptions = false;
  }

  function handleShapeHover(tool: ToolMode | null) {
    // Clear any pending timeout
    if (shapeHoverTimeout) {
      clearTimeout(shapeHoverTimeout);
      shapeHoverTimeout = null;
    }

    if (tool) {
      // Immediately show submenu for new tool
      hoveredShapeTool = tool;
      showShapeOptions = true;
    } else {
      // Delay hiding to allow mouse to move to submenu
      shapeHoverTimeout = setTimeout(() => {
        hoveredShapeTool = null;
        showShapeOptions = false;
      }, 150);
    }
  }

  function keepShapeOptionsOpen() {
    // Clear timeout when mouse enters submenu
    if (shapeHoverTimeout) {
      clearTimeout(shapeHoverTimeout);
      shapeHoverTimeout = null;
    }
  }

  function selectLineStyle(style: LineStyle) {
    store.setActiveLineStyle(style);
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

  <!-- Stamp tool with dropdown -->
  <div class="relative">
    <button
      onclick={toggleStampsMenu}
      class="p-2 rounded transition-colors flex items-center gap-0.5"
      class:bg-[var(--nord8)]={store.activeTool === 'stamp'}
      style="color: {store.activeTool === 'stamp' ? 'var(--nord0)' : 'var(--nord4)'};"
      title="Stamp"
    >
      <Stamp size={16} />
      <ChevronRight size={12} class="rotate-90 opacity-60" />
    </button>

    {#if showStampsMenu}
      <div
        class="absolute top-full left-0 mt-1 rounded-lg shadow-lg py-1 z-50"
        style="background-color: var(--nord1); border: 1px solid var(--nord3); min-width: 160px;"
      >
        {#each STAMP_PRESETS as stamp}
          <button
            onclick={() => selectStampType(stamp.type)}
            class="w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-[var(--nord2)] transition-colors"
            class:bg-[var(--nord3)]={store.activeStampType === stamp.type && store.activeTool === 'stamp'}
          >
            <span
              class="px-2 py-0.5 rounded text-[10px] font-bold"
              style="background-color: {stamp.bgColor}; color: {stamp.color};"
            >
              {stamp.label}
            </span>
          </button>
        {/each}

        <!-- Custom text stamp -->
        <div class="px-3 py-2 mt-1" style="border-top: 1px solid var(--nord3);">
          <div class="text-[10px] uppercase opacity-40 mb-1">Custom Text</div>
          <div class="flex gap-1">
            <input
              type="text"
              bind:value={customStampInput}
              placeholder="Custom text..."
              class="flex-1 px-2 py-1 text-xs rounded"
              style="background-color: var(--nord2); color: var(--nord6); border: 1px solid var(--nord3);"
              onkeydown={(e) => {
                if (e.key === 'Enter' && customStampInput.trim()) {
                  store.setCustomStampText(customStampInput.trim());
                  selectStampType('Custom');
                }
              }}
            />
            <button
              onclick={() => {
                if (customStampInput.trim()) {
                  store.setCustomStampText(customStampInput.trim());
                  selectStampType('Custom');
                }
              }}
              class="px-2 py-1 rounded text-xs"
              style="background-color: var(--nord10); color: var(--nord6);"
              disabled={!customStampInput.trim()}
            >
              Add
            </button>
          </div>
        </div>

        <!-- Image stamp -->
        <div class="px-3 py-2" style="border-top: 1px solid var(--nord3);">
          <div class="text-[10px] uppercase opacity-40 mb-1">Image Stamp</div>
          <button
            onclick={loadStampImage}
            class="w-full flex items-center justify-center gap-2 px-2 py-1.5 rounded text-xs hover:bg-[var(--nord2)] transition-colors"
            style="background-color: var(--nord3);"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <path d="m21 15-5-5L5 21" />
            </svg>
            <span>Load PNG/JPG...</span>
          </button>
          {#if store.stampImageData}
            <div class="mt-2 flex items-center gap-2">
              <img
                src={store.stampImageData}
                alt="Stamp preview"
                class="h-8 w-auto rounded"
                style="max-width: 60px; object-fit: contain;"
              />
              <span class="text-[10px] opacity-40">Ready</span>
            </div>
          {/if}
        </div>

        <!-- Rotation -->
        <div class="px-3 py-2" style="border-top: 1px solid var(--nord3);">
          <div class="text-[10px] uppercase opacity-40 mb-1">Rotation</div>
          <div class="flex gap-1">
            {#each rotationOptions as opt}
              <button
                onclick={() => store.setStampRotation(opt.value)}
                class="flex-1 p-1 rounded text-[10px] transition-colors"
                class:bg-[var(--nord8)]={store.stampRotation === opt.value}
                class:text-[var(--nord0)]={store.stampRotation === opt.value}
                style="background-color: {store.stampRotation === opt.value ? '' : 'var(--nord2)'};"
              >
                {opt.label}
              </button>
            {/each}
          </div>
        </div>
      </div>
    {/if}
  </div>

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

    <!-- Shapes dropdown with nested options -->
    <div class="relative">
      <button
        onclick={toggleShapesMenu}
        class="p-2 rounded transition-colors flex items-center gap-0.5"
        class:bg-[var(--nord8)]={isShapeTool}
        style="color: {isShapeTool ? 'var(--nord0)' : 'var(--nord4)'};"
        title="Shapes"
      >
        {#if store.activeTool === 'ellipse'}
          <Circle size={16} />
        {:else if store.activeTool === 'line'}
          <Minus size={16} />
        {:else if store.activeTool === 'arrow'}
          <ArrowRight size={16} />
        {:else}
          <Square size={16} />
        {/if}
        <ChevronRight size={12} class="rotate-90 opacity-60" />
      </button>

      {#if showShapesMenu}
        <div
          class="absolute top-full left-0 mt-1 rounded-lg shadow-lg py-1 z-50"
          style="background-color: var(--nord1); border: 1px solid var(--nord3); min-width: 140px;"
          onmouseleave={() => handleShapeHover(null)}
        >
          {#each shapeTools as shape}
            <div class="relative">
              <button
                onclick={() => selectShapeTool(shape.tool)}
                onmouseenter={() => handleShapeHover(shape.tool)}
                class="w-full flex items-center justify-between gap-2 px-3 py-1.5 text-xs hover:bg-[var(--nord2)] transition-colors"
                class:bg-[var(--nord3)]={store.activeTool === shape.tool}
              >
                <div class="flex items-center gap-2">
                  <shape.icon size={14} />
                  <span>{shape.label}</span>
                </div>
                <ChevronRight size={12} class="opacity-40" />
              </button>

              <!-- Nested options submenu -->
              {#if hoveredShapeTool === shape.tool && showShapeOptions}
                <div
                  class="absolute left-full top-0 ml-1 rounded-lg shadow-lg p-2 z-50"
                  style="background-color: var(--nord1); border: 1px solid var(--nord3); min-width: 160px;"
                  onmouseenter={keepShapeOptionsOpen}
                  onmouseleave={() => handleShapeHover(null)}
                >
                  <!-- Line Style Section -->
                  <div class="mb-2">
                    <div class="text-[10px] uppercase opacity-40 mb-1 px-1">Line Style</div>
                    <div class="flex gap-1">
                      {#each lineStyles as lineStyle}
                        <button
                          onclick={() => selectLineStyle(lineStyle.style)}
                          class="flex-1 p-1.5 rounded text-[10px] transition-colors flex flex-col items-center gap-1"
                          class:bg-[var(--nord8)]={store.activeLineStyle === lineStyle.style}
                          class:text-[var(--nord0)]={store.activeLineStyle === lineStyle.style}
                          style="background-color: {store.activeLineStyle === lineStyle.style ? '' : 'var(--nord2)'};"
                          title={lineStyle.label}
                        >
                          <svg width="24" height="6" viewBox="0 0 24 6">
                            {#if lineStyle.style === 'solid'}
                              <line x1="0" y1="3" x2="24" y2="3" stroke="currentColor" stroke-width="2" />
                            {:else if lineStyle.style === 'dashed'}
                              <line x1="0" y1="3" x2="24" y2="3" stroke="currentColor" stroke-width="2" stroke-dasharray="4 2" />
                            {:else}
                              <line x1="0" y1="3" x2="24" y2="3" stroke="currentColor" stroke-width="2" stroke-dasharray="1 2" />
                            {/if}
                          </svg>
                        </button>
                      {/each}
                    </div>
                  </div>

                  <!-- Stroke Color Section (for all shapes) -->
                  <div class="mb-2 pt-2" style="border-top: 1px solid var(--nord3);">
                    <div class="text-[10px] uppercase opacity-40 mb-1 px-1">Stroke Color</div>
                    <div class="grid grid-cols-4 gap-1 mb-2">
                      {#each HIGHLIGHT_COLORS.slice(0, 8) as color}
                        <button
                          onclick={() => store.setActiveColor(color.value)}
                          class="w-5 h-5 rounded border transition-transform hover:scale-110"
                          style="
                            background-color: {color.value};
                            border-color: {store.activeColor === color.value ? 'var(--nord6)' : 'transparent'};
                          "
                          title={color.name}
                        ></button>
                      {/each}
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="text-[9px] opacity-50">{Math.round(store.activeOpacity * 100)}%</span>
                      <input
                        type="range"
                        min="0.1"
                        max="1"
                        step="0.1"
                        value={store.activeOpacity}
                        oninput={(e) => store.setActiveOpacity(parseFloat((e.target as HTMLInputElement).value))}
                        class="flex-1 h-1"
                      />
                    </div>
                  </div>

                  <!-- Arrow Heads Section (only for arrow) -->
                  {#if shape.tool === 'arrow'}
                    <div class="mb-2 pt-2" style="border-top: 1px solid var(--nord3);">
                      <div class="text-[10px] uppercase opacity-40 mb-1 px-1">Start Arrow</div>
                      <div class="flex gap-1 mb-2">
                        {#each arrowHeadStyles as arrowStyle}
                          <button
                            onclick={() => selectStartArrow(arrowStyle.style)}
                            class="flex-1 p-1 rounded text-[9px] transition-colors"
                            class:bg-[var(--nord8)]={store.activeStartArrow === arrowStyle.style}
                            class:text-[var(--nord0)]={store.activeStartArrow === arrowStyle.style}
                            style="background-color: {store.activeStartArrow === arrowStyle.style ? '' : 'var(--nord2)'};"
                          >
                            {arrowStyle.label}
                          </button>
                        {/each}
                      </div>
                      <div class="text-[10px] uppercase opacity-40 mb-1 px-1">End Arrow</div>
                      <div class="flex gap-1">
                        {#each arrowHeadStyles as arrowStyle}
                          <button
                            onclick={() => selectEndArrow(arrowStyle.style)}
                            class="flex-1 p-1 rounded text-[9px] transition-colors"
                            class:bg-[var(--nord8)]={store.activeEndArrow === arrowStyle.style}
                            class:text-[var(--nord0)]={store.activeEndArrow === arrowStyle.style}
                            style="background-color: {store.activeEndArrow === arrowStyle.style ? '' : 'var(--nord2)'};"
                          >
                            {arrowStyle.label}
                          </button>
                        {/each}
                      </div>
                    </div>
                  {/if}

                  <!-- Fill Section (only for rectangle and ellipse) -->
                  {#if shape.tool === 'rectangle' || shape.tool === 'ellipse'}
                    <div class="pt-2" style="border-top: 1px solid var(--nord3);">
                      <div class="flex items-center gap-2 mb-2">
                        <label class="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={store.activeFillEnabled}
                            onchange={(e) => store.setActiveFillEnabled((e.target as HTMLInputElement).checked)}
                            class="w-3 h-3 rounded"
                          />
                          <span class="text-[10px]" style="color: var(--nord4);">Fill</span>
                        </label>
                      </div>

                      {#if store.activeFillEnabled}
                        <div class="grid grid-cols-4 gap-1 mb-2">
                          {#each HIGHLIGHT_COLORS.slice(0, 8) as color}
                            <button
                              onclick={() => store.setActiveFillColor(color.value)}
                              class="w-5 h-5 rounded border transition-transform hover:scale-110"
                              style="
                                background-color: {color.value};
                                border-color: {store.activeFillColor === color.value ? 'var(--nord6)' : 'transparent'};
                              "
                              title={color.name}
                            ></button>
                          {/each}
                        </div>
                        <div class="flex items-center gap-2">
                          <span class="text-[9px] opacity-50">{Math.round(store.activeFillOpacity * 100)}%</span>
                          <input
                            type="range"
                            min="0.1"
                            max="1"
                            step="0.1"
                            value={store.activeFillOpacity}
                            oninput={(e) => store.setActiveFillOpacity(parseFloat((e.target as HTMLInputElement).value))}
                            class="flex-1 h-1"
                          />
                        </div>
                      {/if}
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>

    <!-- Sequence Number with dropdown -->
    <div class="relative">
      <button
        onclick={toggleSequenceMenu}
        class="p-2 rounded transition-colors flex items-center gap-0.5"
        class:bg-[var(--nord8)]={store.activeTool === 'sequenceNumber'}
        style="color: {store.activeTool === 'sequenceNumber' ? 'var(--nord0)' : 'var(--nord4)'};"
        title="Sequence Number"
      >
        <Hash size={16} />
        <ChevronRight size={12} class="rotate-90 opacity-60" />
      </button>

      {#if showSequenceMenu}
        <div
          class="absolute top-full left-0 mt-1 rounded-lg shadow-lg p-2 z-50"
          style="background-color: var(--nord1); border: 1px solid var(--nord3); min-width: 160px;"
        >
          <!-- Quick select button -->
          <button
            onclick={() => { selectTool('sequenceNumber'); showSequenceMenu = false; }}
            class="w-full flex items-center gap-2 px-2 py-1.5 text-xs rounded hover:bg-[var(--nord2)] transition-colors mb-2"
            class:bg-[var(--nord3)]={store.activeTool === 'sequenceNumber'}
          >
            <Hash size={14} />
            <span>Use Sequence Numbers</span>
          </button>

          <!-- Next Number -->
          <div class="pt-2" style="border-top: 1px solid var(--nord3);">
            <div class="text-[10px] uppercase opacity-40 mb-1 px-1">Next Number</div>
            <div class="flex items-center gap-2 mb-3">
              <button
                onclick={() => { if (store.sequenceCounter > 1) store.setSequenceCounter(store.sequenceCounter - 1); }}
                class="w-7 h-7 rounded flex items-center justify-center text-sm font-medium transition-colors hover:bg-[var(--nord3)]"
                style="background-color: var(--nord2);"
                disabled={store.sequenceCounter <= 1}
              >
                −
              </button>
              <input
                type="number"
                min="1"
                value={store.sequenceCounter}
                oninput={handleSequenceInputChange}
                class="w-12 px-2 py-1 text-xs rounded text-center font-medium"
                style="background-color: var(--nord2); color: var(--nord6); border: 1px solid var(--nord3);"
              />
              <button
                onclick={() => store.setSequenceCounter(store.sequenceCounter + 1)}
                class="w-7 h-7 rounded flex items-center justify-center text-sm font-medium transition-colors hover:bg-[var(--nord3)]"
                style="background-color: var(--nord2);"
              >
                +
              </button>
            </div>
            <button
              onclick={handleResetSequence}
              class="w-full flex items-center justify-center gap-2 py-1.5 rounded text-xs transition-colors hover:bg-[var(--nord2)]"
              style="background-color: var(--nord3); color: var(--nord4);"
            >
              <RotateCcw size={12} />
              <span>Reset to 1</span>
            </button>
          </div>

          <!-- Color Section -->
          <div class="mt-2 pt-2" style="border-top: 1px solid var(--nord3);">
            <div class="text-[10px] uppercase opacity-40 mb-1 px-1">Color</div>
            <div class="grid grid-cols-4 gap-1 mb-2">
              {#each HIGHLIGHT_COLORS.slice(0, 8) as color}
                <button
                  onclick={() => store.setActiveColor(color.value)}
                  class="w-5 h-5 rounded border transition-transform hover:scale-110"
                  style="
                    background-color: {color.value};
                    border-color: {store.activeColor === color.value ? 'var(--nord6)' : 'transparent'};
                  "
                  title={color.name}
                ></button>
              {/each}
            </div>
            <div class="flex items-center gap-2">
              <span class="text-[9px] opacity-50">{Math.round(store.activeOpacity * 100)}%</span>
              <input
                type="range"
                min="0.1"
                max="1"
                step="0.1"
                value={store.activeOpacity}
                oninput={(e) => store.setActiveOpacity(parseFloat((e.target as HTMLInputElement).value))}
                class="flex-1 h-1"
              />
            </div>
          </div>
        </div>
      {/if}
    </div>
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

  <!-- Clear all -->
  <button
    onclick={handleClearAll}
    class="p-2 rounded transition-colors hover:bg-[var(--nord11)] hover:text-white"
    title="Clear all annotations"
  >
    <Trash2 size={16} />
  </button>
</div>
