<script lang="ts">
  import { MessageSquare, X } from 'lucide-svelte';
  import {
    type Annotation,
    type AnnotationType,
    type AnnotationsStore,
    type Rect,
    type InkPath,
    type LineStyle,
  } from '$lib/stores/annotations.svelte';

  interface Props {
    store: AnnotationsStore;
    page: number;
    pageWidth: number;
    pageHeight: number;
    scale?: number;
    interactive?: boolean; // Whether to enable drawing/selection
  }

  let { store, page, pageWidth, pageHeight, scale = 1, interactive = true }: Props = $props();

  let overlayElement: SVGSVGElement;
  let isDrawing = $state(false);
  let drawStart = $state<{ x: number; y: number } | null>(null);
  let drawRect = $state<Rect | null>(null);
  let editingComment = $state<string | null>(null);
  let commentText = $state('');

  // Convert ink path points to SVG path data
  function inkPathToSvg(path: InkPath, pageW: number, pageH: number, s: number): string {
    const points = path.points;
    if (!points || points.length < 2) return '';

    // Convert normalized points to pixel coordinates
    const pixelPoints = points.map(p => ({
      x: p.x * pageW * s,
      y: p.y * pageH * s,
    }));

    // Start path
    let d = `M ${pixelPoints[0].x} ${pixelPoints[0].y}`;

    // Use quadratic bezier curves for smooth lines
    for (let i = 1; i < pixelPoints.length; i++) {
      const prev = pixelPoints[i - 1];
      const curr = pixelPoints[i];
      const midX = (prev.x + curr.x) / 2;
      const midY = (prev.y + curr.y) / 2;
      d += ` Q ${prev.x} ${prev.y} ${midX} ${midY}`;
    }

    // End at last point
    const last = pixelPoints[pixelPoints.length - 1];
    d += ` L ${last.x} ${last.y}`;

    return d;
  }

  // Get SVG dash array for line style
  function getDashArray(style: LineStyle | undefined, strokeWidth: number): string {
    if (!style || style === 'solid') return '';
    const sw = Math.max(strokeWidth, 2);
    if (style === 'dashed') return `${sw * 3} ${sw * 2}`;
    if (style === 'dotted') return `${sw} ${sw}`;
    return '';
  }

  // Freetext (typewriter) state
  let editingFreetext = $state<string | null>(null);
  let freetextValue = $state('');
  let freetextInputRef: HTMLTextAreaElement;

  const annotations = $derived(store.getAnnotationsForPage(page));

  // Convert mouse event to NORMALIZED coordinates (0-1)
  // This ensures annotations are zoom-independent
  function getRelativeCoords(e: MouseEvent): { x: number; y: number } {
    const rect = overlayElement.getBoundingClientRect();
    // Get pixel position relative to overlay
    const pixelX = (e.clientX - rect.left) / scale;
    const pixelY = (e.clientY - rect.top) / scale;
    // Convert to normalized (0-1) coordinates
    return {
      x: pixelX / pageWidth,
      y: pixelY / pageHeight,
    };
  }

  // Convert normalized rect to pixel rect for display
  function toPixelRect(rect: Rect): Rect {
    return {
      x: rect.x * pageWidth * scale,
      y: rect.y * pageHeight * scale,
      width: rect.width * pageWidth * scale,
      height: rect.height * pageHeight * scale,
    };
  }

  function handleMouseDown(e: MouseEvent) {
    if (!store.activeTool || e.button !== 0) return;

    // Prevent event from bubbling to container (stops panning/scrolling)
    e.stopPropagation();
    e.preventDefault();

    const coords = getRelativeCoords(e);
    isDrawing = true;
    drawStart = coords;
    drawRect = { x: coords.x, y: coords.y, width: 0, height: 0 };
  }

  function handleMouseMove(e: MouseEvent) {
    if (!isDrawing || !drawStart) return;

    // Prevent event from bubbling during drawing
    e.stopPropagation();

    const coords = getRelativeCoords(e);
    const x = Math.min(drawStart.x, coords.x);
    const y = Math.min(drawStart.y, coords.y);
    const width = Math.abs(coords.x - drawStart.x);
    const height = Math.abs(coords.y - drawStart.y);

    drawRect = { x, y, width, height };
  }

  function handleMouseUp(e: MouseEvent) {
    if (!isDrawing || !drawRect || !store.activeTool) {
      isDrawing = false;
      drawStart = null;
      drawRect = null;
      return;
    }

    // Prevent event from bubbling
    e.stopPropagation();

    // Only create annotation if it has meaningful size (threshold in normalized space)
    // 0.005 = 0.5% of page dimension, roughly 3-4 pixels at typical zoom
    if (drawRect.width > 0.005 && drawRect.height > 0.005) {
      if (store.activeTool === 'comment') {
        // For comments, show input dialog
        const annotation = store.addAnnotation({
          type: 'comment',
          page,
          rect: drawRect,
          color: store.activeColor,
          opacity: 0.8,
          text: '',
        });
        editingComment = annotation.id;
        commentText = '';
      } else if (store.activeTool === 'freetext') {
        // For freetext, create annotation with defined area and show input
        // Default fontsize 12pt matches PyMuPDF default
        const annotation = store.addAnnotation({
          type: 'freetext',
          page,
          rect: drawRect,
          color: store.activeColor,
          opacity: 1,
          text: '',
          fontsize: 12,
        });
        editingFreetext = annotation.id;
        freetextValue = '';
        // Focus input after render
        setTimeout(() => freetextInputRef?.focus(), 0);
      } else if (store.activeTool === 'area-select') {
        // Area selection mode: use pendingMarkupType
        const markupType = store.pendingMarkupType;
        store.addAnnotation({
          type: markupType,
          page,
          rect: drawRect,
          color: store.activeColor,
          opacity: markupType === 'highlight' ? 0.3 : 0.8,
        });
      }
    }

    isDrawing = false;
    drawStart = null;
    drawRect = null;
  }

  function handleAnnotationClick(e: MouseEvent, annotation: Annotation) {
    e.stopPropagation();

    if (!store.activeTool) {
      // Select mode
      store.selectAnnotation(
        store.selectedId === annotation.id ? null : annotation.id
      );
    }
  }

  function handleDeleteAnnotation(id: string) {
    store.deleteAnnotation(id);
  }

  function handleCommentSave(id: string) {
    if (commentText.trim()) {
      store.updateAnnotation(id, { text: commentText });
    } else {
      store.deleteAnnotation(id);
    }
    editingComment = null;
    commentText = '';
  }

  function handleCommentCancel(id: string) {
    if (!store.getAnnotationsForPage(page).find(a => a.id === id)?.text) {
      store.deleteAnnotation(id);
    }
    editingComment = null;
    commentText = '';
  }

  // Freetext handlers
  function handleFreetextSave(id: string) {
    if (freetextValue.trim()) {
      store.updateAnnotation(id, { text: freetextValue });
    } else {
      store.deleteAnnotation(id);
    }
    editingFreetext = null;
    freetextValue = '';
  }

  function handleFreetextCancel(id: string) {
    const ann = store.getAnnotationsForPage(page).find(a => a.id === id);
    if (!ann?.text) {
      store.deleteAnnotation(id);
    }
    editingFreetext = null;
    freetextValue = '';
  }

  function handleFreetextKeydown(e: KeyboardEvent, id: string) {
    if (e.key === 'Escape') {
      handleFreetextCancel(id);
    }
    // Enter without Shift saves
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleFreetextSave(id);
    }
  }

  const cursorStyle = $derived(() => {
    if (!interactive) return 'default';
    if (!store.activeTool) return 'default';
    if (store.activeTool === 'comment') return 'cell';
    if (store.activeTool === 'freetext') return 'text';
    return 'crosshair';
  });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<svg
  bind:this={overlayElement}
  class="absolute inset-0"
  class:pointer-events-auto={interactive}
  class:pointer-events-none={!interactive}
  style="cursor: {cursorStyle()};"
  width={pageWidth * scale}
  height={pageHeight * scale}
  onmousedown={interactive ? handleMouseDown : undefined}
  onmousemove={interactive ? handleMouseMove : undefined}
  onmouseup={interactive ? handleMouseUp : undefined}
  onmouseleave={interactive ? () => { isDrawing = false; drawRect = null; } : undefined}
