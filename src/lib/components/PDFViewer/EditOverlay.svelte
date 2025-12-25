<script lang="ts">
  /**
   * EditOverlay - Renders and handles content editing operations
   *
   * This overlay allows users to:
   * - Draw new text boxes, images, and shapes
   * - Select and move existing edit operations
   * - Resize operations using handles
   * - Edit text content inline
   * - Click existing PDF text blocks to edit them
   */

  import { X, Move, Type } from 'lucide-svelte';
  import { invoke } from '@tauri-apps/api/core';
  import { onMount } from 'svelte';
  import type {
    EditsStore,
    EditorOp,
    NormalizedRect,
    InsertTextOp,
    InsertImageOp,
    DrawShapeOp,
    ReplaceTextOp,
  } from '$lib/stores/edits.svelte';

  // Types for text blocks with font info from Tauri
  interface SpanInfo {
    text: string;
    font: string;
    size: number;
    color: string;
    bold: boolean;
    italic: boolean;
    rect: NormalizedRect;
  }

  interface TextLineInfo {
    text: string;
    rect: NormalizedRect;
    spans: SpanInfo[];
  }

  interface TextBlockInfo {
    rect: NormalizedRect;
    lines: TextLineInfo[];
    text: string;
    dominantFont: string | null;
    dominantSize: number | null;
    dominantColor: string | null;
  }

  interface PageTextContent {
    success: boolean;
    page: number;
    blocks: TextBlockInfo[];
    pageWidth: number;
    pageHeight: number;
    error?: string;
  }

  interface Props {
    store: EditsStore;
    page: number;
    pageWidth: number;
    pageHeight: number;
    pdfPath: string;
    scale?: number;
    interactive?: boolean;
    hasPreview?: boolean; // When true, hide operation visuals (preview image shows them)
  }

  let { store, page, pageWidth, pageHeight, pdfPath, scale = 1, interactive = true, hasPreview = false }: Props = $props();

  let overlayElement: HTMLDivElement;

  // Drawing state
  let isDrawing = $state(false);
  let drawStart = $state<{ x: number; y: number } | null>(null);
  let drawEnd = $state<{ x: number; y: number } | null>(null);

  // Dragging state
  let isDragging = $state(false);
  let dragOffset = $state<{ x: number; y: number } | null>(null);

  // Editing text state
  let editingTextId = $state<string | null>(null);
  let editingTextContent = $state('');

  // PDF text blocks (existing text in the document)
  let textBlocks = $state<TextBlockInfo[]>([]);
  let isLoadingBlocks = $state(false);
  let showTextBlocks = $state(true); // Toggle to show/hide existing text highlights

  // Operations for this page
  const pageOps = $derived(store.getOpsForPage(page));

  // Fetch text blocks with font info from the PDF
  async function fetchTextBlocks() {
    if (!pdfPath) return;

    isLoadingBlocks = true;
    try {
      // Use font-aware command to get detailed font info
      // Note: Tauri command uses "input" parameter, not "path"
      const result = await invoke<PageTextContent>('pdf_get_text_blocks_with_fonts', {
        input: pdfPath,
        page: page - 1, // 0-indexed for backend
      });
      if (result.success) {
        textBlocks = result.blocks;
      } else {
        console.error('[EditOverlay] Failed to fetch text blocks:', result.error);
        textBlocks = [];
      }
    } catch (e) {
      console.error('[EditOverlay] Failed to fetch text blocks:', e);
      textBlocks = [];
    } finally {
      isLoadingBlocks = false;
    }
  }

  // Get combined text from a block
  function getBlockText(block: TextBlockInfo): string {
    // Use the pre-extracted text if available
    if (block.text) return block.text;
    // Fallback: reconstruct from lines
    return block.lines.map(line =>
      line.spans ? line.spans.map(s => s.text).join('') : line.text
    ).join('\n');
  }

  // Map PDF font names to CSS-friendly font families
  function mapFontFamily(pdfFont: string | null): string {
    if (!pdfFont) return 'Helvetica, Arial, sans-serif';

    const fontLower = pdfFont.toLowerCase();

    // Sans-serif fonts (most common in OCR and modern documents)
    if (fontLower.includes('arial') || fontLower.includes('helv') || fontLower.includes('helvetica')) {
      return 'Helvetica, Arial, sans-serif';
    }
    if (fontLower.includes('sans') || fontLower.includes('gothic') || fontLower.includes('calibri')) {
      return 'Arial, Helvetica, sans-serif';
    }
    if (fontLower.includes('verdana')) return 'Verdana, Geneva, sans-serif';
    if (fontLower.includes('tahoma')) return 'Tahoma, Geneva, sans-serif';
    if (fontLower.includes('trebuchet')) return 'Trebuchet MS, sans-serif';

    // Serif fonts
    if (fontLower.includes('times') || fontLower.includes('tiro') || fontLower.includes('roman')) {
      return 'Times New Roman, Times, serif';
    }
    if (fontLower.includes('georgia')) return 'Georgia, serif';
    if (fontLower.includes('palatino')) return 'Palatino Linotype, Book Antiqua, serif';
    if (fontLower.includes('garamond')) return 'Garamond, serif';
    if (fontLower.includes('cambria')) return 'Cambria, Georgia, serif';

    // Monospace fonts
    if (fontLower.includes('courier') || fontLower.includes('mono') || fontLower.includes('consol')) {
      return 'Courier New, Courier, monospace';
    }

    // OCR-specific fonts (Tesseract often uses these)
    if (fontLower.includes('freeserif')) return 'Times New Roman, Times, serif';
    if (fontLower.includes('freesans')) return 'Arial, Helvetica, sans-serif';
    if (fontLower.includes('freemono')) return 'Courier New, Courier, monospace';
    if (fontLower.includes('dejavu')) {
      if (fontLower.includes('serif')) return 'DejaVu Serif, Times New Roman, serif';
      if (fontLower.includes('mono')) return 'DejaVu Sans Mono, Courier New, monospace';
      return 'DejaVu Sans, Arial, sans-serif';
    }
    if (fontLower.includes('liberation')) {
      if (fontLower.includes('serif')) return 'Liberation Serif, Times New Roman, serif';
      if (fontLower.includes('mono')) return 'Liberation Mono, Courier New, monospace';
      return 'Liberation Sans, Arial, sans-serif';
    }
    if (fontLower.includes('noto')) {
      if (fontLower.includes('serif')) return 'Noto Serif, Times New Roman, serif';
      if (fontLower.includes('mono')) return 'Noto Mono, Courier New, monospace';
      return 'Noto Sans, Arial, sans-serif';
    }

    // Fallback: try to detect font category from name
    if (fontLower.includes('serif')) return 'Times New Roman, Times, serif';
    if (fontLower.includes('mono')) return 'Courier New, Courier, monospace';

    // Default to sans-serif (most common for modern/OCR documents)
    return 'Arial, Helvetica, sans-serif';
  }

  // Check if block has bold text
  function hasBlockBold(block: TextBlockInfo): boolean {
    for (const line of block.lines) {
      if (line.spans) {
        for (const span of line.spans) {
          if (span.bold && span.text.trim()) return true;
        }
      }
    }
    return false;
  }

  // Check if block has italic text
  function hasBlockItalic(block: TextBlockInfo): boolean {
    for (const line of block.lines) {
      if (line.spans) {
        for (const span of line.spans) {
          if (span.italic && span.text.trim()) return true;
        }
      }
    }
    return false;
  }

  // Check if a block is already being edited (has a ReplaceTextOp)
  function isBlockBeingEdited(block: TextBlockInfo): boolean {
    return pageOps.some(op => {
      if (op.type !== 'replace_text') return false;
      // Check if the op rect overlaps significantly with the block
      const overlap = rectsOverlap(op.rect, block.rect);
      return overlap > 0.5; // 50% overlap threshold
    });
  }

  // Calculate overlap ratio between two rects
  function rectsOverlap(a: NormalizedRect, b: NormalizedRect): number {
    const x0 = Math.max(a.x, b.x);
    const y0 = Math.max(a.y, b.y);
    const x1 = Math.min(a.x + a.width, b.x + b.width);
    const y1 = Math.min(a.y + a.height, b.y + b.height);

    if (x1 <= x0 || y1 <= y0) return 0;

    const overlapArea = (x1 - x0) * (y1 - y0);
    const blockArea = b.width * b.height;
    return blockArea > 0 ? overlapArea / blockArea : 0;
  }

  // Handle click on an existing text block
  function handleTextBlockClick(block: TextBlockInfo) {
    if (!interactive) return;
    if (store.activeTool !== 'select' && store.activeTool !== 'text' && store.activeTool !== null) return;

    // Create a ReplaceTextOp for this block
    const text = getBlockText(block);

    // Use the block's font info if available, otherwise fall back to toolbar defaults
    const style = {
      fontFamily: mapFontFamily(block.dominantFont),
      fontSize: block.dominantSize || store.activeTextStyle.fontSize,
      color: block.dominantColor || store.activeTextStyle.color,
      bold: hasBlockBold(block),
      italic: hasBlockItalic(block),
      align: store.activeTextStyle.align, // Keep alignment from toolbar
    };

    console.log('[EditOverlay] Block font info:', {
      dominantFont: block.dominantFont,
      dominantSize: block.dominantSize,
      dominantColor: block.dominantColor,
      mappedStyle: style,
    });

    const op = store.addOp<ReplaceTextOp>({
      type: 'replace_text',
      page,
      rect: { ...block.rect },
      originalText: text,
      text: text, // Start with original text
      style,
    });

    // Start editing immediately
    editingTextId = op.id;
    editingTextContent = text;
    store.selectOp(op.id);
  }

  // Fetch blocks when page or path changes
  $effect(() => {
    if (pdfPath && page) {
      fetchTextBlocks();
    }
  });

  // Convert normalized coords to pixels
  function toPixels(rect: NormalizedRect): { x: number; y: number; width: number; height: number } {
    return {
      x: rect.x * pageWidth * scale,
      y: rect.y * pageHeight * scale,
      width: rect.width * pageWidth * scale,
      height: rect.height * pageHeight * scale,
    };
  }

  // Convert pixel coords to normalized
  function toNormalized(x: number, y: number, width: number, height: number): NormalizedRect {
    return {
      x: x / (pageWidth * scale),
      y: y / (pageHeight * scale),
      width: width / (pageWidth * scale),
      height: height / (pageHeight * scale),
    };
  }

  // Get mouse position relative to overlay
  function getMousePos(e: MouseEvent): { x: number; y: number } {
    const rect = overlayElement.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    };
  }

  // Cursor style based on tool
  const cursorStyle = $derived(() => {
    if (!interactive) return 'default';
    if (isDragging) return 'grabbing';
    if (!store.activeTool) return 'default';
    if (store.activeTool === 'select') return 'default';
    if (store.activeTool === 'text') return 'text';
    return 'crosshair';
  });

  function handleMouseDown(e: MouseEvent) {
    if (e.button !== 0 || !interactive) return;

    const pos = getMousePos(e);

    // Handle select tool - check if clicking on an operation
    if (store.activeTool === 'select' || !store.activeTool) {
      const clickedOp = findOpAtPosition(pos);
      if (clickedOp) {
        store.selectOp(clickedOp.id);
        isDragging = true;
        const px = toPixels(clickedOp.rect);
        dragOffset = { x: pos.x - px.x, y: pos.y - px.y };
        return;
      } else {
        store.selectOp(null);
      }
      return;
    }

    // Start drawing for other tools
    if (store.activeTool === 'text' || store.activeTool === 'image' ||
        store.activeTool === 'shape-rect' || store.activeTool === 'shape-ellipse' ||
        store.activeTool === 'line') {
      isDrawing = true;
      drawStart = pos;
      drawEnd = pos;
    }
  }

  function handleMouseMove(e: MouseEvent) {
    if (!interactive) return;

    const pos = getMousePos(e);

    if (isDrawing && drawStart) {
      drawEnd = pos;
    }

    if (isDragging && store.selectedId && dragOffset) {
      const op = store.getOpById(store.selectedId);
      if (op) {
        const newX = (pos.x - dragOffset.x) / (pageWidth * scale);
        const newY = (pos.y - dragOffset.y) / (pageHeight * scale);
        store.updateOp(store.selectedId, {
          rect: { ...op.rect, x: newX, y: newY },
        });
      }
    }
  }

  function handleMouseUp(e: MouseEvent) {
    if (!interactive) return;

    if (isDragging) {
      isDragging = false;
      dragOffset = null;
      return;
    }

    if (isDrawing && drawStart && drawEnd) {
      const minSize = 10; // Minimum size in pixels

      const x = Math.min(drawStart.x, drawEnd.x);
      const y = Math.min(drawStart.y, drawEnd.y);
      const width = Math.abs(drawEnd.x - drawStart.x);
      const height = Math.abs(drawEnd.y - drawStart.y);

      // Only create if big enough
      if (width >= minSize || height >= minSize) {
        const rect = toNormalized(x, y, Math.max(width, minSize), Math.max(height, minSize));

        if (store.activeTool === 'text') {
          const op = store.addOp<InsertTextOp>({
            type: 'insert_text',
            page,
            rect,
            text: '',
            style: { ...store.activeTextStyle },
          });
          // Start editing immediately
          editingTextId = op.id;
          editingTextContent = '';
        } else if (store.activeTool === 'image') {
          store.addOp<InsertImageOp>({
            type: 'insert_image',
            page,
            rect,
            keepAspect: true,
          });
        } else if (store.activeTool === 'shape-rect') {
          store.addOp<DrawShapeOp>({
            type: 'draw_shape',
            page,
            rect,
            shape: 'rect',
            strokeColor: store.activeStrokeColor,
            strokeWidth: store.activeStrokeWidth,
            fillColor: store.activeFillEnabled ? store.activeFillColor : undefined,
          });
        } else if (store.activeTool === 'shape-ellipse') {
          store.addOp<DrawShapeOp>({
            type: 'draw_shape',
            page,
            rect,
            shape: 'ellipse',
            strokeColor: store.activeStrokeColor,
            strokeWidth: store.activeStrokeWidth,
            fillColor: store.activeFillEnabled ? store.activeFillColor : undefined,
          });
        } else if (store.activeTool === 'line') {
          store.addOp<DrawShapeOp>({
            type: 'draw_shape',
            page,
            rect,
            shape: 'line',
            strokeColor: store.activeStrokeColor,
            strokeWidth: store.activeStrokeWidth,
          });
        }
      }
    }

    isDrawing = false;
    drawStart = null;
    drawEnd = null;
  }

  function findOpAtPosition(pos: { x: number; y: number }): EditorOp | undefined {
    // Search in reverse order (topmost first)
    for (let i = pageOps.length - 1; i >= 0; i--) {
      const op = pageOps[i];
      const px = toPixels(op.rect);
      if (
        pos.x >= px.x &&
        pos.x <= px.x + px.width &&
        pos.y >= px.y &&
        pos.y <= px.y + px.height
      ) {
        return op;
      }
    }
    return undefined;
  }

  function handleTextBlur(op: EditorOp) {
    if ((op.type === 'insert_text' || op.type === 'replace_text') && editingTextId === op.id) {
      store.updateOp(op.id, { text: editingTextContent });
      editingTextId = null;
      editingTextContent = '';
    }
  }

  function handleTextKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      editingTextId = null;
      editingTextContent = '';
    }
  }

  function startEditingText(op: EditorOp) {
    if (op.type === 'insert_text' || op.type === 'replace_text') {
      editingTextId = op.id;
      editingTextContent = op.text;
    }
  }

  // Preview rect while drawing
  const previewRect = $derived.by(() => {
    if (!isDrawing || !drawStart || !drawEnd) return null;
    return {
      x: Math.min(drawStart.x, drawEnd.x),
      y: Math.min(drawStart.y, drawEnd.y),
      width: Math.abs(drawEnd.x - drawStart.x),
      height: Math.abs(drawEnd.y - drawStart.y),
    };
  });
