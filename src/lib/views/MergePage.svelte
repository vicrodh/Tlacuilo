<script lang="ts">
  import { Upload, FolderOpen, Trash2, X, FileText } from 'lucide-svelte';
  import { onMount, onDestroy } from 'svelte';
  import { listen } from '@tauri-apps/api/event';
  import { open, save } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';
  import { dndzone } from 'svelte-dnd-action';
  import { renderFirstPageThumbnail, renderAllPageThumbnails } from '$lib/utils/pdfjs';

// Navigation prop reserved for future use
export let onNavigate: ((page: string) => void) | undefined;

  type FileItem = {
    id: string;
    name: string;
    path: string;
    thumb?: string;
    pages: PageItem[];
  };

  type PageItem = {
    id: string;
    fileId: string;
    fileName: string;
    pageNumber: number;
    thumb?: string;
  };

  let files: FileItem[] = [];
  let canvasFiles: FileItem[] = [];
  let sourcePages: PageItem[] = [];
  let destPages: PageItem[] = [];
  let viewMode: 'file' | 'page' = 'file';
  let topCollapsed = false;
  let status = 'Ready';
  let unlistenDrop: (() => void) | null = null;

  function setStatus(msg: string) {
    status = msg;
  }

  function toFileItem(paths: string[]): FileItem[] {
    return paths.map((p) => ({
      id: crypto.randomUUID(),
      name: p.split('/').pop() || p,
      path: p,
      pages: []
    }));
  }

  async function addFiles(paths: string[]) {
    const items = toFileItem(paths);
    files = [...files, ...items];
    canvasFiles = [...canvasFiles, ...items];
    setStatus(`Queue: ${canvasFiles.length} file(s).`);
    for (const item of items) {
      // file-level thumb
      try {
        item.thumb = await renderFirstPageThumbnail(item.path, 160);
      } catch (err) {
        console.error('thumb error', err);
      }
      // page-level thumbs
      try {
        const pages: string[] = await renderAllPageThumbnails(item.path, 140);
        sourcePages = [...sourcePages, ...pages.map((p: string, idx: number) => ({
          id: `${item.id}-p${idx + 1}`,
          fileId: item.id,
          fileName: item.name,
          pageNumber: idx + 1,
          thumb: p
        }))];
      } catch (err) {
        console.error('page render error', err);
      }
    }
  }

  async function pickFiles() {
    const selected = await open({ multiple: true, filters: [{ name: 'PDF files', extensions: ['pdf'] }] });
    if (!selected) return;
    const list = Array.isArray(selected) ? selected : [selected];
    await addFiles(list.map(String));
  }

  async function doMerge() {
    if (viewMode === 'file' && canvasFiles.length < 1) {
      setStatus('Add files to merge.');
      return;
    }
    if (viewMode === 'page' && destPages.length < 1) {
      setStatus('Add pages to destination.');
      return;
    }
    const output = await save({ defaultPath: 'merged.pdf', filters: [{ name: 'PDF files', extensions: ['pdf'] }] });
    if (!output) {
      setStatus('Merge cancelled (no output selected).');
      return;
    }
    try {
      const inputs = viewMode === 'file'
        ? canvasFiles.map((f) => f.path)
        : Array.from(new Set(destPages.map((p) => p.fileId)))
            .map((id) => files.find((f) => f.id === id)?.path || '')
            .filter(Boolean);
      const result = await invoke<string>('merge_pdfs', { inputs, output });
      setStatus(`Merged into ${result}`);
    } catch (err) {
      setStatus(`Merge failed: ${err}`);
    }
  }

  function removeFile(id: string) {
    files = files.filter((f) => f.id !== id);
    canvasFiles = canvasFiles.filter((f) => f.id !== id);
    sourcePages = sourcePages.filter((p) => p.fileId !== id);
    destPages = destPages.filter((p) => p.fileId !== id);
  }

  function addToCanvas(id: string) {
    const f = files.find((x) => x.id === id);
    if (!f) return;
    if (canvasFiles.find((x) => x.id === id)) return;
    canvasFiles = [...canvasFiles, f];
  }

  function removeFromCanvas(id: string) {
    canvasFiles = canvasFiles.filter((f) => f.id !== id);
  }

  function removeDestPage(id: string) {
    destPages = destPages.filter((p) => p.id !== id);
  }

  onMount(async () => {
    unlistenDrop = await listen<string[]>('tauri://file-drop', (e) => {
      const pdfs = e.payload.filter((p) => p.toLowerCase().endsWith('.pdf'));
      if (pdfs.length > 0) addFiles(pdfs);
    });
  });

  onDestroy(() => {
    if (unlistenDrop) unlistenDrop();
  });
