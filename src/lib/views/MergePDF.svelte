<script lang="ts">
  import { Upload, FolderOpen, Trash2, X, ChevronUp, ChevronDown } from 'lucide-svelte';
  import { dndzone } from 'svelte-dnd-action';
  import { flip } from 'svelte/animate';
  import { listen } from '@tauri-apps/api/event';
  import { open, save } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';
  import { onMount, onDestroy } from 'svelte';
  import { renderFirstPageThumbnail, renderAllPageThumbnails } from '$lib/utils/pdfjs';

  interface PDFFile {
    id: string;
    name: string;
    path: string;
    thumbnail: string;
    pages: PDFPage[];
  }

  interface PDFPage {
    id: string;
    fileId: string;
    fileName: string;
    pageNumber: number;
    thumbnail: string;
  }

  let files = $state<PDFFile[]>([]);
  let viewMode = $state<'file' | 'page'>('file');
  let activeTab = $state<string>('');
  let destinationPages = $state<PDFPage[]>([]);
  let mergedPDFPath = $state<string | null>(null);
  let isTopSectionCollapsed = $state(false);
  let status = $state<string>('');
  let unlistenDrop: (() => void) | null = null;

  const flipDurationMs = 200;

  onMount(async () => {
    // Listen for file drops from Tauri
    unlistenDrop = await listen<string[]>('tauri://file-drop', async (e) => {
      const pdfs = e.payload.filter((p: string) => p.toLowerCase().endsWith('.pdf'));
      if (pdfs.length > 0) {
        await addFiles(pdfs);
      }
    });
  });

  onDestroy(() => {
    if (unlistenDrop) unlistenDrop();
  });

  async function addFiles(paths: string[]) {
    status = 'Loading files...';
    for (const path of paths) {
      const name = path.split('/').pop() || path;
      const fileId = `file-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

      try {
        // Get thumbnail for file
        const thumbnail = await renderFirstPageThumbnail(path, 160);

        // Get all page thumbnails
        const pageThumbnails = await renderAllPageThumbnails(path, 120);

        const pages: PDFPage[] = pageThumbnails.map((thumb, idx) => ({
          id: `${fileId}-page-${idx}`,
          fileId,
          fileName: name,
          pageNumber: idx + 1,
          thumbnail: thumb,
        }));

        const newFile: PDFFile = {
          id: fileId,
          name,
          path,
          thumbnail,
          pages,
        };

        files = [...files, newFile];

        if (!activeTab) {
          activeTab = fileId;
        }
      } catch (err) {
        console.error('Error loading PDF:', err);
        // Still add file even if thumbnail fails
        const newFile: PDFFile = {
          id: fileId,
          name,
          path,
          thumbnail: '',
          pages: [],
        };
        files = [...files, newFile];
        if (!activeTab) {
          activeTab = fileId;
        }
      }
    }
    status = '';
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
    files = files.filter((f) => f.id !== fileId);
    // Also remove pages from destination that belong to this file
    destinationPages = destinationPages.filter((p) => p.fileId !== fileId);
    if (activeTab === fileId && files.length > 0) {
      activeTab = files[0].id;
    }
  }

  function handleFilesDnd(e: CustomEvent<{ items: PDFFile[] }>) {
    files = e.detail.items;
  }

  function handleSourcePagesDnd(e: CustomEvent<{ items: PDFPage[] }>) {
    const activeFile = files.find((f) => f.id === activeTab);
    if (activeFile) {
      files = files.map((f) =>
        f.id === activeTab ? { ...f, pages: e.detail.items } : f
      );
    }
  }

  function handleDestinationPagesDnd(e: CustomEvent<{ items: PDFPage[] }>) {
    destinationPages = e.detail.items;
  }

  function addPageToDestination(page: PDFPage) {
    // Create a copy with unique ID for destination
    const destPage: PDFPage = {
      ...page,
      id: `dest-${page.id}-${Date.now()}`,
    };
    destinationPages = [...destinationPages, destPage];
  }

  function removePageFromDestination(pageId: string) {
    destinationPages = destinationPages.filter((p) => p.id !== pageId);
  }

  async function handleMerge() {
    if (files.length === 0) return;

    status = 'Merging PDFs...';
    try {
      // Get output path from save dialog
      const outputPath = await save({
        filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
        defaultPath: 'merged.pdf',
      });

      if (!outputPath) {
        status = '';
        return;
      }

      // In file view, merge all files in order
      // In page view, we would need to create a custom merge based on destinationPages
      const inputs = files.map((f) => f.path);

      const result = await invoke<string>('merge_pdfs', {
        inputs,
        output: outputPath,
      });

      mergedPDFPath = result;
      status = `Merged successfully: ${result}`;
    } catch (err) {
      console.error('Merge error:', err);
      status = `Error: ${err}`;
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    // File drop is handled by Tauri file-drop event
  }

  $effect(() => {
    // Set first file as active tab when files are added
    if (files.length > 0 && !activeTab) {
      activeTab = files[0].id;
    }
  });

  const activeFile = $derived(files.find((f) => f.id === activeTab));
  const totalPages = $derived(
    viewMode === 'page'
      ? destinationPages.length
      : files.reduce((acc, f) => acc + f.pages.length, 0)
  );
</script>

<div class="flex-1 flex overflow-hidden">
  <!-- Left Column - 85% -->
  <div class="flex-1 flex flex-col overflow-hidden">
    <!-- Top Section - File/Page View -->
    {#if !isTopSectionCollapsed}
      <div
        class="border-b flex flex-col relative"
        style="height: {viewMode === 'file' ? '260px' : '500px'}; background-color: var(--nord1); border-color: var(--nord3);"
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
        {#if viewMode === 'page' && files.length > 0}
          <div
            class="flex gap-2 px-4 pt-3 border-b overflow-x-auto"
            style="border-color: var(--nord3);"
          >
            {#each files as file}
              <button
                onclick={() => (activeTab = file.id)}
                class="px-4 py-2 rounded-t text-sm transition-colors flex-shrink-0 max-w-[150px] truncate"
                style="background-color: {activeTab === file.id ? 'var(--nord2)' : 'transparent'};"
                title={file.name}
              >
                {file.name}
              </button>
            {/each}
          </div>
        {/if}

        <!-- Content Area -->
        <div class="flex-1 overflow-hidden p-4">
          {#if viewMode === 'file'}
            <!-- File View - Horizontal list of files -->
            <div
              class="h-full overflow-x-auto overflow-y-hidden flex gap-4"
              use:dndzone={{ items: files, flipDurationMs, type: 'files' }}
              onconsider={handleFilesDnd}
              onfinalize={handleFilesDnd}
            >
              {#if files.length === 0}
                <div class="h-full flex items-center justify-center opacity-60 w-full">
                  <p class="text-sm">No files added yet</p>
                </div>
              {:else}
                {#each files as file (file.id)}
                  <div
                    class="flex-shrink-0 cursor-move"
                    animate:flip={{ duration: flipDurationMs }}
                  >
                    <div
                      class="w-32 h-32 flex items-center justify-center rounded mb-2 overflow-hidden"
                      style="background-color: var(--nord2);"
                    >
                      {#if file.thumbnail}
                        <img src={file.thumbnail} alt={file.name} class="max-w-full max-h-full object-contain" />
                      {:else}
                        <span class="text-xs opacity-60">PDF</span>
                      {/if}
                    </div>
                    <div
                      class="w-32 p-1 rounded text-center text-xs"
                      style="background-color: var(--nord0);"
                      title={file.name}
                    >
                      <p class="line-clamp-2 break-all leading-tight">{file.name}</p>
                      <p class="opacity-60">{file.pages.length} pages</p>
                    </div>
                  </div>
                {/each}
              {/if}
            </div>
          {:else}
            <!-- Page View - Two horizontal containers -->
            <div class="h-full flex flex-col gap-4">
              <!-- Source Pages -->
              <div class="flex-1 overflow-hidden">
                <h4 class="text-xs opacity-60 mb-2 uppercase">Source Pages</h4>
                <div
                  class="h-[calc(100%-24px)] overflow-x-auto overflow-y-hidden flex gap-2 p-2 rounded"
                  style="background-color: var(--nord0);"
                  use:dndzone={{ items: activeFile?.pages || [], flipDurationMs, type: 'pages' }}
                  onconsider={handleSourcePagesDnd}
                  onfinalize={handleSourcePagesDnd}
                >
                  {#if activeFile}
                    {#each activeFile.pages as page (page.id)}
                      <div
                        class="relative flex-shrink-0 w-24 cursor-move group"
                        animate:flip={{ duration: flipDurationMs }}
                      >
                        <div
                          class="w-24 h-32 flex items-center justify-center rounded mb-1 overflow-hidden"
                          style="background-color: var(--nord3);"
                        >
                          {#if page.thumbnail}
                            <img src={page.thumbnail} alt="Page {page.pageNumber}" class="max-w-full max-h-full object-contain" />
                          {:else}
                            <span class="text-xs opacity-60">P{page.pageNumber}</span>
                          {/if}
                        </div>
                        <p class="text-xs text-center opacity-60">Page {page.pageNumber}</p>
                        <!-- Add to destination button -->
                        <button
                          onclick={() => addPageToDestination(page)}
                          class="absolute top-1 right-1 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity text-xs"
                          style="background-color: var(--nord8); color: var(--nord0);"
                          title="Add to merged document"
                        >
                          +
                        </button>
                      </div>
                    {/each}
                  {:else}
                    <div class="h-full flex items-center justify-center opacity-60 w-full">
                      <p class="text-xs">Select a file tab to view pages</p>
                    </div>
                  {/if}
                </div>
              </div>

              <!-- Destination Pages -->
              <div class="flex-1 overflow-hidden">
                <h4 class="text-xs opacity-60 mb-2 uppercase">Merged Document</h4>
                <div
                  class="h-[calc(100%-24px)] overflow-x-auto overflow-y-hidden flex gap-2 p-2 rounded"
                  style="background-color: var(--nord0);"
                  use:dndzone={{ items: destinationPages, flipDurationMs, type: 'destpages' }}
                  onconsider={handleDestinationPagesDnd}
                  onfinalize={handleDestinationPagesDnd}
                >
                  {#if destinationPages.length === 0}
                    <div class="h-full flex items-center justify-center opacity-60 w-full">
                      <p class="text-xs">Drag pages here to create merged document</p>
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
                            <img src={page.thumbnail} alt="Page {page.pageNumber}" class="max-w-full max-h-full object-contain" />
                          {:else}
                            <span class="text-xs opacity-60">P{page.pageNumber}</span>
                          {/if}
                        </div>
                        <!-- Remove button -->
                        <button
                          onclick={() => removePageFromDestination(page.id)}
                          class="absolute top-1 right-1 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                          style="background-color: var(--nord11);"
                          title="Remove from merged document"
                        >
                          <X size={12} />
                        </button>
                        <p class="text-xs text-center opacity-60">Page {page.pageNumber}</p>
                        <!-- Source file info -->
                        <div class="mt-1 text-center">
                          <p class="text-xs opacity-40 truncate" title={page.fileName}>
                            {page.fileName}
                          </p>
                          <p class="text-xs opacity-40">Pg {page.pageNumber}</p>
                        </div>
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
          {viewMode === 'file' ? 'File View' : 'Page View'} - {files.length} file(s)
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
    <div class="flex-1 overflow-auto p-6">
      <div
        class="h-full rounded-lg flex items-center justify-center"
        style="background-color: var(--nord2);"
      >
        {#if mergedPDFPath}
          <div class="text-center">
            <p class="text-lg mb-2">Merged PDF Created</p>
            <p class="text-sm opacity-60">{mergedPDFPath}</p>
            <p class="text-sm opacity-60 mt-2">{totalPages} pages total</p>
          </div>
        {:else if status}
          <p class="opacity-60">{status}</p>
        {:else}
          <p class="opacity-60">PDF preview will appear here</p>
        {/if}
      </div>
    </div>
  </div>

  <!-- Right Column - 15% -->
  <div
    class="w-[15%] min-w-[180px] flex flex-col gap-4 p-4 border-l"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <!-- File List or Drag & Drop Area -->
    {#if files.length === 0}
      <div
        class="flex-1 flex flex-col items-center justify-center border-2 border-dashed rounded-lg p-4 cursor-pointer"
        style="border-color: var(--nord3);"
        role="button"
        tabindex="0"
        ondragover={handleDragOver}
        ondrop={handleDrop}
        onclick={handleFilePicker}
        onkeydown={(e) => e.key === 'Enter' && handleFilePicker()}
      >
        <Upload size={32} style="color: var(--nord8);" class="mb-2" />
        <p class="text-sm text-center opacity-60">
          Drop files here
        </p>
      </div>
    {:else}
      <div class="flex-1 overflow-y-auto">
        <h4 class="text-xs opacity-60 mb-3 uppercase">Files ({files.length})</h4>
        {#each files as file}
          <div
            class="mb-2 p-2 rounded group hover:bg-[var(--nord2)] transition-colors"
            title={file.path}
          >
            <div class="flex items-start justify-between gap-2">
              <p class="text-xs flex-1 truncate">{file.name}</p>
              <button
                onclick={() => removeFile(file.id)}
                class="opacity-0 group-hover:opacity-100 transition-opacity p-1"
                style="color: var(--nord11);"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        {/each}
      </div>
    {/if}

    <!-- File Picker Button -->
    <button
      onclick={handleFilePicker}
      class="flex items-center justify-center gap-2 px-4 py-3 rounded transition-colors hover:opacity-80"
      style="background-color: var(--nord2); border: 1px solid var(--nord3);"
    >
      <FolderOpen size={18} />
      <span class="text-sm">Add Files</span>
    </button>

    <!-- View Mode Toggle - Only visible when files exist -->
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
      disabled={files.length === 0}
      class="px-4 py-3 rounded transition-colors disabled:opacity-50 hover:opacity-90"
      style="background-color: var(--nord8); color: var(--nord0);"
    >
      Merge
    </button>
  </div>
</div>