>
  <!-- Rendered annotations -->
  {#each annotations as annotation (annotation.id)}
    {@const pixelRect = toPixelRect(annotation.rect)}
    {#if annotation.type === 'highlight'}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <rect
        x={pixelRect.x}
        y={pixelRect.y}
        width={pixelRect.width}
        height={pixelRect.height}
        fill={annotation.color}
        fill-opacity={annotation.opacity}
        class="cursor-pointer hover:opacity-80 transition-opacity"
        class:ring-2={store.selectedId === annotation.id}
        onclick={(e) => handleAnnotationClick(e, annotation)}
      />
    {:else if annotation.type === 'underline'}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <line
        x1={pixelRect.x}
        y1={pixelRect.y + pixelRect.height}
        x2={pixelRect.x + pixelRect.width}
        y2={pixelRect.y + pixelRect.height}
        stroke={annotation.color}
        stroke-width="2"
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
      />
    {:else if annotation.type === 'strikethrough'}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <line
        x1={pixelRect.x}
        y1={pixelRect.y + pixelRect.height / 2}
        x2={pixelRect.x + pixelRect.width}
        y2={pixelRect.y + pixelRect.height / 2}
        stroke={annotation.color}
        stroke-width="2"
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
      />
    {:else if annotation.type === 'comment'}
      <!-- Comment marker -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <g
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
      >
        <rect
          x={pixelRect.x}
          y={pixelRect.y}
          width="24"
          height="24"
          rx="4"
          fill={annotation.color}
        />
        <foreignObject
          x={pixelRect.x + 4}
          y={pixelRect.y + 4}
          width="16"
          height="16"
        >
          <MessageSquare size={16} style="color: white;" />
        </foreignObject>
      </g>
    {:else if annotation.type === 'freetext'}
      <!-- Freetext / Typewriter annotation -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      {@const fontSize = (annotation.fontsize || 12) * scale}
      <foreignObject
        x={pixelRect.x}
        y={pixelRect.y}
        width={Math.max(pixelRect.width, 100)}
        height={Math.max(pixelRect.height, fontSize * 1.5)}
        class="cursor-pointer overflow-visible"
        onclick={(e) => handleAnnotationClick(e, annotation)}
      >
        <div
          xmlns="http://www.w3.org/1999/xhtml"
          class="whitespace-pre-wrap"
          style="
            color: {annotation.color};
            font-family: Helvetica, Arial, sans-serif;
            font-size: {fontSize}px;
            line-height: 1.3;
          "
        >
          {annotation.text || ''}
        </div>
      </foreignObject>
    {:else if annotation.type === 'ink' && annotation.paths}
      <!-- Ink/freehand annotation -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <g
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
      >
        {#each annotation.paths as path}
          {@const strokeWidth = (path.strokeWidth || 0.003) * pageWidth * scale}
          <path
            d={inkPathToSvg(path, pageWidth, pageHeight, scale)}
            fill="none"
            stroke={path.color || annotation.color}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
            opacity={annotation.opacity}
          />
        {/each}
      </g>
    {:else if annotation.type === 'rectangle'}
      <!-- Rectangle annotation -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      {@const strokeWidth = (annotation.strokeWidth || 0.002) * pageWidth * scale}
      <rect
        x={pixelRect.x}
        y={pixelRect.y}
        width={pixelRect.width}
        height={pixelRect.height}
        fill={annotation.fill?.enabled ? annotation.fill.color : 'none'}
        fill-opacity={annotation.fill?.enabled ? annotation.fill.opacity : 0}
        stroke={annotation.color}
        stroke-width={strokeWidth}
        stroke-dasharray={getDashArray(annotation.lineStyle, strokeWidth)}
        opacity={annotation.opacity}
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
      />
    {:else if annotation.type === 'ellipse'}
      <!-- Ellipse annotation -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      {@const strokeWidth = (annotation.strokeWidth || 0.002) * pageWidth * scale}
      {@const cx = pixelRect.x + pixelRect.width / 2}
      {@const cy = pixelRect.y + pixelRect.height / 2}
      {@const rx = pixelRect.width / 2}
      {@const ry = pixelRect.height / 2}
      <ellipse
        {cx} {cy} {rx} {ry}
        fill={annotation.fill?.enabled ? annotation.fill.color : 'none'}
        fill-opacity={annotation.fill?.enabled ? annotation.fill.opacity : 0}
        stroke={annotation.color}
        stroke-width={strokeWidth}
        stroke-dasharray={getDashArray(annotation.lineStyle, strokeWidth)}
        opacity={annotation.opacity}
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
      />
    {:else if annotation.type === 'line'}
      <!-- Line annotation -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      {@const strokeWidth = (annotation.strokeWidth || 0.002) * pageWidth * scale}
      <line
        x1={pixelRect.x}
        y1={pixelRect.y}
        x2={pixelRect.x + pixelRect.width}
        y2={pixelRect.y + pixelRect.height}
        stroke={annotation.color}
        stroke-width={strokeWidth}
        stroke-dasharray={getDashArray(annotation.lineStyle, strokeWidth)}
        opacity={annotation.opacity}
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
      />
    {:else if annotation.type === 'arrow'}
      <!-- Arrow annotation -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      {@const strokeWidth = (annotation.strokeWidth || 0.002) * pageWidth * scale}
      {@const arrowId = `arrow-${annotation.id}`}
      {@const hasStartArrow = annotation.startArrow && annotation.startArrow !== 'none'}
      {@const hasEndArrow = annotation.endArrow && annotation.endArrow !== 'none'}
      {@const isClosedStart = annotation.startArrow === 'closed'}
      {@const isClosedEnd = annotation.endArrow === 'closed'}
      <defs>
        {#if hasEndArrow}
          <marker
            id="{arrowId}-end"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto"
          >
            <path
              d="M 0 0 L 10 5 L 0 10 {isClosedEnd ? 'z' : ''}"
              fill={isClosedEnd ? annotation.color : 'none'}
              stroke={annotation.color}
              stroke-width="1"
            />
          </marker>
        {/if}
        {#if hasStartArrow}
          <marker
            id="{arrowId}-start"
            viewBox="0 0 10 10"
            refX="1"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto"
          >
            <path
              d="M 10 0 L 0 5 L 10 10 {isClosedStart ? 'z' : ''}"
              fill={isClosedStart ? annotation.color : 'none'}
              stroke={annotation.color}
              stroke-width="1"
            />
          </marker>
        {/if}
      </defs>
      <line
        x1={pixelRect.x}
        y1={pixelRect.y}
        x2={pixelRect.x + pixelRect.width}
        y2={pixelRect.y + pixelRect.height}
        stroke={annotation.color}
        stroke-width={strokeWidth}
        stroke-dasharray={getDashArray(annotation.lineStyle, strokeWidth)}
        marker-start={hasStartArrow ? `url(#${arrowId}-start)` : undefined}
        marker-end={hasEndArrow ? `url(#${arrowId}-end)` : undefined}
        opacity={annotation.opacity}
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
      />
    {:else if annotation.type === 'sequenceNumber'}
      <!-- Sequence number annotation -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      {@const r = Math.min(pixelRect.width, pixelRect.height) / 2}
      {@const cx = pixelRect.x + pixelRect.width / 2}
      {@const cy = pixelRect.y + pixelRect.height / 2}
      {@const fontSize = r * 1.2}
      <g
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
      >
        <circle
          {cx} {cy} {r}
          fill={annotation.color}
          opacity={annotation.opacity}
        />
        <text
          x={cx}
          y={cy}
          text-anchor="middle"
          dominant-baseline="central"
          fill="white"
          font-size="{fontSize}px"
          font-weight="bold"
          font-family="Helvetica, Arial, sans-serif"
        >
          {annotation.sequenceNumber || 1}
        </text>
      </g>
    {/if}
  {/each}

  <!-- Drawing preview -->
  {#if isDrawing && drawRect && store.activeTool}
    {@const previewRect = toPixelRect(drawRect)}
    {#if store.activeTool === 'area-select' && store.pendingMarkupType === 'highlight'}
      <rect
        x={previewRect.x}
        y={previewRect.y}
        width={previewRect.width}
        height={previewRect.height}
        fill={store.activeColor}
        fill-opacity="0.3"
        stroke={store.activeColor}
        stroke-width="1"
        stroke-dasharray="4"
      />
    {:else if store.activeTool === 'area-select' && store.pendingMarkupType === 'underline'}
      <line
        x1={previewRect.x}
        y1={previewRect.y + previewRect.height}
        x2={previewRect.x + previewRect.width}
        y2={previewRect.y + previewRect.height}
        stroke={store.activeColor}
        stroke-width="2"
        stroke-dasharray="4"
      />
    {:else if store.activeTool === 'area-select' && store.pendingMarkupType === 'strikethrough'}
      <line
        x1={previewRect.x}
        y1={previewRect.y + previewRect.height / 2}
        x2={previewRect.x + previewRect.width}
        y2={previewRect.y + previewRect.height / 2}
        stroke={store.activeColor}
        stroke-width="2"
        stroke-dasharray="4"
      />
    {:else if store.activeTool === 'comment'}
      <rect
        x={previewRect.x}
        y={previewRect.y}
        width={previewRect.width}
        height={previewRect.height}
        fill="none"
        stroke={store.activeColor}
        stroke-width="2"
        stroke-dasharray="4"
      />
    {:else if store.activeTool === 'freetext'}
      <rect
        x={previewRect.x}
        y={previewRect.y}
        width={previewRect.width}
        height={previewRect.height}
        fill="rgba(255,255,255,0.8)"
        stroke={store.activeColor}
        stroke-width="1"
        stroke-dasharray="4"
      />
    {/if}
  {/if}
</svg>

<!-- Comment edit popup -->
{#if editingComment}
  {@const annotation = annotations.find(a => a.id === editingComment)}
  {#if annotation}
    {@const popupRect = toPixelRect(annotation.rect)}
    <div
      class="absolute z-50 p-3 rounded-lg shadow-lg"
      style="
        left: {popupRect.x + popupRect.width + 10}px;
        top: {popupRect.y}px;
        background-color: var(--nord1);
        border: 1px solid var(--nord3);
        min-width: 200px;
      "
    >
      <textarea
        bind:value={commentText}
        class="w-full h-20 px-2 py-1 rounded text-sm resize-none"
        style="background-color: var(--nord2); border: 1px solid var(--nord3);"
        placeholder="Enter comment..."
      ></textarea>
      <div class="flex justify-end gap-2 mt-2">
        <button
          onclick={() => handleCommentCancel(editingComment!)}
          class="px-3 py-1 rounded text-xs hover:bg-[var(--nord2)]"
        >
          Cancel
        </button>
        <button
          onclick={() => handleCommentSave(editingComment!)}
          class="px-3 py-1 rounded text-xs"
          style="background-color: var(--nord8); color: var(--nord0);"
        >
          Save
        </button>
      </div>
    </div>
  {/if}
{/if}

<!-- Freetext edit input -->
{#if editingFreetext}
  {@const annotation = annotations.find(a => a.id === editingFreetext)}
  {#if annotation}
    {@const inputRect = toPixelRect(annotation.rect)}
    {@const editFontSize = (annotation.fontsize || 12) * scale}
    <div
      class="absolute z-50"
      style="
        left: {inputRect.x}px;
        top: {inputRect.y}px;
      "
    >
      <textarea
        bind:this={freetextInputRef}
        bind:value={freetextValue}
        onkeydown={(e) => handleFreetextKeydown(e, editingFreetext!)}
        onblur={() => handleFreetextSave(editingFreetext!)}
        class="px-1 py-0.5 rounded outline-none resize"
        style="
          background-color: rgba(255, 255, 255, 0.95);
          border: 1px solid {annotation.color};
          color: {annotation.color};
          font-family: Helvetica, Arial, sans-serif;
          font-size: {editFontSize}px;
          line-height: 1.3;
          width: {Math.max(inputRect.width, 100)}px;
          height: {Math.max(inputRect.height, editFontSize * 2)}px;
        "
        placeholder="Type here..."
      ></textarea>
      <div class="text-[10px] mt-1 opacity-60" style="color: var(--nord4);">
        Enter to save, Shift+Enter for new line, Esc to cancel
      </div>
    </div>
  {/if}
{/if}

<!-- Selected annotation controls -->
{#if store.selectedId && !editingComment && !editingFreetext}
  {@const selected = annotations.find(a => a.id === store.selectedId)}
  {#if selected}
    {@const selectedRect = toPixelRect(selected.rect)}
    <div
      class="absolute z-40 flex items-center gap-1 p-1 rounded"
      style="
        left: {selectedRect.x + selectedRect.width + 4}px;
        top: {selectedRect.y}px;
        background-color: var(--nord1);
        border: 1px solid var(--nord3);
      "
    >
      {#if (selected.type === 'comment' || selected.type === 'freetext') && selected.text}
        <div
          class="px-2 py-1 text-xs max-w-[200px]"
          style="color: var(--nord4);"
        >
          {selected.text}
        </div>
      {/if}
      <button
        onclick={() => handleDeleteAnnotation(store.selectedId!)}
        class="p-1 rounded hover:bg-[var(--nord11)] hover:text-white transition-colors"
        title="Delete annotation"
      >
        <X size={14} />
      </button>
    </div>
  {/if}
{/if}