</script>

<div class="flex flex-col h-[calc(100vh-22px)] bg-[var(--nord0)] text-[var(--nord6)]">
  <div class="grid grid-cols-[85%_15%] gap-4 p-4">
    <!-- Left Column -->
    <div class="flex flex-col gap-3">
      <!-- Top area -->
      <div class={`rounded-xl border border-[var(--nord2)] bg-[var(--nord1)] p-3 ${viewMode === 'page' ? 'h-[500px]' : 'h-[260px]'}`}>
        <div class="flex items-center justify-between mb-2">
          <div class="text-sm font-semibold">{viewMode === 'file' ? 'File view' : 'Page view'}</div>
          <div class="flex items-center gap-2">
            {#if canvasFiles.length > 0}
              <div class="join text-xs">
                <button class={`btn btn-xs join-item ${viewMode === 'file' ? 'btn-active' : ''}`} on:click={() => (viewMode = 'file')}>File</button>
                <button class={`btn btn-xs join-item ${viewMode === 'page' ? 'btn-active' : ''}`} on:click={() => (viewMode = 'page')}>Page</button>
              </div>
            {/if}
            <button class="btn btn-xs btn-ghost" on:click={() => (topCollapsed = !topCollapsed)}>{topCollapsed ? 'Expand' : 'Collapse'}</button>
          </div>
        </div>

        {#if !topCollapsed}
          {#if viewMode === 'file'}
            <div class="text-xs text-[var(--nord4)] mb-2">Drag to reorder files</div>
            <div
              class="flex gap-3 overflow-x-auto rounded-lg border border-dashed border-[var(--nord2)] bg-[var(--nord0)] p-3"
              use:dndzone={{ items: canvasFiles, flipDurationMs: 150 }}
              on:consider={(e) => (canvasFiles = e.detail.items)}
              on:finalize={(e) => (canvasFiles = e.detail.items)}
            >
              {#if canvasFiles.length === 0}
                <div class="text-sm text-[var(--nord4)]">Add files to start.</div>
              {:else}
                {#each canvasFiles as file (file.id)}
                  <div class="w-28 flex-shrink-0 space-y-1 rounded border border-[var(--nord2)] bg-[var(--nord1)] p-2">
                    <div class="h-24 rounded bg-[var(--nord2)] grid place-items-center text-xs text-[var(--nord4)]">
                      {#if file.thumb}
                        <img src={file.thumb} class="max-h-20 object-contain" alt={file.name} />
                      {:else}
                        PDF
                      {/if}
                    </div>
                    <div class="text-[11px] text-center">
                      <p class="font-semibold" title={file.path}>{file.name}</p>
                      <p class="text-[var(--nord4)]">pages: {sourcePages.filter((p) => p.fileId === file.id).length || '…'}</p>
                    </div>
                  </div>
                {/each}
              {/if}
            </div>
          {:else}
            <div class="grid grid-cols-2 gap-3 h-full">
              <div
                class="rounded-lg border border-dashed border-[var(--nord2)] bg-[var(--nord0)] p-3 overflow-auto"
                use:dndzone={{ items: sourcePages, type: 'page', flipDurationMs: 150 }}
                on:consider={(e) => (sourcePages = e.detail.items)}
                on:finalize={(e) => (sourcePages = e.detail.items)}
              >
                <p class="text-sm font-semibold mb-2">Source pages</p>
                <div class="flex flex-wrap gap-2">
                  {#each sourcePages as page (page.id)}
                    <div class="relative w-20 cursor-move rounded border border-[var(--nord2)] bg-[var(--nord1)] p-1">
                      <div class="h-20 rounded bg-[var(--nord2)] grid place-items-center text-[11px] text-[var(--nord4)]">
                        {#if page.thumb}
                          <img src={page.thumb} class="max-h-16 object-contain" alt={`p${page.pageNumber}`} />
                        {:else}
                          <span>P{page.pageNumber}</span>
                        {/if}
                      </div>
                      <p class="text-[10px] font-semibold truncate" title={`${page.fileName} pg ${page.pageNumber}`}>{page.fileName}</p>
                      <p class="text-[9px] text-[var(--nord4)]">Pg {page.pageNumber}</p>
                    </div>
                  {/each}
                </div>
              </div>
              <div
                class="rounded-lg border border-dashed border-[var(--nord2)] bg-[var(--nord0)] p-3 overflow-auto"
                use:dndzone={{ items: destPages, type: 'page', flipDurationMs: 150 }}
                on:consider={(e) => (destPages = e.detail.items)}
                on:finalize={(e) => (destPages = e.detail.items)}
              >
                <p class="text-sm font-semibold mb-2">Merged document</p>
                <div class="flex flex-wrap gap-2">
                  {#each destPages as page (page.id)}
                    <div class="relative w-20 cursor-move rounded border border-[var(--nord2)] bg-[var(--nord1)] p-1">
                      <button class="absolute right-1 top-1 btn btn-ghost btn-[10px]" on:click={() => removeDestPage(page.id)}>✕</button>
                      <div class="h-20 rounded bg-[var(--nord2)] grid place-items-center text-[11px] text-[var(--nord4)]">
                        {#if page.thumb}
                          <img src={page.thumb} class="max-h-16 object-contain" alt={`p${page.pageNumber}`} />
                        {:else}
                          <span>P{page.pageNumber}</span>
                        {/if}
                      </div>
                      <p class="text-[10px] font-semibold truncate" title={`${page.fileName} pg ${page.pageNumber}`}>{page.fileName}</p>
                      <p class="text-[9px] text-[var(--nord4)]">Pg {page.pageNumber}</p>
                    </div>
                  {/each}
                </div>
              </div>
            </div>
          {/if}
        {/if}
      </div>

      <div class="flex-1 rounded-xl border border-[var(--nord2)] bg-[var(--nord1)] p-4">
        <p class="text-sm font-semibold mb-2">Viewer / output</p>
        <div class="h-full rounded border border-[var(--nord2)] bg-[var(--nord0)] grid place-items-center text-sm text-[var(--nord4)]">
          PDF preview area
        </div>
      </div>
    </div>

    <!-- Right Column -->
    <div class="rounded-xl border border-[var(--nord2)] bg-[var(--nord1)] p-3 flex flex-col gap-3">
      <div class="flex items-center justify-between">
        <p class="text-sm font-semibold">Files</p>
        <button class="btn btn-xs btn-ghost" on:click={() => files = []}>Clear</button>
      </div>

      {#if files.length === 0}
        <div class="flex-1 rounded border border-dashed border-[var(--nord2)] bg-[var(--nord0)] grid place-items-center text-sm text-[var(--nord4)]">
          <div class="flex flex-col items-center gap-2">
            <Upload size={32} />
            <p>Drop files here</p>
          </div>
        </div>
      {:else}
        <div class="flex-1 overflow-auto space-y-2">
          {#each files as file (file.id)}
            <div class="flex items-center justify-between rounded border border-[var(--nord2)] bg-[var(--nord0)] px-3 py-2 text-sm">
              <div class="flex items-center gap-2">
                <FileText size={16} />
                <span class="font-semibold" title={file.path}>{file.name}</span>
              </div>
              <div class="flex items-center gap-2">
                <button class="btn btn-xs btn-outline" on:click={() => addToCanvas(file.id)}>Add</button>
                <button class="btn btn-xs btn-ghost" on:click={() => removeFile(file.id)}><Trash2 size={14} /></button>
              </div>
            </div>
          {/each}
        </div>
      {/if}

      <button class="btn btn-sm w-full" on:click={pickFiles}><FolderOpen size={16} /> Pick files</button>
      <button class="btn btn-sm bg-[var(--nord10)] text-[var(--nord6)] w-full" on:click={doMerge}>Merge</button>
    </div>
  </div>

  <div class="h-10 border-t border-[var(--nord2)] bg-[var(--nord1)] px-4 flex items-center justify-between text-sm text-[var(--nord4)]">
    <div>Status: {status}</div>
    <div>IH PDF · Offline toolkit</div>
  </div>
</div>
