<script lang="ts">
  import {
    Upload,
    FolderOpen,
    Trash2,
    FileText,
    ScanText,
    Languages,
    Check,
    AlertCircle,
    AlertTriangle,
    Info,
    Settings2,
    BookOpen
  } from 'lucide-svelte';
  import { listen } from '@tauri-apps/api/event';
  import { open, save } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';
  import { onMount, onDestroy } from 'svelte';
  import { log, logSuccess, logError, logWarning, registerFile, unregisterModule } from '$lib/stores/status.svelte';
  import { setPendingOpenFile } from '$lib/stores/status.svelte';

  interface Props {
    onOpenInViewer?: (path: string) => void;
  }

  let { onOpenInViewer }: Props = $props();

  const MODULE = 'OCR';

  interface OcrDependencies {
    ocrmypdf_installed: boolean;
    ocrmypdf_version: string | null;
    tesseract_installed: boolean;
    tesseract_version: string | null;
    available_languages: string[];
  }

  interface OcrAnalysis {
    success: boolean;
    page_count?: number;
    has_text?: boolean;
    has_images?: boolean;
    needs_ocr?: boolean;
    recommendation?: string;
    error?: string;
  }

  interface OcrResult {
    success: boolean;
    output_path?: string;
    exit_code: number;
    message?: string;
    error?: string;
  }

  interface OcrOptions {
    language: string;
    deskew: boolean;
    rotate_pages: boolean;
    remove_background: boolean;
    clean: boolean;
    skip_text: boolean;
    force_ocr: boolean;
    redo_ocr: boolean;
    optimize: number;
  }

  interface EditableOcrOptions {
    language: string;
    dpi: number;
    font_family: string;
    preserve_images: boolean;
    embed_metrics: boolean;
  }

  interface EditableOcrResult {
    success: boolean;
    output_path?: string;
    mode?: string;
    pages_processed?: number;
    total_blocks?: number;
    metrics_embedded?: boolean;
    error?: string;
  }

  type OcrMode = 'searchable' | 'editable';

  let dependencies = $state<OcrDependencies | null>(null);
  let dependencyError = $state<string | null>(null);
  let isCheckingDeps = $state(true);

  let filePath = $state<string | null>(null);
  let fileName = $state('');
  let analysis = $state<OcrAnalysis | null>(null);
  let isAnalyzing = $state(false);

  let isProcessing = $state(false);
  let result = $state<OcrResult | null>(null);

  let showAdvanced = $state(false);
  let ocrMode = $state<OcrMode>('searchable');

  // Searchable OCR options (invisible text layer)
  let options = $state<OcrOptions>({
    language: 'eng',
    deskew: true,           // Enable by default for better results
    rotate_pages: true,     // Enable by default for scanned docs
    remove_background: false,
    clean: false,           // Requires 'unpaper' to be installed
    skip_text: false,       // Don't skip - we want full OCR
    force_ocr: true,        // Force OCR for Tagged PDFs
    redo_ocr: false,
    optimize: 1,
  });

  // Editable OCR options (real text objects with accurate font sizes)
  let editableOptions = $state<EditableOcrOptions>({
    language: 'eng',
    dpi: 300,
    font_family: 'auto',
    preserve_images: true,
    embed_metrics: true,
  });

  let unlistenDrop: (() => void) | null = null;

  onMount(async () => {
    await checkDependencies();

    unlistenDrop = await listen<string[]>('tauri://file-drop', async (e) => {
      const pdfs = e.payload.filter((p: string) => p.toLowerCase().endsWith('.pdf'));
      if (pdfs.length > 0) {
        await loadFile(pdfs[0]);
      }
    });
  });

  onDestroy(() => {
    if (unlistenDrop) unlistenDrop();
    unregisterModule(MODULE);
  });

  async function checkDependencies() {
    isCheckingDeps = true;
    dependencyError = null;

    try {
      dependencies = await invoke<OcrDependencies>('ocr_check_dependencies');

      if (!dependencies.ocrmypdf_installed) {
        dependencyError = 'OCRmyPDF is not installed. Install with: pip install ocrmypdf';
      } else if (!dependencies.tesseract_installed) {
        dependencyError = 'Tesseract is not installed. Install with your package manager.';
      } else if (dependencies.available_languages.length === 0) {
        logWarning('No Tesseract language packs found. Install with: sudo pacman -S tesseract-data-eng', MODULE);
      }
    } catch (err) {
      console.error('Dependency check failed:', err);
      dependencyError = String(err);
    }

    isCheckingDeps = false;
  }

  async function loadFile(path: string) {
    filePath = path;
    fileName = path.split('/').pop() || path;
    result = null;
    analysis = null;

    registerFile(path, fileName, MODULE);
    log(`Loaded ${fileName}`, 'info', MODULE);

    await analyzeFile(path);
  }

  async function analyzeFile(path: string) {
    isAnalyzing = true;

    try {
      analysis = await invoke<OcrAnalysis>('ocr_analyze_pdf', { input: path });

      if (analysis.success) {
        const status = analysis.needs_ocr
          ? 'File appears to be scanned - OCR recommended'
          : analysis.has_text
            ? 'File already contains text'
            : 'Unable to determine - try OCR';
        log(`Analysis: ${status}`, 'info', MODULE);
      } else {
        logError(`Analysis failed: ${analysis.error}`, MODULE);
      }
    } catch (err) {
      console.error('Analysis failed:', err);
      logError(`Analysis failed: ${err}`, MODULE);
    }

    isAnalyzing = false;
  }

  async function handleFilePicker() {
    const selected = await open({
      multiple: false,
      filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
    });
    if (selected) {
      await loadFile(selected as string);
    }
  }

  function removeFile() {
    filePath = null;
    fileName = '';
    analysis = null;
    result = null;
    unregisterModule(MODULE);
  }

  async function handleOCR() {
    if (!filePath) return;

    const modeLabel = ocrMode === 'editable' ? 'editable' : 'ocr';
    const outputPath = await save({
      title: `Save ${ocrMode === 'editable' ? 'Editable' : 'OCR'} PDF as`,
      filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
      defaultPath: `${modeLabel}_${fileName}`,
    });

    if (!outputPath) return;

    isProcessing = true;
    result = null;

    if (ocrMode === 'editable') {
      log('Running Editable OCR (creating real text objects)...', 'info', MODULE);

      try {
        const editableResult = await invoke<EditableOcrResult>('ocr_run_editable', {
          input: filePath,
          output: outputPath,
          options: {
            ...editableOptions,
            language: options.language, // Use the shared language selector
          },
        });

        // Convert to common result format
        result = {
          success: editableResult.success,
          output_path: editableResult.output_path,
          exit_code: editableResult.success ? 0 : 1,
          message: editableResult.success
            ? `Processed ${editableResult.pages_processed} pages, ${editableResult.total_blocks} text blocks`
            : undefined,
          error: editableResult.error,
        };

        if (editableResult.success) {
          logSuccess(`Editable OCR complete: ${editableResult.output_path}`, MODULE);
          if (editableResult.pages_processed) {
            log(`${editableResult.pages_processed} pages, ${editableResult.total_blocks} text blocks`, 'info', MODULE);
          }
        } else {
          logError(`Editable OCR failed: ${editableResult.error}`, MODULE);
        }
      } catch (err) {
        console.error('Editable OCR error:', err);
        logError(`Editable OCR failed: ${err}`, MODULE);
        result = {
          success: false,
          exit_code: 1,
          error: String(err),
        };
      }
    } else {
      // Searchable OCR mode (original behavior)
      log('Running OCR (creating searchable text layer)...', 'info', MODULE);

      try {
        result = await invoke<OcrResult>('ocr_run', {
          input: filePath,
          output: outputPath,
          options: options,
        });

        if (result.success) {
          logSuccess(`OCR complete: ${result.output_path}`, MODULE);
          if (result.message) {
            log(result.message, 'info', MODULE);
          }
        } else {
          logError(`OCR failed: ${result.error}`, MODULE);
        }
      } catch (err) {
        console.error('OCR error:', err);
        logError(`OCR failed: ${err}`, MODULE);
      }
    }

    isProcessing = false;
  }

  const languageNames: Record<string, string> = {
    eng: 'English',
    spa: 'Spanish',
    fra: 'French',
    deu: 'German',
    ita: 'Italian',
    por: 'Portuguese',
    rus: 'Russian',
    jpn: 'Japanese',
    chi_sim: 'Chinese (Simplified)',
    chi_tra: 'Chinese (Traditional)',
    kor: 'Korean',
    ara: 'Arabic',
    afr: 'Afrikaans',
    osd: 'Orientation/Script Detection',
  };

  function getLanguageName(code: string): string {
    return languageNames[code] || code;
  }

  const canProcess = $derived(() => {
    return filePath !== null && !isProcessing && dependencies?.tesseract_installed && dependencies?.available_languages.length > 0;
  });
