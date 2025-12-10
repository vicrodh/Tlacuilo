<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import { open, save } from '@tauri-apps/plugin-dialog';
  import { dndzone } from 'svelte-dnd-action';
  import { onMount, onDestroy } from 'svelte';
  import { listen } from '@tauri-apps/api/event';
  import { renderFirstPageThumbnail } from '$lib/utils/pdfjs';

type MergeItem = {
  id: string;
  path: string;
  name: string;
  thumb?: string;
  thumbStatus?: 'pending' | 'ok' | 'error';
};

  export let onBack: (() => void) | undefined;
  export let onMerged: ((path: string) => void) | undefined;

  let mergeItems: MergeItem[] = [];
  let status = 'Drop PDFs or use the picker to start.';
  let unlistenDrop: (() => void) | null = null;

  function setStatus(msg: string) {
    status = msg;
  }

function addPaths(paths: string[]) {
  const newItems = paths.map((p) => {
    const name = p.split('/').pop() || p;
    return { id: crypto.randomUUID(), path: p, name, thumbStatus: 'pending' as const };
  });
  mergeItems = [...mergeItems, ...newItems];
  setStatus(`Queue: ${mergeItems.length} file(s).`);
}

  async function pickFiles() {
    const files = await open({ multiple: true, filters: [{ name: 'PDF files', extensions: ['pdf'] }] });
    if (!files) return;
    const list = Array.isArray(files) ? files : [files];
    addPaths(list.map(String));
  }

  async function runMerge() {
    if (mergeItems.length < 2) {
      setStatus('Add at least two PDFs to merge.');
      return;
    }
    const output = await save({ defaultPath: 'merged.pdf', filters: [{ name: 'PDF files', extensions: ['pdf'] }] });
    if (!output) {
      setStatus('Merge cancelled (no output selected).');
      return;
    }
    try {
      const inputs = mergeItems.map((m) => m.path);
      const result = await invoke<string>('merge_pdfs', { inputs, output });
      setStatus(`Merged into ${result}`);
      onMerged?.(result);
    } catch (err) {
      setStatus(`Merge failed: ${err}`);
      console.error('merge_pdfs error', err);
    }
  }

  function removeItem(id: string) {
    mergeItems = mergeItems.filter((i) => i.id !== id);
    setStatus(`Queue: ${mergeItems.length} file(s).`);
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
  for (const item of mergeItems) {
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
</script>

<div class="grid h-[calc(100vh-64px)] grid-cols-[360px,1fr] gap-4">
  <aside class="flex h-full flex-col rounded-2xl border border-base-300 bg-base-100 p-4 shadow-sm">
    <div class="flex items-center justify-between">
      <p class="text-base font-semibold">Merge workspace</p>
      {#if onBack}
        <button class="btn btn-xs btn-ghost" on:click={onBack}>Back</button>
      {/if}
    </div>
    <p class="text-xs text-base-content/60 mt-1">Drop PDFs or use the picker. Drag to reorder.</p>

    <div class="mt-3 flex-1 space-y-2 overflow-auto rounded-xl border border-dashed border-base-300 bg-base-200/50 p-3">
      {#if mergeItems.length === 0}
        <div class="flex h-full items-center justify-center text-sm text-base-content/60">
          Drop PDFs here or click picker.
        </div>
      {:else}
        {#each mergeItems as item (item.id)}
          <div class="flex items-center justify-between rounded-lg border border-base-200 bg-base-100 px-3 py-2 text-sm">
            <div class="flex items-center gap-2">
              <span class="badge badge-outline">PDF</span>
              <span class="font-semibold text-base-content">{item.name}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-xs text-base-content/60 max-w-[200px] truncate" title={item.path}>{item.path}</span>
              <button class="btn btn-xs btn-ghost" on:click={() => removeItem(item.id)}>Remove</button>
            </div>
          </div>
        {/each}
      {/if}
    </div>

    <div class="mt-3 flex gap-2">
      <button class="btn btn-sm btn-outline flex-1" on:click={pickFiles}>Pick files</button>
      <button class="btn btn-sm bg-blue-700 text-blue-50 hover:bg-blue-800" on:click={runMerge}>Merge</button>
    </div>
    <div class="mt-2 rounded-lg bg-base-200/60 px-3 py-2 text-xs text-base-content/70">{status}</div>
  </aside>

  <section class="h-full rounded-2xl border border-base-300 bg-base-100 p-4 shadow-sm overflow-hidden">
    <div class="mb-3 flex items-center justify-between">
      <p class="text-base font-semibold">Pages map (beta)</p>
      <span class="text-xs text-base-content/60">Rendering first page per file</span>
    </div>
    <div class="h-[calc(100%-48px)] overflow-auto rounded-xl border border-dashed border-base-200 bg-base-200/40 p-4">
      {#if mergeItems.length === 0}
        <div class="grid h-full place-items-center text-sm text-base-content/60">Add PDFs to preview.</div>
      {:else}
        <div
          class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4"
          use:dndzone={{ items: mergeItems, flipDurationMs: 150 }}
          on:consider={(e) => (mergeItems = e.detail.items)}
          on:finalize={(e) => (mergeItems = e.detail.items)}
        >
          {#each mergeItems as item (item.id)}
            <div class="rounded-lg border border-base-200 bg-base-100 p-2 shadow-sm space-y-2">
              <div class="flex items-center justify-between gap-2">
                <p class="truncate text-xs font-semibold" title={item.name}>{item.name}</p>
                <button class="btn btn-ghost btn-xs" on:click={() => removeItem(item.id)}>✕</button>
              </div>
              <div class="flex items-center justify-center rounded-md border border-base-200 bg-base-200/60 min-h-[140px]">
                {#if item.thumbStatus === 'ok' && item.thumb}
                  <img src={item.thumb} alt={`thumb-${item.name}`} class="max-h-40 object-contain" />
                {:else if item.thumbStatus === 'error'}
                  <span class="text-xs text-red-500">Render error</span>
                {:else}
                  <span class="text-xs text-base-content/60">Rendering…</span>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </section>
</div>
