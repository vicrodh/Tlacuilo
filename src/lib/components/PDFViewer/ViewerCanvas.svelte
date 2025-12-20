<script lang="ts">
  import { onMount, onDestroy, untrack } from 'svelte';
  import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist';

  interface Props {
    pdfDoc: PDFDocumentProxy;
    currentPage: number;
    zoom: number;
    rotation: number;
    activeTool: string;
  }

  let {
    pdfDoc,
    currentPage,
    zoom,
    rotation,
    activeTool,
  }: Props = $props();

  let canvasContainer: HTMLDivElement;
  let canvas: HTMLCanvasElement;
  let annotationCanvas: HTMLCanvasElement;
  let isRendering = $state(false);
  let currentRenderTask: any = null;
  let renderVersion = 0; // Track render version to prevent stale renders

  // Render the current page
  async function renderPage(version: number) {
    // Use untrack to prevent isRendering from triggering effect re-runs
    const shouldSkip = untrack(() => isRendering);
    if (!pdfDoc || !canvas || shouldSkip) return;

    // Cancel any ongoing render
    if (currentRenderTask) {
      currentRenderTask.cancel();
      currentRenderTask = null;
    }

    isRendering = true;

    try {
      const page = await pdfDoc.getPage(currentPage);

      // Calculate viewport with zoom and rotation
      const baseViewport = page.getViewport({ scale: 1, rotation });
      const viewport = page.getViewport({ scale: zoom * 1.5, rotation }); // 1.5x for better quality

      // Set canvas dimensions
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.width = `${viewport.width / 1.5}px`;
      canvas.style.height = `${viewport.height / 1.5}px`;

      // Also size annotation canvas
      annotationCanvas.width = viewport.width;
      annotationCanvas.height = viewport.height;
      annotationCanvas.style.width = `${viewport.width / 1.5}px`;
      annotationCanvas.style.height = `${viewport.height / 1.5}px`;

      const context = canvas.getContext('2d');
      if (!context) {
        throw new Error('Could not get canvas context');
      }

      // Clear canvas
      context.fillStyle = 'white';
      context.fillRect(0, 0, canvas.width, canvas.height);

      // Render the page
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      currentRenderTask = page.render({
        canvasContext: context,
        viewport: viewport,
      } as any);
      await currentRenderTask.promise;
      currentRenderTask = null;

    } catch (err: any) {
      if (err?.name !== 'RenderingCancelledException') {
        console.error('Failed to render page:', err);
      }
    } finally {
      isRendering = false;
    }
  }

  // Handle annotation canvas interactions
  let isDrawing = $state(false);
  let lastPoint = $state<{ x: number; y: number } | null>(null);

  function getCanvasPoint(e: MouseEvent): { x: number; y: number } {
    const rect = annotationCanvas.getBoundingClientRect();
    const scaleX = annotationCanvas.width / rect.width;
    const scaleY = annotationCanvas.height / rect.height;
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    };
  }

  function handleMouseDown(e: MouseEvent) {
    if (activeTool === 'pen' || activeTool === 'highlight') {
      isDrawing = true;
      lastPoint = getCanvasPoint(e);
    }
  }

  function handleMouseMove(e: MouseEvent) {
    if (!isDrawing || !lastPoint) return;

    const ctx = annotationCanvas.getContext('2d');
    if (!ctx) return;

    const currentPoint = getCanvasPoint(e);

    ctx.beginPath();
    ctx.moveTo(lastPoint.x, lastPoint.y);
    ctx.lineTo(currentPoint.x, currentPoint.y);

    if (activeTool === 'pen') {
      ctx.strokeStyle = 'rgba(46, 52, 64, 0.9)'; // Nord0
      ctx.lineWidth = 3;
      ctx.lineCap = 'round';
    } else if (activeTool === 'highlight') {
      ctx.strokeStyle = 'rgba(235, 203, 139, 0.4)'; // Nord13 with transparency
      ctx.lineWidth = 20;
      ctx.lineCap = 'round';
    }

    ctx.stroke();
    lastPoint = currentPoint;
  }

  function handleMouseUp() {
    isDrawing = false;
    lastPoint = null;
  }

  // Panning support
  let isPanning = $state(false);
  let panStart = $state<{ x: number; y: number } | null>(null);
  let scrollStart = $state<{ x: number; y: number } | null>(null);

  function handlePanStart(e: MouseEvent) {
    if (activeTool === 'pan' || e.button === 1) { // Middle mouse button
      isPanning = true;
      panStart = { x: e.clientX, y: e.clientY };
      scrollStart = {
        x: canvasContainer.scrollLeft,
        y: canvasContainer.scrollTop,
      };
      e.preventDefault();
    }
  }

  function handlePanMove(e: MouseEvent) {
    if (!isPanning || !panStart || !scrollStart) return;

    const dx = e.clientX - panStart.x;
    const dy = e.clientY - panStart.y;

    canvasContainer.scrollLeft = scrollStart.x - dx;
    canvasContainer.scrollTop = scrollStart.y - dy;
  }

  function handlePanEnd() {
    isPanning = false;
    panStart = null;
    scrollStart = null;
  }

  // Cursor based on tool
  const cursorMap: Record<string, string> = {
    select: 'default',
    pan: 'grab',
    pen: 'crosshair',
    highlight: 'crosshair',
    text: 'text',
    redact: 'crosshair',
    stamp: 'copy',
  };

  $effect(() => {
    // Track dependencies explicitly
    const doc = pdfDoc;
    const page = currentPage;
    const z = zoom;
    const r = rotation;

    // Increment version and render
    renderVersion++;
    const version = renderVersion;
    renderPage(version);
  });

  onMount(() => {
    document.addEventListener('mouseup', handlePanEnd);
    document.addEventListener('mouseup', handleMouseUp);
  });

  onDestroy(() => {
    document.removeEventListener('mouseup', handlePanEnd);
    document.removeEventListener('mouseup', handleMouseUp);
    if (currentRenderTask) {
      currentRenderTask.cancel();
    }
  });
</script>

<div
  bind:this={canvasContainer}
  class="h-full overflow-auto flex items-center justify-center p-4"
  style="background-color: var(--nord0); cursor: {isPanning ? 'grabbing' : cursorMap[activeTool] || 'default'};"
  onmousedown={handlePanStart}
  onmousemove={(e) => { handlePanMove(e); handleMouseMove(e); }}
  role="application"
  aria-label="PDF viewer"
>
  <div class="relative shadow-2xl">
    <!-- Main PDF canvas -->
    <canvas
      bind:this={canvas}
      class="block"
      style="background: white;"
    ></canvas>

    <!-- Annotation overlay canvas -->
    <canvas
      bind:this={annotationCanvas}
      class="absolute top-0 left-0 pointer-events-auto"
      onmousedown={handleMouseDown}
    ></canvas>

    <!-- Loading overlay -->
    {#if isRendering}
      <div class="absolute inset-0 flex items-center justify-center bg-white/50">
        <div class="w-6 h-6 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin"></div>
      </div>
    {/if}
  </div>
</div>
