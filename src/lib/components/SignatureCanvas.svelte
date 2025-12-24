<script lang="ts">
  import { Eraser, Undo2, Download } from 'lucide-svelte';
  import { onMount, onDestroy } from 'svelte';

  interface Props {
    width?: number;
    height?: number;
    strokeColor?: string;
    strokeWidth?: number;
    onSave?: (dataUrl: string) => void;
  }

  let {
    width = 500,
    height = 200,
    strokeColor = '#2E3440',
    strokeWidth = 2.5,
    onSave
  }: Props = $props();

  let canvasEl: HTMLCanvasElement;
  let ctx: CanvasRenderingContext2D | null = null;
  let isDrawing = $state(false);
  let hasContent = $state(false);
  let lastX = 0;
  let lastY = 0;

  // History for undo
  let history: ImageData[] = [];
  const MAX_HISTORY = 20;

  onMount(() => {
    ctx = canvasEl.getContext('2d');
    if (ctx) {
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = strokeWidth;
      clearCanvas();
    }
  });

  function saveToHistory() {
    if (!ctx) return;
    const imageData = ctx.getImageData(0, 0, canvasEl.width, canvasEl.height);
    history.push(imageData);
    if (history.length > MAX_HISTORY) {
      history.shift();
    }
  }

  function getCoords(e: MouseEvent | TouchEvent): { x: number; y: number } {
    const rect = canvasEl.getBoundingClientRect();
    const scaleX = canvasEl.width / rect.width;
    const scaleY = canvasEl.height / rect.height;

    if ('touches' in e) {
      const touch = e.touches[0];
      return {
        x: (touch.clientX - rect.left) * scaleX,
        y: (touch.clientY - rect.top) * scaleY
      };
    }
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY
    };
  }

  function startDrawing(e: MouseEvent | TouchEvent) {
    if (!ctx) return;
    e.preventDefault();

    saveToHistory();
    isDrawing = true;
    const { x, y } = getCoords(e);
    lastX = x;
    lastY = y;

    // Draw a dot for single clicks
    ctx.beginPath();
    ctx.arc(x, y, strokeWidth / 2, 0, Math.PI * 2);
    ctx.fillStyle = strokeColor;
    ctx.fill();
    hasContent = true;
  }

  function draw(e: MouseEvent | TouchEvent) {
    if (!isDrawing || !ctx) return;
    e.preventDefault();

    const { x, y } = getCoords(e);

    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(x, y);
    ctx.stroke();

    lastX = x;
    lastY = y;
    hasContent = true;
  }

  function stopDrawing() {
    isDrawing = false;
  }

  export function clearCanvas() {
    if (!ctx) return;
    saveToHistory();
    ctx.fillStyle = 'transparent';
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
    hasContent = false;
  }

  export function undo() {
    if (!ctx || history.length === 0) return;
    const previous = history.pop();
    if (previous) {
      ctx.putImageData(previous, 0, 0);
      hasContent = !isCanvasEmpty();
    }
  }

  function isCanvasEmpty(): boolean {
    if (!ctx) return true;
    const imageData = ctx.getImageData(0, 0, canvasEl.width, canvasEl.height);
    const data = imageData.data;
    for (let i = 3; i < data.length; i += 4) {
      if (data[i] !== 0) return false;
    }
    return true;
  }

  export function getSignatureDataUrl(): string | null {
    if (!hasContent) return null;

    // Create a trimmed version of the signature
    const trimmed = getTrimmedCanvas();
    return trimmed?.toDataURL('image/png') ?? null;
  }

  function getTrimmedCanvas(): HTMLCanvasElement | null {
    if (!ctx) return null;

    const imageData = ctx.getImageData(0, 0, canvasEl.width, canvasEl.height);
    const data = imageData.data;

    let minX = canvasEl.width;
    let minY = canvasEl.height;
    let maxX = 0;
    let maxY = 0;

    for (let y = 0; y < canvasEl.height; y++) {
      for (let x = 0; x < canvasEl.width; x++) {
        const alpha = data[(y * canvasEl.width + x) * 4 + 3];
        if (alpha > 0) {
          minX = Math.min(minX, x);
          minY = Math.min(minY, y);
          maxX = Math.max(maxX, x);
          maxY = Math.max(maxY, y);
        }
      }
    }

    if (minX >= maxX || minY >= maxY) return null;

    // Add padding
    const padding = 10;
    minX = Math.max(0, minX - padding);
    minY = Math.max(0, minY - padding);
    maxX = Math.min(canvasEl.width, maxX + padding);
    maxY = Math.min(canvasEl.height, maxY + padding);

    const trimmedWidth = maxX - minX;
    const trimmedHeight = maxY - minY;

    const trimmedCanvas = document.createElement('canvas');
    trimmedCanvas.width = trimmedWidth;
    trimmedCanvas.height = trimmedHeight;
    const trimmedCtx = trimmedCanvas.getContext('2d');

    if (trimmedCtx) {
      trimmedCtx.drawImage(
        canvasEl,
        minX, minY, trimmedWidth, trimmedHeight,
        0, 0, trimmedWidth, trimmedHeight
      );
    }

    return trimmedCanvas;
  }

  function handleSave() {
    const dataUrl = getSignatureDataUrl();
    if (dataUrl) {
      onSave?.(dataUrl);
    }
  }
</script>

<div class="signature-canvas-wrapper">
  <canvas
    bind:this={canvasEl}
    {width}
    {height}
    class="signature-canvas"
    onmousedown={startDrawing}
    onmousemove={draw}
    onmouseup={stopDrawing}
    onmouseleave={stopDrawing}
    ontouchstart={startDrawing}
    ontouchmove={draw}
    ontouchend={stopDrawing}
  ></canvas>

  <div class="canvas-controls">
    <button
      onclick={undo}
      disabled={history.length === 0}
      class="control-btn"
      title="Undo"
    >
      <Undo2 size={16} />
    </button>
    <button
      onclick={clearCanvas}
      disabled={!hasContent}
      class="control-btn"
      title="Clear"
    >
      <Eraser size={16} />
    </button>
    {#if onSave}
      <button
        onclick={handleSave}
        disabled={!hasContent}
        class="control-btn save"
        title="Save to library"
      >
        <Download size={16} />
        <span>Save</span>
      </button>
    {/if}
  </div>
</div>

<style>
  .signature-canvas-wrapper {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .signature-canvas {
    width: 100%;
    height: auto;
    background-color: var(--nord6);
    border-radius: 0.5rem;
    cursor: crosshair;
    touch-action: none;
  }

  .canvas-controls {
    display: flex;
    gap: 0.5rem;
  }

  .control-btn {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    border-radius: 0.5rem;
    font-size: 0.875rem;
    background-color: var(--nord2);
    color: var(--nord5);
    transition: all 0.15s ease;
  }

  .control-btn:hover:not(:disabled) {
    background-color: var(--nord3);
  }

  .control-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .control-btn.save {
    background-color: var(--nord10);
    color: var(--nord6);
    margin-left: auto;
  }

  .control-btn.save:hover:not(:disabled) {
    background-color: var(--nord9);
  }
</style>
