<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';
  import {
    ChevronLeft,
    ChevronRight,
    ZoomIn,
    ZoomOut,
    RotateCw,
    X,
    Minus,
    Plus,
    Check,
    ExternalLink,
  } from 'lucide-svelte';

  interface Props {
    filePath: string;
    showToolbar?: boolean;
    showSidebar?: boolean;
    initialPage?: number;
    initialZoom?: number;
    onClose?: () => void;
    onSave?: () => void;
    onSaveAs?: () => void;
  }

  let {
    filePath,
    showToolbar = true,
    showSidebar = true,
    initialPage = 1,
    initialZoom = 1,
    onClose,
    onSave,
    onSaveAs,
  }: Props = $props();

  // Types from Rust backend
  interface PdfInfo {
    path: string;
    num_pages: number;
    page_sizes: { width: number; height: number }[];
  }

  interface RenderedPage {
    data: string; // base64 PNG
    width: number;
    height: number;
    page: number;
  }

  // State
  let pdfInfo = $state<PdfInfo | null>(null);
  let currentPage = $state(initialPage);
  let totalPages = $state(0);
  let zoom = $state(initialZoom);
  let rotation = $state(0);
  let isLoading = $state(true);
  let error = $state<string | null>(null);
  let fileName = $state('');

  // Current page image
  let pageImage = $state<string | null>(null);
  let pageWidth = $state(0);
  let pageHeight = $state(0);
  let isRenderingPage = $state(false);

  // Sidebar state
  let sidebarCollapsed = $state(false);
  let thumbnails = $state<RenderedPage[]>([]);
  let isLoadingThumbnails = $state(false);

  // UI elements
  let canvasContainer: HTMLDivElement;
  let pageInputValue = $state('1');

  // Load PDF info
  async function loadPDF() {
    isLoading = true;
    error = null;

    try {
      console.log('[MuPDFViewer] Opening PDF:', filePath);
      pdfInfo = await invoke<PdfInfo>('pdf_open', { path: filePath });
      totalPages = pdfInfo.num_pages;
      currentPage = Math.min(initialPage, totalPages);
      fileName = filePath.split('/').pop() || 'Document';
      pageInputValue = String(currentPage);

      console.log('[MuPDFViewer] PDF loaded:', pdfInfo.num_pages, 'pages');

      // Render current page
      await renderCurrentPage();

      // Load thumbnails in background
      loadThumbnails();

      isLoading = false;
    } catch (err) {
      console.error('[MuPDFViewer] Failed to load PDF:', err);
      error = String(err);
      isLoading = false;
    }
  }

  // Render current page at current zoom
  async function renderCurrentPage() {
    if (!pdfInfo || isRenderingPage) return;

    isRenderingPage = true;

    try {
      // Calculate DPI based on zoom (base DPI is 150 for good quality)
      const dpi = Math.round(150 * zoom);

      console.log('[MuPDFViewer] Rendering page', currentPage, 'at DPI', dpi);

      const rendered = await invoke<RenderedPage>('pdf_render_page', {
        path: filePath,
        page: currentPage,
        dpi: dpi,
        maxWidth: null,
        maxHeight: null,
      });

      pageImage = `data:image/png;base64,${rendered.data}`;
      pageWidth = rendered.width;
      pageHeight = rendered.height;
    } catch (err) {
      console.error('[MuPDFViewer] Failed to render page:', err);
    } finally {
      isRenderingPage = false;
    }
  }

  // Load thumbnails for sidebar
  async function loadThumbnails() {
    if (!pdfInfo || isLoadingThumbnails) return;

    isLoadingThumbnails = true;

    try {
      const pages = Array.from({ length: pdfInfo.num_pages }, (_, i) => i + 1);

      const rendered = await invoke<RenderedPage[]>('pdf_render_thumbnails', {
        path: filePath,
        pages: pages,
        maxSize: 150,
      });

      thumbnails = rendered;
      console.log('[MuPDFViewer] Loaded', thumbnails.length, 'thumbnails');
    } catch (err) {
      console.error('[MuPDFViewer] Failed to load thumbnails:', err);
    } finally {
      isLoadingThumbnails = false;
    }
  }

  // Navigation
  function goToPage(page: number) {
    if (page >= 1 && page <= totalPages && page !== currentPage) {
      currentPage = page;
      pageInputValue = String(page);
      renderCurrentPage();
    }
  }

  function prevPage() {
    goToPage(currentPage - 1);
  }

  function nextPage() {
    goToPage(currentPage + 1);
  }

  // Zoom
  function zoomIn() {
    setZoom(Math.min(zoom + 0.25, 4));
  }

  function zoomOut() {
    setZoom(Math.max(zoom - 0.25, 0.25));
  }

  function setZoom(value: number) {
    const newZoom = Math.max(0.25, Math.min(4, value));
    if (newZoom !== zoom) {
      zoom = newZoom;
      renderCurrentPage();
    }
  }

  // Rotation (client-side only for now)
  function rotate() {
    rotation = (rotation + 90) % 360;
  }

  // Page input handling
  function handlePageInput(e: Event) {
    const target = e.target as HTMLInputElement;
    const value = parseInt(target.value, 10);
    if (!isNaN(value) && value >= 1 && value <= totalPages) {
      goToPage(value);
    }
  }

  function handlePageKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      const value = parseInt(pageInputValue, 10);
      if (!isNaN(value) && value >= 1 && value <= totalPages) {
        goToPage(value);
      } else {
        pageInputValue = String(currentPage);
      }
    }
  }

  // Panning support
  let isPanning = $state(false);
  let panStart = $state<{ x: number; y: number } | null>(null);
  let scrollStart = $state<{ x: number; y: number } | null>(null);

  function handlePanStart(e: MouseEvent) {
    if (e.button === 1 || e.button === 0) {
      isPanning = true;
      panStart = { x: e.clientX, y: e.clientY };
      scrollStart = {
        x: canvasContainer?.scrollLeft ?? 0,
        y: canvasContainer?.scrollTop ?? 0,
      };
    }
  }

  function handlePanMove(e: MouseEvent) {
    if (!isPanning || !panStart || !scrollStart || !canvasContainer) return;

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

  // Keyboard navigation
  function handleKeydown(e: KeyboardEvent) {
    if (e.target instanceof HTMLInputElement) return;

    if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
      prevPage();
    } else if (e.key === 'ArrowRight' || e.key === 'PageDown') {
      nextPage();
    } else if (e.key === 'Home') {
      goToPage(1);
    } else if (e.key === 'End') {
      goToPage(totalPages);
    } else if (e.key === '+' || e.key === '=') {
      zoomIn();
    } else if (e.key === '-') {
      zoomOut();
    }
  }

  // Zoom presets
  const zoomPresets = [0.5, 0.75, 1, 1.25, 1.5, 2, 3];

  onMount(() => {
    loadPDF();
    window.addEventListener('keydown', handleKeydown);
    document.addEventListener('mouseup', handlePanEnd);
  });

  onDestroy(() => {
    window.removeEventListener('keydown', handleKeydown);
    document.removeEventListener('mouseup', handlePanEnd);
  });

  // Reload when file path changes
  $effect(() => {
    if (filePath) {
      loadPDF();
    }
  });
