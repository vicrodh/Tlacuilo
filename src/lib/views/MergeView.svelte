<script lang="ts">
import { invoke } from '@tauri-apps/api/core';
import { open, save } from '@tauri-apps/plugin-dialog';
import { listen } from '@tauri-apps/api/event';
import { dndzone } from 'svelte-dnd-action';
import { onMount, onDestroy } from 'svelte';
import { renderFirstPageThumbnail } from '$lib/utils/pdfjs';

type MergeItem = {
  id: string;
  path: string;
  name: string;
  thumb?: string;
  thumbStatus?: 'pending' | 'ok' | 'error';
};

type PageItem = {
  id: string;
  fileId: string;
  fileName: string;
  pageNumber: number;
  thumb?: string;
};

export let onBack: (() => void) | undefined;
export let onMerged: ((path: string) => void) | undefined;

let libraryItems: MergeItem[] = [];
let canvasItems: MergeItem[] = [];
let sourcePages: PageItem[] = [];
let destPages: PageItem[] = [];
let viewMode: 'file' | 'page' = 'file';
let topCollapsed = false;
let status = 'Drop PDFs or use the picker to start.';
let unlistenDrop: (() => void) | null = null;

function setStatus(msg: string) {
  status = msg;
}

function addPaths(paths: string[]) {
  const newItems = paths.map((p, idx) => {
    const name = p.split('/').pop() || p;
    const id = crypto.randomUUID();
    return { id, path: p, name, thumbStatus: 'pending' as const };
  });
  libraryItems = [...libraryItems, ...newItems];
  canvasItems = [...canvasItems, ...newItems];
  setStatus(`Queue: ${canvasItems.length} file(s).`);
  // kick off page placeholders
  newItems.forEach((item) => {
    // reset source pages
    sourcePages = [
      ...sourcePages,
      {
        id: `${item.id}-p1`,
        fileId: item.id,
        fileName: item.name,
        pageNumber: 1
      }
    ];
  });
}

async function pickFiles() {
  const files = await open({ multiple: true, filters: [{ name: 'PDF files', extensions: ['pdf'] }] });
  if (!files) return;
    const list = Array.isArray(files) ? files : [files];
    addPaths(list.map(String));
}

async function runMerge() {
  if (viewMode === 'page' && destPages.length === 0) {
    setStatus('Add pages to the destination area.');
    return;
  }
  if (viewMode === 'file' && canvasItems.length < 2) {
    setStatus('Add at least two PDFs to merge.');
    return;
  }
  const output = await save({ defaultPath: 'merged.pdf', filters: [{ name: 'PDF files', extensions: ['pdf'] }] });
  if (!output) {
      setStatus('Merge cancelled (no output selected).');
      return;
  }
  try {
    const inputs =
      viewMode === 'page' && destPages.length > 0
        ? Array.from(new Set(destPages.map((p) => p.fileId))).map(
            (id) => canvasItems.find((i) => i.id === id)?.path || ''
          )
        : canvasItems.map((m) => m.path);
    const result = await invoke<string>('merge_pdfs', { inputs, output });
    setStatus(`Merged into ${result}`);
    onMerged?.(result);
  } catch (err) {
    setStatus(`Merge failed: ${err}`);
      console.error('merge_pdfs error', err);
    }
  }

  function removeFromCanvas(id: string) {
    canvasItems = canvasItems.filter((i) => i.id !== id);
    setStatus(`Queue: ${canvasItems.length} file(s).`);
  }

function removeFromLibrary(id: string) {
  libraryItems = libraryItems.filter((i) => i.id !== id);
  canvasItems = canvasItems.filter((i) => i.id !== id);
  sourcePages = sourcePages.filter((p) => p.fileId !== id);
  destPages = destPages.filter((p) => p.fileId !== id);
  setStatus(`Queue: ${canvasItems.length} file(s).`);
}

function addToCanvas(id: string) {
  const item = libraryItems.find((i) => i.id === id);
    if (!item) return;
    if (canvasItems.find((i) => i.id === id)) return;
    canvasItems = [...canvasItems, item];
  setStatus(`Queue: ${canvasItems.length} file(s).`);
}

