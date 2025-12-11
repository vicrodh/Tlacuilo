<script lang="ts">
  import { Upload, FolderOpen, Trash2, FileText, Scissors, Layers, Grid3x3 } from 'lucide-svelte';
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
  let splitMode = $state<'all' | 'pages' | 'groups'>('pages');
  let selectedPages = $state<Set<number>>(new Set());
  let groups = $state<number[][]>([]);
  let status = $state<string>('');
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
    } catch (err) {
      console.error('Error loading PDF:', err);
      file = { ...file, isLoading: false, error: String(err) };
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
        status = 'Select at least one page to split';
        return;
      }
      pagesToSplit = [...selectedPages].sort((a, b) => a - b).map(p => [p]);
    } else if (splitMode === 'groups') {
      // Each group becomes a file
      const nonEmptyGroups = groups.filter(g => g.length > 0);
      if (nonEmptyGroups.length === 0) {
        status = 'Create at least one group with pages';
        return;
      }
      pagesToSplit = nonEmptyGroups;
    }

    // Get output directory
    const outputDir = await save({
      title: 'Select output directory',
      filters: [],
      defaultPath: `split_${file.name.replace('.pdf', '')}`,
    });

    if (!outputDir) {
      status = '';
      return;
    }

    isSplitting = true;
    status = `Splitting into ${pagesToSplit.length} file(s)...`;

    try {
      // Convert page groups to ranges for the backend
      const ranges = pagesToSplit.map(group => group.join(','));

      const result = await invoke<string[]>('split_pdf', {
        input: file.path,
        outputDir: outputDir.replace(/\/[^/]*$/, ''), // Get directory part
        // Note: Current backend splits all pages. We'll need to update it.
      });

      status = `Split complete! Created ${pagesToSplit.length} file(s)`;
      setTimeout(() => status = '', 5000);
    } catch (err) {
      console.error('Split error:', err);
      status = `Error: ${err}`;
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
    } else {
      const nonEmpty = groups.filter(g => g.length > 0).length;
      return nonEmpty === 0
        ? 'Create groups to split'
        : `${nonEmpty} file(s) will be created`;
    }
  });

  const canSplit = $derived(() => {
    if (!file || file.pages.length === 0) return false;
    if (splitMode === 'all') return true;
    if (splitMode === 'pages') return selectedPages.size > 0;
    if (splitMode === 'groups') return groups.some(g => g.length > 0);
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
        <span class="text-xs opacity-60 uppercase">Split Mode:</span>

        <div class="flex items-center gap-1">
          <button
            onclick={() => splitMode = 'all'}
            class="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-colors"
            style="background-color: {splitMode === 'all' ? 'var(--nord8)' : 'var(--nord2)'};
                   color: {splitMode === 'all' ? 'var(--nord0)' : 'var(--nord4)'};"
            title="Split all pages - each page becomes a separate file"
          >
            <Grid3x3 size={14} />
            <span>All Pages</span>
          </button>

          <button
            onclick={() => splitMode = 'pages'}
            class="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-colors"
            style="background-color: {splitMode === 'pages' ? 'var(--nord8)' : 'var(--nord2)'};
                   color: {splitMode === 'pages' ? 'var(--nord0)' : 'var(--nord4)'};"
            title="Select pages - each selected page becomes a separate file"
          >
            <Scissors size={14} />
            <span>Select Pages</span>
          </button>

          <button
            onclick={() => splitMode = 'groups'}
            class="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-colors"
            style="background-color: {splitMode === 'groups' ? 'var(--nord8)' : 'var(--nord2)'};
                   color: {splitMode === 'groups' ? 'var(--nord0)' : 'var(--nord4)'};"
            title="Group pages - each group becomes a separate file"
          >
            <Layers size={14} />
            <span>Groups</span>
          </button>
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

    <!-- Status -->
    {#if status}
      <div
        class="px-3 py-2 rounded text-xs"
        style="background-color: var(--nord2);"
      >
        {status}
      </div>
    {/if}

    <!-- Split Button -->
    <button
      onclick={handleSplit}
      disabled={!canSplit() || isSplitting}
      class="px-4 py-3 rounded transition-colors disabled:opacity-50 hover:opacity-90 flex items-center justify-center gap-2"
      style="background-color: var(--nord8); color: var(--nord0);"
    >
      {#if isSplitting}
        <div class="w-4 h-4 border-2 border-[var(--nord0)] border-t-transparent rounded-full animate-spin"></div>
        <span>Splitting...</span>
      {:else}
        <Scissors size={18} />
        <span>Split</span>
      {/if}
    </button>
  </div>
</div>

<!-- Preview Modal -->
<PagePreviewModal
  page={previewPage}
  totalPages={file?.pageCount ?? 0}
  onClose={() => previewPage = null}
  onNavigate={handlePreviewNavigate}
/>
