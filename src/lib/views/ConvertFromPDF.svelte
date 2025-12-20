<script lang="ts">
  import { Upload, FolderOpen, Download, Image, HelpCircle, FileText, ChevronLeft, ChevronRight } from 'lucide-svelte';
  import { listen } from '@tauri-apps/api/event';
  import { open } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';
  import { onMount, onDestroy } from 'svelte';
  import { log, logSuccess, logError, registerFile, unregisterModule } from '$lib/stores/status.svelte';

  const MODULE = 'Export';

  interface PDFInfo {
    path: string;
    name: string;
    pageCount: number;
    thumbnails: (string | null)[];
    isLoading: boolean;
    error: string | null;
  }

  // State
  let pdfFile = $state<PDFInfo | null>(null);
  let isExporting = $state(false);
  let unlistenDrop: (() => void) | null = null;
  let previewPage = $state(0);

  // Options
  let outputFormat = $state<'png' | 'jpg' | 'webp' | 'tiff'>('png');
  let dpi = $state(150);
  let pageRange = $state<'all' | 'custom'>('all');
  let customRange = $state('');

  onMount(async () => {
    unlistenDrop = await listen<string[]>('tauri://file-drop', async (e) => {
      const pdfs = e.payload.filter((p: string) => {
        const ext = p.split('.').pop()?.toLowerCase() || '';
        return ext === 'pdf';
      });
      if (pdfs.length > 0) {
        await loadPDF(pdfs[0]);
      }
    });
  });

  onDestroy(() => {
    if (unlistenDrop) unlistenDrop();
    unregisterModule(MODULE);
  });

  async function handleFilePicker() {
    const selected = await open({
      multiple: false,
      filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
    });
    if (selected) {
      await loadPDF(selected as string);
    }
  }

  async function loadPDF(path: string) {
    const name = path.split('/').pop() || path;

    pdfFile = {
      path,
      name,
      pageCount: 0,
      thumbnails: [],
      isLoading: true,
      error: null,
    };

    try {
      // Get page count by invoking backend
      const { readFile } = await import('@tauri-apps/plugin-fs');
      const contents = await readFile(path);

      // Use pdf.js or similar to get page count - for now we'll parse from the file
      // This is a simple approach; in production you'd want proper PDF parsing
      const text = new TextDecoder('latin1').decode(contents.slice(0, 50000));
      const countMatch = text.match(/\/Count\s+(\d+)/);
      const pageCount = countMatch ? parseInt(countMatch[1], 10) : 1;

      pdfFile = {
        ...pdfFile,
        pageCount,
        thumbnails: new Array(pageCount).fill(null),
        isLoading: false,
      };

      previewPage = 0;
      registerFile(path, name, MODULE);
      log(`Loaded ${name} (${pageCount} pages)`, 'info', MODULE);
    } catch (err) {
      console.error('Error loading PDF:', err);
      pdfFile = {
        ...pdfFile!,
        isLoading: false,
        error: String(err),
      };
      logError(`Failed to load PDF: ${err}`, MODULE);
    }
  }

  function clearFile() {
    pdfFile = null;
    previewPage = 0;
  }

  function prevPage() {
    if (pdfFile && previewPage > 0) {
      previewPage--;
    }
  }

  function nextPage() {
    if (pdfFile && previewPage < pdfFile.pageCount - 1) {
      previewPage++;
    }
  }

  async function handleExport() {
    if (!pdfFile) return;

    isExporting = true;
    log('Exporting PDF to images...', 'info', MODULE);

    try {
      const { open: openDialog } = await import('@tauri-apps/plugin-dialog');
      const outputDir = await openDialog({
        directory: true,
        title: 'Select output folder',
      });

      if (!outputDir) {
        isExporting = false;
        return;
      }

      const pages = pageRange === 'custom' && customRange ? customRange : undefined;

      const result = await invoke<string[]>('pdf_to_images', {
        input: pdfFile.path,
        outputDir: outputDir,
        format: outputFormat,
        dpi: dpi,
        pages: pages,
      });

      const count = result.length > 1 ? result.length - 1 : pdfFile.pageCount;
      logSuccess(`Exported ${count} images to ${outputDir}`, MODULE);
    } catch (err) {
      console.error('Export error:', err);
      logError(`Export failed: ${err}`, MODULE);
    }

    isExporting = false;
  }

  const canExport = $derived(pdfFile !== null && !pdfFile.isLoading && !isExporting);
</script>