onMount(async () => {
  unlistenDrop = await listen<string[]>('tauri://file-drop', (event) => {
      const pdfs = event.payload.filter((p) => p.toLowerCase().endsWith('.pdf'));
      if (pdfs.length === 0) {
        setStatus('Dropped files are not PDF; ignored.');
        return;
      }
      addPaths(pdfs);
    });
  });

  onDestroy(() => {
    if (unlistenDrop) unlistenDrop();
  });

  $: renderThumbs();

  async function renderThumbs() {
    for (const item of canvasItems) {
      if (item.thumbStatus === 'ok') continue;
      try {
        item.thumbStatus = 'pending';
        item.thumb = await renderFirstPageThumbnail(item.path, 200);
        item.thumbStatus = 'ok';
      } catch (err) {
        item.thumb = undefined;
        item.thumbStatus = 'error';
        console.error('Thumb render failed', err);
      }
    }
  }

  async function renderPagesForFile(item: MergeItem) {
    try {
      // naive: reuse first-page thumb for now; placeholder per page
      const thumb = await renderFirstPageThumbnail(item.path, 160);
      // mock 3 pages minimum; in real implementation, detect page count
      const pages = Array.from({ length: 3 }, (_, idx) => ({
        id: `${item.id}-p${idx + 1}`,
        fileId: item.id,
        fileName: item.name,
        pageNumber: idx + 1,
        thumb
      }));
      sourcePages = [...sourcePages.filter((p) => p.fileId !== item.id), ...pages];
    } catch (err) {
      console.error('Page render failed', err);
    }
  }

  $: if (viewMode === 'page') {
    canvasItems.forEach((item) => {
      if (!sourcePages.find((p) => p.fileId === item.id)) {
        renderPagesForFile(item);
      }
    });
  }
</script>

