<script lang="ts">
  import { Upload, FolderOpen, Trash2, FileText, Scissors, Layers, Grid3x3, FileOutput, FileX, HelpCircle } from 'lucide-svelte';
  import { listen } from '@tauri-apps/api/event';
  import { open, save } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';
  import { onMount, onDestroy } from 'svelte';
  import {
    getPageCount,
    loadPdfPages,
    clearPdfCache,
    type PageData
  } from '$lib/utils/pdfjs';
  import PageSelector from '$lib/components/PageSelector.svelte';
  import PagePreviewModal from '$lib/components/PagePreviewModal.svelte';
  import { log, logSuccess, logError, registerFile, unregisterModule } from '$lib/stores/status.svelte';

  const MODULE = 'Split';

  interface PDFFile {
    id: string;
    name: string;
    path: string;
    pageCount: number;
    pages: PageData[];
    isLoading: boolean;
    error: string | null;
  }

  let file = $state<PDFFile | null>(null);
  let splitMode = $state<'all' | 'pages' | 'groups' | 'extract' | 'remove'>('pages');
  let selectedPages = $state<Set<number>>(new Set());
  let groups = $state<number[][]>([]);
  let isSplitting = $state(false);
  let unlistenDrop: (() => void) | null = null;

  // Preview modal state
  let previewPage = $state<PageData | null>(null);

  onMount(async () => {
    unlistenDrop = await listen<string[]>('tauri://file-drop', async (e) => {
      const pdfs = e.payload.filter((p: string) => p.toLowerCase().endsWith('.pdf'));
      if (pdfs.length > 0) {
        await loadFile(pdfs[0]); // Only take the first file
      }
    });
  });

  onDestroy(() => {
    if (unlistenDrop) unlistenDrop();
    if (file) clearPdfCache(file.path);
    unregisterModule(MODULE);
  });

  async function loadFile(path: string) {
    // Clear previous file
    if (file) {
      clearPdfCache(file.path);
    }

    const name = path.split('/').pop() || path;
    const fileId = `file-${Date.now()}`;

    file = {
      id: fileId,
      name,
      path,
      pageCount: 0,
      pages: [],
      isLoading: true,
      error: null,
    };

    // Reset selections
    selectedPages = new Set();
    groups = [];

    try {
      const pageCount = await getPageCount(path);
      file = { ...file, pageCount };

      const pages = await loadPdfPages(path, fileId, name, 140);
      file = { ...file, pages, isLoading: false };

      // Register file and log
      registerFile(path, name, MODULE);
      log(`Loaded ${name} (${pageCount} pages)`, 'info', MODULE);
    } catch (err) {
      console.error('Error loading PDF:', err);
      file = { ...file, isLoading: false, error: String(err) };
      logError(`Failed to load ${name}: ${err}`, MODULE);
    }
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
    if (file) {
      clearPdfCache(file.path);
      unregisterModule(MODULE);
      file = null;
      selectedPages = new Set();
      groups = [];
    }
  }

  async function handleSplit() {
    if (!file || file.pages.length === 0) return;

    // Determine what to split
    let pagesToSplit: number[][] = [];

    if (splitMode === 'all') {
      // Each page becomes a separate file
      pagesToSplit = file.pages.map(p => [p.pageNumber]);
    } else if (splitMode === 'pages') {
      // Each selected page becomes a separate file
      if (selectedPages.size === 0) {
        log('Select at least one page to split', 'warning', MODULE);
        return;
      }
      pagesToSplit = [...selectedPages].sort((a, b) => a - b).map(p => [p]);
    } else if (splitMode === 'groups') {
      // Each group becomes a file
      const nonEmptyGroups = groups.filter(g => g.length > 0);
      if (nonEmptyGroups.length === 0) {
        log('Create at least one group with pages', 'warning', MODULE);
        return;
      }
      pagesToSplit = nonEmptyGroups;
    } else if (splitMode === 'extract') {
      // All selected pages go into ONE file
      if (selectedPages.size === 0) {
        log('Select at least one page to extract', 'warning', MODULE);
        return;
      }
      pagesToSplit = [[...selectedPages].sort((a, b) => a - b)];
    } else if (splitMode === 'remove') {
      // All NON-selected pages go into ONE file
      if (selectedPages.size === 0) {
        log('Select at least one page to remove', 'warning', MODULE);
        return;
      }
      if (selectedPages.size === file.pageCount) {
        log('Cannot remove all pages', 'warning', MODULE);
        return;
      }
      const allPages = file.pages.map(p => p.pageNumber);
      const remaining = allPages.filter(p => !selectedPages.has(p));
      pagesToSplit = [remaining];
    }

    // Get output directory
    const outputDir = await save({
      title: 'Select output directory',
      filters: [],
      defaultPath: `split_${file.name.replace('.pdf', '')}`,
    });

    if (!outputDir) {
      return;
    }

    isSplitting = true;
    log(`Splitting into ${pagesToSplit.length} file(s)...`, 'info', MODULE);

    try {
      // Convert page groups to ranges for the backend (e.g., [1,2,3] -> "1,2,3")
      const ranges = pagesToSplit.map(group => group.join(','));

      // Extract directory from the save dialog path
      const dirPath = outputDir.replace(/\/[^/]*$/, '');

      const result = await invoke<string[]>('split_pdf', {
        input: file.path,
        outputDir: dirPath,
        ranges: ranges,
      });

      logSuccess(`Split complete! Created ${pagesToSplit.length} file(s) in ${dirPath}`, MODULE);
    } catch (err) {
      console.error('Split error:', err);
      logError(`Split failed: ${err}`, MODULE);
    }

    isSplitting = false;
  }

  function handlePreviewPage(page: PageData) {
    previewPage = page;
  }

  function handlePreviewNavigate(pageNumber: number) {
    if (!file) return;
    const page = file.pages.find(p => p.pageNumber === pageNumber);
    if (page) previewPage = page;
  }

  // Compute split summary
  const splitSummary = $derived(() => {
    if (!file) return '';

    if (splitMode === 'all') {
      return `${file.pageCount} files will be created`;
    } else if (splitMode === 'pages') {
      return selectedPages.size === 0
        ? 'Select pages to split'
        : `${selectedPages.size} file(s) will be created`;
    } else if (splitMode === 'groups') {
      const nonEmpty = groups.filter(g => g.length > 0).length;
      return nonEmpty === 0
        ? 'Create groups to split'
        : `${nonEmpty} file(s) will be created`;
    } else if (splitMode === 'extract') {
      return selectedPages.size === 0
        ? 'Select pages to extract'
        : `1 file with ${selectedPages.size} page(s)`;
    } else if (splitMode === 'remove') {
      if (selectedPages.size === 0) return 'Select pages to remove';
      if (selectedPages.size === file.pageCount) return 'Cannot remove all pages';
      return `1 file with ${file.pageCount - selectedPages.size} page(s)`;
    }
    return '';
  });

  const canSplit = $derived(() => {
    if (!file || file.pages.length === 0) return false;
    if (splitMode === 'all') return true;
    if (splitMode === 'pages') return selectedPages.size > 0;
    if (splitMode === 'groups') return groups.some(g => g.length > 0);
    if (splitMode === 'extract') return selectedPages.size > 0;
    if (splitMode === 'remove') return selectedPages.size > 0 && selectedPages.size < file.pageCount;
    return false;
  });
