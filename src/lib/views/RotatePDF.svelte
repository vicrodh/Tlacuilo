<script lang="ts">
  import {
    Upload,
    FolderOpen,
    Trash2,
    FileText,
    RotateCw,
    Layers,
    Grid3x3,
    ChevronLeft,
    ChevronRight,
    ZoomIn,
    ZoomOut,
    Columns,
    RectangleVertical,
    RectangleHorizontal,
    LayoutGrid
  } from 'lucide-svelte';
  import { listen } from '@tauri-apps/api/event';
  import { open, save } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';
  import { onMount, onDestroy } from 'svelte';
  import {
    getPageCount,
    loadPdfPages,
    renderPageForViewer,
    clearPdfCache,
    type PageData
  } from '$lib/utils/pdfjs';
  import PageSelector from '$lib/components/PageSelector.svelte';
  import PagePreviewModal from '$lib/components/PagePreviewModal.svelte';
  import { log, logSuccess, logError, registerFile, unregisterModule } from '$lib/stores/status.svelte';

  const MODULE = 'Rotate';

  interface PDFFile {
    id: string;
    name: string;
    path: string;
    pageCount: number;
    pages: PageData[];
    isLoading: boolean;
    error: string | null;
  }

  const DEGREE_OPTIONS = [0, 90, 180, 270, 360, -90, -180, -270];

  let file = $state<PDFFile | null>(null);
  let rotationMode = $state<'all' | 'pages' | 'groups'>('pages');
  let rotationDegrees = $state<number>(90);
  let groupDegrees = $state<number[]>([]);
  let pageRotations = $state<Map<number, number>>(new Map());
  let previewEnabled = $state(false);
  let selectedPages = $state<Set<number>>(new Set());
  let groups = $state<number[][]>([]);
  let isRotating = $state(false);
  let unlistenDrop: (() => void) | null = null;
  let resultPath = $state<string | null>(null);

  // Result viewer state
  let viewerImages = $state<{ page: number; image: string }[]>([]);
  let viewerTotalPages = $state(0);
  let viewerCurrentPage = $state(1);
  let isLoadingViewer = $state(false);
  let viewerZoom = $state(100);
  let viewerLayout = $state<'single' | 'double' | 'grid'>('single');
  let fitMode = $state<'auto' | 'width' | 'height'>('auto');
  let resultThumbnails = $state<{ page: number; image: string }[]>([]);
  let isLoadingThumbs = $state(false);
  let pageInputValue = $state('1');
  const ZOOM_LEVELS = [50, 75, 100, 125, 150, 200, 300];

  // Preview modal state
  let previewPage = $state<PageData | null>(null);

  onMount(async () => {
    unlistenDrop = await listen<string[]>('tauri://file-drop', async (e) => {
      const pdfs = e.payload.filter((p: string) => p.toLowerCase().endsWith('.pdf'));
      if (pdfs.length > 0) {
        await loadFile(pdfs[0]); // Only take the first file dropped
      }
    });
  });

  onDestroy(() => {
    if (unlistenDrop) unlistenDrop();
    if (file) clearPdfCache(file.path);
    unregisterModule(MODULE);
  });

  $effect(() => {
    // Keep groupDegrees aligned with groups length
    groupDegrees = groups.map((_, idx) => groupDegrees[idx] ?? rotationDegrees);
  });

  async function loadFile(path: string) {
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

    selectedPages = new Set();
    groups = [];
    groupDegrees = [];
    pageRotations = new Map();
    previewEnabled = false;
    resultPath = null;

    try {
      const pageCount = await getPageCount(path);
      file = { ...file, pageCount };

      const pages = await loadPdfPages(path, fileId, name, 140);
      file = { ...file, pages, isLoading: false };

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
      groupDegrees = [];
      pageRotations = new Map();
      resultPath = null;
      previewEnabled = false;
    }
  }

  function onRotationChange(event: Event) {
    const value = Number((event.target as HTMLSelectElement).value);
    rotationDegrees = value;
  }

  function handlePageRotationChange(pageNumber: number, degrees: number) {
    const next = new Map(pageRotations);
    if (degrees === 0 || degrees === 360 || degrees === -0) {
      next.delete(pageNumber);
    } else {
      next.set(pageNumber, degrees);
    }
    pageRotations = next;
  }

  function onGroupRotationChange(idx: number, event: Event) {
    const value = Number((event.target as HTMLSelectElement).value);
    const next = [...groupDegrees];
    next[idx] = value;
    groupDegrees = next;
  }

  function getRotationForPage(pageNumber: number): number {
    // 1-indexed pageNumber
    if (rotationMode === 'all') return rotationDegrees;
    if (rotationMode === 'pages') {
      return pageRotations.get(pageNumber) ?? rotationDegrees;
    }
    // groups
    const groupIdx = groups.findIndex(g => g.includes(pageNumber));
    if (groupIdx >= 0) {
      return pageRotations.get(pageNumber) ?? (groupDegrees[groupIdx] ?? rotationDegrees);
    }
    return rotationDegrees;
  }

  function pagesForLayout(base: number): number[] {
    if (viewerLayout === 'single') return [base];
    if (viewerLayout === 'double') return [base, Math.min(base + 1, viewerTotalPages)].filter((p, idx, arr) => arr.indexOf(p) === idx);
    // grid: up to 4 pages
    const pages: number[] = [];
    for (let i = 0; i < 4; i++) {
      const p = base + i;
      if (p <= viewerTotalPages) pages.push(p);
    }
    return pages;
  }

  async function loadResultViewer(pdfPath: string) {
    isLoadingViewer = true;
    viewerTotalPages = await getPageCount(pdfPath);
    viewerCurrentPage = 1;
    pageInputValue = '1';
    const pages = pagesForLayout(1);
    viewerImages = [];
    for (const p of pages) {
      const img = await renderPageForViewer(pdfPath, p, 800 * (viewerZoom / 100));
      viewerImages = [...viewerImages, { page: p, image: img }];
    }
    void loadResultThumbnails(pdfPath);
    isLoadingViewer = false;
  }

  async function goToViewerPage(page: number) {
    if (!resultPath || page < 1 || page > viewerTotalPages) return;
    isLoadingViewer = true;
    viewerCurrentPage = page;
    pageInputValue = String(page);
    viewerImages = [];
    const pages = pagesForLayout(page);
    for (const p of pages) {
      const img = await renderPageForViewer(resultPath, p, 800 * (viewerZoom / 100));
      viewerImages = [...viewerImages, { page: p, image: img }];
    }
    isLoadingViewer = false;
  }

  function handleViewerPageInput(e: Event) {
    const value = parseInt((e.target as HTMLInputElement).value, 10);
    if (!isNaN(value)) {
      goToViewerPage(value);
    }
  }

  function changeZoom(delta: number) {
    const idx = ZOOM_LEVELS.findIndex((z) => z >= viewerZoom);
    const nextIdx = Math.min(Math.max(idx + delta, 0), ZOOM_LEVELS.length - 1);
    viewerZoom = ZOOM_LEVELS[nextIdx];
    if (resultPath) {
      goToViewerPage(viewerCurrentPage);
    }
  }

  async function changeLayout(layout: 'single' | 'double' | 'grid') {
    viewerLayout = layout;
    if (resultPath) {
      await goToViewerPage(viewerCurrentPage);
    }
  }

  async function loadResultThumbnails(pdfPath: string) {
    isLoadingThumbs = true;
    resultThumbnails = [];
    try {
      const total = await getPageCount(pdfPath);
      const thumbs: { page: number; image: string }[] = [];
      for (let i = 1; i <= total; i++) {
        const img = await renderPageForViewer(pdfPath, i, 180);
        thumbs.push({ page: i, image: img });
      }
      resultThumbnails = thumbs;
    } catch (err) {
      console.error('Error loading thumbnails:', err);
    }
    isLoadingThumbs = false;
  }

  function thumbBorder(page: number): string {
    return page === viewerCurrentPage ? '2px solid var(--nord8)' : '1px solid var(--nord3)';
  }

  async function handleRotate() {
    if (!file || file.pages.length === 0) return;

    resultPath = null;

    // Determine rotations
    let rotationEntries: string[] = [];

    if (rotationMode === 'all') {
      // No per-page entries; backend will use --degrees for all pages
    } else if (rotationMode === 'pages') {
      if (selectedPages.size === 0) {
        log('Select at least one page to rotate', 'warning', MODULE);
        return;
      }
      rotationEntries = [...selectedPages]
        .sort((a, b) => a - b)
        .map(p => `${p - 1}=${getRotationForPage(p)}`);
    } else if (rotationMode === 'groups') {
      const nonEmptyGroups = groups.filter(g => g.length > 0);
      if (nonEmptyGroups.length === 0) {
        log('Create at least one group with pages', 'warning', MODULE);
        return;
      }
      rotationEntries = groups.flatMap((group, idx) =>
        group.map(pageNum => `${pageNum - 1}=${pageRotations.get(pageNum) ?? groupDegrees[idx] ?? rotationDegrees}`)
      );
    }

    const outputPath = await save({
      title: 'Save rotated PDF as',
      filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
      defaultPath: `rotated_${file.name}`,
    });

    if (!outputPath) return;

    isRotating = true;
    log('Rotating pages...', 'info', MODULE);

    try {
      const result = await invoke<string>('rotate_pdf', {
        input: file.path,
        degrees: rotationDegrees,
        output: outputPath as string,
        rotations: rotationEntries.length > 0 ? rotationEntries : undefined,
      });

      logSuccess(`Rotation complete: ${result}`, MODULE);
      resultPath = result;
      await loadResultViewer(result);
    } catch (err) {
      console.error('Rotate error:', err);
      logError(`Rotate failed: ${err}`, MODULE);
    }

    isRotating = false;
  }

  function handlePreviewPage(page: PageData) {
    previewPage = page;
  }

  function handlePreviewNavigate(pageNumber: number) {
    if (!file) return;
    const page = file.pages.find(p => p.pageNumber === pageNumber);
    if (page) previewPage = page;
  }

  const rotationSummary = $derived(() => {
    if (!file) return '';
    if (rotationMode === 'all') {
      return `All ${file.pageCount} pages will be rotated ${rotationDegrees}°`;
    }
    if (rotationMode === 'pages') {
      return selectedPages.size === 0
        ? 'Select pages to rotate'
        : `${selectedPages.size} page(s) will be rotated ${rotationDegrees}°`;
    }
    const nonEmpty = groups.filter(g => g.length > 0);
    if (nonEmpty.length === 0) return 'Create groups to rotate';
    return `${nonEmpty.length} group(s) with ${nonEmpty.reduce((acc, g) => acc + g.length, 0)} page(s)`;
  });

  const canRotate = $derived(() => {
    if (!file || file.pages.length === 0) return false;
    if (rotationMode === 'all') return true;
    if (rotationMode === 'pages') return selectedPages.size > 0;
    if (rotationMode === 'groups') return groups.some(g => g.length > 0);
    return false;
  });
