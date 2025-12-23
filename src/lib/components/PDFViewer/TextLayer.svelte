<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import type { AnnotationsStore, AnnotationType } from '$lib/stores/annotations.svelte';
  import { getAuthorString } from '$lib/stores/settings.svelte';

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
  }

  let { pdfPath, page, pageWidth, pageHeight, scale = 1, store }: Props = $props();

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

  // Check if text-select mode is active
  const isTextSelectMode = $derived(store.activeTool === 'text-select');
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="absolute inset-0 text-layer"
  data-text-layer-page={page}
  style="
    width: {pageWidth * scale}px;
    height: {pageHeight * scale}px;
    pointer-events: {isTextSelectMode ? 'auto' : 'none'};
    user-select: {isTextSelectMode ? 'text' : 'none'};
    z-index: {isTextSelectMode ? 20 : 5};
    cursor: {isTextSelectMode ? 'text' : 'default'};
  "
  onmouseup={handleMouseUp}
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