</script>

<div class="flex-1 flex overflow-hidden">
  <!-- Main Content Area -->
  <div class="flex-1 flex flex-col overflow-hidden">
    <!-- Split Mode Toolbar -->
    {#if file && file.pages.length > 0}
      <div
        class="flex items-center gap-4 px-4 py-2 border-b"
        style="background-color: var(--nord1); border-color: var(--nord3);"
      >
        <span class="text-xs opacity-60 uppercase">Mode:</span>

        <div class="flex items-center gap-1">
          <!-- Split: All Pages -->
          <div class="relative group">
            <button
              onclick={() => splitMode = 'all'}
              class="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-colors"
              style="background-color: {splitMode === 'all' ? 'var(--nord8)' : 'var(--nord2)'};
                     color: {splitMode === 'all' ? 'var(--nord0)' : 'var(--nord4)'};"
            >
              <Grid3x3 size={14} />
              <span>All Pages</span>
              <HelpCircle size={12} class="opacity-50" />
            </button>
            <div class="absolute left-0 top-full mt-1 px-3 py-2 rounded text-xs w-56 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 pointer-events-none"
                 style="background-color: var(--nord3); color: var(--nord6);">
              Split every page into its own file. A 10-page PDF becomes 10 separate files.
            </div>
          </div>

          <!-- Split: Select Pages -->
          <div class="relative group">
            <button
              onclick={() => splitMode = 'pages'}
              class="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-colors"
              style="background-color: {splitMode === 'pages' ? 'var(--nord8)' : 'var(--nord2)'};
                     color: {splitMode === 'pages' ? 'var(--nord0)' : 'var(--nord4)'};"
            >
              <Scissors size={14} />
              <span>Split Pages</span>
              <HelpCircle size={12} class="opacity-50" />
            </button>
            <div class="absolute left-0 top-full mt-1 px-3 py-2 rounded text-xs w-56 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 pointer-events-none"
                 style="background-color: var(--nord3); color: var(--nord6);">
              Select pages to split. Each selected page becomes its own file.
            </div>
          </div>

          <!-- Split: Groups -->
          <div class="relative group">
            <button
              onclick={() => splitMode = 'groups'}
              class="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-colors"
              style="background-color: {splitMode === 'groups' ? 'var(--nord8)' : 'var(--nord2)'};
                     color: {splitMode === 'groups' ? 'var(--nord0)' : 'var(--nord4)'};"
            >
              <Layers size={14} />
              <span>Groups</span>
              <HelpCircle size={12} class="opacity-50" />
            </button>
            <div class="absolute left-0 top-full mt-1 px-3 py-2 rounded text-xs w-56 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 pointer-events-none"
                 style="background-color: var(--nord3); color: var(--nord6);">
              Create custom groups of pages. Each group becomes a separate file.
            </div>
          </div>

          <div class="w-px h-6 mx-1" style="background-color: var(--nord3);"></div>

          <!-- Extract Pages -->
          <div class="relative group">
            <button
              onclick={() => splitMode = 'extract'}
              class="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-colors"
              style="background-color: {splitMode === 'extract' ? 'var(--nord14)' : 'var(--nord2)'};
                     color: {splitMode === 'extract' ? 'var(--nord0)' : 'var(--nord4)'};"
            >
              <FileOutput size={14} />
              <span>Extract</span>
              <HelpCircle size={12} class="opacity-50" />
            </button>
            <div class="absolute left-0 top-full mt-1 px-3 py-2 rounded text-xs w-56 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 pointer-events-none"
                 style="background-color: var(--nord3); color: var(--nord6);">
              Keep only the selected pages. Creates ONE file containing just those pages.
            </div>
          </div>

          <!-- Remove Pages -->
          <div class="relative group">
            <button
              onclick={() => splitMode = 'remove'}
              class="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-colors"
              style="background-color: {splitMode === 'remove' ? 'var(--nord11)' : 'var(--nord2)'};
                     color: {splitMode === 'remove' ? 'var(--nord6)' : 'var(--nord4)'};"
            >
              <FileX size={14} />
              <span>Remove</span>
              <HelpCircle size={12} class="opacity-50" />
            </button>
            <div class="absolute left-0 top-full mt-1 px-3 py-2 rounded text-xs w-56 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 pointer-events-none"
                 style="background-color: var(--nord3); color: var(--nord6);">
              Delete the selected pages. Creates ONE file without those pages.
            </div>
          </div>
        </div>

        <span class="text-xs opacity-60 ml-auto">{splitSummary()}</span>
      </div>
    {/if}

    <!-- Content -->
    <div class="flex-1 overflow-auto p-4">
      {#if !file}
        <!-- Empty State -->
        <div
          class="h-full flex flex-col items-center justify-center rounded-lg"
          style="background-color: var(--nord1);"
        >
          <Scissors size={48} class="opacity-40 mb-4" />
          <p class="text-lg opacity-60 mb-2">No file loaded</p>
          <p class="text-sm opacity-40">Add a PDF file using the panel on the right</p>
        </div>
      {:else if file.isLoading}
        <!-- Loading State -->
        <div
          class="h-full flex flex-col items-center justify-center rounded-lg"
          style="background-color: var(--nord1);"
        >
          <div class="w-8 h-8 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin mb-4"></div>
          <p class="opacity-60">Loading pages...</p>
        </div>
      {:else if file.error}
        <!-- Error State -->
        <div
          class="h-full flex flex-col items-center justify-center rounded-lg"
          style="background-color: var(--nord1);"
        >
          <p class="text-lg mb-2" style="color: var(--nord11);">Error loading PDF</p>
          <p class="text-sm opacity-60">{file.error}</p>
        </div>
      {:else}
        <!-- Page Selector -->
        <div
          class="h-full rounded-lg p-4"
          style="background-color: var(--nord1);"
        >
          <PageSelector
            pages={file.pages}
            mode={splitMode}
            bind:selectedPages
            bind:groups
            onPreviewPage={handlePreviewPage}
          />
        </div>
      {/if}
    </div>
  </div>

  <!-- Right Sidebar -->
  <div
    class="w-[15%] min-w-[180px] flex flex-col gap-4 p-4 border-l"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <!-- File Info or Drop Area -->
    {#if !file}
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
      <div class="flex-1 overflow-y-auto">
        <h4 class="text-xs opacity-60 mb-3 uppercase">File</h4>
        <div
          class="p-3 rounded group hover:bg-[var(--nord2)] transition-colors"
          title={file.path}
        >
          <div class="flex items-start gap-2">
            <FileText size={20} class="flex-shrink-0 opacity-60 mt-0.5" />
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium truncate">{file.name}</p>
              <p class="text-xs opacity-50 mt-1">
                {#if file.isLoading}
                  Loading...
                {:else}
                  {file.pageCount} page{file.pageCount !== 1 ? 's' : ''}
                {/if}
              </p>
            </div>
            <button
              onclick={removeFile}
              class="opacity-0 group-hover:opacity-100 transition-opacity p-1"
              style="color: var(--nord11);"
              title="Remove file"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>
      </div>
    {/if}

    <!-- Add File Button -->
    <button
      onclick={handleFilePicker}
      class="flex items-center justify-center gap-2 px-4 py-3 rounded transition-colors hover:opacity-80"
      style="background-color: var(--nord2); border: 1px solid var(--nord3);"
    >
      <FolderOpen size={18} />
      <span class="text-sm">{file ? 'Change File' : 'Add File'}</span>
    </button>

    <!-- Action Button -->
    {#if true}
      {@const actionLabel = splitMode === 'extract' ? 'Extract' : splitMode === 'remove' ? 'Remove' : 'Split'}
      {@const actionColor = splitMode === 'extract' ? 'var(--nord14)' : splitMode === 'remove' ? 'var(--nord11)' : 'var(--nord8)'}
      {@const textColor = splitMode === 'remove' ? 'var(--nord6)' : 'var(--nord0)'}
      <button
        onclick={handleSplit}
        disabled={!canSplit() || isSplitting}
        class="px-4 py-3 rounded transition-colors disabled:opacity-50 hover:opacity-90 flex items-center justify-center gap-2"
        style="background-color: {actionColor}; color: {textColor};"
      >
        {#if isSplitting}
          <div class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
          <span>{actionLabel}ing...</span>
        {:else}
          {#if splitMode === 'extract'}
            <FileOutput size={18} />
          {:else if splitMode === 'remove'}
            <FileX size={18} />
          {:else}
            <Scissors size={18} />
          {/if}
          <span>{actionLabel}</span>
        {/if}
      </button>
    {/if}
  </div>
</div>

<!-- Preview Modal -->
<PagePreviewModal
  page={previewPage}
  totalPages={file?.pageCount ?? 0}
  onClose={() => previewPage = null}
  onNavigate={handlePreviewNavigate}
/>