</script>

<div class="flex-1 flex overflow-hidden">
  <!-- Main Content Area -->
  <div class="flex-1 flex flex-col overflow-hidden">
    {#if resultPath}
      <!-- Result viewer -->
      <div
        class="flex items-center gap-3 px-4 py-2 border-b"
        style="background-color: var(--nord1); border-color: var(--nord3);"
      >
        <button
          class="px-3 py-1.5 rounded text-xs hover:bg-[var(--nord2)] transition-colors"
          style="border: 1px solid var(--nord3);"
          onclick={() => { resultPath = null; previewEnabled = false; }}
        >
          Back to rotate
        </button>
        <span class="text-xs opacity-60 truncate">Previewing: {resultPath}</span>
        <div class="flex items-center gap-2 ml-auto">
          <button
            class="p-2 rounded hover:bg-[var(--nord2)]"
            onclick={() => goToViewerPage(viewerCurrentPage - 1)}
            disabled={viewerCurrentPage <= 1 || isLoadingViewer}
          >
            <ChevronLeft size={14} />
          </button>
          <div class="flex items-center gap-1 text-xs">
            <input
              class="w-12 px-2 py-1 rounded border text-center"
              style="background-color: var(--nord0); border-color: var(--nord3);"
              value={pageInputValue}
              oninput={handleViewerPageInput}
            />
            <span class="opacity-60">/ {viewerTotalPages}</span>
          </div>
          <button
            class="p-2 rounded hover:bg-[var(--nord2)]"
            onclick={() => goToViewerPage(viewerCurrentPage + 1)}
            disabled={viewerCurrentPage >= viewerTotalPages || isLoadingViewer}
          >
            <ChevronRight size={14} />
          </button>

          <div class="flex items-center gap-1 ml-4">
            <button
              class="p-2 rounded hover:bg-[var(--nord2)]"
              onclick={() => changeZoom(-1)}
              disabled={isLoadingViewer}
            >
              <ZoomOut size={14} />
            </button>
            <span class="text-xs w-10 text-center">{viewerZoom}%</span>
            <button
              class="p-2 rounded hover:bg-[var(--nord2)]"
              onclick={() => changeZoom(1)}
              disabled={isLoadingViewer}
            >
              <ZoomIn size={14} />
            </button>
          </div>

          <div class="flex items-center gap-1 ml-2">
            <span class="text-xs opacity-60">Fit</span>
            <div class="flex items-center gap-1">
              <button
                class="p-1 rounded border"
                style="border-color: var(--nord3); background-color: {fitMode === 'auto' ? 'var(--nord8)' : 'var(--nord2)'};"
                onclick={() => fitMode = 'auto'}
                title="Auto"
              >
                <RectangleHorizontal size={14} />
              </button>
              <button
                class="p-1 rounded border"
                style="border-color: var(--nord3); background-color: {fitMode === 'width' ? 'var(--nord8)' : 'var(--nord2)'};"
                onclick={() => fitMode = 'width'}
                title="Fit width"
              >
                <RectangleHorizontal size={14} />
              </button>
              <button
                class="p-1 rounded border"
                style="border-color: var(--nord3); background-color: {fitMode === 'height' ? 'var(--nord8)' : 'var(--nord2)'};"
                onclick={() => fitMode = 'height'}
                title="Fit height"
              >
                <RectangleVertical size={14} />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="flex-1 overflow-auto p-4">
        <div class="h-full flex gap-4">
          <div
            class="flex-1 rounded-lg flex items-center justify-center"
            style="background-color: var(--nord1);"
          >
            {#if isLoadingViewer}
              <div class="w-10 h-10 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin"></div>
            {:else if viewerImages.length > 0}
              <div class="w-full h-full flex flex-wrap items-start justify-center gap-4 overflow-auto p-4">
                {#each viewerImages as item (item.page)}
                  <div class="flex flex-col items-center gap-1">
                    <img
                      src={item.image}
                      alt={`Page ${item.page}`}
                      class="max-h-[85vh] max-w-full object-contain"
                      style={`width: ${viewerLayout === 'grid' ? '320px' : 'auto'}; ${fitMode === 'width' ? 'width: 100%; height: auto;' : ''}${fitMode === 'height' ? 'height: 80vh; width: auto;' : ''}`}
                    />
                    <span class="text-xs opacity-60">Page {item.page}</span>
                  </div>
                {/each}
              </div>
            {:else}
              <p class="opacity-60 text-sm">No preview available</p>
            {/if}
          </div>

          <div
            class="w-52 rounded-lg border p-3 flex flex-col gap-2"
            style="background-color: var(--nord1); border-color: var(--nord3);"
          >
            <div class="flex items-center justify-between text-xs">
              <span class="opacity-60">Thumbnails</span>
              {#if isLoadingThumbs}
                <span class="opacity-60">Loading...</span>
              {/if}
            </div>
            <div class="flex-1 overflow-auto space-y-2">
              {#if resultThumbnails.length === 0 && !isLoadingThumbs}
                <p class="text-xs opacity-50">No thumbnails</p>
              {:else}
                {#each resultThumbnails as thumb (thumb.page)}
                  <button
                    class="w-full text-left rounded p-1 transition-colors"
                    style={`border: ${thumbBorder(thumb.page)}; background-color: ${thumb.page === viewerCurrentPage ? 'var(--nord2)' : 'transparent'};`}
                    onclick={() => goToViewerPage(thumb.page)}
                  >
                    <div class="w-full aspect-[3/4] overflow-hidden flex items-center justify-center" style="background-color: var(--nord0);">
                      <img src={thumb.image} alt={`Page ${thumb.page}`} class="w-full object-contain" />
                    </div>
                    <div class="text-[11px] opacity-70 mt-1">Page {thumb.page}</div>
                  </button>
                {/each}
              {/if}
            </div>
          </div>
        </div>
      </div>
    {:else}
      <!-- Rotate Mode Toolbar -->
      {#if file && file.pages.length > 0}
        <div
          class="flex items-center gap-4 px-4 py-2 border-b"
          style="background-color: var(--nord1); border-color: var(--nord3);"
        >
          <span class="text-xs opacity-60 uppercase">Rotate Mode:</span>

          <div class="flex items-center gap-1">
            <button
              onclick={() => rotationMode = 'all'}
              class="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-colors"
              style="background-color: {rotationMode === 'all' ? 'var(--nord8)' : 'var(--nord2)'};
                     color: {rotationMode === 'all' ? 'var(--nord0)' : 'var(--nord4)'};"
              title="Rotate all pages"
            >
              <Grid3x3 size={14} />
              <span>All Pages</span>
            </button>

            <button
              onclick={() => rotationMode = 'pages'}
              class="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-colors"
              style="background-color: {rotationMode === 'pages' ? 'var(--nord8)' : 'var(--nord2)'};
                     color: {rotationMode === 'pages' ? 'var(--nord0)' : 'var(--nord4)'};"
              title="Rotate selected pages"
            >
              <RotateCw size={14} />
              <span>Select Pages</span>
            </button>

            <button
              onclick={() => rotationMode = 'groups'}
              class="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-colors"
              style="background-color: {rotationMode === 'groups' ? 'var(--nord8)' : 'var(--nord2)'};
                     color: {rotationMode === 'groups' ? 'var(--nord0)' : 'var(--nord4)'};"
              title="Rotate by groups"
            >
              <Layers size={14} />
              <span>Groups</span>
            </button>
          </div>

        <div class="flex items-center gap-2 ml-auto flex-wrap justify-end">
          <label class="text-xs opacity-60" for="rotation-select">Rotation</label>
          <select
            id="rotation-select"
            class="text-xs px-2 py-1 rounded border"
            style="background-color: var(--nord2); border-color: var(--nord3);"
              bind:value={rotationDegrees}
              onchange={onRotationChange}
            >
              {#each DEGREE_OPTIONS as deg}
                <option value={deg}>{deg}°</option>
              {/each}
            </select>
            <button
              class="px-2 py-1 rounded text-xs border transition-colors"
              style="border-color: var(--nord3); background-color: {previewEnabled ? 'var(--nord8)' : 'var(--nord2)'}; color: {previewEnabled ? 'var(--nord0)' : 'var(--nord4)'};"
              onclick={() => previewEnabled = !previewEnabled}
              title="Preview shows rotations on thumbnails only"
            >
              {previewEnabled ? 'Preview on' : 'Preview off'}
            </button>
            <div class="flex items-center gap-1 ml-2">
              <span class="text-xs opacity-60">Layout</span>
              <div class="flex items-center gap-1">
                <button
                  class="p-1 rounded border"
                  style="border-color: var(--nord3); background-color: {viewerLayout === 'single' ? 'var(--nord8)' : 'var(--nord2)'};"
                  onclick={() => changeLayout('single')}
                  title="Single page"
                >
                  <RectangleVertical size={14} />
                </button>
                <button
                  class="p-1 rounded border"
                  style="border-color: var(--nord3); background-color: {viewerLayout === 'double' ? 'var(--nord8)' : 'var(--nord2)'};"
                  onclick={() => changeLayout('double')}
                  title="Two-up"
                >
                  <Columns size={14} />
                </button>
                <button
                  class="p-1 rounded border"
                  style="border-color: var(--nord3); background-color: {viewerLayout === 'grid' ? 'var(--nord8)' : 'var(--nord2)'};"
                  onclick={() => changeLayout('grid')}
                  title="2x2 grid"
                >
                  <LayoutGrid size={14} />
                </button>
              </div>
            </div>
          </div>

          <span class="text-xs opacity-60">{rotationSummary()}</span>
        </div>

        {#if rotationMode === 'groups' && groups.length > 0}
          <div
            class="px-4 py-2 border-b flex items-center gap-2 flex-wrap"
            style="background-color: var(--nord1); border-color: var(--nord3);"
          >
            <span class="text-xs opacity-60">Group angles:</span>
            {#each groups as group, idx}
              <div
                class="flex items-center gap-2 px-2 py-1 rounded"
                style="background-color: var(--nord2); border: 1px solid var(--nord3);"
              >
                <span class="text-xs">Group {idx + 1}</span>
                <select
                  class="text-xs px-2 py-1 rounded border"
                  style="background-color: var(--nord0); border-color: var(--nord3);"
                  bind:value={groupDegrees[idx]}
                  onchange={(e) => onGroupRotationChange(idx, e)}
                >
                  {#each DEGREE_OPTIONS as deg}
                    <option value={deg}>{deg}°</option>
                  {/each}
                </select>
                <span class="text-[11px] opacity-60">{group.length} page(s)</span>
              </div>
            {/each}
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
              <RotateCw size={48} class="opacity-40 mb-4" />
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
                mode={rotationMode}
                bind:selectedPages
                bind:groups
                onPreviewPage={handlePreviewPage}
                showRotationControls={rotationMode !== 'all'}
                rotationValues={pageRotations}
                rotationOptions={DEGREE_OPTIONS}
                onRotationChange={handlePageRotationChange}
                previewRotationForPage={previewEnabled ? getRotationForPage : undefined}
              />
            </div>
          {/if}
        </div>
      {/if}
    {/if}
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

    <!-- Rotate Button -->
    <button
      onclick={handleRotate}
      disabled={!canRotate() || isRotating}
      class="px-4 py-3 rounded transition-colors disabled:opacity-50 hover:opacity-90 flex items-center justify-center gap-2"
      style="background-color: var(--nord8); color: var(--nord0);"
    >
      {#if isRotating}
        <div class="w-4 h-4 border-2 border-[var(--nord0)] border-t-transparent rounded-full animate-spin"></div>
        <span>Rotating...</span>
      {:else}
        <RotateCw size={18} />
        <span>Rotate</span>
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
