<script lang="ts">
  import {
    Upload,
    FolderOpen,
    Trash2,
    FileText,
    FileArchive,
    Download,
    Check,
    AlertCircle
  } from 'lucide-svelte';
  import { listen } from '@tauri-apps/api/event';
  import { open, save } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';
  import { onMount, onDestroy } from 'svelte';
  import { log, logSuccess, logError, registerFile, unregisterModule } from '$lib/stores/status.svelte';

  const MODULE = 'Compress';

  interface CompressionResult {
    output_path: string;
    original_size: number;
    compressed_size: number;
    ratio: number;
    bytes_saved: number;
    percent_saved: number;
  }

  interface EstimationResult {
    original_size: number;
    page_count: number;
    bytes_per_page: number;
    estimated_reduction: number;
    estimated_size: number;
  }

  let filePath = $state<string | null>(null);
  let fileName = $state('');
  let fileSize = $state(0);
  let estimation = $state<EstimationResult | null>(null);
  let compressionLevel = $state<'low' | 'medium' | 'high'>('medium');
  let isCompressing = $state(false);
  let result = $state<CompressionResult | null>(null);
  let unlistenDrop: (() => void) | null = null;

  onMount(async () => {
    unlistenDrop = await listen<string[]>('tauri://file-drop', async (e) => {
      const pdfs = e.payload.filter((p: string) => p.toLowerCase().endsWith('.pdf'));
      if (pdfs.length > 0) {
        await loadFile(pdfs[0]);
      }
    });
  });

  onDestroy(() => {
    if (unlistenDrop) unlistenDrop();
    unregisterModule(MODULE);
  });

  function formatSize(bytes: number): string {
    const KB = 1024;
    const MB = KB * 1024;
    const GB = MB * 1024;

    if (bytes >= GB) {
      return `${(bytes / GB).toFixed(2)} GB`;
    } else if (bytes >= MB) {
      return `${(bytes / MB).toFixed(2)} MB`;
    } else if (bytes >= KB) {
      return `${(bytes / KB).toFixed(2)} KB`;
    } else {
      return `${bytes} bytes`;
    }
  }

  async function loadFile(path: string) {
    filePath = path;
    fileName = path.split('/').pop() || path;
    result = null;
    estimation = null;

    registerFile(path, fileName, MODULE);
    log(`Loaded ${fileName}`, 'info', MODULE);

    try {
      const est = await invoke<EstimationResult>('estimate_compression', { input: path });
      estimation = est;
      fileSize = est.original_size;
      log(`File size: ${formatSize(est.original_size)}, ${est.page_count} pages`, 'info', MODULE);
    } catch (err) {
      console.error('Estimation error:', err);
      logError(`Failed to analyze file: ${err}`, MODULE);
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
    filePath = null;
    fileName = '';
    fileSize = 0;
    estimation = null;
    result = null;
    unregisterModule(MODULE);
  }

  async function handleCompress() {
    if (!filePath) return;

    const outputPath = await save({
      title: 'Save compressed PDF as',
      filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
      defaultPath: `compressed_${fileName}`,
    });

    if (!outputPath) return;

    isCompressing = true;
    result = null;
    log(`Compressing with ${compressionLevel} level...`, 'info', MODULE);

    try {
      const res = await invoke<CompressionResult>('compress_pdf', {
        input: filePath,
        output: outputPath,
        level: compressionLevel,
      });

      result = res;

      if (res.bytes_saved > 0) {
        logSuccess(
          `Compressed: ${formatSize(res.original_size)} -> ${formatSize(res.compressed_size)} (${res.percent_saved.toFixed(1)}% saved)`,
          MODULE
        );
      } else {
        log(
          `File is already optimized. Size increased by ${formatSize(Math.abs(res.bytes_saved))}`,
          'warning',
          MODULE
        );
      }
    } catch (err) {
      console.error('Compression error:', err);
      logError(`Compression failed: ${err}`, MODULE);
    }

    isCompressing = false;
  }

  const levelDescriptions = {
    low: 'Remove unused objects only. Fastest, minimal reduction.',
    medium: 'Garbage collection + stream compression. Good balance.',
    high: 'Maximum compression + optimization. Best reduction, slower.',
  };

  const canCompress = $derived(() => filePath !== null && !isCompressing);
</script>

<div class="flex-1 flex overflow-hidden">
  <!-- Main Content Area -->
  <div class="flex-1 flex flex-col overflow-hidden p-6">
    {#if !filePath}
      <!-- Empty State -->
      <div
        class="flex-1 flex flex-col items-center justify-center rounded-xl border-2 border-dashed cursor-pointer transition-colors hover:border-[var(--nord8)]"
        style="border-color: var(--nord3); background-color: var(--nord1);"
        role="button"
        tabindex="0"
        onclick={handleFilePicker}
        onkeydown={(e) => e.key === 'Enter' && handleFilePicker()}
      >
        <FileArchive size={64} class="opacity-30 mb-4" />
        <p class="text-xl opacity-60 mb-2">Compress PDF</p>
        <p class="text-sm opacity-40 mb-6">Drop a PDF file here or click to browse</p>
        <button
          class="flex items-center gap-2 px-6 py-3 rounded-lg transition-colors hover:opacity-90"
          style="background-color: var(--nord8); color: var(--nord0);"
        >
          <FolderOpen size={20} />
          <span>Select File</span>
        </button>
      </div>
    {:else}
      <!-- File Loaded State -->
      <div class="flex-1 flex flex-col gap-6">
        <!-- File Info Card -->
        <div
          class="rounded-xl p-6"
          style="background-color: var(--nord1);"
        >
          <div class="flex items-start gap-4">
            <div
              class="w-16 h-16 rounded-xl flex items-center justify-center"
              style="background-color: var(--nord2);"
            >
              <FileText size={32} style="color: var(--nord8);" />
            </div>
            <div class="flex-1">
              <h3 class="text-lg font-medium mb-1">{fileName}</h3>
              <div class="flex items-center gap-4 text-sm opacity-60">
                <span>Size: {formatSize(fileSize)}</span>
                {#if estimation}
                  <span>Pages: {estimation.page_count}</span>
                  <span>~{formatSize(estimation.bytes_per_page)}/page</span>
                {/if}
              </div>
              {#if estimation}
                <div class="mt-3 text-sm">
                  <span class="opacity-60">Estimated reduction: </span>
                  <span style="color: var(--nord14);">
                    ~{(estimation.estimated_reduction * 100).toFixed(0)}%
                  </span>
                  <span class="opacity-40 ml-2">
                    (~{formatSize(estimation.estimated_size)} after compression)
                  </span>
                </div>
              {/if}
            </div>
            <button
              onclick={removeFile}
              class="p-2 rounded hover:bg-[var(--nord2)] transition-colors"
              style="color: var(--nord11);"
              title="Remove file"
            >
              <Trash2 size={20} />
            </button>
          </div>
        </div>

        <!-- Compression Level Selector -->
        <div
          class="rounded-xl p-6"
          style="background-color: var(--nord1);"
        >
          <h4 class="text-sm opacity-60 uppercase mb-4">Compression Level</h4>
          <div class="grid grid-cols-3 gap-4">
            {#each (['low', 'medium', 'high'] as const) as level}
              <button
                onclick={() => compressionLevel = level}
                class="p-4 rounded-lg border-2 transition-all text-left hover:border-[var(--nord8)]"
                style="
                  background-color: {compressionLevel === level ? 'var(--nord2)' : 'var(--nord0)'};
                  border-color: {compressionLevel === level ? 'var(--nord8)' : 'var(--nord3)'};
                "
              >
                <div class="flex items-center gap-2 mb-2">
                  {#if compressionLevel === level}
                    <Check size={16} style="color: var(--nord8);" />
                  {/if}
                  <span class="font-medium capitalize">{level}</span>
                </div>
                <p class="text-xs opacity-60">{levelDescriptions[level]}</p>
              </button>
            {/each}
          </div>
        </div>

        <!-- Result Card -->
        {#if result}
          <div
            class="rounded-xl p-6"
            style="background-color: var(--nord1);"
          >
            <h4 class="text-sm opacity-60 uppercase mb-4">Compression Result</h4>
            <div class="grid grid-cols-2 gap-6">
              <div>
                <p class="text-xs opacity-50 mb-1">Original Size</p>
                <p class="text-2xl font-medium">{formatSize(result.original_size)}</p>
              </div>
              <div>
                <p class="text-xs opacity-50 mb-1">Compressed Size</p>
                <p class="text-2xl font-medium" style="color: var(--nord14);">
                  {formatSize(result.compressed_size)}
                </p>
              </div>
            </div>

            <div class="mt-4 flex items-center gap-4">
              {#if result.bytes_saved > 0}
                <div
                  class="flex items-center gap-2 px-4 py-2 rounded-lg"
                  style="background-color: rgba(163, 190, 140, 0.2);"
                >
                  <Check size={18} style="color: var(--nord14);" />
                  <span style="color: var(--nord14);">
                    Saved {formatSize(result.bytes_saved)} ({result.percent_saved.toFixed(1)}%)
                  </span>
                </div>
              {:else}
                <div
                  class="flex items-center gap-2 px-4 py-2 rounded-lg"
                  style="background-color: rgba(235, 203, 139, 0.2);"
                >
                  <AlertCircle size={18} style="color: var(--nord13);" />
                  <span style="color: var(--nord13);">
                    File already optimized (size increased by {formatSize(Math.abs(result.bytes_saved))})
                  </span>
                </div>
              {/if}
            </div>

            <div class="mt-4 text-xs opacity-50">
              Saved to: {result.output_path}
            </div>
          </div>
        {/if}

        <!-- Spacer -->
        <div class="flex-1"></div>
      </div>
    {/if}
  </div>

  <!-- Right Sidebar -->
  <div
    class="w-64 flex flex-col gap-4 p-4 border-l"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <!-- Action Buttons -->
    <div class="flex-1 flex flex-col gap-3">
      <button
        onclick={handleFilePicker}
        class="flex items-center justify-center gap-2 px-4 py-3 rounded-lg transition-colors hover:opacity-80"
        style="background-color: var(--nord2); border: 1px solid var(--nord3);"
      >
        <FolderOpen size={18} />
        <span class="text-sm">{filePath ? 'Change File' : 'Select File'}</span>
      </button>

      {#if filePath}
        <button
          onclick={handleCompress}
          disabled={!canCompress()}
          class="flex items-center justify-center gap-2 px-4 py-3 rounded-lg transition-colors disabled:opacity-50 hover:opacity-90"
          style="background-color: var(--nord8); color: var(--nord0);"
        >
          {#if isCompressing}
            <div class="w-4 h-4 border-2 border-[var(--nord0)] border-t-transparent rounded-full animate-spin"></div>
            <span>Compressing...</span>
          {:else}
            <FileArchive size={18} />
            <span>Compress PDF</span>
          {/if}
        </button>
      {/if}
    </div>

    <!-- Info -->
    <div class="text-xs opacity-50 p-3 rounded-lg" style="background-color: var(--nord2);">
      <p class="mb-2 font-medium">Compression Tips</p>
      <ul class="space-y-1 list-disc list-inside">
        <li>PDFs with images benefit most</li>
        <li>Text-heavy PDFs may not shrink much</li>
        <li>High level linearizes for web viewing</li>
      </ul>
    </div>
  </div>
</div>
