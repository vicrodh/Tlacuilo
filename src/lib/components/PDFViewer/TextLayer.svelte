<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import type { AnnotationsStore, AnnotationType, MarkupType } from '$lib/stores/annotations.svelte';
  import { getAuthorString } from '$lib/stores/settings.svelte';
  import TextContextMenu from './TextContextMenu.svelte';

  interface NormalizedRect {
    x: number;
    y: number;
    width: number;
    height: number;
  }

  interface TextCharInfo {
    char: string;
    quad: number[]; // [x0,y0, x1,y1, x2,y2, x3,y3] normalized
  }

  interface TextLineInfo {
    text: string;
    rect: NormalizedRect;
    chars: TextCharInfo[];
  }

  interface TextBlockInfo {
    rect: NormalizedRect;
    lines: TextLineInfo[];
  }

  interface PageTextContent {
    page: number;
    blocks: TextBlockInfo[];
  }

  interface Props {
    pdfPath: string;
    page: number;
    pageWidth: number;
    pageHeight: number;
    scale?: number;
    store: AnnotationsStore;
    showAnnotationTools?: boolean;
    onSearchText?: (text: string) => void;
  }

  let { pdfPath, page, pageWidth, pageHeight, scale = 1, store, showAnnotationTools = false, onSearchText }: Props = $props();

  // Context menu state
  let contextMenu = $state({ visible: false, x: 0, y: 0, text: '' });

  let textContent = $state<PageTextContent | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);

  // Custom selection state for pixel-perfect rendering
  interface SelectionPoint {
    blockIndex: number;
    lineIndex: number;
    charIndex: number;
  }

  let selectionStart = $state<SelectionPoint | null>(null);
  let selectionEnd = $state<SelectionPoint | null>(null);
  let isSelecting = $state(false);

  // Get selected character quads for rendering
  const selectedQuads = $derived.by(() => {
    if (!textContent || !selectionStart || !selectionEnd) return [];

    const quads: { quad: number[]; }[] = [];

    // Normalize selection direction (start should be before end)
    let start = selectionStart;
    let end = selectionEnd;

    const startKey = start.blockIndex * 10000 + start.lineIndex * 100 + start.charIndex;
    const endKey = end.blockIndex * 10000 + end.lineIndex * 100 + end.charIndex;

    if (endKey < startKey) {
      [start, end] = [end, start];
    }

    // Collect all character quads in the selection range
    let inSelection = false;
    for (let bi = 0; bi < textContent.blocks.length; bi++) {
      const block = textContent.blocks[bi];
      for (let li = 0; li < block.lines.length; li++) {
        const line = block.lines[li];
        for (let ci = 0; ci < line.chars.length; ci++) {
          const isStart = bi === start.blockIndex && li === start.lineIndex && ci === start.charIndex;
          const isEnd = bi === end.blockIndex && li === end.lineIndex && ci === end.charIndex;

          if (isStart) inSelection = true;

          if (inSelection) {
            quads.push({ quad: line.chars[ci].quad });
          }

          if (isEnd) {
            inSelection = false;
            break;
          }
        }
        if (!inSelection && bi === end.blockIndex && li === end.lineIndex) break;
      }
      if (!inSelection && bi === end.blockIndex) break;
    }

    return quads;
  });

  // Get selected text string
  const selectedText = $derived.by(() => {
    if (!textContent || !selectionStart || !selectionEnd) return '';

    let start = selectionStart;
    let end = selectionEnd;

    const startKey = start.blockIndex * 10000 + start.lineIndex * 100 + start.charIndex;
    const endKey = end.blockIndex * 10000 + end.lineIndex * 100 + end.charIndex;

    if (endKey < startKey) {
      [start, end] = [end, start];
    }

    let text = '';
    let inSelection = false;
    let lastLineIndex = -1;
    let lastBlockIndex = -1;

    for (let bi = 0; bi < textContent.blocks.length; bi++) {
      const block = textContent.blocks[bi];
      for (let li = 0; li < block.lines.length; li++) {
        const line = block.lines[li];
        for (let ci = 0; ci < line.chars.length; ci++) {
          const isStart = bi === start.blockIndex && li === start.lineIndex && ci === start.charIndex;
          const isEnd = bi === end.blockIndex && li === end.lineIndex && ci === end.charIndex;

          if (isStart) {
            inSelection = true;
            lastBlockIndex = bi;
            lastLineIndex = li;
          }

          if (inSelection) {
            // Add newline when changing lines
            if (bi !== lastBlockIndex || li !== lastLineIndex) {
              text += '\n';
              lastBlockIndex = bi;
              lastLineIndex = li;
            }
            text += line.chars[ci].char;
          }

          if (isEnd) {
            inSelection = false;
            break;
          }
        }
        if (!inSelection && bi === end.blockIndex && li === end.lineIndex) break;
      }
      if (!inSelection && bi === end.blockIndex) break;
    }

    return text;
  });

  // Find character at normalized coordinates
  function findCharAt(normX: number, normY: number): SelectionPoint | null {
    if (!textContent) return null;

    for (let bi = 0; bi < textContent.blocks.length; bi++) {
      const block = textContent.blocks[bi];
      for (let li = 0; li < block.lines.length; li++) {
        const line = block.lines[li];
        // Check if Y is in line bounds (with tolerance)
        if (normY >= line.rect.y - 0.005 && normY <= line.rect.y + line.rect.height + 0.005) {
          // Find character by X position
          for (let ci = 0; ci < line.chars.length; ci++) {
            const char = line.chars[ci];
            const minX = Math.min(char.quad[0], char.quad[2], char.quad[4], char.quad[6]);
            const maxX = Math.max(char.quad[0], char.quad[2], char.quad[4], char.quad[6]);
            const minY = Math.min(char.quad[1], char.quad[3], char.quad[5], char.quad[7]);
            const maxY = Math.max(char.quad[1], char.quad[3], char.quad[5], char.quad[7]);

            if (normX >= minX && normX <= maxX && normY >= minY && normY <= maxY) {
              return { blockIndex: bi, lineIndex: li, charIndex: ci };
            }
          }

          // If in line but no exact char hit, find closest
          if (normX >= line.rect.x && normX <= line.rect.x + line.rect.width) {
            let closestDist = Infinity;
            let closestIndex = 0;
            for (let ci = 0; ci < line.chars.length; ci++) {
              const char = line.chars[ci];
              const charCenterX = (char.quad[0] + char.quad[2]) / 2;
              const dist = Math.abs(normX - charCenterX);
              if (dist < closestDist) {
                closestDist = dist;
                closestIndex = ci;
              }
            }
            return { blockIndex: bi, lineIndex: li, charIndex: closestIndex };
          }
        }
      }
    }
    return null;
  }

  // Clear custom selection
  function clearSelection() {
    selectionStart = null;
    selectionEnd = null;
    isSelecting = false;
  }

  // Set custom selection for a word (used by double-click)
  function setWordSelection(blockIndex: number, lineIndex: number, startChar: number, endChar: number) {
    selectionStart = { blockIndex, lineIndex, charIndex: startChar };
    selectionEnd = { blockIndex, lineIndex, charIndex: endChar };
  }

  // Handle selection start
  function handleMouseDown(e: MouseEvent) {
    if (e.button !== 0) return; // Only left click

    const textLayer = e.currentTarget as HTMLElement;
    const layerRect = textLayer.getBoundingClientRect();
    const normX = (e.clientX - layerRect.left) / (pageWidth * scale);
    const normY = (e.clientY - layerRect.top) / (pageHeight * scale);

    const charPos = findCharAt(normX, normY);
    if (charPos) {
      selectionStart = charPos;
      selectionEnd = charPos;
      isSelecting = true;
    } else {
      clearSelection();
    }
  }

  // Handle selection update
  function handleMouseMove(e: MouseEvent) {
    if (!isSelecting || !selectionStart) return;

    const textLayer = document.querySelector(`[data-text-layer-page="${page}"]`) as HTMLElement;
    if (!textLayer) return;

    const layerRect = textLayer.getBoundingClientRect();
    const normX = (e.clientX - layerRect.left) / (pageWidth * scale);
    const normY = (e.clientY - layerRect.top) / (pageHeight * scale);

    const charPos = findCharAt(normX, normY);
    if (charPos) {
      selectionEnd = charPos;
    }
  }

  // Handle selection end
  function handleSelectionEnd() {
    isSelecting = false;
  }

  // Load text content when page changes
  $effect(() => {
    loadTextContent(pdfPath, page);
    // Clear selection when page changes
    clearSelection();
  });

  // Action to scale text span to target width
  function scaleToWidth(node: HTMLSpanElement, targetWidth: number) {
    function applyScale() {
      const actualWidth = node.scrollWidth;
      if (actualWidth > 0 && targetWidth > 0) {
        const scaleX = targetWidth / actualWidth;
        if (Math.abs(scaleX - 1) > 0.01) {
          node.style.transform = `scaleX(${scaleX})`;
        }
      }
    }

    // Apply after font loads
    requestAnimationFrame(applyScale);

    return {
      update(newTargetWidth: number) {
        targetWidth = newTargetWidth;
        requestAnimationFrame(applyScale);
      }
    };
  }

  async function loadTextContent(path: string, pageNum: number) {
    if (!path) return;

    loading = true;
    error = null;

    try {
      const content = await invoke<PageTextContent>('pdf_get_text_blocks', {
        path,
        page: pageNum,
      });
      textContent = content;
    } catch (e) {
      error = String(e);
      console.error('Failed to load text content:', e);
    } finally {
      loading = false;
    }
  }

  // Convert normalized rect to pixel coordinates
  function toPixelRect(rect: NormalizedRect): { x: number; y: number; width: number; height: number } {
    return {
      x: rect.x * pageWidth * scale,
      y: rect.y * pageHeight * scale,
      width: rect.width * pageWidth * scale,
      height: rect.height * pageHeight * scale,
    };
  }

  // Handle text selection end (for annotation mode)
  function handleMouseUp(e: MouseEvent) {
    // Only create annotations in text-select mode
    if (store.activeTool !== 'text-select') {
      return;
    }

    // Use our custom selection
    if (selectedQuads.length === 0) return;

    // Get the pending markup type (defaults to highlight)
    const markupType = store.pendingMarkupType;
    const author = getAuthorString() || undefined;

    // Convert quads to normalized rects
    const rects = mergeQuadsToNormalizedRects(selectedQuads);

    // Create annotation for each line rect
    for (const rect of rects) {
      store.addAnnotation({
        type: markupType,
        page,
        rect,
        color: store.activeColor,
        opacity: markupType === 'highlight' ? 0.3 : 0.8,
        author,
      });
    }

    // Clear selection after creating annotation
    clearSelection();
  }

  // Check if text-select mode is active (for annotation creation via mouseup)
  const isTextSelectMode = $derived(store.activeTool === 'text-select');

  // TextLayer should capture events only in text-select mode or when no tool is active (for copy)
  const shouldCaptureEvents = $derived(store.activeTool === null || store.activeTool === 'text-select');

  // Context menu handlers
  function handleContextMenu(e: MouseEvent) {
    // Use our custom selection
    if (selectedText) {
      e.preventDefault();
      contextMenu = {
        visible: true,
        x: e.clientX,
        y: e.clientY,
        text: selectedText,
      };
    }
  }

  function closeContextMenu() {
    contextMenu = { visible: false, x: 0, y: 0, text: '' };
  }

  function handleCopy() {
    navigator.clipboard.writeText(contextMenu.text);
    clearSelection();
    closeContextMenu();
  }

  // Default colors for context menu annotations
  const CONTEXT_MENU_COLORS = {
    highlight: '#FFEB3B',   // Yellow
    underline: '#2196F3',   // Blue
    strikethrough: '#F44336', // Red
  };

  function handleHighlight() {
    createMarkupFromSelection('highlight', CONTEXT_MENU_COLORS.highlight);
    clearSelection();
    closeContextMenu();
  }

  function handleUnderline() {
    createMarkupFromSelection('underline', CONTEXT_MENU_COLORS.underline);
    clearSelection();
    closeContextMenu();
  }

  function handleStrikethrough() {
    createMarkupFromSelection('strikethrough', CONTEXT_MENU_COLORS.strikethrough);
    clearSelection();
    closeContextMenu();
  }

  function handleSearchFromMenu() {
    const text = contextMenu.text;
    clearSelection();
    closeContextMenu();
    onSearchText?.(text);
  }

  function createMarkupFromSelection(type: MarkupType, color?: string) {
    // Use our custom selection quads
    if (selectedQuads.length === 0) return;

    const author = getAuthorString() || undefined;
    const annotationColor = color || store.activeColor;

    // Convert quads to normalized rects and merge by line
    const normalizedRects = mergeQuadsToNormalizedRects(selectedQuads);

    for (const rect of normalizedRects) {
      store.addAnnotation({
        type,
        page,
        rect,
        color: annotationColor,
        opacity: type === 'highlight' ? 0.3 : 0.8,
        author,
      });
    }
  }

  // Convert quads to normalized rects (0-1 range) for annotations
  function mergeQuadsToNormalizedRects(quads: { quad: number[] }[]): NormalizedRect[] {
    if (quads.length === 0) return [];

    const rects: NormalizedRect[] = [];
    let currentRect: NormalizedRect | null = null;

    for (const { quad } of quads) {
      const minX = Math.min(quad[0], quad[6]);
      const maxX = Math.max(quad[2], quad[4]);
      const minY = Math.min(quad[1], quad[3]);
      const maxY = Math.max(quad[5], quad[7]);

      if (currentRect && Math.abs(currentRect.y - minY) < 0.005 && Math.abs((currentRect.y + currentRect.height) - maxY) < 0.005) {
        // Same line, extend the rect
        currentRect.width = maxX - currentRect.x;
      } else {
        // New line or first rect
        if (currentRect) rects.push(currentRect);
        currentRect = { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
      }
    }

    if (currentRect) rects.push(currentRect);
    return rects;
  }

  // Close context menu on outside click
  function handleDocumentClick(e: MouseEvent) {
    if (contextMenu.visible) {
      closeContextMenu();
    }
  }

  $effect(() => {
    if (contextMenu.visible) {
      document.addEventListener('click', handleDocumentClick);
      return () => {
        document.removeEventListener('click', handleDocumentClick);
      };
    }
  });

  // Custom double-click handler for precise word selection
  function handleDoubleClick(e: MouseEvent) {
    // Prevent browser's native double-click word selection
    e.preventDefault();
    e.stopPropagation();

    if (!textContent) return;

    const textLayer = e.currentTarget as HTMLElement;
    const layerRect = textLayer.getBoundingClientRect();
    const normX = (e.clientX - layerRect.left) / (pageWidth * scale);
    const normY = (e.clientY - layerRect.top) / (pageHeight * scale);

    // Find which block/line contains this position
    for (let bi = 0; bi < textContent.blocks.length; bi++) {
      const block = textContent.blocks[bi];
      for (let li = 0; li < block.lines.length; li++) {
        const line = block.lines[li];
        if (normY >= line.rect.y - 0.005 && normY <= line.rect.y + line.rect.height + 0.005) {
          // Find character index
          let charIndex = -1;
          for (let ci = 0; ci < line.chars.length; ci++) {
            const char = line.chars[ci];
            const minX = Math.min(char.quad[0], char.quad[2], char.quad[4], char.quad[6]);
            const maxX = Math.max(char.quad[0], char.quad[2], char.quad[4], char.quad[6]);
            if (normX >= minX && normX <= maxX) {
              charIndex = ci;
              break;
            }
          }

          // If not found exactly, find closest
          if (charIndex < 0 && normX >= line.rect.x && normX <= line.rect.x + line.rect.width) {
            let closestDist = Infinity;
            for (let ci = 0; ci < line.chars.length; ci++) {
              const char = line.chars[ci];
              const charCenterX = (char.quad[0] + char.quad[2]) / 2;
              const dist = Math.abs(normX - charCenterX);
              if (dist < closestDist) {
                closestDist = dist;
                charIndex = ci;
              }
            }
          }

          if (charIndex < 0) return;

          // Find word boundaries
          const text = line.text;
          let startIndex = charIndex;
          while (startIndex > 0 && !/\s/.test(text[startIndex - 1])) {
            startIndex--;
          }

          let endIndex = charIndex;
          while (endIndex < text.length - 1 && !/\s/.test(text[endIndex + 1])) {
            endIndex++;
          }

          // Skip if just whitespace
          const word = text.slice(startIndex, endIndex + 1);
          if (!word.trim()) return;

          // Set our custom selection
          setWordSelection(bi, li, startIndex, endIndex);
          return;
        }
      }
    }
  }

  // Convert quad to pixel polygon points for SVG
  function quadToPixelPoints(quad: number[]): string {
    const points = [
      quad[0] * pageWidth * scale, quad[1] * pageHeight * scale,
      quad[2] * pageWidth * scale, quad[3] * pageHeight * scale,
      quad[4] * pageWidth * scale, quad[5] * pageHeight * scale,
      quad[6] * pageWidth * scale, quad[7] * pageHeight * scale,
    ];
    return points.join(',');
  }

  // Merge adjacent quads on same line into rectangles for cleaner rendering
  function mergeQuadsToRects(quads: { quad: number[] }[]): { x: number; y: number; width: number; height: number }[] {
    if (quads.length === 0) return [];

    const rects: { x: number; y: number; width: number; height: number }[] = [];
    let currentRect: { x: number; y: number; width: number; height: number } | null = null;

    for (const { quad } of quads) {
      const minX = Math.min(quad[0], quad[6]) * pageWidth * scale;
      const maxX = Math.max(quad[2], quad[4]) * pageWidth * scale;
      const minY = Math.min(quad[1], quad[3]) * pageHeight * scale;
      const maxY = Math.max(quad[5], quad[7]) * pageHeight * scale;

      if (currentRect && Math.abs(currentRect.y - minY) < 2 && Math.abs((currentRect.y + currentRect.height) - maxY) < 2) {
        // Same line, extend the rect
        currentRect.width = maxX - currentRect.x;
      } else {
        // New line or first rect
        if (currentRect) rects.push(currentRect);
        currentRect = { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
      }
    }

    if (currentRect) rects.push(currentRect);
    return rects;
  }

  // Derived merged selection rects for rendering
  const selectionRects = $derived(mergeQuadsToRects(selectedQuads));
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="absolute inset-0 text-layer"
  data-text-layer-page={page}
  style="
    width: {pageWidth * scale}px;
    height: {pageHeight * scale}px;
    pointer-events: {shouldCaptureEvents ? 'auto' : 'none'};
    user-select: none;
    z-index: {isTextSelectMode ? 20 : 5};
    cursor: {shouldCaptureEvents ? 'text' : 'default'};
  "
  onmousedown={handleMouseDown}
  onmousemove={handleMouseMove}
  onmouseup={(e) => { handleSelectionEnd(); handleMouseUp(e); }}
  oncontextmenu={handleContextMenu}
  ondblclick={handleDoubleClick}
>
  <!-- Custom selection overlay (rendered first, behind text) -->
  {#if selectionRects.length > 0}
    <svg class="absolute inset-0 pointer-events-none" style="width: {pageWidth * scale}px; height: {pageHeight * scale}px;">
      {#each selectionRects as rect}
        <rect
          x={rect.x}
          y={rect.y}
          width={rect.width}
          height={rect.height}
          fill="rgba(0, 120, 215, 0.3)"
        />
      {/each}
    </svg>
  {/if}
  {#if textContent}
    {#each textContent.blocks as block}
      {#each block.lines as line}
        {@const pixelRect = toPixelRect(line.rect)}
        {@const fontSize = pixelRect.height * 0.82}
        <span
          use:scaleToWidth={pixelRect.width}
          class="absolute whitespace-pre text-span"
          style="
            left: {pixelRect.x}px;
            top: {pixelRect.y}px;
            font-size: {fontSize}px;
            line-height: {pixelRect.height}px;
            height: {pixelRect.height}px;
            transform-origin: left top;
          "
        >{line.text}</span>
      {/each}
    {/each}
  {/if}
</div>

<!-- Context menu (rendered outside text layer for proper z-index) -->
<TextContextMenu
  visible={contextMenu.visible}
  x={contextMenu.x}
  y={contextMenu.y}
  selectedText={contextMenu.text}
  onCopy={handleCopy}
  onHighlight={handleHighlight}
  onUnderline={handleUnderline}
  onStrikethrough={handleStrikethrough}
  onSearch={handleSearchFromMenu}
  onClose={closeContextMenu}
/>

<style>
  .text-layer {
    overflow: hidden;
  }

  .text-layer span {
    /* Make text invisible - selection is rendered via our custom SVG overlay */
    color: transparent !important;
    background: transparent !important;
  }

  /* Hide browser's native selection - we use custom SVG overlay */
  .text-layer span::selection {
    background: transparent;
  }

  .text-layer span::-moz-selection {
    background: transparent;
  }
</style>
