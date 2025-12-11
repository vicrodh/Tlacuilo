<script lang="ts">
  import { Upload, FolderOpen, Trash2, X, ChevronUp, ChevronDown, ChevronLeft, ChevronRight, Plus } from 'lucide-svelte';
  import { dndzone, SOURCES, TRIGGERS } from 'svelte-dnd-action';
  import { flip } from 'svelte/animate';
  import { listen } from '@tauri-apps/api/event';
  import { open, save } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';
  import { onMount, onDestroy } from 'svelte';
  import { renderFirstPageThumbnail, renderAllPageThumbnails, renderPageForViewer, getPageCount } from '$lib/utils/pdfjs';

  interface PDFFile {
    id: string;
    name: string;
    path: string;
    thumbnail: string;
    pageCount: number;
    pages: PDFPage[];
  }

  interface PDFPage {
    id: string;
    fileId: string;
    filePath: string;
    fileName: string;
    pageNumber: number;
    thumbnail: string;
  }

  let files = $state<PDFFile[]>([]);
  let activeFileIds = $state<Set<string>>(new Set()); // Files currently in the workspace
  let viewMode = $state<'file' | 'page'>('file');
  let activeTab = $state<string>('');
  let destinationPages = $state<PDFPage[]>([]);
  let mergedPDFPath = $state<string | null>(null);
  let isTopSectionCollapsed = $state(false);
  let status = $state<string>('');
  let unlistenDrop: (() => void) | null = null;
  let loadingFiles = $state<Set<string>>(new Set()); // Track files being loaded

  // PDF Viewer state
  let viewerImage = $state<string>('');
  let viewerCurrentPage = $state(1);
  let viewerTotalPages = $state(0);
  let isLoadingViewer = $state(false);

  // DnD state for copy behavior
  let draggedFromSource = $state<PDFPage | null>(null);

  const flipDurationMs = 200;

  // Derived: files currently active in the workspace
  const workingFiles = $derived(files.filter((f) => activeFileIds.has(f.id)));

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
    for (const path of paths) {
      const name = path.split('/').pop() || path;
      const fileId = `file-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

      // Add file immediately with loading state
      const placeholderFile: PDFFile = {
        id: fileId,
        name,
        path,
        thumbnail: '',
        pageCount: 0,
        pages: [],
      };
      files = [...files, placeholderFile];
      activeFileIds = new Set([...activeFileIds, fileId]);
      loadingFiles = new Set([...loadingFiles, fileId]);

      if (!activeTab) {
        activeTab = fileId;
      }

      // Load thumbnails asynchronously
      loadFileData(fileId, path, name);
    }
  }

  async function loadFileData(fileId: string, path: string, name: string) {
    try {
      // Get page count first
      const pageCount = await getPageCount(path);

      // Get thumbnail for file (first page)
      const thumbnail = await renderFirstPageThumbnail(path, 160);

      // Get all page thumbnails
      const pageThumbnails = await renderAllPageThumbnails(path, 120);

      const pages: PDFPage[] = pageThumbnails.map((thumb, idx) => ({
        id: `${fileId}-page-${idx}`,
        fileId,
        filePath: path,
        fileName: name,
        pageNumber: idx + 1,
        thumbnail: thumb,
      }));

      // Update file with loaded data
      files = files.map((f) =>
        f.id === fileId
          ? { ...f, thumbnail, pageCount, pages }
          : f
      );
    } catch (err) {
      console.error('Error loading PDF:', err);
      // Try to at least get page count
      try {
        const pageCount = await getPageCount(path);
        files = files.map((f) =>
          f.id === fileId ? { ...f, pageCount } : f
        );
      } catch {
        // File might be corrupted, leave as is
      }
    } finally {
      loadingFiles = new Set([...loadingFiles].filter((id) => id !== fileId));
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
    // Completely remove file from list and workspace
    files = files.filter((f) => f.id !== fileId);
    activeFileIds = new Set([...activeFileIds].filter((id) => id !== fileId));
    // Also remove pages from destination that belong to this file
    destinationPages = destinationPages.filter((p) => p.fileId !== fileId);
    if (activeTab === fileId && workingFiles.length > 0) {
      activeTab = workingFiles[0].id;
    }
  }

  function closeTab(fileId: string) {
    // Remove from workspace but keep in files list
    activeFileIds = new Set([...activeFileIds].filter((id) => id !== fileId));
    // Also remove pages from destination that belong to this file
    destinationPages = destinationPages.filter((p) => p.fileId !== fileId);
    // Switch to another tab if this was active
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
    // Reorder files based on the drag result
    const reorderedIds = e.detail.items.map((f) => f.id);
    // Rebuild files array with the new order for working files, keeping non-working at end
    const working = e.detail.items;
    const nonWorking = files.filter((f) => !activeFileIds.has(f.id));
    files = [...working, ...nonWorking];
  }

  function handleSourcePagesDnd(e: CustomEvent<{ items: PDFPage[]; info: { source: string; trigger: string } }>) {
    const { items, info } = e.detail;

    // If dragging started from source, track the page for copy behavior
    if (info.source === SOURCES.POINTER && info.trigger === TRIGGERS.DRAG_STARTED) {
      const draggedItem = items.find((item) => (item as any).isDndShadowItem);
      if (draggedItem) {
        draggedFromSource = { ...draggedItem, id: draggedItem.id.replace('id:dnd-shadow-placeholder-', '') };
      }
    }

    // On finalize, restore original pages (don't remove from source)
    if (info.trigger === TRIGGERS.DROPPED_INTO_ANOTHER || info.trigger === TRIGGERS.DROPPED_OUTSIDE_OF_ANY) {
      // Restore the page that was dragged - source should keep all pages
      const activeFile = files.find((f) => f.id === activeTab);
      if (activeFile) {
        // Keep original pages unchanged
        return;
      }
    }

    // Only update for reordering within source
    if (info.trigger === TRIGGERS.DROPPED_INTO_ZONE) {
      const activeFile = files.find((f) => f.id === activeTab);
      if (activeFile) {
        // Filter out any shadow items and restore original IDs
        const cleanItems = items.filter((item) => !(item as any).isDndShadowItem);
        files = files.map((f) =>
          f.id === activeTab ? { ...f, pages: cleanItems } : f
        );
      }
    }
  }

  function handleDestinationPagesDnd(e: CustomEvent<{ items: PDFPage[]; info: { source: string; trigger: string } }>) {
    const { items, info } = e.detail;

    // When a page is dropped from source, create a copy with new ID
    if (info.trigger === TRIGGERS.DROPPED_INTO_ZONE && draggedFromSource) {
      // Check if this is a new page from source (has source ID pattern)
      const hasNewPage = items.some((item) =>
        !item.id.startsWith('dest-') && !item.id.includes('dnd-shadow')
      );

      if (hasNewPage) {
        // Transform items: give new IDs to pages from source
        const transformedItems = items
          .filter((item) => !(item as any).isDndShadowItem)
          .map((item) => {
            if (!item.id.startsWith('dest-')) {
              // This is a page from source, give it a destination ID
              return {
                ...item,
                id: `dest-${item.id}-${Date.now()}`,
              };
            }
            return item;
          });
        destinationPages = transformedItems;
        draggedFromSource = null;
        return;
      }
    }

    // Normal reordering within destination
    const cleanItems = items.filter((item) => !(item as any).isDndShadowItem);
    destinationPages = cleanItems;
    draggedFromSource = null;
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

  async function loadMergedPDFPreview(pdfPath: string) {
    isLoadingViewer = true;
    try {
      viewerTotalPages = await getPageCount(pdfPath);
      viewerCurrentPage = 1;
      viewerImage = await renderPageForViewer(pdfPath, 1);
    } catch (err) {
      console.error('Error loading merged PDF preview:', err);
      viewerImage = '';
    }
    isLoadingViewer = false;
  }

  async function goToPage(page: number) {
    if (!mergedPDFPath || page < 1 || page > viewerTotalPages) return;
    isLoadingViewer = true;
    try {
      viewerCurrentPage = page;
      viewerImage = await renderPageForViewer(mergedPDFPath, page);
    } catch (err) {
      console.error('Error loading page:', err);
    }
    isLoadingViewer = false;
  }

  async function handleMerge() {
    if (files.length === 0) return;

    // In page view with destination pages, use merge_pages
    // Otherwise use merge_pdfs for full files
    const usePageMerge = viewMode === 'page' && destinationPages.length > 0;

    if (usePageMerge && destinationPages.length === 0) {
      status = 'Add pages to the Merged Document first';
      return;
    }

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

      let result: string;

      if (usePageMerge) {
        // Page-by-page merge: convert destinationPages to [(filePath, pageNumber), ...]
        const pages: [string, number][] = destinationPages.map((p) => [p.filePath, p.pageNumber]);

        result = await invoke<string>('merge_pages', {
          pages,
          output: outputPath,
        });
      } else {
        // Full file merge - use workingFiles in their current order
        const inputs = workingFiles.map((f) => f.path);

        result = await invoke<string>('merge_pdfs', {
          inputs,
          output: outputPath,
        });
      }

      mergedPDFPath = result;
      status = 'Merge complete!';

      // Load preview of the merged PDF
      await loadMergedPDFPreview(result);
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
    // Set first working file as active tab when files are added
    if (workingFiles.length > 0 && !activeTab) {
      activeTab = workingFiles[0].id;
    }
  });

  const activeFile = $derived(files.find((f) => f.id === activeTab));
  const totalPages = $derived(
    viewMode === 'page'
      ? destinationPages.length
      : workingFiles.reduce((acc, f) => acc + f.pageCount, 0)
  );
  const canMerge = $derived(
    viewMode === 'file' ? workingFiles.length >= 2 : destinationPages.length >= 1
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
        {#if viewMode === 'page' && workingFiles.length > 0}
          <div
            class="flex gap-1 px-4 pt-2 border-b overflow-x-auto"
            style="border-color: var(--nord3);"
          >
            {#each workingFiles as file}
              <div
                class="flex items-center gap-1 px-2 py-1.5 rounded-t text-xs transition-colors flex-shrink-0 max-w-[140px] group"
                style="background-color: {activeTab === file.id ? 'var(--nord2)' : 'transparent'};"
              >
                <button
                  onclick={() => (activeTab = file.id)}
                  class="truncate flex-1 text-left"
                  title={file.name}
                >
                  {file.name}
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
            <!-- File View - Horizontal list of files -->
            <div
              class="h-full overflow-x-auto overflow-y-hidden flex gap-4"
              use:dndzone={{ items: workingFiles, flipDurationMs, type: 'files' }}
              onconsider={handleFilesDnd}
              onfinalize={handleFilesDnd}
            >
              {#if workingFiles.length === 0}
                <div class="h-full flex items-center justify-center opacity-60 w-full">
                  <p class="text-sm">No files added yet</p>
                </div>
              {:else}
                {#each workingFiles as file (file.id)}
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
                      <p class="opacity-60">{file.pageCount} page{file.pageCount !== 1 ? 's' : ''}</p>
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
                <h4 class="text-xs opacity-60 mb-2 uppercase">Source Pages {activeFile ? `(${activeFile.pageCount} pages)` : ''}</h4>
                <div
                  class="h-[calc(100%-24px)] overflow-x-auto overflow-y-hidden flex gap-2 p-2 rounded"
                  style="background-color: var(--nord0);"
                  use:dndzone={{ items: activeFile?.pages || [], flipDurationMs, type: 'mergepages', dropFromOthersDisabled: true, centreDraggedOnCursor: true }}
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
                <h4 class="text-xs opacity-60 mb-2 uppercase">Merged Document ({destinationPages.length} pages)</h4>
                <div
                  class="h-[calc(100%-24px)] overflow-x-auto overflow-y-hidden flex gap-2 p-2 rounded min-h-[120px]"
                  style="background-color: var(--nord0);"
                  use:dndzone={{ items: destinationPages, flipDurationMs, type: 'mergepages', dropFromOthersDisabled: false, centreDraggedOnCursor: true }}
                  onconsider={handleDestinationPagesDnd}
                  onfinalize={handleDestinationPagesDnd}
                >
                  {#if destinationPages.length === 0}
                    <div class="h-full flex items-center justify-center opacity-60 w-full">
                      <p class="text-xs">Drag pages here or click + to add them</p>
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
          {viewMode === 'file' ? 'File View' : 'Page View'} - {workingFiles.length} file(s){viewMode === 'page' ? `, ${destinationPages.length} pages selected` : ''}
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
        class="h-full rounded-lg flex flex-col items-center justify-center relative"
        style="background-color: var(--nord2);"
      >
        {#if isLoadingViewer}
          <p class="opacity-60">Loading preview...</p>
        {:else if viewerImage && mergedPDFPath}
          <!-- PDF Preview with navigation -->
          <div class="flex-1 flex items-center justify-center p-4 overflow-auto w-full">
            <img
              src={viewerImage}
              alt="Page {viewerCurrentPage}"
              class="max-h-full object-contain shadow-lg rounded"
            />
          </div>
          <!-- Page Navigation -->
          <div
            class="flex items-center gap-4 py-3 px-4 rounded-t-lg"
            style="background-color: var(--nord1);"
          >
            <button
              onclick={() => goToPage(viewerCurrentPage - 1)}
              disabled={viewerCurrentPage <= 1}
              class="p-2 rounded hover:bg-[var(--nord2)] transition-colors disabled:opacity-30"
            >
              <ChevronLeft size={20} />
            </button>
            <span class="text-sm">
              Page {viewerCurrentPage} of {viewerTotalPages}
            </span>
            <button
              onclick={() => goToPage(viewerCurrentPage + 1)}
              disabled={viewerCurrentPage >= viewerTotalPages}
              class="p-2 rounded hover:bg-[var(--nord2)] transition-colors disabled:opacity-30"
            >
              <ChevronRight size={20} />
            </button>
          </div>
        {:else if status}
          <p class="opacity-60">{status}</p>
        {:else}
          <p class="opacity-60">PDF preview will appear here after merge</p>
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
          {@const isActive = activeFileIds.has(file.id)}
          {@const isLoading = loadingFiles.has(file.id)}
          <div
            class="mb-3 p-2 rounded group hover:bg-[var(--nord2)] transition-colors"
            class:opacity-50={!isActive}
            title={file.path}
          >
            <!-- Thumbnail -->
            <div
              class="w-full aspect-[3/4] rounded mb-2 overflow-hidden flex items-center justify-center"
              style="background-color: var(--nord2);"
            >
              {#if isLoading}
                <div class="flex flex-col items-center gap-1">
                  <div class="w-4 h-4 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin"></div>
                  <span class="text-xs opacity-60">Loading...</span>
                </div>
              {:else if file.thumbnail}
                <img src={file.thumbnail} alt={file.name} class="max-w-full max-h-full object-contain" />
              {:else}
                <span class="text-xs opacity-60">PDF</span>
              {/if}
            </div>
            <!-- File info and actions -->
            <div class="flex items-start justify-between gap-1">
              <div class="flex-1 min-w-0">
                <p class="text-xs truncate" title={file.name}>{file.name}</p>
                <p class="text-xs opacity-50">
                  {#if isLoading}
                    Loading...
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
      disabled={!canMerge}
      class="px-4 py-3 rounded transition-colors disabled:opacity-50 hover:opacity-90"
      style="background-color: var(--nord8); color: var(--nord0);"
    >
      Merge
    </button>
  </div>
</div>