</script>

<div
  bind:this={overlayElement}
  class="absolute inset-0"
  class:pointer-events-none={!interactive}
  style="
    width: {pageWidth * scale}px;
    height: {pageHeight * scale}px;
    z-index: 30;
    cursor: {cursorStyle()};
  "
  onmousedown={handleMouseDown}
  onmousemove={handleMouseMove}
  onmouseup={handleMouseUp}
  onmouseleave={handleMouseUp}
  role="application"
  aria-label="Edit overlay"
>
  <!-- Render existing PDF text blocks (clickable to edit) -->
  {#if showTextBlocks && interactive && (store.activeTool === 'select' || store.activeTool === 'text' || store.activeTool === null)}
    {#each textBlocks as block}
      {#if !isBlockBeingEdited(block)}
        {@const px = toPixels(block.rect)}
        <button
          type="button"
          class="absolute transition-all duration-150 cursor-pointer group"
          style="
            left: {px.x}px;
            top: {px.y}px;
            width: {px.width}px;
            height: {px.height}px;
          "
          onclick={() => handleTextBlockClick(block)}
          title="Click to edit this text"
        >
          <!-- Subtle highlight on hover -->
          <div
            class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity"
            style="
              background-color: rgba(136, 192, 208, 0.15);
              border: 1px dashed var(--nord8);
            "
          ></div>
          <!-- Edit indicator on hover -->
          <div
            class="absolute -top-5 left-0 opacity-0 group-hover:opacity-100 transition-opacity text-xs px-1 py-0.5 rounded flex items-center gap-1"
            style="background-color: var(--nord10); color: var(--nord6);"
          >
            <Type size={10} />
            <span>Edit</span>
          </div>
        </button>
      {/if}
    {/each}
  {/if}

  <!-- Render existing operations -->
  {#each pageOps as op}
    {@const px = toPixels(op.rect)}
    {@const isSelected = store.selectedId === op.id}
    {@const isActivelyEditing = editingTextId === op.id}
    {@const showVisuals = !hasPreview || isActivelyEditing}
    {@const minEditWidth = Math.max(px.width, 300)}
    {@const minEditHeight = Math.max(px.height, 100)}

    <div
      class="absolute"
      class:ring-2={isSelected && showVisuals}
      class:ring-[var(--nord8)]={isSelected && showVisuals}
      class:z-50={isActivelyEditing}
      style="
        left: {px.x}px;
        top: {px.y}px;
        width: {isActivelyEditing ? minEditWidth : px.width}px;
        min-height: {isActivelyEditing ? minEditHeight : px.height}px;
        height: {isActivelyEditing ? 'auto' : px.height + 'px'};
      "
    >
      {#if op.type === 'insert_text' || op.type === 'replace_text'}
        {@const textOp = op as InsertTextOp}
        {@const isReplaceOp = op.type === 'replace_text'}
        <!-- Text box - always show textarea when actively editing -->
        {#if editingTextId === op.id}
          <textarea
            class="w-full p-2 outline-none resize-y"
            style="
              font-family: {textOp.style.fontFamily};
              font-size: {textOp.style.fontSize * scale}px;
              color: {textOp.style.color};
              font-weight: {textOp.style.bold ? 'bold' : 'normal'};
              font-style: {textOp.style.italic ? 'italic' : 'normal'};
              text-align: {textOp.style.align || 'left'};
              background-color: rgba(255, 255, 255, 0.98);
              border: 2px solid var(--nord10);
              border-radius: 4px;
              min-height: {minEditHeight}px;
              box-shadow: 0 4px 12px rgba(0,0,0,0.15);
              line-height: 1.4;
            "
            bind:value={editingTextContent}
            onblur={() => handleTextBlur(op)}
            onkeydown={(e) => handleTextKeydown(e)}
          ></textarea>
        {:else if showVisuals}
          <div
            class="w-full h-full p-1 overflow-hidden cursor-text"
            style="
              font-family: {textOp.style.fontFamily};
              font-size: {textOp.style.fontSize * scale}px;
              color: {textOp.style.color};
              font-weight: {textOp.style.bold ? 'bold' : 'normal'};
              font-style: {textOp.style.italic ? 'italic' : 'normal'};
              text-align: {textOp.style.align || 'left'};
              background-color: {isReplaceOp ? 'white' : (textOp.text ? 'transparent' : 'rgba(136, 192, 208, 0.1)')};
              border: 1px dashed {textOp.text ? 'transparent' : 'var(--nord8)'};
            "
            ondblclick={() => startEditingText(op)}
          >
            {textOp.text || 'Double-click to edit...'}
          </div>
        {/if}
      {:else if op.type === 'insert_image' && showVisuals}
        {@const imgOp = op as InsertImageOp}
        <!-- Image placeholder -->
        <div
          class="w-full h-full flex items-center justify-center"
          style="
            background-color: rgba(136, 192, 208, 0.1);
            border: 2px dashed var(--nord8);
          "
        >
          {#if imgOp.imageData}
            <img
              src={imgOp.imageData}
              alt="Inserted image"
              class="max-w-full max-h-full object-contain"
            />
          {:else}
            <span class="text-xs opacity-50">Click to select image</span>
          {/if}
        </div>
      {:else if op.type === 'draw_shape' && showVisuals}
        {@const shapeOp = op as DrawShapeOp}
        <!-- Shape -->
        <svg class="w-full h-full" viewBox="0 0 {px.width} {px.height}">
          {#if shapeOp.shape === 'rect'}
            <rect
              x={shapeOp.strokeWidth / 2}
              y={shapeOp.strokeWidth / 2}
              width={px.width - shapeOp.strokeWidth}
              height={px.height - shapeOp.strokeWidth}
              stroke={shapeOp.strokeColor}
              stroke-width={shapeOp.strokeWidth}
              fill={shapeOp.fillColor || 'none'}
            />
          {:else if shapeOp.shape === 'ellipse'}
            <ellipse
              cx={px.width / 2}
              cy={px.height / 2}
              rx={(px.width - shapeOp.strokeWidth) / 2}
              ry={(px.height - shapeOp.strokeWidth) / 2}
              stroke={shapeOp.strokeColor}
              stroke-width={shapeOp.strokeWidth}
              fill={shapeOp.fillColor || 'none'}
            />
          {:else if shapeOp.shape === 'line'}
            <line
              x1={0}
              y1={px.height}
              x2={px.width}
              y2={0}
              stroke={shapeOp.strokeColor}
              stroke-width={shapeOp.strokeWidth}
            />
          {/if}
        </svg>
      {/if}

      <!-- Selection handles -->
      {#if isSelected && interactive}
        <!-- Remove button -->
        <button
          onclick={() => store.removeOp(op.id)}
          class="absolute -top-2 -right-2 w-5 h-5 rounded-full flex items-center justify-center transition-colors hover:scale-110"
          style="background-color: var(--nord11); color: var(--nord6);"
          title="Remove"
        >
          <X size={12} />
        </button>

        <!-- Move indicator -->
        <div
          class="absolute -top-2 -left-2 w-5 h-5 rounded-full flex items-center justify-center"
          style="background-color: var(--nord10); color: var(--nord6);"
        >
          <Move size={12} />
        </div>

        <!-- Resize handles -->
        <div class="absolute -bottom-1 -right-1 w-3 h-3 cursor-se-resize" style="background-color: var(--nord8);"></div>
      {/if}
    </div>
  {/each}

  <!-- Drawing preview -->
  {#if isDrawing && previewRect}
    <div
      class="absolute pointer-events-none"
      style="
        left: {previewRect.x}px;
        top: {previewRect.y}px;
        width: {previewRect.width}px;
        height: {previewRect.height}px;
      "
    >
      {#if store.activeTool === 'text'}
        <div
          class="w-full h-full"
          style="background-color: rgba(136, 192, 208, 0.2); border: 2px dashed var(--nord8);"
        ></div>
      {:else if store.activeTool === 'image'}
        <div
          class="w-full h-full"
          style="background-color: rgba(163, 190, 140, 0.2); border: 2px dashed var(--nord14);"
        ></div>
      {:else if store.activeTool === 'shape-rect'}
        <svg class="w-full h-full">
          <rect
            x={store.activeStrokeWidth / 2}
            y={store.activeStrokeWidth / 2}
            width={previewRect.width - store.activeStrokeWidth}
            height={previewRect.height - store.activeStrokeWidth}
            stroke={store.activeStrokeColor}
            stroke-width={store.activeStrokeWidth}
            fill={store.activeFillEnabled ? store.activeFillColor : 'none'}
            opacity="0.5"
          />
        </svg>
      {:else if store.activeTool === 'shape-ellipse'}
        <svg class="w-full h-full">
          <ellipse
            cx={previewRect.width / 2}
            cy={previewRect.height / 2}
            rx={(previewRect.width - store.activeStrokeWidth) / 2}
            ry={(previewRect.height - store.activeStrokeWidth) / 2}
            stroke={store.activeStrokeColor}
            stroke-width={store.activeStrokeWidth}
            fill={store.activeFillEnabled ? store.activeFillColor : 'none'}
            opacity="0.5"
          />
        </svg>
      {:else if store.activeTool === 'line'}
        <svg class="w-full h-full">
          <line
            x1={0}
            y1={previewRect.height}
            x2={previewRect.width}
            y2={0}
            stroke={store.activeStrokeColor}
            stroke-width={store.activeStrokeWidth}
            opacity="0.5"
          />
        </svg>
      {/if}
    </div>
  {/if}
</div>
