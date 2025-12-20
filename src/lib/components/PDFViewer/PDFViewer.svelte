<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { ExternalLink, X, ZoomIn, ZoomOut, RotateCw, ChevronLeft, ChevronRight } from 'lucide-svelte';
  import ViewerToolbar from './ViewerToolbar.svelte';
  import ViewerSidebar from './ViewerSidebar.svelte';
  import ViewerCanvas from './ViewerCanvas.svelte';
  import type { PDFDocumentProxy } from 'pdfjs-dist';

  interface Props {
    filePath?: string;
    fileData?: Uint8Array;
    showToolbar?: boolean;
    showSidebar?: boolean;
    showDetachButton?: boolean;
    initialPage?: number;
    initialZoom?: number;
    onClose?: () => void;
    onDetach?: () => void;
    mode?: 'view' | 'select' | 'annotate';
  }

  let {
    filePath,
    fileData,
    showToolbar = true,
    showSidebar = true,
    showDetachButton = true,
    initialPage = 1,
    initialZoom = 1,
    onClose,
    onDetach,
    mode = 'view',
  }: Props = $props();

  // PDF State
  let pdfDoc = $state<PDFDocumentProxy | null>(null);
  let currentPage = $state(initialPage);
  let totalPages = $state(0);
  let zoom = $state(initialZoom);
  let rotation = $state(0);
  let isLoading = $state(true);
  let error = $state<string | null>(null);
  let fileName = $state('');

  // Sidebar state
  let sidebarCollapsed = $state(false);

  // Selected pages for multi-select mode
  let selectedPages = $state<Set<number>>(new Set());

  // Active tool
  let activeTool = $state<string>('select');

  // Load PDF
  async function loadPDF() {
    isLoading = true;
    error = null;

    try {
      const pdfjs = await import('pdfjs-dist');

      // Set worker
      pdfjs.GlobalWorkerOptions.workerSrc = new URL(
        'pdfjs-dist/build/pdf.worker.mjs',
        import.meta.url
      ).toString();

      let loadingTask;

      if (fileData) {
        loadingTask = pdfjs.getDocument({ data: fileData });
        fileName = 'Document';
      } else if (filePath) {
        // Read file via Tauri
        const { readFile } = await import('@tauri-apps/plugin-fs');
        const data = await readFile(filePath);
        loadingTask = pdfjs.getDocument({ data });
        fileName = filePath.split('/').pop() || 'Document';
      } else {
        throw new Error('No PDF source provided');
      }

      pdfDoc = await loadingTask.promise;
      totalPages = pdfDoc.numPages;
      currentPage = Math.min(initialPage, totalPages);
      isLoading = false;
    } catch (err) {
      console.error('Failed to load PDF:', err);
      error = String(err);
      isLoading = false;
    }
  }

  // Navigation
  function goToPage(page: number) {
    if (page >= 1 && page <= totalPages) {
      currentPage = page;
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
    zoom = Math.min(zoom + 0.25, 4);
  }

  function zoomOut() {
    zoom = Math.max(zoom - 0.25, 0.25);
  }

  function setZoom(value: number) {
    zoom = Math.max(0.25, Math.min(4, value));
  }

  // Rotation
  function rotate() {
    rotation = (rotation + 90) % 360;
  }

  // Page selection
  function togglePageSelection(page: number) {
    const newSet = new Set(selectedPages);
    if (newSet.has(page)) {
      newSet.delete(page);
    } else {
      newSet.add(page);
    }
    selectedPages = newSet;
  }

  function selectAllPages() {
    const newSet = new Set<number>();
    for (let i = 1; i <= totalPages; i++) {
      newSet.add(i);
    }
    selectedPages = newSet;
  }

  function clearSelection() {
    selectedPages = new Set();
  }

  // Tool handling
  function setActiveTool(tool: string) {
    activeTool = tool;
  }

  // Keyboard navigation
  function handleKeydown(e: KeyboardEvent) {
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

  onMount(() => {
    loadPDF();
    window.addEventListener('keydown', handleKeydown);
  });

  onDestroy(() => {
    window.removeEventListener('keydown', handleKeydown);
    pdfDoc?.destroy();
  });

  // Reactive reload when source changes
  $effect(() => {
    if (filePath || fileData) {
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
    <ViewerToolbar
      {activeTool}
      {zoom}
      {currentPage}
      {totalPages}
      {showDetachButton}
      onToolChange={setActiveTool}
      onZoomIn={zoomIn}
      onZoomOut={zoomOut}
      onZoomSet={setZoom}
      onRotate={rotate}
      onPrevPage={prevPage}
      onNextPage={nextPage}
      onGoToPage={goToPage}
      onDetach={onDetach}
      onClose={onClose}
    />
  {/if}

  <div class="flex-1 flex overflow-hidden">
    <!-- Sidebar with thumbnails -->
    {#if showSidebar && !sidebarCollapsed}
      <ViewerSidebar
        {pdfDoc}
        {currentPage}
        {selectedPages}
        {mode}
        onPageClick={goToPage}
        onPageSelect={togglePageSelection}
        onCollapse={() => sidebarCollapsed = true}
      />
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
      {:else if pdfDoc}
        <ViewerCanvas
          {pdfDoc}
          {currentPage}
          {zoom}
          {rotation}
          {activeTool}
        />
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
      {#if selectedPages.size > 0}
        <span style="color: var(--nord8);">{selectedPages.size} selected</span>
      {/if}
    </div>
  </div>
</div>