<div class="grid h-[calc(100vh-64px)] grid-cols-[14%_1fr] gap-4">
  <aside class="flex h-full flex-col rounded-2xl border border-base-300 bg-base-100 p-4 shadow-sm">
    <div class="flex items-center justify-between">
      <p class="text-base font-semibold">Merge workspace</p>
      {#if onBack}
        <button class="btn btn-xs btn-ghost" on:click={onBack}>Back</button>
      {/if}
    </div>
    <p class="text-xs text-base-content/60 mt-1">Drop PDFs or use the picker.</p>

    <div class="mt-3 flex-1 overflow-auto rounded-xl border border-dashed border-base-300 bg-base-200/50 p-2 space-y-1">
      {#if libraryItems.length === 0}
        <div class="flex h-full items-center justify-center text-sm text-base-content/60">Drop PDFs here or click picker.</div>
      {:else}
        {#each libraryItems as item (item.id)}
          <div class="flex items-center justify-between rounded-lg border border-base-200 bg-base-100 px-3 py-2 text-sm">
            <div class="flex items-center gap-2">
              <span class="badge badge-outline">PDF</span>
              <span class="font-semibold text-base-content" title={item.path}>{item.name}</span>
            </div>
            <div class="flex items-center gap-2">
              <button class="btn btn-xs btn-outline" on:click={() => addToCanvas(item.id)}>Add</button>
              <button class="btn btn-xs btn-ghost" title={item.path} on:click={() => removeFromLibrary(item.id)}>🗑</button>
            </div>
          </div>
        {/each}
      {/if}
    </div>

    <div class="mt-3 flex flex-col gap-2">
      <button class="btn btn-sm btn-outline w-full" on:click={pickFiles}>Pick files</button>
      {#if canvasItems.length > 0}
        <div class="flex items-center justify-between text-xs text-base-content/70">
          <span>View</span>
          <div class="join">
            <button class={`btn btn-xs join-item ${viewMode === 'file' ? 'btn-active' : ''}`} on:click={() => (viewMode = 'file')}>File</button>
            <button class={`btn btn-xs join-item ${viewMode === 'page' ? 'btn-active' : ''}`} on:click={() => (viewMode = 'page')}>Page</button>
          </div>
        </div>
      {/if}
      <button class="btn btn-sm bg-blue-700 text-blue-50 hover:bg-blue-800 w-full" on:click={runMerge}>Merge</button>
    </div>
    <div class="mt-2 rounded-lg bg-base-200/60 px-3 py-2 text-xs text-base-content/70">{status}</div>
  </aside>

  <section class="h-full rounded-2xl border border-base-300 bg-base-100 p-4 shadow-sm overflow-hidden flex flex-col gap-3">
    <div class="flex items-center justify-between">
      <p class="text-base font-semibold">Pages map (beta)</p>
      <button class="btn btn-xs btn-ghost" on:click={() => (topCollapsed = !topCollapsed)}>
        {topCollapsed ? 'Expand' : 'Collapse'}
      </button>
    </div>

    {#if !topCollapsed}
      <div class={viewMode === 'page' ? 'h-[500px] space-y-3 flex flex-col' : 'h-[260px] space-y-3 flex flex-col'}>
        {#if viewMode === 'file'}
          <div class="text-xs text-base-content/60">Drag to reorder files</div>
          <div
            class="flex gap-3 overflow-x-auto rounded-xl border border-dashed border-base-200 bg-base-200/40 p-3"
            use:dndzone={{ items: canvasItems, flipDurationMs: 150 }}
            on:consider={(e) => (canvasItems = e.detail.items)}
            on:finalize={(e) => (canvasItems = e.detail.items)}
          >
            {#each canvasItems as item (item.id)}
              <div class="w-28 flex-shrink-0 space-y-2 rounded-lg border border-base-200 bg-base-100 p-2 shadow-sm">
                <div class="h-28 rounded bg-base-200/80 grid place-items-center text-xs text-base-content/70">
                  {#if item.thumbStatus === 'ok' && item.thumb}
                    <img src={item.thumb} alt={`thumb-${item.name}`} class="max-h-24 object-contain" />
                  {:else}
                    PDF
                  {/if}
                </div>
                <div class="text-xs text-center">
                  <p class="font-semibold" title={item.path}>{item.name}</p>
                  <p class="text-base-content/60">pages: {sourcePages.filter((p) => p.fileId === item.id).length || '—'}</p>
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <div class="flex items-center justify-between text-xs text-base-content/60">
            <span>Drag pages between source and merged</span>
            <span>Tabs per file coming soon</span>
          </div>
          <div class="grid grid-cols-2 gap-3 h-full">
            <div
              class="rounded-xl border border-dashed border-base-200 bg-base-200/40 p-3 overflow-auto"
              use:dndzone={{ items: sourcePages, flipDurationMs: 150, type: 'page' }}
              on:consider={(e) => (sourcePages = e.detail.items)}
              on:finalize={(e) => (sourcePages = e.detail.items)}
            >
              <p class="text-sm font-semibold mb-2">Source pages</p>
              <div class="flex flex-wrap gap-2">
                {#each sourcePages as page (page.id)}
                  <div class="relative w-24 cursor-move rounded border border-base-200 bg-base-100 p-1">
                    <div class="h-28 rounded bg-base-200/80 grid place-items-center text-xs text-base-content/70">
                      {#if page.thumb}
                        <img src={page.thumb} alt={`p${page.pageNumber}`} class="max-h-24 object-contain" />
                      {:else}
                        <span>P{page.pageNumber}</span>
                      {/if}
                    </div>
                    <p class="text-[11px] font-semibold truncate" title={`${page.fileName} - pg ${page.pageNumber}`}>{page.fileName}</p>
                    <p class="text-[10px] text-base-content/60">Pg {page.pageNumber}</p>
                  </div>
                {/each}
              </div>
            </div>
            <div
              class="rounded-xl border border-dashed border-base-200 bg-base-200/40 p-3 overflow-auto"
              use:dndzone={{ items: destPages, flipDurationMs: 150, type: 'page' }}
              on:consider={(e) => (destPages = e.detail.items)}
              on:finalize={(e) => (destPages = e.detail.items)}
            >
              <p class="text-sm font-semibold mb-2">Merged document</p>
              <div class="flex flex-wrap gap-2">
                {#each destPages as page (page.id)}
                  <div class="relative w-24 cursor-move rounded border border-base-200 bg-base-100 p-1">
                    <button class="absolute right-1 top-1 btn btn-ghost btn-[10px]" on:click={() => (destPages = destPages.filter((p) => p.id !== page.id))}>✕</button>
                    <div class="h-28 rounded bg-base-200/80 grid place-items-center text-xs text-base-content/70">
                      {#if page.thumb}
                        <img src={page.thumb} alt={`p${page.pageNumber}`} class="max-h-24 object-contain" />
                      {:else}
                        <span>P{page.pageNumber}</span>
                      {/if}
                    </div>
                    <p class="text-[11px] font-semibold truncate" title={`${page.fileName} - pg ${page.pageNumber}`}>{page.fileName}</p>
                    <p class="text-[10px] text-base-content/60">Pg {page.pageNumber}</p>
                  </div>
                {/each}
              </div>
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <div class="flex-1 rounded-xl border border-base-300 bg-base-200/40 p-4">
      <p class="text-sm font-semibold mb-2">Viewer / output</p>
      <div class="h-full rounded bg-base-100/80 border border-base-200 grid place-items-center text-sm text-base-content/60">
        PDF preview area
      </div>
    </div>
  </section>
</div>
