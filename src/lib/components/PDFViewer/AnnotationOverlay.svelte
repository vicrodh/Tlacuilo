<script lang="ts">
  import { MessageSquare, X } from 'lucide-svelte';
  import {
    type Annotation,
    type AnnotationType,
    type AnnotationsStore,
    type Rect,
  } from '$lib/stores/annotations.svelte';

  interface Props {
    store: AnnotationsStore;
    page: number;
    pageWidth: number;
    pageHeight: number;
    scale?: number;
  }

  let { store, page, pageWidth, pageHeight, scale = 1 }: Props = $props();

  let overlayElement: SVGSVGElement;
  let isDrawing = $state(false);
  let drawStart = $state<{ x: number; y: number } | null>(null);
  let drawRect = $state<Rect | null>(null);
  let editingComment = $state<string | null>(null);
  let commentText = $state('');

  const annotations = $derived(store.getAnnotationsForPage(page));

  function getRelativeCoords(e: MouseEvent): { x: number; y: number } {
    const rect = overlayElement.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) / scale,
      y: (e.clientY - rect.top) / scale,
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

    // Only create annotation if it has meaningful size
    if (drawRect.width > 5 && drawRect.height > 5) {
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
      } else {
        store.addAnnotation({
          type: store.activeTool,
          page,
          rect: drawRect,
          color: store.activeColor,
          opacity: store.activeTool === 'highlight' ? 0.3 : 0.8,
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

  function getAnnotationStyle(annotation: Annotation): string {
    const { rect, color, opacity } = annotation;
    const base = `left: ${rect.x * scale}px; top: ${rect.y * scale}px; width: ${rect.width * scale}px; height: ${rect.height * scale}px;`;

    switch (annotation.type) {
      case 'highlight':
        return `${base} background-color: ${color}; opacity: ${opacity};`;
      case 'underline':
        return `${base} border-bottom: 2px solid ${color};`;
      case 'strikethrough':
        return `${base} background: linear-gradient(transparent 45%, ${color} 45%, ${color} 55%, transparent 55%);`;
      case 'comment':
        return `left: ${rect.x * scale}px; top: ${rect.y * scale}px;`;
      default:
        return base;
    }
  }

  const cursorStyle = $derived(() => {
    if (!store.activeTool) return 'default';
    if (store.activeTool === 'comment') return 'cell';
    return 'crosshair';
  });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<svg
  bind:this={overlayElement}
  class="absolute inset-0 pointer-events-auto"
  style="cursor: {cursorStyle()};"
  width={pageWidth * scale}
  height={pageHeight * scale}
  onmousedown={handleMouseDown}
  onmousemove={handleMouseMove}
  onmouseup={handleMouseUp}
  onmouseleave={() => { isDrawing = false; drawRect = null; }}
>
  <!-- Rendered annotations -->
  {#each annotations as annotation (annotation.id)}
    {#if annotation.type === 'highlight'}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <rect
        x={annotation.rect.x * scale}
        y={annotation.rect.y * scale}
        width={annotation.rect.width * scale}
        height={annotation.rect.height * scale}
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
        x1={annotation.rect.x * scale}
        y1={(annotation.rect.y + annotation.rect.height) * scale}
        x2={(annotation.rect.x + annotation.rect.width) * scale}
        y2={(annotation.rect.y + annotation.rect.height) * scale}
        stroke={annotation.color}
        stroke-width="2"
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
      />
    {:else if annotation.type === 'strikethrough'}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <line
        x1={annotation.rect.x * scale}
        y1={(annotation.rect.y + annotation.rect.height / 2) * scale}
        x2={(annotation.rect.x + annotation.rect.width) * scale}
        y2={(annotation.rect.y + annotation.rect.height / 2) * scale}
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
          x={annotation.rect.x * scale}
          y={annotation.rect.y * scale}
          width="24"
          height="24"
          rx="4"
          fill={annotation.color}
        />
        <foreignObject
          x={annotation.rect.x * scale + 4}
          y={annotation.rect.y * scale + 4}
          width="16"
          height="16"
        >
          <MessageSquare size={16} style="color: white;" />
        </foreignObject>
      </g>
    {/if}
  {/each}

  <!-- Drawing preview -->
  {#if isDrawing && drawRect && store.activeTool}
    {#if store.activeTool === 'highlight'}
      <rect
        x={drawRect.x * scale}
        y={drawRect.y * scale}
        width={drawRect.width * scale}
        height={drawRect.height * scale}
        fill={store.activeColor}
        fill-opacity="0.3"
        stroke={store.activeColor}
        stroke-width="1"
        stroke-dasharray="4"
      />
    {:else if store.activeTool === 'underline'}
      <line
        x1={drawRect.x * scale}
        y1={(drawRect.y + drawRect.height) * scale}
        x2={(drawRect.x + drawRect.width) * scale}
        y2={(drawRect.y + drawRect.height) * scale}
        stroke={store.activeColor}
        stroke-width="2"
        stroke-dasharray="4"
      />
    {:else if store.activeTool === 'strikethrough'}
      <line
        x1={drawRect.x * scale}
        y1={(drawRect.y + drawRect.height / 2) * scale}
        x2={(drawRect.x + drawRect.width) * scale}
        y2={(drawRect.y + drawRect.height / 2) * scale}
        stroke={store.activeColor}
        stroke-width="2"
        stroke-dasharray="4"
      />
    {:else if store.activeTool === 'comment'}
      <rect
        x={drawRect.x * scale}
        y={drawRect.y * scale}
        width={drawRect.width * scale}
        height={drawRect.height * scale}
        fill="none"
        stroke={store.activeColor}
        stroke-width="2"
        stroke-dasharray="4"
      />
    {/if}
  {/if}
</svg>

<!-- Comment edit popup -->
{#if editingComment}
  {@const annotation = annotations.find(a => a.id === editingComment)}
  {#if annotation}
    <div
      class="absolute z-50 p-3 rounded-lg shadow-lg"
      style="
        left: {(annotation.rect.x + annotation.rect.width + 10) * scale}px;
        top: {annotation.rect.y * scale}px;
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

<!-- Selected annotation controls -->
{#if store.selectedId && !editingComment}
  {@const selected = annotations.find(a => a.id === store.selectedId)}
  {#if selected}
    <div
      class="absolute z-40 flex items-center gap-1 p-1 rounded"
      style="
        left: {(selected.rect.x + selected.rect.width) * scale + 4}px;
        top: {selected.rect.y * scale}px;
        background-color: var(--nord1);
        border: 1px solid var(--nord3);
      "
    >
      {#if selected.type === 'comment' && selected.text}
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
