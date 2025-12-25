<script lang="ts">
  import {
    EyeOff,
    FileUp,
    Trash2,
    CheckCircle,
    AlertTriangle,
    Download,
    RefreshCw,
    Plus,
    X,
    ZoomIn,
    ZoomOut,
  } from 'lucide-svelte';
  import { invoke } from '@tauri-apps/api/core';
  import { open, save } from '@tauri-apps/plugin-dialog';

  interface RedactionMark {
    id: string;
    page: number;
    x0: number;
    y0: number;
    x1: number;
    y1: number;
    applied: boolean;
  }

  interface RenderedPage {
    data: string;
    width: number;
    height: number;
    page: number;
  }

  let filePath = $state<string | null>(null);
  let fileName = $state('');
  let totalPages = $state(0);
  let currentPage = $state(0);
  let pageImage = $state<RenderedPage | null>(null);
  let zoom = $state(1);

  let redactionMarks = $state<RedactionMark[]>([]);
  let isDrawing = $state(false);
  let drawStart = $state<{ x: number; y: number } | null>(null);
  let currentRect = $state<{ x: number; y: number; w: number; h: number } | null>(null);

  let isLoading = $state(false);
  let isApplying = $state(false);
  let error = $state<string | null>(null);
  let successMessage = $state<string | null>(null);

  let canvasContainer: HTMLDivElement;

  async function selectFile() {
    const selected = await open({
      multiple: false,
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });

    if (selected) {
      filePath = selected;
      fileName = selected.split('/').pop() || selected;
      error = null;
      successMessage = null;
      redactionMarks = [];
      await loadDocument();
    }
  }

  async function loadDocument() {
    if (!filePath) return;

    isLoading = true;
    try {
      const info = await invoke<{ total_pages: number }>('pdf_info', { path: filePath });
      totalPages = info.total_pages;
      currentPage = 0;
      await renderPage(0);
    } catch (err) {
      error = String(err);
    } finally {
      isLoading = false;
    }
  }

  async function renderPage(page: number) {
    if (!filePath) return;

    isLoading = true;
    try {
      const result = await invoke<RenderedPage>('render_page', {
        path: filePath,
        page,
        scale: 2.0 * zoom,
      });
      pageImage = result;
      currentPage = page;
    } catch (err) {
      error = String(err);
    } finally {
      isLoading = false;
    }
  }

  function handleMouseDown(e: MouseEvent) {
    if (!pageImage) return;

    const rect = (e.target as HTMLElement).getBoundingClientRect();
    const x = (e.clientX - rect.left) / zoom;
    const y = (e.clientY - rect.top) / zoom;

    isDrawing = true;
    drawStart = { x, y };
    currentRect = { x, y, w: 0, h: 0 };
  }

  function handleMouseMove(e: MouseEvent) {
    if (!isDrawing || !drawStart || !pageImage) return;

    const rect = (e.target as HTMLElement).getBoundingClientRect();
    const x = (e.clientX - rect.left) / zoom;
    const y = (e.clientY - rect.top) / zoom;

    const w = x - drawStart.x;
    const h = y - drawStart.y;

    currentRect = {
      x: w >= 0 ? drawStart.x : x,
      y: h >= 0 ? drawStart.y : y,
      w: Math.abs(w),
      h: Math.abs(h),
    };
  }

  function handleMouseUp() {
    if (!isDrawing || !currentRect || !pageImage) {
      isDrawing = false;
      drawStart = null;
      currentRect = null;
      return;
    }

    // Only add if it's a reasonable size
    if (currentRect.w > 10 && currentRect.h > 10) {
      // Convert screen coordinates to PDF coordinates
      // PDF coordinates have origin at bottom-left, screen at top-left
      const scale = 2.0 * zoom;
      const pdfWidth = pageImage.width / scale;
      const pdfHeight = pageImage.height / scale;

      // Convert Y coordinate (flip)
      const screenY0 = currentRect.y;
      const screenY1 = currentRect.y + currentRect.h;

      const x0 = (currentRect.x / zoom) * (72 / 72); // Already in points-like units
      const x1 = ((currentRect.x + currentRect.w) / zoom) * (72 / 72);

      // Flip Y for PDF coordinates
      const y0 = ((pdfHeight * zoom - screenY1) / zoom) * (72 / 72);
      const y1 = ((pdfHeight * zoom - screenY0) / zoom) * (72 / 72);

      const mark: RedactionMark = {
        id: crypto.randomUUID(),
        page: currentPage,
        x0: currentRect.x * (72 / 72), // Keep screen coords for display
        y0: currentRect.y * (72 / 72),
        x1: (currentRect.x + currentRect.w) * (72 / 72),
        y1: (currentRect.y + currentRect.h) * (72 / 72),
        applied: false,
      };

      redactionMarks = [...redactionMarks, mark];
    }

    isDrawing = false;
    drawStart = null;
    currentRect = null;
  }

  function removeRedactionMark(id: string) {
    redactionMarks = redactionMarks.filter((m) => m.id !== id);
  }

  function clearAllMarks() {
    redactionMarks = [];
  }

  async function applyRedactions() {
    if (!filePath || redactionMarks.length === 0) return;

    const outputPath = await save({
      defaultPath: filePath.replace('.pdf', '_redacted.pdf'),
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });

    if (!outputPath) return;

    isApplying = true;
    error = null;
    successMessage = null;

    try {
      // First, add all redaction marks to the PDF
      let tempPath = filePath;

      for (let i = 0; i < redactionMarks.length; i++) {
        const mark = redactionMarks[i];
        const isLast = i === redactionMarks.length - 1;

        // For intermediate saves, use a temp approach
        const targetPath = isLast ? filePath + '.temp' : filePath + '.temp';

        await invoke('pdf_add_redaction', {
          input: tempPath,
          output: targetPath,
          page: mark.page,
          x0: mark.x0,
          y0: mark.y0,
          x1: mark.x1,
          y1: mark.y1,
        });

        tempPath = targetPath;
      }

      // Now apply all redactions
      const result = await invoke<{
        success: boolean;
        message: string;
        redactions_applied: number;
      }>('pdf_apply_redactions', {
        input: tempPath,
        output: outputPath,
        redactImages: true,
        redactGraphics: true,
      });

      if (result.success) {
        successMessage = `Redacted ${result.redactions_applied} area(s). Saved to ${outputPath.split('/').pop()}`;
        redactionMarks = redactionMarks.map((m) => ({ ...m, applied: true }));
      } else {
        error = result.message;
      }
    } catch (err) {
      error = String(err);
    } finally {
      isApplying = false;
    }
  }

  function zoomIn() {
    zoom = Math.min(3, zoom + 0.25);
    if (filePath) renderPage(currentPage);
  }

  function zoomOut() {
    zoom = Math.max(0.5, zoom - 0.25);
    if (filePath) renderPage(currentPage);
  }

  function prevPage() {
    if (currentPage > 0) renderPage(currentPage - 1);
  }

  function nextPage() {
    if (currentPage < totalPages - 1) renderPage(currentPage + 1);
  }

  // Filter marks for current page
  let currentPageMarks = $derived(redactionMarks.filter((m) => m.page === currentPage));