</script>

<div
  class="flex flex-col h-full overflow-hidden"
  style="background-color: var(--nord0);"
>
  <!-- Toolbar -->
  {#if showToolbar}
    <div
      class="flex items-center justify-between px-3 py-2 border-b"
      style="background-color: var(--nord1); border-color: var(--nord3);"
    >
      <!-- Left: Rotate -->
      <div class="flex items-center gap-1">
        <button
          onclick={rotate}
          class="p-2 rounded-lg transition-colors hover:bg-[var(--nord2)]"
          title="Rotate 90deg"
        >
          <RotateCw size={16} />
        </button>
      </div>

      <!-- Center: Navigation -->
      <div class="flex items-center gap-2">
        <button
          onclick={prevPage}
          disabled={currentPage <= 1}
          class="p-1.5 rounded transition-colors hover:bg-[var(--nord2)] disabled:opacity-30"
          title="Previous page"
        >
          <ChevronLeft size={18} />
        </button>

        <div class="flex items-center gap-1">
          <input
            type="text"
            bind:value={pageInputValue}
            onblur={handlePageInput}
            onkeydown={handlePageKeydown}
            class="w-12 px-2 py-1 rounded text-center text-sm"
            style="background-color: var(--nord2); border: 1px solid var(--nord3);"
          />
          <span class="text-sm opacity-60">/ {totalPages}</span>
        </div>

        <button
          onclick={nextPage}
          disabled={currentPage >= totalPages}
          class="p-1.5 rounded transition-colors hover:bg-[var(--nord2)] disabled:opacity-30"
          title="Next page"
        >
          <ChevronRight size={18} />
        </button>
      </div>

      <!-- Right: Zoom & Actions -->
      <div class="flex items-center gap-2">
        <button
          onclick={zoomOut}
          class="p-1.5 rounded transition-colors hover:bg-[var(--nord2)]"
          title="Zoom out"
        >
          <Minus size={16} />
        </button>

        <div class="relative group">
          <button
            class="px-2 py-1 rounded text-sm min-w-[60px] hover:bg-[var(--nord2)] transition-colors"
            style="background-color: var(--nord2);"
          >
            {Math.round(zoom * 100)}%
          </button>
          <div
            class="absolute top-full left-1/2 -translate-x-1/2 mt-1 py-1 rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50"
            style="background-color: var(--nord2); min-width: 80px;"
          >
            {#each zoomPresets as preset}
              <button
                onclick={() => setZoom(preset)}
                class="w-full px-3 py-1.5 text-sm text-left hover:bg-[var(--nord3)] transition-colors"
                style="color: {zoom === preset ? 'var(--nord8)' : 'var(--nord4)'};"
              >
                {Math.round(preset * 100)}%
              </button>
            {/each}
          </div>
        </div>

        <button
          onclick={zoomIn}
          class="p-1.5 rounded transition-colors hover:bg-[var(--nord2)]"
          title="Zoom in"
        >
          <Plus size={16} />
        </button>

        <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

        {#if onClose}
          <button
            onclick={onClose}
            class="p-2 rounded-lg transition-colors hover:bg-[var(--nord11)] hover:text-white"
            title="Close"
          >
            <X size={16} />
          </button>
        {/if}
      </div>
    </div>
  {/if}

  <div class="flex-1 flex overflow-hidden">
    <!-- Sidebar with thumbnails -->
    {#if showSidebar && !sidebarCollapsed}
      <div
        class="w-40 flex flex-col border-r overflow-hidden"
        style="background-color: var(--nord1); border-color: var(--nord3);"
      >
        <div
          class="flex items-center justify-between px-3 py-2 border-b"
          style="border-color: var(--nord3);"
        >
          <span class="text-xs uppercase opacity-60">Pages</span>
          <button
            onclick={() => sidebarCollapsed = true}
            class="p-1 rounded hover:bg-[var(--nord2)] transition-colors"
            title="Hide thumbnails"
          >
            <ChevronLeft size={14} />
          </button>
        </div>

        <div class="flex-1 overflow-y-auto p-2 space-y-2">
          {#if isLoadingThumbnails && thumbnails.length === 0}
            {#each Array(Math.min(totalPages, 5)) as _, i}
              <div class="w-full">
                <div
                  class="aspect-[3/4] rounded flex items-center justify-center"
                  style="background-color: var(--nord2); border: 2px solid var(--nord3);"
                >
                  <div class="w-4 h-4 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin"></div>
                </div>
                <p class="mt-1 text-xs text-center opacity-40">{i + 1}</p>
              </div>
            {/each}
          {:else}
            {#each thumbnails as thumb (thumb.page)}
              <button
                onclick={() => goToPage(thumb.page)}
                class="w-full relative group"
              >
                <div
                  class="relative rounded overflow-hidden transition-all"
                  style="border: 2px solid {currentPage === thumb.page ? 'var(--nord8)' : 'var(--nord3)'};"
                >
                  <div class="aspect-[3/4] flex items-center justify-center bg-white">
                    <img
                      src="data:image/png;base64,{thumb.data}"
                      alt="Page {thumb.page}"
                      class="max-w-full max-h-full object-contain"
                    />
                  </div>

                  {#if currentPage === thumb.page}
                    <div
                      class="absolute bottom-0 left-0 right-0 h-0.5"
                      style="background-color: var(--nord8);"
                    ></div>
                  {/if}
                </div>

                <p
                  class="mt-1 text-xs text-center"
                  style="color: {currentPage === thumb.page ? 'var(--nord8)' : 'var(--nord4)'};"
                >
                  {thumb.page}
                </p>
              </button>
            {/each}
          {/if}
        </div>
      </div>
    {/if}

    <!-- Sidebar toggle when collapsed -->
    {#if showSidebar && sidebarCollapsed}
      <button
        onclick={() => sidebarCollapsed = false}
        class="w-8 flex items-center justify-center border-r hover:bg-[var(--nord2)] transition-colors"
        style="background-color: var(--nord1); border-color: var(--nord3);"
        title="Show thumbnails"
      >
        <ChevronRight size={16} />
      </button>
    {/if}

    <!-- Main canvas -->
    <div class="flex-1 overflow-hidden">
      {#if isLoading}
        <div class="h-full flex items-center justify-center">
          <div class="flex flex-col items-center gap-4">
            <div class="w-8 h-8 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin"></div>
            <p class="text-sm opacity-60">Loading PDF...</p>
          </div>
        </div>
      {:else if error}
        <div class="h-full flex items-center justify-center">
          <div class="flex flex-col items-center gap-4 text-center px-8">
            <p class="text-lg" style="color: var(--nord11);">Failed to load PDF</p>
            <p class="text-sm opacity-60">{error}</p>
            <button
              onclick={loadPDF}
              class="px-4 py-2 rounded text-sm hover:opacity-80"
              style="background-color: var(--nord2);"
            >
              Retry
            </button>
          </div>
        </div>
      {:else if pageImage}
        <div
          bind:this={canvasContainer}
          class="h-full overflow-auto flex items-center justify-center p-4"
          style="background-color: var(--nord0); cursor: {isPanning ? 'grabbing' : 'grab'};"
          onmousedown={handlePanStart}
          onmousemove={handlePanMove}
          role="application"
          aria-label="PDF viewer"
        >
          <div class="relative shadow-2xl">
            <img
              src={pageImage}
              alt="Page {currentPage}"
              class="block"
              style="
                background: white;
                transform: rotate({rotation}deg);
                max-width: none;
              "
              draggable="false"
            />

            {#if isRenderingPage}
              <div class="absolute inset-0 flex items-center justify-center bg-white/50">
                <div class="w-6 h-6 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin"></div>
              </div>
            {/if}
          </div>
        </div>
      {/if}
    </div>
  </div>

  <!-- Bottom status bar -->
  <div
    class="h-7 flex items-center justify-between px-3 text-xs border-t"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <div class="flex items-center gap-4">
      <span class="opacity-60 truncate max-w-[300px]" title={filePath}>{fileName}</span>
    </div>
    <div class="flex items-center gap-4">
      <span class="opacity-60">{Math.round(zoom * 100)}%</span>
      <span class="opacity-60">Page {currentPage} of {totalPages}</span>
      <span class="text-[10px] opacity-40">MuPDF</span>
    </div>
  </div>
</div>
