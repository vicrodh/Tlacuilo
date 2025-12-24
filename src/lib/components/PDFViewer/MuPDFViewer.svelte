<script lang="ts">
  import { onMount, onDestroy, tick, untrack } from 'svelte';
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
    Download,
    Upload,
    FileDown,
    FileUp,
    MoreVertical,
    Printer,
  } from 'lucide-svelte';
  import { save, open } from '@tauri-apps/plugin-dialog';
  import { createAnnotationsStore } from '$lib/stores/annotations.svelte';
  import { debugLog } from '$lib/stores/debugLog.svelte';
  import AnnotationToolbar from './AnnotationToolbar.svelte';
  import AnnotationOverlay from './AnnotationOverlay.svelte';
  import ViewerRightSidebar from './ViewerRightSidebar.svelte';
  import TextLayer from './TextLayer.svelte';
  import SearchHighlightLayer from './SearchHighlightLayer.svelte';
  import PrintDialog from './PrintDialog.svelte';

  interface Props {
    filePath: string;
    tabId?: string;           // Tab identifier for multi-tab support
    isActive?: boolean;       // Whether this tab is currently active
    showToolbar?: boolean;
    showSidebar?: boolean;
    initialPage?: number;
    initialZoom?: number;
    onClose?: () => void;
    onSave?: () => void;
    onSaveAs?: () => void;
    onAnnotationsDirtyChange?: (dirty: boolean) => void;
  }

  let {
    filePath,
    tabId,
    isActive = true,
    showToolbar = true,
    showSidebar = true,
    initialPage = 1,
    initialZoom = 1,
    onClose,
    onSave,
    onSaveAs,
    onAnnotationsDirtyChange,
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
  let showAnnotationOverlay = $state(true); // Toggle visibility of overlay
  let annotationsDirty = $state(false);
  let isSavingAnnotations = $state(false);
  let annotationsInitialized = $state(false);
  let lastAnnotationCount = $state(0);

  // Print
  let showPrintDialog = $state(false);
  let isPrinting = $state(false);

  // Search trigger (for context menu -> search tab communication)
  let searchTrigger = $state<{ text: string; timestamp: number } | null>(null);

  function handleSearchText(text: string) {
    searchTrigger = { text, timestamp: Date.now() };
  }

  // Search highlight state (for highlighting matches in viewport)
  let searchHighlight = $state<{ query: string; currentPage: number; currentIndex: number }>({
    query: '',
    currentPage: 0,
    currentIndex: 0,
  });

  function handleSearchStateChange(query: string, currentPage: number, currentIndex: number) {
    searchHighlight = { query, currentPage, currentIndex };
  }

  // Load annotations from PDF (industry standard - reads native PDF annotations)
  async function loadAnnotations() {
    try {
      // Read annotations directly from PDF (not from sidecar JSON)
      const json = await invoke<string>('annotations_read_from_pdf', { input: filePath });
      const data = JSON.parse(json);

      if (Object.keys(data).length > 0) {
        // Convert string keys to numbers
        const converted: Record<number, any[]> = {};
        for (const [key, value] of Object.entries(data)) {
          converted[Number(key)] = value as any[];
        }
        annotationsStore.importAnnotations(converted);
        console.log(`[MuPDFViewer] Loaded ${Object.values(data).flat().length} annotations from PDF`);
      }

      // Mark as initialized and not dirty after load
      lastAnnotationCount = annotationsStore.getAllAnnotations().length;
      annotationsInitialized = true;
      annotationsDirty = false;
    } catch (err) {
      console.error('[MuPDFViewer] Failed to load annotations from PDF:', err);
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

  // Annotation menu state
  let showAnnotationMenu = $state(false);
  let isExporting = $state(false);
  let menuButtonRef: HTMLButtonElement;
  let menuPosition = $state({ top: 0, left: 0 });

  function toggleAnnotationMenu() {
    if (!showAnnotationMenu && menuButtonRef) {
      const rect = menuButtonRef.getBoundingClientRect();
      menuPosition = {
        top: rect.bottom + 4,
        left: rect.right - 180, // menu width is 180px
      };
    }
    showAnnotationMenu = !showAnnotationMenu;
  }

  // Convert Date objects to ISO strings for JSON serialization
  function serializeAnnotations() {
    const data = annotationsStore.exportAnnotations() as Record<number, any[]>;
    const serialized: Record<number, any[]> = {};
    for (const [page, anns] of Object.entries(data)) {
      serialized[Number(page)] = anns.map((a: any) => ({
        ...a,
        createdAt: a.createdAt instanceof Date ? a.createdAt.toISOString() : a.createdAt,
        modifiedAt: a.modifiedAt instanceof Date ? a.modifiedAt.toISOString() : a.modifiedAt,
      }));
    }
    return JSON.stringify(serialized);
  }

  // Embed annotations into PDF (overwrite same file)
  async function saveAnnotationsToPdf() {
    const annotationCount = annotationsStore.getAllAnnotations().length;

    if (!confirm(`Save ${annotationCount} annotation${annotationCount !== 1 ? 's' : ''} to PDF?\n\nThis will overwrite the current file.`)) {
      return;
    }

    isExporting = true;
    showAnnotationMenu = false;
    try {
      const json = serializeAnnotations();
      // PyMuPDF reads the file into memory, so we can write directly to the same path
      const result = await invoke<{ output_path: string; total: number; errors: string[] }>(
        'annotations_embed_in_pdf',
        { input: filePath, annotationsJson: json, output: filePath }
      );

      if (result.errors.length > 0) {
        console.warn('[MuPDFViewer] Some annotations failed:', result.errors);
        alert(`Saved ${result.total} annotations. ${result.errors.length} failed.`);
      }

      // Clear dirty flag since annotations are now in PDF
      annotationsDirty = false;

      // Reload the PDF to show embedded annotations
      await loadPDF();
    } catch (err) {
      console.error('[MuPDFViewer] Failed to save annotations to PDF:', err);
      alert(`Failed to save annotations to PDF: ${err}`);
    } finally {
      isExporting = false;
    }
  }

  // Embed annotations into PDF (Save As...)
  async function saveAnnotationsToPdfAs() {
    const outputPath = await save({
      title: 'Save PDF with Annotations',
      defaultPath: filePath.replace('.pdf', '-annotated.pdf'),
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });
    if (!outputPath) return;

    isExporting = true;
    showAnnotationMenu = false;
    try {
      const json = serializeAnnotations();
      const result = await invoke<{ output_path: string; total: number; errors: string[] }>(
        'annotations_embed_in_pdf',
        { input: filePath, annotationsJson: json, output: outputPath }
      );
      if (result.errors.length > 0) {
        console.warn('[MuPDFViewer] Some annotations failed:', result.errors);
        alert(`Saved ${result.total} annotations. ${result.errors.length} failed.`);
      }
      // No success alert needed - file was saved
    } catch (err) {
      console.error('[MuPDFViewer] Failed to embed annotations:', err);
      alert(`Failed to save annotations to PDF: ${err}`);
    } finally {
      isExporting = false;
    }
  }

  // Print document
  async function handlePrint(withAnnotations: boolean) {
    showPrintDialog = false;
    isPrinting = true;

    try {
      let pdfPath = filePath;

      if (withAnnotations && annotationsStore.getAllAnnotations().length > 0) {
        // Embed annotations to temp file
        const json = serializeAnnotations();
        const result = await invoke<{ output_path: string }>(
          'print_prepare_pdf',
          { input: filePath, annotationsJson: json }
        );
        pdfPath = result.output_path;
      }

      // Open system print dialog
      await invoke('print_pdf', { path: pdfPath });
    } catch (err) {
      console.error('[MuPDFViewer] Print failed:', err);
      alert(`Failed to print: ${err}`);
    } finally {
      isPrinting = false;
    }
  }

  // Reload annotations from PDF (discard local changes)
  async function reloadAnnotationsFromPdf() {
    showAnnotationMenu = false;

    if (annotationsDirty) {
      if (!confirm('Discard unsaved changes and reload annotations from PDF?')) {
        return;
      }
    }

    try {
      // Clear current annotations
      annotationsStore.clearAnnotations();

      const json = await invoke<string>('annotations_read_from_pdf', { input: filePath });
      const data = JSON.parse(json);

      if (Object.keys(data).length > 0) {
        const converted: Record<number, any[]> = {};
        for (const [key, value] of Object.entries(data)) {
          converted[Number(key)] = value as any[];
        }
        annotationsStore.importAnnotations(converted);
      }

      lastAnnotationCount = annotationsStore.getAllAnnotations().length;
      annotationsDirty = false;
    } catch (err) {
      console.error('[MuPDFViewer] Failed to reload annotations from PDF:', err);
      alert(`Failed to reload annotations from PDF: ${err}`);
    }
  }

  // Export to XFDF
  async function exportToXfdf() {
    // First embed to a temp PDF, then export XFDF
    const outputPath = await save({
      title: 'Export Annotations as XFDF',
      defaultPath: filePath.replace('.pdf', '.xfdf'),
      filters: [{ name: 'XFDF', extensions: ['xfdf'] }],
    });
    if (!outputPath) return;

    isExporting = true;
    showAnnotationMenu = false;
    try {
      // Create temp PDF with annotations
      const tempPath = filePath.replace('.pdf', '-temp-annot.pdf');
      const json = serializeAnnotations();
      await invoke('annotations_embed_in_pdf', {
        input: filePath,
        annotationsJson: json,
        output: tempPath,
      });

      // Export XFDF from temp PDF
      const result = await invoke<{ output_path: string; exported: number }>(
        'annotations_export_xfdf',
        { input: tempPath, output: outputPath }
      );
      alert(`Exported ${result.exported} annotations to XFDF`);
    } catch (err) {
      console.error('[MuPDFViewer] Failed to export XFDF:', err);
      alert(`Failed to export XFDF: ${err}`);
    } finally {
      isExporting = false;
    }
  }

  // Import from XFDF
  async function importFromXfdf() {
    const xfdfPath = await open({
      title: 'Import Annotations from XFDF',
      filters: [{ name: 'XFDF', extensions: ['xfdf'] }],
    });
    if (!xfdfPath || Array.isArray(xfdfPath)) return;

    showAnnotationMenu = false;
    try {
      // Import XFDF to temp PDF
      const tempPath = filePath.replace('.pdf', '-temp-xfdf.pdf');
      await invoke('annotations_import_xfdf', {
        input: filePath,
        xfdf: xfdfPath,
        output: tempPath,
      });

      // Read annotations from temp PDF
      const json = await invoke<string>('annotations_read_from_pdf', { input: tempPath });
      const data = JSON.parse(json);

      // Convert and import
      const converted: Record<number, any[]> = {};
      for (const [key, value] of Object.entries(data)) {
        converted[Number(key)] = value as any[];
      }
      annotationsStore.importAnnotations(converted);
      annotationsDirty = true;
      alert(`Imported ${Object.values(data).flat().length} annotations from XFDF`);
    } catch (err) {
      console.error('[MuPDFViewer] Failed to import XFDF:', err);
      alert(`Failed to import XFDF: ${err}`);
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

  // Notify parent of dirty state changes
  // Use untrack to prevent the callback reference from being tracked
  // (callbacks are recreated on each parent render, causing infinite loops if tracked)
  $effect(() => {
    const dirty = annotationsDirty;
    untrack(() => {
      onAnnotationsDirtyChange?.(dirty);
    });
  });

  // Track previous isActive state for detecting transitions
  // Using a regular variable (not $state) to avoid effect loop
  let wasActive = isActive;

  // Handle tab activation/deactivation for resource management
  $effect(() => {
    const currentIsActive = isActive; // Read once
    if (currentIsActive && !wasActive) {
      // Tab was re-activated - reload visible pages if they were cleared
      console.log('[MuPDFViewer] Tab activated, reloading visible content');
      if (pdfInfo && loadedPages.size === 0) {
        tick().then(() => {
          loadVisiblePages();
          loadVisibleThumbnails();
        });
      }
    }
    // Update outside of reactive tracking - this doesn't trigger the effect
    // because wasActive is not a $state
    wasActive = currentIsActive;
  });

  // Sidebar state
  let sidebarCollapsed = $state(false);

  // Virtual thumbnails: only load visible ones
  let loadedThumbnails = $state<Map<number, RenderedPage>>(new Map());
  let loadingThumbnails = $state<Set<number>>(new Set());
  const THUMBNAIL_BUFFER = 5; // Load 5 above/below visible

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
    debugLog('MuPDFViewer', 'loadPDF() called', { filePath });
    isLoading = true;
    error = null;

    try {
      debugLog('MuPDFViewer', 'Invoking pdf_open...');
      pdfInfo = await invoke<PdfInfo>('pdf_open', { path: filePath });
      debugLog('MuPDFViewer', 'pdf_open completed', { pages: pdfInfo.num_pages });

      totalPages = pdfInfo.num_pages;
      currentPage = Math.min(initialPage, totalPages);
      fileName = filePath.split('/').pop() || 'Document';
      pageInputValue = String(currentPage);

      debugLog('MuPDFViewer', 'Clearing loaded pages...');
      loadedPages = new Map();
      loadingPages = new Set();

      isLoading = false;
      debugLog('MuPDFViewer', 'isLoading set to false');

      // Clear thumbnails for new document
      debugLog('MuPDFViewer', 'Clearing thumbnails...');
      loadedThumbnails = new Map();
      loadingThumbnails = new Set();

      // Wait for DOM to render, then load visible content
      debugLog('MuPDFViewer', 'Awaiting tick()...');
      await tick();
      debugLog('MuPDFViewer', 'tick() completed, loading visible pages...');
      loadVisiblePages();
      debugLog('MuPDFViewer', 'loadVisiblePages() completed');
      loadVisibleThumbnails();
      debugLog('MuPDFViewer', 'loadVisibleThumbnails() completed');

      // Load saved annotations
      debugLog('MuPDFViewer', 'Loading annotations...');
      await loadAnnotations();
      debugLog('MuPDFViewer', 'Annotations loaded');

      if (initialPage > 1) {
        debugLog('MuPDFViewer', 'Scrolling to initial page', { initialPage });
        scrollToPage(initialPage);
      }

      debugLog('MuPDFViewer', 'loadPDF() completed successfully');
    } catch (err) {
      debugLog('MuPDFViewer', 'loadPDF() FAILED', err, 'error');
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
        hideAnnotations: true, // Always hide PDF annotations - our overlay renders them
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

  // Load a single thumbnail
  async function loadThumbnail(pageNum: number): Promise<void> {
    if (loadedThumbnails.has(pageNum) || loadingThumbnails.has(pageNum)) return;

    loadingThumbnails.add(pageNum);
    loadingThumbnails = new Set(loadingThumbnails);

    try {
      const rendered = await invoke<RenderedPage[]>('pdf_render_thumbnails', {
        path: filePath,
        pages: [pageNum],
        maxSize: 150,
      });

      if (rendered.length > 0) {
        loadedThumbnails.set(pageNum, rendered[0]);
        loadedThumbnails = new Map(loadedThumbnails);
      }
    } catch (err) {
      console.error(`[MuPDFViewer] Failed to load thumbnail ${pageNum}:`, err);
    } finally {
      loadingThumbnails.delete(pageNum);
      loadingThumbnails = new Set(loadingThumbnails);
    }
  }

  // Load visible thumbnails - now handled by PagesTab component
  function loadVisibleThumbnails() {
    // This is now a no-op as PagesTab handles its own thumbnail loading
    // The function is kept for compatibility with initial load calls
  }

  // Handle sidebar scroll - now handled by PagesTab component
  function handleThumbnailScroll() {
    // No-op, PagesTab manages its own scroll handling
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

  // Focus on a search result at specific Y position
  function focusOnSearchResult(page: number, normalizedY: number) {
    if (page < 1 || page > totalPages) return;

    currentPage = page;
    pageInputValue = String(page);

    const element = pageElements.get(page);
    if (element && canvasContainer) {
      isScrollingToPage = true;

      // Get page dimensions
      const dims = getPageDimensions(page - 1);
      const pageHeight = dims.height;

      // Calculate the Y offset within the page
      const yOffset = normalizedY * pageHeight;

      // Get the page's position relative to the container
      const pageRect = element.getBoundingClientRect();
      const containerRect = canvasContainer.getBoundingClientRect();
      const pageTopInContainer = pageRect.top - containerRect.top + canvasContainer.scrollTop;

      // Scroll to position the match roughly in the upper third of viewport
      const targetScroll = pageTopInContainer + yOffset - (containerRect.height / 3);
      canvasContainer.scrollTo({
        top: Math.max(0, targetScroll),
        behavior: 'smooth',
      });

      setTimeout(() => {
        isScrollingToPage = false;
      }, 500);
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

  // Keyboard navigation and shortcuts
  function handleKeydown(e: KeyboardEvent) {
    // Skip if typing in input
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

    const isMod = e.ctrlKey || e.metaKey;

    // Undo: Ctrl+Z
    if (isMod && e.key === 'z' && !e.shiftKey) {
      e.preventDefault();
      if (annotationsStore.canUndo()) {
        annotationsStore.undo();
        annotationsDirty = true;
      }
      return;
    }

    // Redo: Ctrl+Y or Ctrl+Shift+Z
    if (isMod && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
      e.preventDefault();
      if (annotationsStore.canRedo()) {
        annotationsStore.redo();
        annotationsDirty = true;
      }
      return;
    }

    // Save: Ctrl+S
    if (isMod && e.key === 's') {
      e.preventDefault();
      saveAnnotations();
      return;
    }

    // Print: Ctrl+P
    if (isMod && e.key === 'p') {
      e.preventDefault();
      showPrintDialog = true;
      return;
    }

    // Close: Escape
    if (e.key === 'Escape') {
      // Deselect annotation first, or close viewer
      if (annotationsStore.selectedId) {
        annotationsStore.selectAnnotation(null);
      } else if (onClose) {
        onClose();
      }
      return;
    }

    // Navigation
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

  // Close annotation menu when clicking outside
  function handleClickOutside(e: MouseEvent) {
    if (showAnnotationMenu) {
      const target = e.target as HTMLElement;
      // Check if click is inside the menu button or the fixed menu
      const isMenuButton = menuButtonRef?.contains(target);
      const isInsideMenu = target.closest('[style*="z-index: 99999"]');
      if (!isMenuButton && !isInsideMenu) {
        showAnnotationMenu = false;
      }
    }
  }

  // Track if we've already loaded to prevent double-loading
  let hasLoadedFile = '';

  onMount(async () => {
    debugLog('MuPDFViewer', 'onMount() called', { filePath, tabId });
    window.addEventListener('keydown', handleKeydown);
    document.addEventListener('mouseup', handlePanEnd);
    document.addEventListener('click', handleClickOutside);

    // Listen for menu save event (Ctrl+S)
    unlistenSave = await listen('menu-save', () => {
      if (annotationsDirty) {
        saveAnnotationsToPdf();
      }
    });

    debugLog('MuPDFViewer', 'onMount() completed');
  });

  onDestroy(() => {
    debugLog('MuPDFViewer', 'onDestroy() called', { filePath, tabId });
    window.removeEventListener('keydown', handleKeydown);
    document.removeEventListener('mouseup', handlePanEnd);
    document.removeEventListener('click', handleClickOutside);
    unlistenSave?.();
  });

  // Load when file path changes (or on initial mount)
  $effect(() => {
    if (filePath && filePath !== hasLoadedFile) {
      debugLog('MuPDFViewer', '$effect: filePath changed, loading PDF', { from: hasLoadedFile, to: filePath });
      hasLoadedFile = filePath;
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

        <button
          onclick={saveAnnotationsToPdf}
          disabled={isExporting || !annotationsDirty}
          class="p-2 rounded-lg transition-colors relative"
          class:hover:bg-[var(--nord2)]={annotationsDirty && !isExporting}
          class:opacity-40={!annotationsDirty}
          class:cursor-not-allowed={!annotationsDirty}
          class:animate-pulse={isExporting}
          title={annotationsDirty ? "Save annotations to PDF" : "No changes to save"}
        >
          <Save size={16} />
          {#if annotationsDirty}
            <div
              class="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full"
              style="background-color: var(--nord13);"
            ></div>
          {/if}
        </button>

        <!-- Print button -->
        <button
          onclick={() => showPrintDialog = true}
          disabled={isPrinting}
          class="p-2 rounded-lg transition-colors hover:bg-[var(--nord2)]"
          class:animate-pulse={isPrinting}
          title="Print document"
        >
          <Printer size={16} />
        </button>

        <!-- Annotation export/import menu -->
        <button
          bind:this={menuButtonRef}
          onclick={toggleAnnotationMenu}
          class="p-2 rounded-lg transition-colors hover:bg-[var(--nord2)]"
          class:bg-[var(--nord2)]={showAnnotationMenu}
          title="Annotation options"
          disabled={isExporting}
        >
          {#if isExporting}
            <div class="w-4 h-4 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin"></div>
          {:else}
            <MoreVertical size={16} />
          {/if}
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
        <AnnotationToolbar
          store={annotationsStore}
          showOverlay={showAnnotationOverlay}
          onToggleOverlay={() => showAnnotationOverlay = !showAnnotationOverlay}
        />
      </div>
    {/if}
  {/if}

  <div class="flex-1 flex overflow-hidden">
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

                  <!-- Text layer for text selection (always visible for copy support) -->
                  <TextLayer
                    pdfPath={filePath}
                    page={pageNum}
                    pageWidth={loadedPage.width}
                    pageHeight={loadedPage.height}
                    scale={1}
                    store={annotationsStore}
                    showAnnotationTools={showAnnotationTools}
                    onSearchText={handleSearchText}
                  />

                  <!-- Search highlight layer (shows matches when searching) -->
                  {#if searchHighlight.query}
                    <SearchHighlightLayer
                      pdfPath={filePath}
                      page={pageNum}
                      pageWidth={loadedPage.width}
                      pageHeight={loadedPage.height}
                      searchQuery={searchHighlight.query}
                      currentMatchPage={searchHighlight.currentPage}
                      currentMatchIndex={searchHighlight.currentIndex}
                    />
                  {/if}

                  <!-- Annotation overlay (always render since PDF hides native annotations) -->
                  {#if showAnnotationOverlay}
                    <AnnotationOverlay
                      store={annotationsStore}
                      page={pageNum}
                      pageWidth={loadedPage.width}
                      pageHeight={loadedPage.height}
                      scale={1}
                      interactive={showAnnotationTools && annotationsStore.activeTool !== 'text-select'}
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

      {/if}
    </div>

    <!-- Right Sidebar with tabs -->
    {#if showSidebar}
      <ViewerRightSidebar
        {filePath}
        {currentPage}
        {totalPages}
        annotationsStore={annotationsStore}
        {loadedThumbnails}
        {loadingThumbnails}
        onNavigateToPage={goToPage}
        onFocusOnResult={focusOnSearchResult}
        onLoadThumbnail={loadThumbnail}
        onThumbnailScroll={handleThumbnailScroll}
        onFileReload={loadPDF}
        {searchTrigger}
        onSearchStateChange={handleSearchStateChange}
      />
    {/if}
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

<!-- Fixed position annotation menu (portal) -->
{#if showAnnotationMenu}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="fixed py-1 rounded-lg shadow-lg min-w-[180px]"
    style="
      top: {menuPosition.top}px;
      left: {menuPosition.left}px;
      background-color: var(--nord1);
      border: 1px solid var(--nord3);
      z-index: 99999;
    "
    onclick={(e) => e.stopPropagation()}
  >
    <button
      onclick={saveAnnotationsToPdf}
      class="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-[var(--nord2)] transition-colors"
    >
      <Save size={14} />
      Save to PDF
    </button>
    <button
      onclick={saveAnnotationsToPdfAs}
      class="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-[var(--nord2)] transition-colors"
    >
      <Download size={14} />
      Save to PDF as...
    </button>
    <button
      onclick={reloadAnnotationsFromPdf}
      class="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-[var(--nord2)] transition-colors"
    >
      <Upload size={14} />
      Reload from PDF
    </button>
    <div class="my-1 border-t" style="border-color: var(--nord3);"></div>
    <button
      onclick={() => { showPrintDialog = true; showAnnotationMenu = false; }}
      class="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-[var(--nord2)] transition-colors"
      disabled={isPrinting}
    >
      <Printer size={14} />
      Print...
    </button>
    <div class="my-1 border-t" style="border-color: var(--nord3);"></div>
    <button
      onclick={exportToXfdf}
      class="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-[var(--nord2)] transition-colors"
    >
      <FileDown size={14} />
      Export XFDF
    </button>
    <button
      onclick={importFromXfdf}
      class="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-[var(--nord2)] transition-colors"
    >
      <FileUp size={14} />
      Import XFDF
    </button>
  </div>
{/if}

<!-- Print Dialog -->
<PrintDialog
  visible={showPrintDialog}
  annotationCount={annotationsStore.getAllAnnotations().length}
  onPrint={handlePrint}
  onCancel={() => showPrintDialog = false}
/>
