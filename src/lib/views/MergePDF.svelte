<script lang="ts">
  import { Upload, FolderOpen, Trash2, X, ChevronUp, ChevronDown, Plus, FileText } from 'lucide-svelte';
  import { dndzone } from 'svelte-dnd-action';
  import { flip } from 'svelte/animate';
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
  import { log, logSuccess, logError, registerFile, unregisterFile, unregisterModule } from '$lib/stores/status.svelte';
  import { PDFViewer } from '$lib/components/PDFViewer';

  const MODULE = 'Merge';

  interface PDFFile {
    id: string;
    name: string;
    path: string;
    pageCount: number;
    pages: PageData[];
    isLoading: boolean;
    error: string | null;
  }

  let files = $state<PDFFile[]>([]);
  let activeFileIds = $state<Set<string>>(new Set());
  let viewMode = $state<'file' | 'page'>('file');
  let activeTab = $state<string>('');
  let destinationPages = $state<PageData[]>([]);
  let mergedPDFPath = $state<string | null>(null);
  let isTopSectionCollapsed = $state(false);
  let unlistenDrop: (() => void) | null = null;

  const flipDurationMs = 200;

  // Derived: files currently active in the workspace
  const workingFiles = $derived(files.filter((f) => activeFileIds.has(f.id)));
  const activeFile = $derived(files.find((f) => f.id === activeTab));

  onMount(async () => {
    unlistenDrop = await listen<string[]>('tauri://file-drop', async (e) => {
      const pdfs = e.payload.filter((p: string) => p.toLowerCase().endsWith('.pdf'));
      if (pdfs.length > 0) {
        await addFiles(pdfs);
      }
    });
  });

  onDestroy(() => {
    if (unlistenDrop) unlistenDrop();
    unregisterModule(MODULE);
  });

  async function addFiles(paths: string[]) {
    for (const path of paths) {
      const name = path.split('/').pop() || path;
      const fileId = `file-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

      // Add file immediately with loading state
      const newFile: PDFFile = {
        id: fileId,
        name,
        path,
        pageCount: 0,
        pages: [],
        isLoading: true,
        error: null,
      };

      files = [...files, newFile];
      activeFileIds = new Set([...activeFileIds, fileId]);

      if (!activeTab) {
        activeTab = fileId;
      }

      // Load PDF data asynchronously
      loadFileData(fileId, path, name);
    }
  }

  async function loadFileData(fileId: string, path: string, name: string) {
    try {
      // Get page count first (fast operation)
      const pageCount = await getPageCount(path);

      // Update file with page count
      files = files.map((f) =>
        f.id === fileId ? { ...f, pageCount } : f
      );

      // Load all pages with thumbnails
      const pages = await loadPdfPages(path, fileId, name, 120, (current, total) => {
        // Progress callback - could update UI here
      });

      // Update file with pages
      files = files.map((f) =>
        f.id === fileId ? { ...f, pages, isLoading: false } : f
      );

      // Register and log
      const file = files.find(f => f.id === fileId);
      if (file) {
        registerFile(path, name, MODULE);
        log(`Loaded ${name} (${pageCount} pages)`, 'info', MODULE);
      }
    } catch (err) {
      console.error('Error loading PDF:', err);
      files = files.map((f) =>
        f.id === fileId
          ? { ...f, isLoading: false, error: String(err) }
          : f
      );
      logError(`Failed to load ${name}: ${err}`, MODULE);
    }
  }

  async function handleFilePicker() {
    const selected = await open({
      multiple: true,
      filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
    });
    if (selected && selected.length > 0) {
      await addFiles(selected as string[]);
    }
  }

  function removeFile(fileId: string) {
    const file = files.find((f) => f.id === fileId);
    if (file) {
      clearPdfCache(file.path);
      unregisterFile(file.path, MODULE);
    }
    files = files.filter((f) => f.id !== fileId);
    activeFileIds = new Set([...activeFileIds].filter((id) => id !== fileId));
    destinationPages = destinationPages.filter((p) => p.fileId !== fileId);

    if (activeTab === fileId) {
      const remaining = [...activeFileIds].filter((id) => id !== fileId);
      activeTab = remaining.length > 0 ? remaining[0] : '';
    }
  }

  function closeTab(fileId: string) {
    activeFileIds = new Set([...activeFileIds].filter((id) => id !== fileId));
    destinationPages = destinationPages.filter((p) => p.fileId !== fileId);

    if (activeTab === fileId) {
      const remaining = [...activeFileIds].filter((id) => id !== fileId);
      activeTab = remaining.length > 0 ? remaining[0] : '';
    }
  }

  function addFileToWorkspace(fileId: string) {
    activeFileIds = new Set([...activeFileIds, fileId]);
    if (!activeTab) {
      activeTab = fileId;
    }
  }

  function handleFilesDnd(e: CustomEvent<{ items: PDFFile[] }>) {
    const working = e.detail.items;
    const nonWorking = files.filter((f) => !activeFileIds.has(f.id));
    files = [...working, ...nonWorking];
  }

  function handleDestinationPagesDnd(e: CustomEvent<{ items: PageData[] }>) {
    destinationPages = e.detail.items;
  }

  function addPageToDestination(page: PageData) {
    const destPage: PageData = {
      ...page,
      id: `dest-${page.id}-${Date.now()}`,
    };
    destinationPages = [...destinationPages, destPage];
  }

  function removePageFromDestination(pageId: string) {
    destinationPages = destinationPages.filter((p) => p.id !== pageId);
  }

  function clearMergedPreview() {
    mergedPDFPath = null;
  }

  async function handleMerge() {
    if (workingFiles.length === 0) return;

    const usePageMerge = viewMode === 'page' && destinationPages.length > 0;

    if (viewMode === 'page' && destinationPages.length === 0) {
      log('Add pages to the Merged Document first', 'warning', MODULE);
      return;
    }

    log('Merging PDFs...', 'info', MODULE);
    try {
      const outputPath = await save({
        filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
        defaultPath: 'merged.pdf',
      });

      if (!outputPath) {
        return;
      }

      let result: string;

      if (usePageMerge) {
        const pages: [string, number][] = destinationPages.map((p) => [p.filePath, p.pageNumber]);
        result = await invoke<string>('merge_pages', { pages, output: outputPath });
      } else {
        const inputs = workingFiles.map((f) => f.path);
        result = await invoke<string>('merge_pdfs', { inputs, output: outputPath });
      }

      mergedPDFPath = result;
      logSuccess(`Merge complete! Saved to ${outputPath}`, MODULE);
    } catch (err) {
      console.error('Merge error:', err);
      logError(`Merge failed: ${err}`, MODULE);
    }
  }

  $effect(() => {
    if (workingFiles.length > 0 && !activeTab) {
      activeTab = workingFiles[0].id;
    }
  });

  const canMerge = $derived(
    viewMode === 'file' ? workingFiles.length >= 2 : destinationPages.length >= 1
  );
</script>

<div class="flex-1 flex overflow-hidden">
  <!-- Left Column - 85% (Content Area) -->
  <div class="flex-1 flex flex-col overflow-hidden">
    <!-- Top Section - File/Page View -->
    {#if !isTopSectionCollapsed}
      <div
        class="border-b flex flex-col relative"
        style="height: {viewMode === 'file' ? '280px' : '520px'}; background-color: var(--nord1); border-color: var(--nord3);"
      >
        <!-- Collapse Button -->
        <button
          onclick={() => (isTopSectionCollapsed = true)}
          class="absolute top-2 right-2 p-1 rounded hover:bg-[var(--nord2)] transition-colors z-10"
          title="Collapse section"
        >
          <ChevronUp size={16} />
        </button>

        <!-- Tabs - Only in Page View -->
        {#if viewMode === 'page' && workingFiles.length > 0}
          <div
            class="flex gap-1 px-4 pt-2 border-b overflow-x-auto flex-shrink-0"
            style="border-color: var(--nord3);"
          >
            {#each workingFiles as file}
              <div
                class="flex items-center gap-1 px-3 py-1.5 rounded-t text-xs transition-colors flex-shrink-0 max-w-[160px] group cursor-pointer"
                style="background-color: {activeTab === file.id ? 'var(--nord2)' : 'transparent'};"
              >
                <button
                  onclick={() => (activeTab = file.id)}
                  class="truncate flex-1 text-left flex items-center gap-1"
                  title={file.name}
                >
                  <FileText size={12} class="flex-shrink-0 opacity-60" />
                  <span class="truncate">{file.name}</span>
                  <span class="opacity-50">({file.pageCount})</span>
                </button>
                <button
                  onclick={() => closeTab(file.id)}
                  class="p-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity hover:bg-[var(--nord3)]"
                  title="Remove from workspace"
                >
                  <X size={12} />
                </button>
              </div>
            {/each}
          </div>
        {/if}

        <!-- Content Area -->
        <div class="flex-1 overflow-hidden p-4">
          {#if viewMode === 'file'}
            <!-- File View - Horizontal list with thumbnails -->
            <div
              class="h-full overflow-x-auto overflow-y-hidden flex gap-4 items-start"
              use:dndzone={{ items: workingFiles, flipDurationMs, type: 'files' }}
              onconsider={handleFilesDnd}
              onfinalize={handleFilesDnd}
            >
              {#if workingFiles.length === 0}
                <div class="h-full flex items-center justify-center opacity-60 w-full">
                  <p class="text-sm">Add files using the panel on the right</p>
                </div>
              {:else}
                {#each workingFiles as file (file.id)}
                  <div
                    class="flex-shrink-0 cursor-move"
                    animate:flip={{ duration: flipDurationMs }}
                  >
                    <!-- PDF Thumbnail -->
                    <div
                      class="w-36 h-44 flex items-center justify-center rounded mb-2 overflow-hidden relative"
                      style="background-color: var(--nord2);"
                    >
                      {#if file.isLoading}
                        <div class="flex flex-col items-center gap-2">
                          <div class="w-5 h-5 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin"></div>
                          <span class="text-xs opacity-60">Loading...</span>
                        </div>
                      {:else if file.pages.length > 0 && file.pages[0].thumbnail}
                        <img
                          src={file.pages[0].thumbnail}
                          alt={file.name}
                          class="max-w-full max-h-full object-contain"
                        />
                      {:else if file.error}
                        <span class="text-xs text-center px-2" style="color: var(--nord11);">Error loading</span>
                      {:else}
                        <FileText size={32} class="opacity-40" />
                      {/if}
                    </div>
                    <!-- File Info -->
                    <div
                      class="w-36 p-2 rounded text-center text-xs"
                      style="background-color: var(--nord0);"
                      title={file.name}
                    >
                      <p class="line-clamp-2 break-all leading-tight">{file.name}</p>
                      <p class="opacity-60 mt-1">
                        {#if file.isLoading}
                          Loading...
                        {:else}
                          {file.pageCount} page{file.pageCount !== 1 ? 's' : ''}
                        {/if}
                      </p>
                    </div>
                  </div>
                {/each}
              {/if}
            </div>
          {:else}
            <!-- Page View - Source and Destination -->
            <div class="h-full flex flex-col gap-3">
              <!-- Source Pages -->
              <div class="flex-1 overflow-hidden flex flex-col">
                <h4 class="text-xs opacity-60 mb-2 uppercase flex-shrink-0">
                  Source Pages
                  {#if activeFile}
                    ({activeFile.pageCount} pages)
                  {/if}
                </h4>
                <div
                  class="flex-1 overflow-x-auto overflow-y-hidden flex gap-2 p-2 rounded items-start"
                  style="background-color: var(--nord0);"
                >
                  {#if !activeFile}
                    <div class="h-full flex items-center justify-center opacity-60 w-full">
                      <p class="text-xs">Select a file tab above to view its pages</p>
                    </div>
                  {:else if activeFile.isLoading}
                    <div class="h-full flex items-center justify-center w-full">
                      <div class="flex flex-col items-center gap-2">
                        <div class="w-5 h-5 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin"></div>
                        <span class="text-xs opacity-60">Loading pages...</span>
                      </div>
                    </div>
                  {:else if activeFile.pages.length === 0}
                    <div class="h-full flex items-center justify-center opacity-60 w-full">
                      <p class="text-xs">No pages found</p>
                    </div>
                  {:else}
                    {#each activeFile.pages as page (page.id)}
                      <div class="relative flex-shrink-0 w-24 group">
                        <div
                          class="w-24 h-32 flex items-center justify-center rounded mb-1 overflow-hidden"
                          style="background-color: var(--nord3);"
                        >
                          {#if page.thumbnail}
                            <img
                              src={page.thumbnail}
                              alt="Page {page.pageNumber}"
                              class="max-w-full max-h-full object-contain"
                            />
                          {:else}
                            <span class="text-xs opacity-60">P{page.pageNumber}</span>
                          {/if}
                        </div>
                        <p class="text-xs text-center opacity-60">Page {page.pageNumber}</p>
                        <!-- Add button -->
                        <button
                          onclick={() => addPageToDestination(page)}
                          class="absolute top-1 right-1 w-6 h-6 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity text-sm font-bold"
                          style="background-color: var(--nord8); color: var(--nord0);"
                          title="Add to merged document"
                        >
                          +
                        </button>
                      </div>
                    {/each}
                  {/if}
                </div>
              </div>

              <!-- Destination Pages -->
              <div class="flex-1 overflow-hidden flex flex-col">
                <h4 class="text-xs opacity-60 mb-2 uppercase flex-shrink-0">
                  Merged Document ({destinationPages.length} pages)
                </h4>
                <div
                  class="flex-1 overflow-x-auto overflow-y-hidden flex gap-2 p-2 rounded items-start min-h-[140px]"
                  style="background-color: var(--nord0);"
                  use:dndzone={{ items: destinationPages, flipDurationMs, type: 'destpages' }}
                  onconsider={handleDestinationPagesDnd}
                  onfinalize={handleDestinationPagesDnd}
                >
                  {#if destinationPages.length === 0}
                    <div class="h-full flex items-center justify-center opacity-60 w-full">
                      <p class="text-xs">Click + on pages above to add them here. Drag to reorder.</p>
                    </div>
                  {:else}
                    {#each destinationPages as page (page.id)}
                      <div
                        class="relative flex-shrink-0 w-24 cursor-move group"
                        animate:flip={{ duration: flipDurationMs }}
                      >
                        <div
                          class="w-24 h-32 flex items-center justify-center rounded mb-1 overflow-hidden"
                          style="background-color: var(--nord3);"
                        >
                          {#if page.thumbnail}
                            <img
                              src={page.thumbnail}
                              alt="Page {page.pageNumber}"
                              class="max-w-full max-h-full object-contain"
                            />
                          {:else}
                            <span class="text-xs opacity-60">P{page.pageNumber}</span>
                          {/if}
                        </div>
                        <!-- Remove button -->
                        <button
                          onclick={() => removePageFromDestination(page.id)}
                          class="absolute top-1 right-1 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                          style="background-color: var(--nord11);"
                          title="Remove"
                        >
                          <X size={12} />
                        </button>
                        <p class="text-xs text-center opacity-60">Page {page.pageNumber}</p>
                        <p class="text-xs text-center opacity-40 truncate" title={page.fileName}>
                          {page.fileName}
                        </p>
                      </div>
                    {/each}
                  {/if}
                </div>
              </div>
            </div>
          {/if}
        </div>
      </div>
    {:else}
      <!-- Collapsed State -->
      <div
        class="border-b flex items-center justify-between px-4 py-2"
        style="background-color: var(--nord1); border-color: var(--nord3);"
      >
        <span class="text-sm opacity-60">
          {viewMode === 'file' ? 'File View' : 'Page View'} - {workingFiles.length} file(s)
          {#if viewMode === 'page'}, {destinationPages.length} pages selected{/if}
        </span>
        <button
          onclick={() => (isTopSectionCollapsed = false)}
          class="p-1 rounded hover:bg-[var(--nord2)] transition-colors"
          title="Expand section"
        >
          <ChevronDown size={16} />
        </button>
      </div>
    {/if}

    <!-- Bottom Section - PDF Viewer -->
    <div class="flex-1 overflow-hidden">
      {#if mergedPDFPath}
        <PDFViewer
          filePath={mergedPDFPath}
          showToolbar={true}
          showSidebar={true}
          showDetachButton={false}
          onClose={clearMergedPreview}
        />
      {:else}
        <!-- Empty State -->
        <div
          class="h-full flex flex-col items-center justify-center rounded-lg m-4"
          style="background-color: var(--nord2);"
        >
          <p class="opacity-60">PDF preview will appear here after merge</p>
        </div>
      {/if}
    </div>
  </div>

  <!-- Right Column - 15% (Simple File List) -->
  <div
    class="w-[15%] min-w-[180px] flex flex-col gap-4 p-4 border-l"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <!-- File List or Drop Area -->
    {#if files.length === 0}
      <div
        class="flex-1 flex flex-col items-center justify-center border-2 border-dashed rounded-lg p-4 cursor-pointer"
        style="border-color: var(--nord3);"
        role="button"
        tabindex="0"
        onclick={handleFilePicker}
        onkeydown={(e) => e.key === 'Enter' && handleFilePicker()}
      >
        <Upload size={32} style="color: var(--nord8);" class="mb-2" />
        <p class="text-sm text-center opacity-60">Drop files here or click to browse</p>
      </div>
    {:else}
      <div class="flex-1 overflow-y-auto">
        <h4 class="text-xs opacity-60 mb-3 uppercase">Files ({files.length})</h4>
        {#each files as file}
          {@const isActive = activeFileIds.has(file.id)}
          <div
            class="mb-2 p-2 rounded group hover:bg-[var(--nord2)] transition-colors flex items-center gap-2"
            class:opacity-50={!isActive}
            title={file.path}
          >
            <FileText size={16} class="flex-shrink-0 opacity-60" />
            <div class="flex-1 min-w-0">
              <p class="text-xs truncate">{file.name}</p>
              <p class="text-xs opacity-50">
                {#if file.isLoading}
                  Loading...
                {:else if file.error}
                  Error
                {:else}
                  {file.pageCount} page{file.pageCount !== 1 ? 's' : ''}
                {/if}
              </p>
            </div>
            {#if isActive}
              <button
                onclick={() => removeFile(file.id)}
                class="opacity-0 group-hover:opacity-100 transition-opacity p-1 flex-shrink-0"
                style="color: var(--nord11);"
                title="Remove file"
              >
                <Trash2 size={14} />
              </button>
            {:else}
              <button
                onclick={() => addFileToWorkspace(file.id)}
                class="opacity-0 group-hover:opacity-100 transition-opacity p-1 flex-shrink-0"
                style="color: var(--nord14);"
                title="Add to workspace"
              >
                <Plus size={14} />
              </button>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    <!-- Add Files Button -->
    <button
      onclick={handleFilePicker}
      class="flex items-center justify-center gap-2 px-4 py-3 rounded transition-colors hover:opacity-80"
      style="background-color: var(--nord2); border: 1px solid var(--nord3);"
    >
      <FolderOpen size={18} />
      <span class="text-sm">Add Files</span>
    </button>

    <!-- View Mode Toggle -->
    {#if files.length > 0}
      <div
        class="flex gap-1 p-1 rounded"
        style="background-color: var(--nord0);"
      >
        <button
          onclick={() => (viewMode = 'file')}
          class="flex-1 px-3 py-2 rounded text-sm transition-colors"
          style="background-color: {viewMode === 'file' ? 'var(--nord8)' : 'transparent'}; color: {viewMode === 'file' ? 'var(--nord0)' : 'var(--nord4)'};"
        >
          File view
        </button>
        <button
          onclick={() => (viewMode = 'page')}
          class="flex-1 px-3 py-2 rounded text-sm transition-colors"
          style="background-color: {viewMode === 'page' ? 'var(--nord8)' : 'transparent'}; color: {viewMode === 'page' ? 'var(--nord0)' : 'var(--nord4)'};"
        >
          Page view
        </button>
      </div>
    {/if}

    <!-- Merge Button -->
    <button
      onclick={handleMerge}
      disabled={!canMerge}
      class="px-4 py-3 rounded transition-colors disabled:opacity-50 hover:opacity-90"
      style="background-color: var(--nord8); color: var(--nord0);"
    >
      Merge
    </button>
  </div>
</div>