</script>

<div class="flex-1 flex overflow-hidden relative">
  <!-- Processing Modal Overlay -->
  {#if isProcessing}
    <div class="fixed inset-0 z-[9999] flex items-center justify-center" style="background-color: rgba(46, 52, 64, 0.95);">
      <div class="flex flex-col items-center gap-6 p-10 rounded-2xl max-w-lg text-center shadow-2xl" style="background-color: var(--nord1); border: 2px solid var(--nord10);">
        <div class="w-24 h-24 rounded-full flex items-center justify-center" style="background-color: var(--nord2);">
          <div class="w-16 h-16 border-4 border-[var(--nord10)] border-t-transparent rounded-full animate-spin"></div>
        </div>
        <div>
          <h3 class="text-2xl font-semibold mb-3" style="color: var(--nord10);">
            {ocrMode === 'editable' ? 'Creating Editable PDF' : 'Running OCR'}
          </h3>
          <p class="text-base opacity-70">
            {ocrMode === 'editable'
              ? 'Extracting text and calculating font sizes...'
              : 'Adding searchable text layer...'}
          </p>
        </div>
        <div class="w-full mt-2">
          <div class="h-3 rounded-full overflow-hidden" style="background-color: var(--nord3);">
            <div
              class="h-full rounded-full"
              style="background-color: var(--nord10); animation: progress-indeterminate 1.5s ease-in-out infinite;"
            ></div>
          </div>
          <p class="text-sm opacity-50 mt-4">This may take several minutes for large documents</p>
          <p class="text-xs opacity-30 mt-1">Do not close this window</p>
        </div>
      </div>
    </div>
  {/if}

  <!-- Main Content Area -->
  <div class="flex-1 flex flex-col overflow-y-auto p-6">
    {#if isCheckingDeps}
      <!-- Checking Dependencies -->
      <div
        class="flex-1 flex flex-col items-center justify-center rounded-xl"
        style="background-color: var(--nord1);"
      >
        <div class="w-8 h-8 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin mb-4"></div>
        <p class="opacity-60">Checking OCR dependencies...</p>
      </div>
    {:else if dependencyError}
      <!-- Dependency Error -->
      <div
        class="flex-1 flex flex-col items-center justify-center rounded-xl"
        style="background-color: var(--nord1);"
      >
        <AlertCircle size={64} style="color: var(--nord11);" class="mb-4" />
        <p class="text-xl mb-2" style="color: var(--nord11);">OCR Not Available</p>
        <p class="text-sm opacity-60 mb-4 text-center max-w-md">{dependencyError}</p>
        <button
          onclick={checkDependencies}
          class="px-4 py-2 rounded-lg transition-colors hover:opacity-80"
          style="background-color: var(--nord2); border: 1px solid var(--nord3);"
        >
          Retry Check
        </button>
      </div>
    {:else if !filePath}
      <!-- Empty State -->
      <div
        class="flex-1 flex flex-col items-center justify-center rounded-xl border-2 border-dashed cursor-pointer transition-colors hover:border-[var(--nord8)]"
        style="border-color: var(--nord3); background-color: var(--nord1);"
        role="button"
        tabindex="0"
        onclick={handleFilePicker}
        onkeydown={(e) => e.key === 'Enter' && handleFilePicker()}
      >
        <ScanText size={64} class="opacity-30 mb-4" />
        <p class="text-xl opacity-60 mb-2">OCR PDF</p>
        <p class="text-sm opacity-40 mb-6 text-center max-w-xs">
          Add searchable text layer to scanned documents
        </p>
        <button
          class="flex items-center gap-2 px-6 py-3 rounded-lg transition-colors hover:opacity-90"
          style="background-color: var(--nord8); color: var(--nord0);"
        >
          <FolderOpen size={20} />
          <span>Select File</span>
        </button>

        {#if dependencies}
          <div class="mt-6 text-xs opacity-40">
            <p>Tesseract {dependencies.tesseract_version} | {dependencies.available_languages.length} language(s) available</p>
          </div>
        {/if}
      </div>
    {:else}
      <!-- File Loaded State -->
      <div class="flex-1 flex flex-col gap-6">
        <!-- File Info Card -->
        <div
          class="rounded-xl p-6"
          style="background-color: var(--nord1);"
        >
          <div class="flex items-start gap-4">
            <div
              class="w-16 h-16 rounded-xl flex items-center justify-center"
              style="background-color: var(--nord2);"
            >
              <FileText size={32} style="color: var(--nord8);" />
            </div>
            <div class="flex-1">
              <h3 class="text-lg font-medium mb-1">{fileName}</h3>
              {#if isAnalyzing}
                <p class="text-sm opacity-60">Analyzing...</p>
              {:else if analysis?.success}
                <div class="flex items-center gap-4 text-sm opacity-60">
                  <span>{analysis.page_count} pages</span>
                  <span>|</span>
                  <span class:text-[var(--nord14)]={analysis.needs_ocr}>
                    {analysis.recommendation}
                  </span>
                </div>
                <div class="mt-2 flex items-center gap-4 text-xs">
                  {#if analysis.has_images}
                    <span class="flex items-center gap-1">
                      <Check size={12} style="color: var(--nord14);" />
                      Contains images
                    </span>
                  {/if}
                  {#if analysis.has_text}
                    <span class="flex items-center gap-1">
                      <Info size={12} style="color: var(--nord8);" />
                      Has text layer
                    </span>
                  {/if}
                </div>
              {:else if analysis?.error}
                <p class="text-sm" style="color: var(--nord11);">{analysis.error}</p>
              {/if}
            </div>
            <button
              onclick={removeFile}
              class="p-2 rounded hover:bg-[var(--nord2)] transition-colors"
              style="color: var(--nord11);"
              title="Remove file"
            >
              <Trash2 size={20} />
            </button>
          </div>
        </div>

        <!-- OCR Mode & Settings -->
        <div
          class="rounded-xl p-6"
          style="background-color: var(--nord1);"
        >
          <div class="flex items-center justify-between mb-4">
            <h4 class="text-sm opacity-60 uppercase">OCR Settings</h4>
            <button
              onclick={() => showAdvanced = !showAdvanced}
              class="flex items-center gap-1 text-xs px-2 py-1 rounded hover:bg-[var(--nord2)]"
            >
              <Settings2 size={14} />
              {showAdvanced ? 'Hide' : 'Show'} Advanced
            </button>
          </div>

          <!-- Mode Selector -->
          <div class="mb-4">
            <p class="text-xs opacity-50 mb-2">OCR Mode</p>
            <div class="flex gap-2">
              <button
                onclick={() => ocrMode = 'searchable'}
                class="flex-1 px-3 py-2 rounded-lg text-sm transition-colors"
                style="background-color: {ocrMode === 'searchable' ? 'var(--nord8)' : 'var(--nord2)'}; color: {ocrMode === 'searchable' ? 'var(--nord0)' : 'inherit'};"
              >
                Searchable
              </button>
              <button
                onclick={() => ocrMode = 'editable'}
                class="flex-1 px-3 py-2 rounded-lg text-sm transition-colors"
                style="background-color: {ocrMode === 'editable' ? 'var(--nord10)' : 'var(--nord2)'}; color: {ocrMode === 'editable' ? 'var(--nord6)' : 'inherit'};"
              >
                Editable
              </button>
            </div>
            <p class="text-xs opacity-40 mt-2">
              {#if ocrMode === 'searchable'}
                Creates invisible text layer for search. Original look preserved.
              {:else}
                Creates real editable text. Accurate font sizes for editing.
              {/if}
            </p>
          </div>

          <div class="flex items-center gap-4 mb-4">
            <Languages size={20} style="color: var(--nord8);" />
            <select
              bind:value={options.language}
              class="flex-1 px-3 py-2 rounded-lg border"
              style="background-color: var(--nord2); border-color: var(--nord3);"
            >
              {#each dependencies?.available_languages || [] as lang}
                <option value={lang}>{getLanguageName(lang)}</option>
              {/each}
            </select>
          </div>

          {#if showAdvanced}
            <div class="pt-4 border-t" style="border-color: var(--nord3);">
              {#if ocrMode === 'searchable'}
                <!-- Searchable OCR options -->
                <div class="grid grid-cols-2 gap-4">
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" bind:checked={options.deskew} class="rounded" />
                    <span class="text-sm">Deskew pages</span>
                  </label>
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" bind:checked={options.rotate_pages} class="rounded" />
                    <span class="text-sm">Auto-rotate pages</span>
                  </label>
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" bind:checked={options.clean} class="rounded" />
                    <span class="text-sm">Clean pages</span>
                  </label>
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" bind:checked={options.remove_background} class="rounded" />
                    <span class="text-sm">Remove background</span>
                  </label>
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" bind:checked={options.skip_text} class="rounded" />
                    <span class="text-sm">Skip pages with text</span>
                  </label>
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" bind:checked={options.force_ocr} class="rounded" />
                    <span class="text-sm">Force OCR</span>
                  </label>

                  <div class="col-span-2 flex items-center gap-4">
                    <span class="text-sm opacity-60">Optimization:</span>
                    <input
                      type="range"
                      min="0"
                      max="3"
                      bind:value={options.optimize}
                      class="flex-1"
                    />
                    <span class="text-sm w-8">{options.optimize}</span>
                  </div>
                </div>
              {:else}
                <!-- Editable OCR options -->
                <div class="space-y-4">
                  <div class="flex items-center gap-4">
                    <span class="text-sm opacity-60 w-24">DPI:</span>
                    <select
                      bind:value={editableOptions.dpi}
                      class="flex-1 px-3 py-2 rounded-lg border"
                      style="background-color: var(--nord2); border-color: var(--nord3);"
                    >
                      <option value={150}>150 DPI (Faster)</option>
                      <option value={300}>300 DPI (Recommended)</option>
                      <option value={400}>400 DPI (Higher quality)</option>
                    </select>
                  </div>

                  <div class="flex items-center gap-4">
                    <span class="text-sm opacity-60 w-24">Font:</span>
                    <select
                      bind:value={editableOptions.font_family}
                      class="flex-1 px-3 py-2 rounded-lg border"
                      style="background-color: var(--nord2); border-color: var(--nord3);"
                    >
                      <option value="auto">Auto (Serif)</option>
                      <option value="times">Times/Serif</option>
                      <option value="helvetica">Helvetica/Sans</option>
                      <option value="courier">Courier/Mono</option>
                    </select>
                  </div>

                  <div class="grid grid-cols-2 gap-4">
                    <label class="flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" bind:checked={editableOptions.preserve_images} class="rounded" />
                      <span class="text-sm">Preserve images</span>
                    </label>
                    <label class="flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" bind:checked={editableOptions.embed_metrics} class="rounded" />
                      <span class="text-sm">Embed metrics</span>
                    </label>
                  </div>

                  <p class="text-xs opacity-40">
                    Higher DPI improves font size accuracy but takes longer.
                    Embedded metrics enable precise editing in future sessions.
                  </p>
                </div>
              {/if}
            </div>
          {/if}
        </div>

        <!-- Result Card -->
        {#if result && !isProcessing}
          <div
            class="rounded-xl p-6"
            style="background-color: var(--nord1); border: 2px solid {result.success ? 'var(--nord14)' : 'var(--nord11)'};"
          >
            {#if result.success}
              <div class="flex items-center gap-4 mb-4">
                <div class="w-14 h-14 rounded-full flex items-center justify-center" style="background-color: rgba(163, 190, 140, 0.2);">
                  <Check size={28} style="color: var(--nord14);" />
                </div>
                <div class="flex-1">
                  <h4 class="text-lg font-medium" style="color: var(--nord14);">
                    {ocrMode === 'editable' ? 'Editable PDF Created!' : 'OCR Complete!'}
                  </h4>
                  {#if result.message}
                    <p class="text-sm opacity-60">{result.message}</p>
                  {/if}
                </div>
              </div>

              <p class="text-xs opacity-50 mb-4 truncate" title={result.output_path}>
                Saved to: {result.output_path}
              </p>

              {#if result?.output_path && onOpenInViewer}
                {@const outputPath = result.output_path}
                <button
                  onclick={() => onOpenInViewer(outputPath)}
                  class="flex items-center justify-center gap-3 w-full px-6 py-4 rounded-xl transition-all hover:scale-[1.02] active:scale-[0.98]"
                  style="background-color: var(--nord10); color: var(--nord6); font-size: 1rem; font-weight: 500;"
                >
                  <BookOpen size={22} />
                  <span>Open in Viewer / Editor</span>
                </button>
              {/if}
            {:else}
              <div class="flex items-center gap-4">
                <div class="w-14 h-14 rounded-full flex items-center justify-center" style="background-color: rgba(191, 97, 106, 0.2);">
                  <AlertCircle size={28} style="color: var(--nord11);" />
                </div>
                <div class="flex-1">
                  <h4 class="text-lg font-medium" style="color: var(--nord11);">OCR Failed</h4>
                  <p class="text-sm opacity-60">{result.error}</p>
                </div>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Spacer -->
        <div class="flex-1"></div>
      </div>
    {/if}
  </div>

  <!-- Right Sidebar -->
  <div
    class="w-64 flex flex-col gap-4 p-4 border-l"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <!-- Action Buttons -->
    <div class="flex-1 flex flex-col gap-3">
      <button
        onclick={handleFilePicker}
        class="flex items-center justify-center gap-2 px-4 py-3 rounded-lg transition-colors hover:opacity-80"
        style="background-color: var(--nord2); border: 1px solid var(--nord3);"
      >
        <FolderOpen size={18} />
        <span class="text-sm">{filePath ? 'Change File' : 'Select File'}</span>
      </button>

      {#if filePath}
        <button
          onclick={handleOCR}
          disabled={!canProcess()}
          class="flex items-center justify-center gap-2 px-4 py-3 rounded-lg transition-colors disabled:opacity-50 hover:opacity-90"
          style="background-color: {ocrMode === 'editable' ? 'var(--nord10)' : 'var(--nord8)'}; color: {ocrMode === 'editable' ? 'var(--nord6)' : 'var(--nord0)'};"
        >
          {#if isProcessing}
            <div class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
            <span>Processing...</span>
          {:else}
            <ScanText size={18} />
            <span>{ocrMode === 'editable' ? 'Run Editable OCR' : 'Run OCR'}</span>
          {/if}
        </button>
      {/if}
    </div>

    <!-- Info -->
    <div class="text-xs opacity-50 p-3 rounded-lg" style="background-color: var(--nord2);">
      <p class="mb-2 font-medium">
        {ocrMode === 'editable' ? 'About Editable OCR' : 'About OCR'}
      </p>
      <ul class="space-y-1 list-disc list-inside">
        {#if ocrMode === 'editable'}
          <li>Creates real editable text</li>
          <li>Accurate font sizes</li>
          <li>Preserves images/logos</li>
        {:else}
          <li>Adds searchable text layer</li>
          <li>Works on scanned documents</li>
          <li>Preserves original quality</li>
        {/if}
      </ul>

      {#if dependencies?.available_languages.length === 0}
        <div class="mt-3 p-2 rounded" style="background-color: rgba(235, 203, 139, 0.2);">
          <p style="color: var(--nord13);">
            No language packs installed. Run:
          </p>
          <code class="text-[10px] block mt-1">
            sudo pacman -S tesseract-data-eng
          </code>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  @keyframes progress-slide {
    0% {
      transform: translateX(-100%);
    }
    50% {
      transform: translateX(0%);
    }
    100% {
      transform: translateX(100%);
    }
  }

  @keyframes progress-indeterminate {
    0% {
      width: 0%;
      margin-left: 0%;
    }
    50% {
      width: 60%;
      margin-left: 20%;
    }
    100% {
      width: 0%;
      margin-left: 100%;
    }
  }
</style>
