<script lang="ts">
  import { onMount, onDestroy, tick, untrack } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';
  import { listen, type UnlistenFn } from '@tauri-apps/api/event';
  import {
    ChevronLeft,
    ChevronRight,
    X,
    Minus,
    Plus,
    MoveHorizontal,
    MoveVertical,
    Maximize,
    PenTool,
    Save,
    FileDown,
    FileUp,
    Printer,
    FolderOpen,
    FormInput,
    SaveAll,
  } from 'lucide-svelte';
  import { save, open, ask, message } from '@tauri-apps/plugin-dialog';
  import { createAnnotationsStore } from '$lib/stores/annotations.svelte';
  import { debugLog } from '$lib/stores/debugLog.svelte';
  import AnnotationToolbar from './AnnotationToolbar.svelte';
  import AnnotationOverlay from './AnnotationOverlay.svelte';
  import FormFieldsOverlay from './FormFieldsOverlay.svelte';
  import ViewerRightSidebar from './ViewerRightSidebar.svelte';
  import TextLayer from './TextLayer.svelte';
  import SearchHighlightLayer from './SearchHighlightLayer.svelte';
  import PrintDialog from './PrintDialog.svelte';
  import OcrProgressSplash from '../OcrProgressSplash.svelte';
  import {
    loadFormFields,
    getFormsStore,
    resetStore as resetFormsStore,
    toggleFormMode,
    getFilledCount,
    saveFilledForm,
    hasModifications as checkFormModifications,
  } from '$lib/stores/forms.svelte';

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

  // Form Fields
  const formsStore = getFormsStore();

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

  // OCR detection state
  interface OcrAnalysis {
    success: boolean;
    page_count?: number;
    has_text?: boolean;
    has_images?: boolean;
    needs_ocr?: boolean;
    recommendation?: string;
    error?: string;
    missing_languages?: string[];
  }

  let documentNeedsOcr = $state(false);
  let ocrAnalyzed = $state(false);
  let showOcrButton = $state(false);
  let isRunningOcr = $state(false);
  let ocrMessage = $state('Processing OCR...');
  // Track if OCR was completed for this session (persists across reloads)
  let ocrCompletedForSession = $state(false);
  // Store the original file path before OCR (for Save As default directory)
  let originalFilePath = $state<string | null>(null);
  // Store the OCR temp file path for cleanup
  let ocrTempFilePath = $state<string | null>(null);

  // Cleanup OCR temp files
  async function cleanupOcrTempFile() {
    if (!ocrTempFilePath) return;

    try {
      // Get the parent directory (session UUID dir) to delete the whole session
      const sessionDir = ocrTempFilePath.substring(0, ocrTempFilePath.lastIndexOf('/'));
      console.log('[OCR] Cleaning up temp session:', sessionDir);

      // Use Tauri fs to remove the directory
      const { remove } = await import('@tauri-apps/plugin-fs');
      await remove(sessionDir, { recursive: true });

      console.log('[OCR] Temp session cleaned up');
      ocrTempFilePath = null;
    } catch (err) {
      console.warn('[OCR] Failed to cleanup temp file:', err);
    }
  }

  // Analyze document for OCR need (called after PDF loads)
  async function analyzeForOcr() {
    // Skip analysis if OCR was already completed this session
    if (ocrCompletedForSession) {
      debugLog('MuPDFViewer', 'Skipping OCR analysis - already completed this session');
      documentNeedsOcr = false;
      showOcrButton = false;
      ocrAnalyzed = true;
      return;
    }

    try {
      debugLog('MuPDFViewer', 'Analyzing document for OCR need...');
      const result = await invoke<OcrAnalysis>('ocr_analyze_pdf', { input: filePath });
      debugLog('MuPDFViewer', 'OCR analysis result:', result);

      ocrAnalyzed = true;

      // If document already has text, no need to prompt for OCR
      if (result.success && result.has_text && !result.needs_ocr) {
        documentNeedsOcr = false;
        showOcrButton = false;
        return;
      }

      if (result.success && result.needs_ocr) {
        documentNeedsOcr = true;

        // Check for missing language packages
        if (result.missing_languages && result.missing_languages.length > 0) {
          await message(
            `This document appears to be scanned and needs OCR for full functionality.\n\nHowever, some language packages are missing:\n${result.missing_languages.join(', ')}\n\nPlease install the required Tesseract language packages.`,
            { title: 'OCR Language Packages Missing', kind: 'warning' }
          );
          showOcrButton = true;
        } else {
          // Ask user if they want to apply OCR
          const applyOcr = await ask(
            'This document appears to be scanned and has no searchable text.\n\nSome features (search, text selection, annotations) may not work properly without OCR.\n\nWould you like to apply OCR now?',
            { title: 'OCR Recommended', kind: 'info', okLabel: 'Apply OCR', cancelLabel: 'Skip' }
          );

          if (applyOcr) {
            // Run OCR directly with splash notification
            await runOcrOnDocument();
          } else {
            showOcrButton = true;
          }
        }
      }
    } catch (err) {
      debugLog('MuPDFViewer', 'OCR analysis failed:', err, 'error');
      // Don't show error to user, just log it
    }
  }

  // Run OCR on the current document (in-place, then reload)
  async function runOcrOnDocument() {
    console.log('[OCR] Starting runOcrOnDocument...');

    // Store the original file path before OCR for Save As default
    originalFilePath = filePath;

    // Set state first
    isRunningOcr = true;
    ocrMessage = 'Processing OCR...';

    // Force UI update and ensure browser paints before heavy work
    await tick();
    await new Promise(resolve => requestAnimationFrame(resolve));
    await new Promise(resolve => setTimeout(resolve, 100)); // Extra delay to ensure paint

    console.log('[OCR] Splash should be visible now, starting invoke...');

    try {
      console.log('[OCR] Invoking ocr_run...', { filePath });

      const result = await invoke<{ success: boolean; output_path?: string; error?: string }>('ocr_run', {
        input: filePath,
        output: null, // Overwrite original (writes to temp first, then replaces)
        options: {
          language: 'eng+spa',
          deskew: true,
          rotate_pages: true,
          remove_background: false,
          clean: false,
          skip_text: false,
          force_ocr: true,
          redo_ocr: false,
          optimize: 1,
        },
      });

      console.log('[OCR] invoke completed, result:', result);

      if (result.success && result.output_path) {
        console.log('[OCR] Success! output_path:', result.output_path);
        ocrMessage = 'OCR complete! Loading processed document...';

        // Mark OCR as completed for this session - prevents re-prompting
        ocrCompletedForSession = true;
        documentNeedsOcr = false;
        showOcrButton = false;

        // Force UI update
        await tick();

        // Small delay to show success message
        await new Promise(resolve => setTimeout(resolve, 300));

        // Load the OCR'd file instead of the original
        // This is a temp file - user can save it later if they want
        const ocrFilePath = result.output_path;
        ocrTempFilePath = ocrFilePath; // Store for cleanup later
        console.log('[OCR] Loading OCR file:', ocrFilePath);

        // Update filePath to the OCR'd version and reload
        // We dispatch an event to open this in a new tab or replace current
        window.dispatchEvent(new CustomEvent('open-pdf-file', { detail: { path: ocrFilePath, replaceTab: tabId } }));

        console.log('[OCR] Dispatched open-pdf-file event');

        await message('OCR processing completed. You are now viewing the processed document.\n\nThe original file was not modified. Use "Save As" to keep the OCR version.', {
          title: 'OCR Complete',
          kind: 'info',
        });
      } else if (result.success) {
        // Success but no output path - shouldn't happen
        console.warn('[OCR] Success but no output_path');
        await message('OCR completed but no output file was created.', {
          title: 'OCR Warning',
          kind: 'warning',
        });
      } else {
        console.error('[OCR] Failed:', result.error);
        await message(`OCR processing failed: ${result.error}`, {
          title: 'OCR Failed',
          kind: 'error',
        });
        showOcrButton = true;
      }
    } catch (err) {
      console.error('[OCR] Exception:', err);
      await message(`OCR processing failed: ${err}`, {
        title: 'OCR Error',
        kind: 'error',
      });
      showOcrButton = true;
    } finally {
      isRunningOcr = false;
      console.log('[OCR] runOcrOnDocument finished, isRunningOcr:', isRunningOcr);
    }
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

  // Exporting state (used by save functions)
  let isExporting = $state(false);

  // Open document handler - dispatches event for parent to handle
  async function handleOpenDocument() {
    try {
      const selected = await open({
        multiple: false,
        filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
      });
      if (selected && typeof selected === 'string') {
        // Dispatch event to open in new tab
        window.dispatchEvent(new CustomEvent('open-pdf-file', { detail: { path: selected } }));
      }
    } catch (err) {
      console.error('[MuPDFViewer] File dialog error:', err);
    }
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

  // Check if current file is in cache/temp directory
  function isWorkingOnTempFile(): boolean {
    return ocrTempFilePath !== null || filePath.includes('/ocr-sessions/');
  }

  // Embed annotations into PDF (overwrite same file, or Save As if temp file)
  async function saveAnnotationsToPdf() {
    // If working on a temp/cache file, redirect to Save As
    if (isWorkingOnTempFile()) {
      await saveAnnotationsToPdfAs();
      return;
    }

    isExporting = true;
    try {
      const json = serializeAnnotations();
      // PyMuPDF reads the file into memory, so we can write directly to the same path
      const result = await invoke<{ output_path: string; total: number; errors: string[] }>(
        'annotations_embed_in_pdf',
        { input: filePath, annotationsJson: json, output: filePath }
      );

      if (result.errors.length > 0) {
        console.warn('[MuPDFViewer] Some items failed to save:', result.errors);
        await message(`Some changes could not be saved:\n${result.errors.slice(0, 3).join('\n')}${result.errors.length > 3 ? `\n...and ${result.errors.length - 3} more` : ''}`, {
          title: 'Warning',
          kind: 'warning',
        });
      }

      // Clear dirty flag
      annotationsDirty = false;

      // Reload the PDF
      await loadPDF();
    } catch (err) {
      console.error('[MuPDFViewer] Failed to save:', err);
      await message(`Failed to save: ${err}`, { title: 'Error', kind: 'error' });
    } finally {
      isExporting = false;
    }
  }

  // Embed annotations into PDF (Save As...)
  async function saveAnnotationsToPdfAs() {
    // Use original file path for default if available (for OCR'd files in temp dir)
    const basePath = originalFilePath || filePath;
    const defaultSavePath = basePath.replace('.pdf', '-annotated.pdf');

    const outputPath = await save({
      title: 'Save PDF with Annotations',
      defaultPath: defaultSavePath,
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });
    if (!outputPath) return;

    isExporting = true;
    try {
      const json = serializeAnnotations();
      const result = await invoke<{ output_path: string; total: number; errors: string[] }>(
        'annotations_embed_in_pdf',
        { input: filePath, annotationsJson: json, output: outputPath }
      );
      if (result.errors.length > 0) {
        console.warn('[MuPDFViewer] Some annotations failed:', result.errors);
        await message(`Some annotations could not be saved:\n${result.errors.slice(0, 3).join('\n')}${result.errors.length > 3 ? `\n...and ${result.errors.length - 3} more` : ''}`, {
          title: 'Warning',
          kind: 'warning',
        });
      }

      // Switch tab to the saved file
      console.log('[Save] Switching tab to saved file:', outputPath);
      window.dispatchEvent(new CustomEvent('open-pdf-file', { detail: { path: outputPath, replaceTab: tabId } }));

      // Cleanup OCR temp file since we saved successfully
      await cleanupOcrTempFile();

      // Clear original file path tracking - we're now on the saved file
      originalFilePath = null;

    } catch (err) {
      console.error('[MuPDFViewer] Failed to save:', err);
      await message(`Failed to save: ${err}`, { title: 'Error', kind: 'error' });
    } finally {
      isExporting = false;
    }
  }

  // Save filled form to new file
  let isSavingForm = $state(false);

  async function saveFilledFormAs() {
    if (!checkFormModifications()) {
      await message('No form fields have been modified.', { title: 'Save Form', kind: 'info' });
      return;
    }

    const defaultPath = filePath.replace('.pdf', '-filled.pdf');
    const outputPath = await save({
      title: 'Save Filled Form',
      defaultPath,
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });

    if (!outputPath) return;

    isSavingForm = true;
    try {
      const result = await saveFilledForm(outputPath);

      if (result.success) {
        await message(
          `Form saved successfully!\n${result.filled_count} field(s) filled.`,
          { title: 'Save Form', kind: 'info' }
        );
      } else {
        throw new Error(result.errors?.join(', ') || 'Unknown error');
      }
    } catch (err) {
      console.error('[MuPDFViewer] Failed to save form:', err);
      await message(`Failed to save form: ${err}`, { title: 'Error', kind: 'error' });
    } finally {
      isSavingForm = false;
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
  // Version counter to signal file reloads to sidebar components
  let fileReloadVersion = $state(0);

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

      // Increment reload version to signal sidebar components to refresh
      fileReloadVersion++;

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

      // Load form fields
      debugLog('MuPDFViewer', 'Loading form fields...');
      await loadFormFields(filePath);
      debugLog('MuPDFViewer', 'Form fields loaded', { isForm: formsStore.isFormPdf, count: formsStore.fields.length });

      if (initialPage > 1) {
        debugLog('MuPDFViewer', 'Scrolling to initial page', { initialPage });
        scrollToPage(initialPage);
      }

      debugLog('MuPDFViewer', 'loadPDF() completed successfully');

      // Analyze for OCR need (async, don't block)
      ocrAnalyzed = false;
      documentNeedsOcr = false;
      showOcrButton = false;
      analyzeForOcr();
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
        maxSize: 200,
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

  // Smooth scroll animation using easeInOutCubic
  function smoothScrollTo(targetY: number, duration: number = 400) {
    if (!canvasContainer) return;

    const startY = canvasContainer.scrollTop;
    const distance = targetY - startY;
    const startTime = performance.now();

    function easeInOutCubic(t: number): number {
      return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    }

    function animate(currentTime: number) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = easeInOutCubic(progress);

      canvasContainer!.scrollTop = startY + distance * eased;

      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        isScrollingToPage = false;
        loadVisiblePages();
      }
    }

    requestAnimationFrame(animate);
  }

  // Scroll to a specific page
  function scrollToPage(page: number) {
    const element = pageElements.get(page);
    if (element && canvasContainer) {
      // Pre-load the target page and nearby pages BEFORE scrolling
      loadPage(page);
      for (let i = 1; i <= 3; i++) {
        if (page - i >= 1) loadPage(page - i);
        if (page + i <= totalPages) loadPage(page + i);
      }

      isScrollingToPage = true;

      // Get target scroll position
      const containerRect = canvasContainer.getBoundingClientRect();
      const elementRect = element.getBoundingClientRect();
      const targetScroll = elementRect.top - containerRect.top + canvasContainer.scrollTop;

      smoothScrollTo(targetScroll, 350);
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

    // Pre-load target page and neighbors
    loadPage(page);
    for (let i = 1; i <= 3; i++) {
      if (page - i >= 1) loadPage(page - i);
      if (page + i <= totalPages) loadPage(page + i);
    }

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
      const targetScroll = Math.max(0, pageTopInContainer + yOffset - (containerRect.height / 3));
      smoothScrollTo(targetScroll, 350);
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

  // Menu event listeners
  let unlistenSave: UnlistenFn | null = null;
  let unlistenSaveAs: UnlistenFn | null = null;
  let unlistenReload: UnlistenFn | null = null;
  let unlistenExportXfdf: UnlistenFn | null = null;
  let unlistenImportXfdf: UnlistenFn | null = null;
  let unlistenPrint: UnlistenFn | null = null;

  // Track if we've already loaded to prevent double-loading
  let hasLoadedFile = '';

  onMount(async () => {
    debugLog('MuPDFViewer', 'onMount() called', { filePath, tabId });
    window.addEventListener('keydown', handleKeydown);
    document.addEventListener('mouseup', handlePanEnd);

    // Listen for menu events
    unlistenSave = await listen('menu-save', () => {
      if (annotationsDirty) {
        saveAnnotationsToPdf();
      }
    });

    unlistenSaveAs = await listen('menu-save-as', () => {
      saveAnnotationsToPdfAs();
    });

    unlistenReload = await listen('menu-reload-annotations', () => {
      reloadAnnotationsFromPdf();
    });

    unlistenExportXfdf = await listen('menu-export-xfdf', () => {
      exportToXfdf();
    });

    unlistenImportXfdf = await listen('menu-import-xfdf', () => {
      importFromXfdf();
    });

    unlistenPrint = await listen('menu-print', () => {
      showPrintDialog = true;
    });

    debugLog('MuPDFViewer', 'onMount() completed');
  });

  onDestroy(() => {
    debugLog('MuPDFViewer', 'onDestroy() called', { filePath, tabId });
    window.removeEventListener('keydown', handleKeydown);
    document.removeEventListener('mouseup', handlePanEnd);
    unlistenSave?.();
    unlistenSaveAs?.();
    unlistenReload?.();
    unlistenExportXfdf?.();
    unlistenImportXfdf?.();
    unlistenPrint?.();

    // Cleanup OCR temp files when tab is closed
    cleanupOcrTempFile();
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
      <!-- Left: Open, Save, Print, Annotate -->
      <div class="flex items-center gap-1">
        <!-- Open Document -->
        <button
          onclick={handleOpenDocument}
          class="p-2 rounded-lg transition-colors hover:bg-[var(--nord2)]"
          title="Open document (Ctrl+O)"
        >
          <FolderOpen size={16} />
        </button>

        <!-- Save annotations -->
        <button
          onclick={saveAnnotationsToPdf}
          disabled={isExporting || !annotationsDirty}
          class="p-2 rounded-lg transition-colors relative"
          class:hover:bg-[var(--nord2)]={annotationsDirty && !isExporting}
          class:opacity-40={!annotationsDirty}
          class:cursor-not-allowed={!annotationsDirty}
          class:animate-pulse={isExporting}
          title={annotationsDirty ? "Save (Ctrl+S)" : "No changes to save"}
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
          title="Print document (Ctrl+P)"
        >
          <Printer size={16} />
        </button>

        <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

        <!-- Annotation tools toggle -->
        <button
          onclick={() => showAnnotationTools = !showAnnotationTools}
          class="p-2 rounded-lg transition-colors"
          class:bg-[var(--nord8)]={showAnnotationTools}
          style="color: {showAnnotationTools ? 'var(--nord0)' : 'var(--nord4)'};"
          title="Annotation tools"
        >
          <PenTool size={16} />
        </button>

        <!-- Form mode toggle (only shown when PDF has forms) -->
        {#if formsStore.isFormPdf}
          {@const counts = getFilledCount()}
          <button
            onclick={toggleFormMode}
            class="p-2 rounded-lg transition-colors flex items-center gap-1"
            class:bg-[var(--nord14)]={formsStore.formModeEnabled}
            style="color: {formsStore.formModeEnabled ? 'var(--nord0)' : 'var(--nord4)'};"
            title="Form mode - Fill form fields ({counts.filled}/{counts.total} filled)"
          >
            <FormInput size={16} />
            {#if counts.total > 0}
              <span class="text-xs font-medium">{counts.filled}/{counts.total}</span>
            {/if}
          </button>

          <!-- Save form button (only shown when there are modifications) -->
          {#if formsStore.hasModifications}
            <button
              onclick={saveFilledFormAs}
              disabled={isSavingForm}
              class="p-2 rounded-lg transition-colors flex items-center gap-1 bg-[var(--nord13)]"
              class:animate-pulse={isSavingForm}
              style="color: var(--nord0);"
              title="Save filled form"
            >
              <SaveAll size={16} />
              <span class="text-xs font-medium">Save Form</span>
            </button>
          {/if}
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

                  <!-- Form fields overlay - use container dims, not rendered image dims -->
                  {@const pdfSize = pdfInfo?.page_sizes[pageNum - 1] || { width: 612, height: 792 }}
                  <FormFieldsOverlay
                    page={pageNum}
                    pageWidth={dims.width}
                    pageHeight={dims.height}
                    pdfPageWidth={pdfSize.width}
                    pdfPageHeight={pdfSize.height}
                    formModeEnabled={formsStore.formModeEnabled}
                  />
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
        {fileReloadVersion}
        onNavigateToPage={goToPage}
        onFocusOnResult={focusOnSearchResult}
        onLoadThumbnail={loadThumbnail}
        onThumbnailScroll={handleThumbnailScroll}
        onFileReload={loadPDF}
        onRunOcr={runOcrOnDocument}
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
      {#if showOcrButton && documentNeedsOcr}
        <span
          class="px-2 py-0.5 rounded text-[10px]"
          style="background-color: var(--nord13); color: var(--nord0);"
          title="This document may need OCR for full functionality"
        >
          OCR Recommended
        </span>
      {/if}
    </div>
    <div class="flex items-center gap-4">
      <span class="opacity-60">{Math.round(zoom * 100)}%</span>
      <span class="opacity-60">Page {currentPage} of {totalPages}</span>
      <span class="text-[10px] opacity-40">MuPDF</span>
    </div>
  </div>
</div>

<!-- Print Dialog -->
<PrintDialog
  visible={showPrintDialog}
  annotationCount={annotationsStore.getAllAnnotations().length}
  onPrint={handlePrint}
  onCancel={() => showPrintDialog = false}
/>

<!-- OCR Progress Splash -->
<OcrProgressSplash visible={isRunningOcr} message={ocrMessage} />
