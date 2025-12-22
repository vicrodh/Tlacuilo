<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';
  import { listen, type UnlistenFn } from '@tauri-apps/api/event';
  import {
    ChevronLeft,
    ChevronRight,
    RotateCw,
    X,
    Minus,
    Plus,
    MoveHorizontal,
    MoveVertical,
    Maximize,
    PenTool,
    Save,
  } from 'lucide-svelte';
  import { createAnnotationsStore } from '$lib/stores/annotations.svelte';
  import AnnotationToolbar from './AnnotationToolbar.svelte';
  import AnnotationOverlay from './AnnotationOverlay.svelte';
  import AnnotationsPanel from './AnnotationsPanel.svelte';

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

  // Annotations
  const annotationsStore = createAnnotationsStore();
  let showAnnotationTools = $state(false);
  let annotationsDirty = $state(false);
  let isSavingAnnotations = $state(false);
  let annotationsInitialized = $state(false);
  let lastAnnotationCount = $state(0);

  // Load annotations from sidecar file
  async function loadAnnotations() {
    try {
      const result = await invoke<string | null>('annotations_load', { pdfPath: filePath });
      if (result) {
        const data = JSON.parse(result);
        // Convert string keys to numbers
        const converted: Record<number, any[]> = {};
        for (const [key, value] of Object.entries(data)) {
          converted[Number(key)] = value as any[];
        }
        annotationsStore.importAnnotations(converted);
      }
      // Mark as initialized and not dirty after load
      lastAnnotationCount = annotationsStore.getAllAnnotations().length;
      annotationsInitialized = true;
      annotationsDirty = false;
    } catch (err) {
      console.error('[MuPDFViewer] Failed to load annotations:', err);
      annotationsInitialized = true;
    }
  }

  // Save annotations to sidecar file
  async function saveAnnotations() {
    if (isSavingAnnotations) return;

    isSavingAnnotations = true;
    try {
      const data = annotationsStore.exportAnnotations();
      const json = JSON.stringify(data);
      await invoke('annotations_save', { pdfPath: filePath, annotationsJson: json });
      lastAnnotationCount = annotationsStore.getAllAnnotations().length;
      annotationsDirty = false;
    } catch (err) {
      console.error('[MuPDFViewer] Failed to save annotations:', err);
    } finally {
      isSavingAnnotations = false;
    }
  }

  // Track annotation changes - only after initialization
  $effect(() => {
    if (!annotationsInitialized) return;

    const currentCount = annotationsStore.getAllAnnotations().length;
    // Mark dirty if count changed after initialization
    if (currentCount !== lastAnnotationCount) {
      annotationsDirty = true;
    }
  });

  // Sidebar state
  let sidebarCollapsed = $state(false);
  let thumbnails = $state<RenderedPage[]>([]);
  let isLoadingThumbnails = $state(false);

  // Zoom mode: 'manual', 'fit-width', 'fit-height', 'fit-page'
  type ZoomMode = 'manual' | 'fit-width' | 'fit-height' | 'fit-page';
  let zoomMode = $state<ZoomMode>('manual');

  // UI elements
  let canvasContainer: HTMLDivElement;
  let pageInputValue = $state('1');

  // Page elements for scroll tracking
  let pageElements: Map<number, HTMLDivElement> = new Map();

  // Virtual scrolling: only load visible pages + buffer
  let loadedPages = $state<Map<number, RenderedPage>>(new Map());
  let loadingPages = $state<Set<number>>(new Set());
  const PAGE_BUFFER = 2; // Pages to load above/below viewport

  // Prevent scroll handler from updating currentPage during programmatic scroll
  let isScrollingToPage = $state(false);

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

      // Clear any previously loaded pages
      loadedPages = new Map();
      loadingPages = new Set();

      isLoading = false;

      // Load thumbnails in background
      loadThumbnails();

      // Wait for DOM to render placeholders, then load visible pages
      await tick();
      loadVisiblePages();

      // Load saved annotations
      await loadAnnotations();

      if (initialPage > 1) {
        scrollToPage(initialPage);
      }
    } catch (err) {
      console.error('[MuPDFViewer] Failed to load PDF:', err);
      error = String(err);
      isLoading = false;
    }
  }

  // Calculate page dimensions at current zoom
  function getPageDimensions(pageIndex: number): { width: number; height: number } {
    if (!pdfInfo || !pdfInfo.page_sizes[pageIndex]) {
      return { width: 612, height: 792 }; // Default letter size
    }
    const size = pdfInfo.page_sizes[pageIndex];
    // Convert from points to pixels at 150 DPI base, scaled by zoom
    const scale = (150 / 72) * zoom;
    return {
      width: Math.round(size.width * scale),
      height: Math.round(size.height * scale),
    };
  }

  // Load a single page
  async function loadPage(pageNum: number): Promise<void> {
    if (loadedPages.has(pageNum) || loadingPages.has(pageNum)) return;

    loadingPages.add(pageNum);
    loadingPages = new Set(loadingPages);

    try {
      const dpi = Math.round(150 * zoom);
      const rendered = await invoke<RenderedPage>('pdf_render_page', {
        path: filePath,
        page: pageNum,
        dpi: dpi,
        maxWidth: null,
        maxHeight: null,
      });

      loadedPages.set(pageNum, rendered);
      loadedPages = new Map(loadedPages);
    } catch (err) {
      console.error(`[MuPDFViewer] Failed to load page ${pageNum}:`, err);
    } finally {
      loadingPages.delete(pageNum);
      loadingPages = new Set(loadingPages);
    }
  }

  // Determine which pages are visible and load them
  function loadVisiblePages() {
    if (!canvasContainer || !pdfInfo) return;

    const containerRect = canvasContainer.getBoundingClientRect();
    const scrollTop = canvasContainer.scrollTop;
    const viewportTop = scrollTop;
    const viewportBottom = scrollTop + containerRect.height;

    // Calculate which pages are visible based on cumulative heights
    let cumulativeHeight = 0;
    const gap = 16; // Gap between pages (gap-4 = 1rem = 16px)
    const pagesToLoad: number[] = [];

    for (let i = 0; i < totalPages; i++) {
      const pageNum = i + 1;
      const dims = getPageDimensions(i);
      const pageTop = cumulativeHeight;
      const pageBottom = pageTop + dims.height;

      // Check if page is in viewport or within buffer
      const inViewport = pageBottom >= viewportTop && pageTop <= viewportBottom;
      const inBuffer = pageBottom >= viewportTop - (dims.height * PAGE_BUFFER) &&
                       pageTop <= viewportBottom + (dims.height * PAGE_BUFFER);

      if (inBuffer) {
        pagesToLoad.push(pageNum);
      }

      cumulativeHeight = pageBottom + gap;
    }

    // Load visible pages (don't await, let them load in parallel)
    for (const pageNum of pagesToLoad) {
      loadPage(pageNum);
    }
  }

  // Re-render visible pages when zoom changes
  async function reRenderPages() {
    if (!pdfInfo) return;

    // Clear loaded pages and reload visible ones
    loadedPages = new Map();
    loadingPages = new Set();
    await tick();
    loadVisiblePages();
  }

  // Load thumbnails for sidebar (in batches for large documents)
  const THUMBNAIL_BATCH_SIZE = 50;

  async function loadThumbnails() {
    if (!pdfInfo || isLoadingThumbnails) return;

    isLoadingThumbnails = true;
    thumbnails = [];

    try {
      // Load in batches of 50 pages
      for (let start = 0; start < pdfInfo.num_pages; start += THUMBNAIL_BATCH_SIZE) {
        const end = Math.min(start + THUMBNAIL_BATCH_SIZE, pdfInfo.num_pages);
        const pages = Array.from({ length: end - start }, (_, i) => start + i + 1);

        const rendered = await invoke<RenderedPage[]>('pdf_render_thumbnails', {
          path: filePath,
          pages: pages,
          maxSize: 150,
        });

        thumbnails = [...thumbnails, ...rendered];
      }

      console.log('[MuPDFViewer] Loaded', thumbnails.length, 'thumbnails');
    } catch (err) {
      console.error('[MuPDFViewer] Failed to load thumbnails:', err);
    } finally {
      isLoadingThumbnails = false;
    }
  }

  // Scroll to a specific page
  function scrollToPage(page: number) {
    const element = pageElements.get(page);
    if (element && canvasContainer) {
      isScrollingToPage = true;
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
      // Reset flag after scroll animation
      setTimeout(() => {
        isScrollingToPage = false;
      }, 500);
    }
  }

  // Navigation
  function goToPage(page: number) {
    if (page >= 1 && page <= totalPages) {
      currentPage = page;
      pageInputValue = String(page);
      scrollToPage(page);
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
    zoomMode = 'manual';
    setZoom(Math.min(zoom + 0.25, 4));
  }

  function zoomOut() {
    zoomMode = 'manual';
    setZoom(Math.max(zoom - 0.25, 0.25));
  }

  function setZoom(value: number) {
    const newZoom = Math.max(0.25, Math.min(4, value));
    if (newZoom !== zoom) {
      zoom = newZoom;
      reRenderPages();
    }
  }

  function setZoomPreset(value: number) {
    zoomMode = 'manual';
    setZoom(value);
  }

  // Calculate zoom to fit width/height/page
  function calculateFitZoom(mode: ZoomMode): number {
    if (!pdfInfo || !canvasContainer) return 1;

    const pageSize = pdfInfo.page_sizes[currentPage - 1];
    if (!pageSize) return 1;

    // Get container dimensions (subtract padding and sidebar)
    const containerWidth = canvasContainer.clientWidth - 32; // 16px padding each side
    const containerHeight = canvasContainer.clientHeight - 32;

    // Page dimensions in points (72 DPI)
    const pageWidthPts = pageSize.width;
    const pageHeightPts = pageSize.height;

    // Calculate zoom factors (150 DPI base)
    const widthZoom = containerWidth / (pageWidthPts * (150 / 72));
    const heightZoom = containerHeight / (pageHeightPts * (150 / 72));

    switch (mode) {
      case 'fit-width':
        return Math.min(Math.max(widthZoom, 0.25), 4);
      case 'fit-height':
        return Math.min(Math.max(heightZoom, 0.25), 4);
      case 'fit-page':
        return Math.min(Math.max(Math.min(widthZoom, heightZoom), 0.25), 4);
      default:
        return 1;
    }
  }

  function fitWidth() {
    zoomMode = 'fit-width';
    const newZoom = calculateFitZoom('fit-width');
    setZoom(newZoom);
  }

  function fitHeight() {
    zoomMode = 'fit-height';
    const newZoom = calculateFitZoom('fit-height');
    setZoom(newZoom);
  }

  function fitPage() {
    zoomMode = 'fit-page';
    const newZoom = calculateFitZoom('fit-page');
    setZoom(newZoom);
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

  // Scroll tracking - update currentPage based on visible page and load visible pages
  function handleScroll() {
    if (!canvasContainer || isScrollingToPage) return;

    const containerRect = canvasContainer.getBoundingClientRect();
    const containerMiddle = containerRect.top + containerRect.height / 3;

    let closestPage = 1;
    let closestDistance = Infinity;

    pageElements.forEach((element, page) => {
      const rect = element.getBoundingClientRect();
      const elementMiddle = rect.top + rect.height / 2;
      const distance = Math.abs(elementMiddle - containerMiddle);

      if (distance < closestDistance) {
        closestDistance = distance;
        closestPage = page;
      }
    });

    if (closestPage !== currentPage) {
      currentPage = closestPage;
      pageInputValue = String(closestPage);
    }

    // Load visible pages on scroll (debounced naturally by browser)
    loadVisiblePages();
  }

  // Panning support
  let isPanning = $state(false);
  let panStart = $state<{ x: number; y: number } | null>(null);
  let scrollStart = $state<{ x: number; y: number } | null>(null);

  // Check if annotation mode is active (tool selected and toolbar visible)
  const isAnnotationMode = $derived(showAnnotationTools && annotationsStore.activeTool !== null);

  function handlePanStart(e: MouseEvent) {
    // Don't start panning if annotation tool is active
    if (isAnnotationMode) return;

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

  // Mouse wheel zoom
  function handleWheel(e: WheelEvent) {
    if (e.ctrlKey) {
      e.preventDefault();
      if (e.deltaY < 0) {
        zoomIn();
      } else {
        zoomOut();
      }
    }
  }

  // Action to register page element
  function pageRef(element: HTMLDivElement, page: number) {
    pageElements.set(page, element);
    return {
      destroy() {
        pageElements.delete(page);
      }
    };
  }

  // Zoom presets
  const zoomPresets = [0.5, 0.75, 1, 1.25, 1.5, 2, 3];

  // Menu event listener
  let unlistenSave: UnlistenFn | null = null;

  onMount(async () => {
    loadPDF();
    window.addEventListener('keydown', handleKeydown);
    document.addEventListener('mouseup', handlePanEnd);

    // Listen for menu save event (Ctrl+S)
    unlistenSave = await listen('menu-save', () => {
      if (annotationsDirty) {
        saveAnnotations();
      }
    });
  });

  onDestroy(() => {
    window.removeEventListener('keydown', handleKeydown);
    document.removeEventListener('mouseup', handlePanEnd);
    unlistenSave?.();
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
      <!-- Left: Rotate & Annotate -->
      <div class="flex items-center gap-1">
        <button
          onclick={rotate}
          class="p-2 rounded-lg transition-colors hover:bg-[var(--nord2)]"
          title="Rotate 90deg"
        >
          <RotateCw size={16} />
        </button>

        <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

        <button
          onclick={() => showAnnotationTools = !showAnnotationTools}
          class="p-2 rounded-lg transition-colors"
          class:bg-[var(--nord8)]={showAnnotationTools}
          style="color: {showAnnotationTools ? 'var(--nord0)' : 'var(--nord4)'};"
          title="Annotation tools"
        >
          <PenTool size={16} />
        </button>

        {#if annotationsDirty}
          <button
            onclick={saveAnnotations}
            disabled={isSavingAnnotations}
            class="p-2 rounded-lg transition-colors hover:bg-[var(--nord2)] relative"
            class:animate-pulse={isSavingAnnotations}
            title="Save annotations"
          >
            <Save size={16} />
            <div
              class="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full"
              style="background-color: var(--nord13);"
            ></div>
          </button>
        {/if}
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
                onclick={() => setZoomPreset(preset)}
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

        <!-- Fit buttons -->
        <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

        <button
          onclick={fitWidth}
          class="p-1.5 rounded transition-colors hover:bg-[var(--nord2)]"
          class:bg-[var(--nord2)]={zoomMode === 'fit-width'}
          title="Fit width"
        >
          <MoveHorizontal size={16} />
        </button>

        <button
          onclick={fitHeight}
          class="p-1.5 rounded transition-colors hover:bg-[var(--nord2)]"
          class:bg-[var(--nord2)]={zoomMode === 'fit-height'}
          title="Fit height"
        >
          <MoveVertical size={16} />
        </button>

        <button
          onclick={fitPage}
          class="p-1.5 rounded transition-colors hover:bg-[var(--nord2)]"
          class:bg-[var(--nord2)]={zoomMode === 'fit-page'}
          title="Fit page"
        >
          <Maximize size={16} />
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

    <!-- Annotation Toolbar -->
    {#if showAnnotationTools}
      <div
        class="flex items-center justify-center px-3 py-2 border-b"
        style="background-color: var(--nord1); border-color: var(--nord3);"
      >
        <AnnotationToolbar store={annotationsStore} />
      </div>
    {/if}
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

    <!-- Main canvas - Continuous scroll view -->
    <div class="flex-1 overflow-hidden flex">
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
      {:else}
        <div
          bind:this={canvasContainer}
          class="flex-1 h-full overflow-y-auto overflow-x-hidden p-4"
          style="background-color: var(--nord0); cursor: {isAnnotationMode ? 'default' : (isPanning ? 'grabbing' : 'grab')};"
          onmousedown={handlePanStart}
          onmousemove={handlePanMove}
          onscroll={handleScroll}
          onwheel={handleWheel}
          role="application"
          aria-label="PDF viewer"
        >
          <div class="flex flex-col items-center gap-4">
            {#each Array.from({ length: totalPages }, (_, i) => i + 1) as pageNum (pageNum)}
              {@const dims = getPageDimensions(pageNum - 1)}
              {@const loadedPage = loadedPages.get(pageNum)}
              {@const isLoading = loadingPages.has(pageNum)}
              <div
                class="relative shadow-2xl"
                use:pageRef={pageNum}
                data-page={pageNum}
                style="width: {dims.width}px; min-height: {dims.height}px;"
              >
                {#if loadedPage}
                  <!-- Loaded page -->
                  <img
                    src="data:image/png;base64,{loadedPage.data}"
                    alt="Page {pageNum}"
                    class="block"
                    style="background: white; transform: rotate({rotation}deg);"
                    draggable="false"
                  />

                  <!-- Annotation overlay -->
                  {#if showAnnotationTools}
                    <AnnotationOverlay
                      store={annotationsStore}
                      page={pageNum}
                      pageWidth={loadedPage.width}
                      pageHeight={loadedPage.height}
                      scale={1}
                    />
                  {/if}
                {:else}
                  <!-- Placeholder -->
                  <div
                    class="flex items-center justify-center"
                    style="width: {dims.width}px; height: {dims.height}px; background-color: var(--nord2);"
                  >
                    {#if isLoading}
                      <div class="w-6 h-6 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin"></div>
                    {:else}
                      <span class="text-sm opacity-40">Page {pageNum}</span>
                    {/if}
                  </div>
                {/if}

                <div
                  class="absolute bottom-2 right-2 px-2 py-1 rounded text-xs pointer-events-none"
                  style="background-color: var(--nord0); color: var(--nord4);"
                >
                  {pageNum}
                </div>
              </div>
            {/each}
          </div>
        </div>

        <!-- Annotations Panel (right sidebar) -->
        {#if showAnnotationTools}
          <div
            class="w-56 border-l flex-shrink-0"
            style="border-color: var(--nord3);"
          >
            <AnnotationsPanel
              store={annotationsStore}
              onNavigateToPage={goToPage}
            />
          </div>
        {/if}
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
