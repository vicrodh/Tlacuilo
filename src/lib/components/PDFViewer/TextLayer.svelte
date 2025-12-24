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

  // Load text content when page changes
  $effect(() => {
    loadTextContent(pdfPath, page);
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

  // Handle text selection end
  function handleMouseUp() {
    // Only capture selection in text-select mode
    if (store.activeTool !== 'text-select') {
      return;
    }

    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return;

    const rects = getSelectionRects(selection);
    if (rects.length === 0) return;

    // Get the pending markup type (defaults to highlight)
    const markupType = store.pendingMarkupType;
    const author = getAuthorString() || undefined;

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
    selection.removeAllRanges();
  }

  // Get normalized rectangles from selection
  function getSelectionRects(selection: Selection): NormalizedRect[] {
    const rects: NormalizedRect[] = [];
    const range = selection.getRangeAt(0);

    // Get all client rects (one per line of selection)
    const clientRects = range.getClientRects();

    // Get the text layer element to calculate relative positions
    const textLayer = document.querySelector(`[data-text-layer-page="${page}"]`);
    if (!textLayer) return rects;

    const layerRect = textLayer.getBoundingClientRect();

    // Padding: ~0.2 of average character width (roughly 0.002 normalized = ~1-2px)
    const paddingX = 0.002;

    for (let i = 0; i < clientRects.length; i++) {
      const rect = clientRects[i];

      // Calculate position relative to the text layer
      const relX = rect.left - layerRect.left;
      const relY = rect.top - layerRect.top;

      // Convert to normalized coordinates (accounting for scale)
      let normalizedRect: NormalizedRect = {
        x: relX / (pageWidth * scale),
        y: relY / (pageHeight * scale),
        width: rect.width / (pageWidth * scale),
        height: rect.height / (pageHeight * scale),
      };

      // Add symmetric padding on both sides
      normalizedRect = {
        x: Math.max(0, normalizedRect.x - paddingX),
        y: normalizedRect.y,
        width: normalizedRect.width + paddingX * 2,
        height: normalizedRect.height,
      };

      // Only add if it has meaningful size
      if (normalizedRect.width > 0.001 && normalizedRect.height > 0.001) {
        rects.push(normalizedRect);
      }
    }

    // Merge adjacent rects on the same line
    return mergeRects(rects);
  }

  // Merge rectangles that are on the same line
  function mergeRects(rects: NormalizedRect[]): NormalizedRect[] {
    if (rects.length <= 1) return rects;

    // Sort by y position
    const sorted = [...rects].sort((a, b) => a.y - b.y);
    const merged: NormalizedRect[] = [];

    let current = sorted[0];
    for (let i = 1; i < sorted.length; i++) {
      const next = sorted[i];

      // Check if on same line (similar y and height)
      const sameLineThreshold = 0.01; // 1% of page height
      if (Math.abs(next.y - current.y) < sameLineThreshold &&
          Math.abs(next.height - current.height) < sameLineThreshold) {
        // Merge: extend current to include next
        const newX = Math.min(current.x, next.x);
        const newRight = Math.max(current.x + current.width, next.x + next.width);
        current = {
          x: newX,
          y: Math.min(current.y, next.y),
          width: newRight - newX,
          height: Math.max(current.height, next.height),
        };
      } else {
        merged.push(current);
        current = next;
      }
    }
    merged.push(current);

    return merged;
  }

  // Check if text-select mode is active (for annotation creation via mouseup)
  const isTextSelectMode = $derived(store.activeTool === 'text-select');

  // Context menu handlers
  function handleContextMenu(e: MouseEvent) {
    const selection = window.getSelection();
    if (selection && !selection.isCollapsed) {
      e.preventDefault();
      contextMenu = {
        visible: true,
        x: e.clientX,
        y: e.clientY,
        text: selection.toString(),
      };
    }
  }

  function closeContextMenu() {
    contextMenu = { visible: false, x: 0, y: 0, text: '' };
  }

  function handleCopy() {
    navigator.clipboard.writeText(contextMenu.text);
    window.getSelection()?.removeAllRanges();
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
    closeContextMenu();
  }

  function handleUnderline() {
    createMarkupFromSelection('underline', CONTEXT_MENU_COLORS.underline);
    closeContextMenu();
  }

  function handleStrikethrough() {
    createMarkupFromSelection('strikethrough', CONTEXT_MENU_COLORS.strikethrough);
    closeContextMenu();
  }

  function handleSearchFromMenu() {
    const text = contextMenu.text;
    window.getSelection()?.removeAllRanges();
    closeContextMenu();
    onSearchText?.(text);
  }

  function createMarkupFromSelection(type: MarkupType, color?: string) {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return;

    const rects = getSelectionRects(selection);
    if (rects.length === 0) return;

    const author = getAuthorString() || undefined;
    const annotationColor = color || store.activeColor;

    for (const rect of rects) {
      store.addAnnotation({
        type,
        page,
        rect,
        color: annotationColor,
        opacity: type === 'highlight' ? 0.3 : 0.8,
        author,
      });
    }

    selection.removeAllRanges();
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
    // Prevent browser's native double-click word selection immediately
    e.preventDefault();
    e.stopPropagation();

    if (!textContent) return;

    // Get click position relative to the text layer
    const textLayer = document.querySelector(`[data-text-layer-page="${page}"]`);
    if (!textLayer) return;

    const layerRect = textLayer.getBoundingClientRect();
    const clickX = (e.clientX - layerRect.left) / (pageWidth * scale);
    const clickY = (e.clientY - layerRect.top) / (pageHeight * scale);

    // Find the character at click position
    let foundLine: TextLineInfo | null = null;
    let foundCharIndex = -1;

    for (const block of textContent.blocks) {
      for (const line of block.lines) {
        // Check if click is within line bounds (with some tolerance)
        if (clickY >= line.rect.y - 0.005 && clickY <= line.rect.y + line.rect.height + 0.005) {
          // Search through characters in this line
          for (let i = 0; i < line.chars.length; i++) {
            const char = line.chars[i];
            // Quad: [x0,y0, x1,y1, x2,y2, x3,y3] - corners of the character
            const minX = Math.min(char.quad[0], char.quad[2], char.quad[4], char.quad[6]);
            const maxX = Math.max(char.quad[0], char.quad[2], char.quad[4], char.quad[6]);
            const minY = Math.min(char.quad[1], char.quad[3], char.quad[5], char.quad[7]);
            const maxY = Math.max(char.quad[1], char.quad[3], char.quad[5], char.quad[7]);

            if (clickX >= minX && clickX <= maxX && clickY >= minY && clickY <= maxY) {
              foundLine = line;
              foundCharIndex = i;
              break;
            }
          }
          if (foundLine) break;

          // If we're in the line but didn't find exact char, find closest
          if (clickX >= line.rect.x && clickX <= line.rect.x + line.rect.width) {
            foundLine = line;
            // Find closest character by X position
            let closestDist = Infinity;
            for (let i = 0; i < line.chars.length; i++) {
              const char = line.chars[i];
              const charCenterX = (char.quad[0] + char.quad[2]) / 2;
              const dist = Math.abs(clickX - charCenterX);
              if (dist < closestDist) {
                closestDist = dist;
                foundCharIndex = i;
              }
            }
            break;
          }
        }
      }
      if (foundLine) break;
    }

    if (!foundLine || foundCharIndex < 0) return;

    // Find word boundaries (like Okular does)
    const text = foundLine.text;

    // Expand backwards to find start of word
    let startIndex = foundCharIndex;
    while (startIndex > 0) {
      const prevChar = text[startIndex - 1];
      if (/\s/.test(prevChar)) break;
      startIndex--;
    }

    // Expand forwards to find end of word
    let endIndex = foundCharIndex;
    while (endIndex < text.length - 1) {
      const nextChar = text[endIndex + 1];
      if (/\s/.test(nextChar)) break;
      endIndex++;
    }

    // Get the word
    const word = text.slice(startIndex, endIndex + 1);
    if (!word.trim()) return;

    // Find the span element for this line and select the word
    const spans = textLayer.querySelectorAll('.text-span');
    let targetSpan: Element | null = null;

    // Find the span that contains this line's text
    for (const span of spans) {
      if (span.textContent === text) {
        targetSpan = span;
        break;
      }
    }

    if (!targetSpan) return;

    // Create a range for the word
    const range = document.createRange();
    const textNode = targetSpan.firstChild;
    if (!textNode || textNode.nodeType !== Node.TEXT_NODE) return;

    try {
      range.setStart(textNode, startIndex);
      range.setEnd(textNode, endIndex + 1);

      // Set the selection
      const selection = window.getSelection();
      if (selection) {
        selection.removeAllRanges();
        selection.addRange(range);
      }
    } catch {
      // If range setting fails, silently ignore
    }
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="absolute inset-0 text-layer"
  data-text-layer-page={page}
  style="
    width: {pageWidth * scale}px;
    height: {pageHeight * scale}px;
    pointer-events: auto;
    user-select: text;
    z-index: {isTextSelectMode ? 20 : 5};
    cursor: text;
  "
  onmouseup={handleMouseUp}
  oncontextmenu={handleContextMenu}
  ondblclick={handleDoubleClick}
>
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
    /* Make text invisible but selectable */
    color: transparent !important;
    background: transparent !important;
  }

  .text-layer span::selection {
    background: rgba(0, 120, 215, 0.3);
  }

  .text-layer span::-moz-selection {
    background: rgba(0, 120, 215, 0.3);
  }
</style>