</script>

<div class="flex flex-col h-full" style="background-color: var(--nord0);">
  <!-- Header -->
  <div
    class="flex items-center justify-between px-4 py-3 border-b"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <div class="flex items-center gap-3">
      <div class="p-2 rounded-lg" style="background-color: var(--nord11);">
        <EyeOff size={20} style="color: var(--nord6);" />
      </div>
      <div>
        <h1 class="text-lg font-semibold" style="color: var(--nord6);">Redact PDF</h1>
        <p class="text-xs opacity-60">Permanently remove sensitive content</p>
      </div>
    </div>

    {#if filePath}
      <div class="flex items-center gap-2">
        <button
          onclick={zoomOut}
          class="p-2 rounded hover:bg-[var(--nord2)] transition-colors"
          title="Zoom Out"
        >
          <ZoomOut size={18} />
        </button>
        <span class="text-sm opacity-60">{Math.round(zoom * 100)}%</span>
        <button
          onclick={zoomIn}
          class="p-2 rounded hover:bg-[var(--nord2)] transition-colors"
          title="Zoom In"
        >
          <ZoomIn size={18} />
        </button>
      </div>
    {/if}
  </div>

  <!-- Alerts -->
  {#if error}
    <div
      class="mx-4 mt-4 p-3 rounded-lg flex items-center gap-2"
      style="background-color: rgba(191, 97, 106, 0.15); border: 1px solid var(--nord11);"
    >
      <AlertTriangle size={16} style="color: var(--nord11);" />
      <span class="text-sm" style="color: var(--nord11);">{error}</span>
      <button onclick={() => (error = null)} class="ml-auto p-1 hover:opacity-70">
        <X size={14} style="color: var(--nord11);" />
      </button>
    </div>
  {/if}

  {#if successMessage}
    <div
      class="mx-4 mt-4 p-3 rounded-lg flex items-center gap-2"
      style="background-color: rgba(163, 190, 140, 0.15); border: 1px solid var(--nord14);"
    >
      <CheckCircle size={16} style="color: var(--nord14);" />
      <span class="text-sm" style="color: var(--nord14);">{successMessage}</span>
      <button onclick={() => (successMessage = null)} class="ml-auto p-1 hover:opacity-70">
        <X size={14} style="color: var(--nord14);" />
      </button>
    </div>
  {/if}

  <!-- Main Content -->
  <div class="flex-1 flex overflow-hidden">
    {#if !filePath}
      <!-- File Selection -->
      <div class="flex-1 flex items-center justify-center p-8">
        <button
          onclick={selectFile}
          class="flex flex-col items-center gap-4 p-8 rounded-xl border-2 border-dashed transition-all hover:border-[var(--nord8)] hover:bg-[var(--nord1)]"
          style="border-color: var(--nord3);"
        >
          <div class="p-4 rounded-full" style="background-color: var(--nord1);">
            <FileUp size={32} style="color: var(--nord8);" />
          </div>
          <div class="text-center">
            <p class="text-lg font-medium" style="color: var(--nord6);">Select PDF to Redact</p>
            <p class="text-sm opacity-50 mt-1">Click to choose a file</p>
          </div>
        </button>
      </div>
    {:else}
      <!-- PDF Viewer with Redaction Overlay -->
      <div class="flex-1 flex flex-col overflow-hidden">
        <!-- Page Navigation -->
        <div
          class="flex items-center justify-center gap-4 px-4 py-2 border-b"
          style="background-color: var(--nord1); border-color: var(--nord3);"
        >
          <button
            onclick={prevPage}
            disabled={currentPage === 0}
            class="px-3 py-1 rounded text-sm transition-colors disabled:opacity-30"
            style="background-color: var(--nord2);"
          >
            Previous
          </button>
          <span class="text-sm">
            Page {currentPage + 1} of {totalPages}
          </span>
          <button
            onclick={nextPage}
            disabled={currentPage >= totalPages - 1}
            class="px-3 py-1 rounded text-sm transition-colors disabled:opacity-30"
            style="background-color: var(--nord2);"
          >
            Next
          </button>
        </div>

        <!-- Canvas Area -->
        <div
          bind:this={canvasContainer}
          class="flex-1 overflow-auto flex items-center justify-center p-4"
          style="background-color: var(--nord0);"
        >
          {#if isLoading}
            <div class="flex items-center gap-2 text-sm opacity-50">
              <RefreshCw size={16} class="animate-spin" />
              <span>Loading...</span>
            </div>
          {:else if pageImage}
            <div
              class="relative shadow-xl cursor-crosshair"
              style="width: {pageImage.width / 2}px; height: {pageImage.height / 2}px;"
              role="application"
              aria-label="PDF page for redaction"
              onmousedown={handleMouseDown}
              onmousemove={handleMouseMove}
              onmouseup={handleMouseUp}
              onmouseleave={handleMouseUp}
            >
              <img
                src={`data:image/png;base64,${pageImage.data}`}
                alt="PDF page {currentPage + 1}"
                class="w-full h-full pointer-events-none select-none"
                draggable="false"
              />

              <!-- Existing Redaction Marks -->
              {#each currentPageMarks as mark (mark.id)}
                <div
                  class="absolute border-2 pointer-events-none"
                  style="
                    left: {mark.x0 * zoom}px;
                    top: {mark.y0 * zoom}px;
                    width: {(mark.x1 - mark.x0) * zoom}px;
                    height: {(mark.y1 - mark.y0) * zoom}px;
                    background-color: rgba(191, 97, 106, 0.3);
                    border-color: var(--nord11);
                  "
                >
                  <button
                    class="absolute -top-2 -right-2 p-0.5 rounded-full pointer-events-auto hover:opacity-80"
                    style="background-color: var(--nord11);"
                    onclick={() => removeRedactionMark(mark.id)}
                  >
                    <X size={12} style="color: var(--nord6);" />
                  </button>
                </div>
              {/each}

              <!-- Current Drawing -->
              {#if currentRect}
                <div
                  class="absolute border-2 border-dashed pointer-events-none"
                  style="
                    left: {currentRect.x * zoom}px;
                    top: {currentRect.y * zoom}px;
                    width: {currentRect.w * zoom}px;
                    height: {currentRect.h * zoom}px;
                    background-color: rgba(191, 97, 106, 0.2);
                    border-color: var(--nord11);
                  "
                ></div>
              {/if}
            </div>
          {/if}
        </div>
      </div>

      <!-- Sidebar with Marks List -->
      <div
        class="w-64 border-l flex flex-col"
        style="background-color: var(--nord1); border-color: var(--nord3);"
      >
        <div class="p-3 border-b" style="border-color: var(--nord3);">
          <h3 class="font-medium text-sm">Redaction Marks</h3>
          <p class="text-xs opacity-50 mt-1">{redactionMarks.length} area(s) marked</p>
        </div>

        <div class="flex-1 overflow-auto p-2 space-y-1">
          {#if redactionMarks.length === 0}
            <p class="text-xs opacity-40 text-center py-4">
              Draw rectangles on the PDF to mark areas for redaction
            </p>
          {:else}
            {#each redactionMarks as mark, i (mark.id)}
              <div
                class="p-2 rounded text-xs flex items-center gap-2"
                style="background-color: var(--nord2);"
              >
                <EyeOff size={12} style="color: var(--nord11);" />
                <span class="flex-1">
                  Page {mark.page + 1}, Area {i + 1}
                </span>
                <button
                  onclick={() => removeRedactionMark(mark.id)}
                  class="p-1 rounded hover:bg-[var(--nord3)] transition-colors"
                >
                  <Trash2 size={12} style="color: var(--nord11);" />
                </button>
              </div>
            {/each}
          {/if}
        </div>

        <!-- Actions -->
        <div class="p-3 border-t space-y-2" style="border-color: var(--nord3);">
          {#if redactionMarks.length > 0}
            <button
              onclick={clearAllMarks}
              class="w-full flex items-center justify-center gap-2 px-3 py-2 rounded text-sm transition-colors hover:bg-[var(--nord2)]"
              style="background-color: var(--nord3);"
            >
              <Trash2 size={14} />
              Clear All
            </button>
          {/if}

          <button
            onclick={applyRedactions}
            disabled={redactionMarks.length === 0 || isApplying}
            class="w-full flex items-center justify-center gap-2 px-3 py-2 rounded text-sm font-medium transition-colors disabled:opacity-40"
            style="background-color: var(--nord11); color: var(--nord6);"
          >
            {#if isApplying}
              <RefreshCw size={14} class="animate-spin" />
              Applying...
            {:else}
              <Download size={14} />
              Apply & Save
            {/if}
          </button>
        </div>

        <!-- Warning -->
        <div class="p-3 border-t" style="border-color: var(--nord3);">
          <div
            class="p-2 rounded text-xs"
            style="background-color: rgba(235, 203, 139, 0.15); color: var(--nord13);"
          >
            <strong>Warning:</strong> Redaction permanently removes content. This cannot be undone.
          </div>
        </div>
      </div>
    {/if}
  </div>
</div>