<div class="flex-1 flex overflow-hidden">
  <!-- Main Content Area -->
  <div class="flex-1 flex flex-col overflow-hidden">
    <!-- Options Toolbar -->
    <div
      class="flex items-center gap-6 px-4 py-3 border-b"
      style="background-color: var(--nord1); border-color: var(--nord3);"
    >
      <!-- Format -->
      <div class="flex items-center gap-2">
        <span class="text-xs opacity-60 uppercase">Format</span>
        <div class="flex gap-1">
          {#each ['png', 'jpg', 'webp', 'tiff'] as fmt}
            <button
              onclick={() => outputFormat = fmt as typeof outputFormat}
              class="px-3 py-1.5 rounded text-xs transition-colors uppercase"
              style="background-color: {outputFormat === fmt ? 'var(--nord8)' : 'var(--nord2)'};
                     color: {outputFormat === fmt ? 'var(--nord0)' : 'var(--nord4)'};
                     border: 1px solid var(--nord3);"
            >
              {fmt}
            </button>
          {/each}
        </div>
      </div>

      <!-- DPI -->
      <div class="flex items-center gap-2">
        <span class="text-xs opacity-60 uppercase">DPI</span>
        <div class="flex items-center gap-1">
          <input
            type="number"
            bind:value={dpi}
            min="72"
            max="600"
            step="50"
            class="w-20 px-2 py-1.5 rounded text-sm text-center"
            style="background-color: var(--nord2); border: 1px solid var(--nord3);"
          />
          <div class="relative group">
            <HelpCircle size={14} class="opacity-40 cursor-help" />
            <div
              class="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 px-3 py-2 rounded text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10"
              style="background-color: var(--nord3);"
            >
              72=Screen, 150=Default, 300=Print
            </div>
          </div>
        </div>
      </div>

      <!-- Page Range -->
      <div class="flex items-center gap-2">
        <span class="text-xs opacity-60 uppercase">Pages</span>
        <div class="flex gap-1">
          <button
            onclick={() => pageRange = 'all'}
            class="px-3 py-1.5 rounded text-xs transition-colors"
            style="background-color: {pageRange === 'all' ? 'var(--nord8)' : 'var(--nord2)'};
                   color: {pageRange === 'all' ? 'var(--nord0)' : 'var(--nord4)'};
                   border: 1px solid var(--nord3);"
          >
            All
          </button>
          <button
            onclick={() => pageRange = 'custom'}
            class="px-3 py-1.5 rounded text-xs transition-colors"
            style="background-color: {pageRange === 'custom' ? 'var(--nord8)' : 'var(--nord2)'};
                   color: {pageRange === 'custom' ? 'var(--nord0)' : 'var(--nord4)'};
                   border: 1px solid var(--nord3);"
          >
            Custom
          </button>
        </div>
        {#if pageRange === 'custom'}
          <input
            type="text"
            bind:value={customRange}
            placeholder="1-3,5,7"
            class="w-24 px-2 py-1.5 rounded text-sm"
            style="background-color: var(--nord2); border: 1px solid var(--nord3);"
          />
        {/if}
      </div>

      <!-- File info -->
      {#if pdfFile}
        <span class="text-xs opacity-60 ml-auto">
          {pdfFile.pageCount} page{pdfFile.pageCount !== 1 ? 's' : ''}
        </span>
      {/if}
    </div>

    <!-- Content Area -->
    <div class="flex-1 overflow-auto p-4">
      {#if !pdfFile}
        <!-- Empty State -->
        <div
          class="h-full flex flex-col items-center justify-center rounded-lg"
          style="background-color: var(--nord1);"
        >
          <FileText size={48} class="opacity-40 mb-4" />
          <p class="text-lg opacity-60 mb-2">No PDF loaded</p>
          <p class="text-sm opacity-40 mb-4">Drag & drop a PDF or use the panel on the right</p>
        </div>
      {:else if pdfFile.isLoading}
        <!-- Loading State -->
        <div
          class="h-full flex flex-col items-center justify-center rounded-lg"
          style="background-color: var(--nord1);"
        >
          <div class="w-8 h-8 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin mb-4"></div>
          <p class="text-sm opacity-60">Loading PDF...</p>
        </div>
      {:else if pdfFile.error}
        <!-- Error State -->
        <div
          class="h-full flex flex-col items-center justify-center rounded-lg"
          style="background-color: var(--nord1);"
        >
          <p class="text-lg mb-2" style="color: var(--nord11);">Error loading PDF</p>
          <p class="text-sm opacity-60">{pdfFile.error}</p>
          <button
            onclick={clearFile}
            class="mt-4 px-4 py-2 rounded text-sm hover:opacity-80"
            style="background-color: var(--nord2);"
          >
            Try Again
          </button>
        </div>
      {:else}
        <!-- PDF Preview -->
        <div
          class="h-full flex flex-col rounded-lg"
          style="background-color: var(--nord1);"
        >
          <!-- Preview Header -->
          <div class="flex items-center justify-between px-4 py-2 border-b" style="border-color: var(--nord3);">
            <p class="text-sm truncate" title={pdfFile.path}>{pdfFile.name}</p>
            <button
              onclick={clearFile}
              class="text-xs px-2 py-1 rounded hover:bg-[var(--nord2)] transition-colors"
              style="color: var(--nord11);"
            >
              Clear
            </button>
          </div>

          <!-- Preview Content -->
          <div class="flex-1 flex items-center justify-center p-8">
            <div
              class="w-64 h-80 rounded flex items-center justify-center"
              style="background-color: var(--nord2);"
            >
              <div class="text-center">
                <FileText size={48} class="mx-auto opacity-40 mb-3" />
                <p class="text-2xl font-bold" style="color: var(--nord8);">
                  Page {previewPage + 1}
                </p>
                <p class="text-xs opacity-50 mt-1">of {pdfFile.pageCount}</p>
              </div>
            </div>
          </div>

          <!-- Page Navigation -->
          <div class="flex items-center justify-center gap-4 px-4 py-3 border-t" style="border-color: var(--nord3);">
            <button
              onclick={prevPage}
              disabled={previewPage === 0}
              class="p-2 rounded hover:bg-[var(--nord2)] transition-colors disabled:opacity-30"
            >
              <ChevronLeft size={20} />
            </button>
            <span class="text-sm">
              {previewPage + 1} / {pdfFile.pageCount}
            </span>
            <button
              onclick={nextPage}
              disabled={previewPage >= pdfFile.pageCount - 1}
              class="p-2 rounded hover:bg-[var(--nord2)] transition-colors disabled:opacity-30"
            >
              <ChevronRight size={20} />
            </button>
          </div>
        </div>
      {/if}
    </div>
  </div>

  <!-- Right Sidebar -->
  <div
    class="w-[15%] min-w-[180px] flex flex-col gap-4 p-4 border-l"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <!-- Drop Area -->
    {#if !pdfFile}
      <div
        class="flex-1 flex flex-col items-center justify-center border-2 border-dashed rounded-lg p-4 cursor-pointer"
        style="border-color: var(--nord3);"
        role="button"
        tabindex="0"
        onclick={handleFilePicker}
        onkeydown={(e) => e.key === 'Enter' && handleFilePicker()}
      >
        <Upload size={32} style="color: var(--nord8);" class="mb-2" />
        <p class="text-sm text-center opacity-60">Drop PDF here or click to browse</p>
      </div>
    {:else}
      <!-- Output Preview -->
      <div class="flex-1 overflow-y-auto">
        <h4 class="text-xs opacity-60 mb-3 uppercase">Output Preview</h4>
        <div class="space-y-2">
          {#each Array(Math.min(pdfFile.pageCount, 8)) as _, i}
            <div
              class="p-2 rounded flex items-center gap-2"
              style="background-color: var(--nord2);"
            >
              <Image size={14} class="flex-shrink-0 opacity-60" />
              <p class="text-xs truncate">page_{String(i + 1).padStart(4, '0')}.{outputFormat}</p>
            </div>
          {/each}
          {#if pdfFile.pageCount > 8}
            <p class="text-xs opacity-40 text-center">
              +{pdfFile.pageCount - 8} more...
            </p>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Load PDF Button -->
    <button
      onclick={handleFilePicker}
      class="flex items-center justify-center gap-2 px-4 py-3 rounded transition-colors hover:opacity-80"
      style="background-color: var(--nord2); border: 1px solid var(--nord3);"
    >
      <FolderOpen size={18} />
      <span class="text-sm">{pdfFile ? 'Change PDF' : 'Load PDF'}</span>
    </button>

    <!-- Export Button -->
    <button
      onclick={handleExport}
      disabled={!canExport}
      class="px-4 py-3 rounded transition-colors disabled:opacity-50 hover:opacity-90 flex items-center justify-center gap-2"
      style="background-color: var(--nord14); color: var(--nord0);"
    >
      {#if isExporting}
        <div class="w-4 h-4 border-2 border-[var(--nord0)] border-t-transparent rounded-full animate-spin"></div>
        <span>Exporting...</span>
      {:else}
        <Download size={18} />
        <span>Export Images</span>
      {/if}
    </button>
  </div>
</div>
