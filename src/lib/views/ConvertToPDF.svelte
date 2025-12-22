<script lang="ts">
  import { Upload, FolderOpen, Trash2, X, Image, FileText, HelpCircle, RotateCw, FlipHorizontal, FlipVertical } from 'lucide-svelte';
  import { dndzone } from 'svelte-dnd-action';
  import { flip } from 'svelte/animate';
  import { listen } from '@tauri-apps/api/event';
  import { open, save, confirm } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';
  import { onMount, onDestroy } from 'svelte';
  import { log, logSuccess, logError, registerFile, unregisterModule } from '$lib/stores/status.svelte';
  import { loadImageThumbnail } from '$lib/utils/thumbnails';

  interface Props {
    onOpenInViewer?: (path: string) => void;
  }

  let { onOpenInViewer }: Props = $props();

  const MODULE = 'Convert';

  interface ImageFile {
    id: string;
    name: string;
    path: string;
    thumbnail: string | null;
    isLoading: boolean;
    error: string | null;
    width?: number;
    height?: number;
    // Per-image transforms
    rotation: 0 | 90 | 180 | 270;
    flipH: boolean;
    flipV: boolean;
    orientation: 'auto' | 'portrait' | 'landscape';
  }

  // State
  let files = $state<ImageFile[]>([]);
  let isConverting = $state(false);
  let unlistenDrop: (() => void) | null = null;

  // Options
  let pageSize = $state<'a4' | 'letter' | 'legal' | 'a3' | 'a5' | 'fit'>('a4');
  let orientation = $state<'auto' | 'portrait' | 'landscape'>('auto');
  let marginMm = $state(10);

  const flipDurationMs = 200;

  const IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'tiff', 'tif', 'bmp', 'gif'];

  onMount(async () => {
    unlistenDrop = await listen<string[]>('tauri://file-drop', async (e) => {
      const images = e.payload.filter((p: string) => {
        const ext = p.split('.').pop()?.toLowerCase() || '';
        return IMAGE_EXTENSIONS.includes(ext);
      });
      if (images.length > 0) {
        await addFiles(images);
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
      const fileId = `img-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

      const newFile: ImageFile = {
        id: fileId,
        name,
        path,
        thumbnail: null,
        isLoading: true,
        error: null,
        rotation: 0,
        flipH: false,
        flipV: false,
        orientation: 'auto',
      };

      files = [...files, newFile];
      loadThumbnail(fileId, path, name);
    }
  }

  async function loadThumbnail(fileId: string, path: string, name: string) {
    try {
      const thumbnail = await loadImageThumbnail(path);

      files = files.map((f) =>
        f.id === fileId ? { ...f, thumbnail, isLoading: false } : f
      );

      registerFile(path, name, MODULE);
      log(`Added ${name}`, 'info', MODULE);
    } catch (err) {
      console.error('Error loading thumbnail:', err);
      files = files.map((f) =>
        f.id === fileId ? { ...f, isLoading: false, error: String(err) } : f
      );
      logError(`Failed to load ${name}: ${err}`, MODULE);
    }
  }

  async function handleFilePicker() {
    const selected = await open({
      multiple: true,
      filters: [{ name: 'Image Files', extensions: IMAGE_EXTENSIONS }],
    });
    if (selected && selected.length > 0) {
      await addFiles(selected as string[]);
    }
  }

  function removeFile(fileId: string) {
    files = files.filter((f) => f.id !== fileId);
  }

  function clearAllFiles() {
    files = [];
  }

  function rotateImage(fileId: string) {
    files = files.map((f) => {
      if (f.id === fileId) {
        const newRotation = ((f.rotation + 90) % 360) as 0 | 90 | 180 | 270;
        return { ...f, rotation: newRotation };
      }
      return f;
    });
  }

  function flipImageH(fileId: string) {
    files = files.map((f) =>
      f.id === fileId ? { ...f, flipH: !f.flipH } : f
    );
  }

  function flipImageV(fileId: string) {
    files = files.map((f) =>
      f.id === fileId ? { ...f, flipV: !f.flipV } : f
    );
  }

  function cycleOrientation(fileId: string) {
    const orientations: ('auto' | 'portrait' | 'landscape')[] = ['auto', 'portrait', 'landscape'];
    files = files.map((f) => {
      if (f.id === fileId) {
        const currentIdx = orientations.indexOf(f.orientation);
        const nextOrientation = orientations[(currentIdx + 1) % orientations.length];
        return { ...f, orientation: nextOrientation };
      }
      return f;
    });
  }

  function handleFilesDnd(e: CustomEvent<{ items: ImageFile[] }>) {
    files = e.detail.items;
  }

  async function handleConvert() {
    if (files.length === 0) return;

    isConverting = true;
    log('Converting images to PDF...', 'info', MODULE);

    try {
      const outputPath = await save({
        filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
        defaultPath: 'images.pdf',
      });

      if (!outputPath) {
        isConverting = false;
        return;
      }

      // Build image data with transforms
      const imageData = files.map((f) => ({
        path: f.path,
        rotation: f.rotation,
        flipH: f.flipH,
        flipV: f.flipV,
        orientation: f.orientation,
      }));

      const result = await invoke<string>('images_to_pdf', {
        images: imageData.map(d => d.path),
        output: outputPath,
        pageSize: pageSize,
        orientation: orientation,
        margin: marginMm,
        transforms: imageData.map(d => ({
          rotation: d.rotation,
          flip_h: d.flipH,
          flip_v: d.flipV,
          orientation: d.orientation,
        })),
      });

      logSuccess(`Created PDF: ${result}`, MODULE);

      // Ask user if they want to open the created PDF
      const openFile = await confirm('Would you like to open the PDF in the viewer?', {
        title: 'Conversion Complete',
        kind: 'info',
        okLabel: 'Open',
        cancelLabel: 'Close',
      });

      if (openFile && onOpenInViewer) {
        onOpenInViewer(result);
      }
    } catch (err) {
      console.error('Conversion error:', err);
      logError(`Conversion failed: ${err}`, MODULE);
    }

    isConverting = false;
  }

  const canConvert = $derived(files.length > 0 && !isConverting);
</script>

<div class="flex-1 flex overflow-hidden">
  <!-- Main Content Area -->
  <div class="flex-1 flex flex-col overflow-hidden">
    <!-- Options Toolbar -->
    <div
      class="flex items-center gap-6 px-4 py-3 border-b"
      style="background-color: var(--nord1); border-color: var(--nord3);"
    >
      <!-- Page Size -->
      <div class="flex items-center gap-2">
        <label class="text-xs opacity-60 uppercase">Page Size</label>
        <div class="relative group">
          <select
            bind:value={pageSize}
            class="px-3 py-1.5 rounded text-sm appearance-none pr-8 cursor-pointer"
            style="background-color: var(--nord2); border: 1px solid var(--nord3);"
          >
            <option value="a4">A4</option>
            <option value="letter">Letter</option>
            <option value="legal">Legal</option>
            <option value="a3">A3</option>
            <option value="a5">A5</option>
            <option value="fit">Fit to Image</option>
          </select>
          <HelpCircle size={12} class="absolute right-2 top-1/2 -translate-y-1/2 opacity-40 pointer-events-none" />
        </div>
      </div>

      <!-- Orientation -->
      <div class="flex items-center gap-2">
        <label class="text-xs opacity-60 uppercase">Orientation</label>
        <div class="flex gap-1">
          <button
            onclick={() => orientation = 'auto'}
            class="px-3 py-1.5 rounded text-xs transition-colors"
            style="background-color: {orientation === 'auto' ? 'var(--nord8)' : 'var(--nord2)'};
                   color: {orientation === 'auto' ? 'var(--nord0)' : 'var(--nord4)'};
                   border: 1px solid var(--nord3);"
          >
            Auto
          </button>
          <button
            onclick={() => orientation = 'portrait'}
            class="px-3 py-1.5 rounded text-xs transition-colors"
            style="background-color: {orientation === 'portrait' ? 'var(--nord8)' : 'var(--nord2)'};
                   color: {orientation === 'portrait' ? 'var(--nord0)' : 'var(--nord4)'};
                   border: 1px solid var(--nord3);"
          >
            Portrait
          </button>
          <button
            onclick={() => orientation = 'landscape'}
            class="px-3 py-1.5 rounded text-xs transition-colors"
            style="background-color: {orientation === 'landscape' ? 'var(--nord8)' : 'var(--nord2)'};
                   color: {orientation === 'landscape' ? 'var(--nord0)' : 'var(--nord4)'};
                   border: 1px solid var(--nord3);"
          >
            Landscape
          </button>
        </div>
      </div>

      <!-- Margin -->
      <div class="flex items-center gap-2">
        <label class="text-xs opacity-60 uppercase">Margin</label>
        <div class="flex items-center gap-1">
          <input
            type="number"
            bind:value={marginMm}
            min="0"
            max="50"
            class="w-16 px-2 py-1.5 rounded text-sm text-center"
            style="background-color: var(--nord2); border: 1px solid var(--nord3);"
          />
          <span class="text-xs opacity-60">mm</span>
        </div>
      </div>

      <!-- File count -->
      <span class="text-xs opacity-60 ml-auto">
        {files.length} image{files.length !== 1 ? 's' : ''} selected
      </span>
    </div>

    <!-- Content Area -->
    <div class="flex-1 overflow-auto p-4">
      {#if files.length === 0}
        <!-- Empty State -->
        <div
          class="h-full flex flex-col items-center justify-center rounded-lg"
          style="background-color: var(--nord1);"
        >
          <Image size={48} class="opacity-40 mb-4" />
          <p class="text-lg opacity-60 mb-2">No images added</p>
          <p class="text-sm opacity-40 mb-4">Drag & drop images or use the panel on the right</p>
          <p class="text-xs opacity-30">Supported: JPG, PNG, WEBP, TIFF, BMP, GIF</p>
        </div>
      {:else}
        <!-- Image Grid with Drag & Drop -->
        <div
          class="rounded-lg p-4 min-h-full"
          style="background-color: var(--nord1);"
        >
          <div class="flex items-center justify-between mb-4">
            <p class="text-xs opacity-60">Drag to reorder. Images will appear in this order in the PDF.</p>
            <button
              onclick={clearAllFiles}
              class="text-xs px-2 py-1 rounded hover:bg-[var(--nord2)] transition-colors"
              style="color: var(--nord11);"
            >
              Clear All
            </button>
          </div>

          <div
            class="grid grid-cols-5 gap-4"
            use:dndzone={{ items: files, flipDurationMs, type: 'images' }}
            onconsider={handleFilesDnd}
            onfinalize={handleFilesDnd}
          >
            {#each files as file, index (file.id)}
              <div
                class="relative group cursor-move"
                animate:flip={{ duration: flipDurationMs }}
              >
                <!-- Order Badge -->
                <div
                  class="absolute -top-2 -left-2 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold z-10"
                  style="background-color: var(--nord8); color: var(--nord0);"
                >
                  {index + 1}
                </div>

                <!-- Thumbnail -->
                <div
                  class="aspect-square rounded overflow-hidden flex items-center justify-center"
                  style="background-color: var(--nord2);"
                >
                  {#if file.isLoading}
                    <div class="flex flex-col items-center gap-2">
                      <div class="w-5 h-5 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin"></div>
                    </div>
                  {:else if file.thumbnail}
                    <img
                      src={file.thumbnail}
                      alt={file.name}
                      class="max-w-full max-h-full object-contain transition-transform"
                      style="transform: rotate({file.rotation}deg) scaleX({file.flipH ? -1 : 1}) scaleY({file.flipV ? -1 : 1});"
                    />
                  {:else if file.error}
                    <span class="text-xs text-center px-2" style="color: var(--nord11);">Error</span>
                  {:else}
                    <Image size={32} class="opacity-40" />
                  {/if}
                </div>

                <!-- Remove Button -->
                <button
                  onclick={() => removeFile(file.id)}
                  class="absolute top-1 right-1 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                  style="background-color: var(--nord11);"
                  title="Remove"
                >
                  <X size={14} style="color: var(--nord6);" />
                </button>

                <!-- Transform Controls -->
                <div
                  class="flex justify-center gap-1 py-1 mt-1 opacity-0 group-hover:opacity-100 transition-opacity rounded"
                  style="background-color: var(--nord2);"
                >
                  <button
                    onclick={(e) => { e.stopPropagation(); rotateImage(file.id); }}
                    class="p-1.5 rounded hover:bg-[var(--nord3)] transition-colors"
                    title="Rotate 90°"
                  >
                    <RotateCw size={14} style="color: var(--nord4);" />
                  </button>
                  <button
                    onclick={(e) => { e.stopPropagation(); flipImageH(file.id); }}
                    class="p-1.5 rounded hover:bg-[var(--nord3)] transition-colors"
                    style="background-color: {file.flipH ? 'var(--nord10)' : 'transparent'};"
                    title="Flip Horizontal"
                  >
                    <FlipHorizontal size={14} style="color: var(--nord4);" />
                  </button>
                  <button
                    onclick={(e) => { e.stopPropagation(); flipImageV(file.id); }}
                    class="p-1.5 rounded hover:bg-[var(--nord3)] transition-colors"
                    style="background-color: {file.flipV ? 'var(--nord10)' : 'transparent'};"
                    title="Flip Vertical"
                  >
                    <FlipVertical size={14} style="color: var(--nord4);" />
                  </button>
                  <button
                    onclick={(e) => { e.stopPropagation(); cycleOrientation(file.id); }}
                    class="px-1.5 py-1 rounded hover:bg-[var(--nord3)] transition-all text-[10px] font-bold min-w-[20px] orientation-btn"
                    style="color: var(--nord4); background-color: {file.orientation !== 'auto' ? 'var(--nord10)' : 'transparent'};"
                    title="Page orientation (click to cycle)"
                  >
                    <span class="orientation-short">{file.orientation === 'auto' ? 'A' : file.orientation === 'portrait' ? 'P' : 'L'}</span>
                    <span class="orientation-full">{file.orientation === 'auto' ? 'Auto' : file.orientation === 'portrait' ? 'Portrait' : 'Landscape'}</span>
                  </button>
                </div>

                <!-- Filename -->
                <p
                  class="text-xs text-center mt-1 truncate px-1"
                  title={file.name}
                >
                  {file.name}
                </p>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  </div>

  <!-- Right Sidebar -->
  <div
    class="w-[15%] min-w-[180px] flex flex-col gap-4 p-4 border-l"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <!-- Drop Area or File Info -->
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
        <p class="text-sm text-center opacity-60">Drop images here or click to browse</p>
      </div>
    {:else}
      <div class="flex-1 overflow-y-auto">
        <h4 class="text-xs opacity-60 mb-3 uppercase">Images ({files.length})</h4>
        {#each files as file, index}
          <div
            class="mb-2 p-2 rounded group hover:bg-[var(--nord2)] transition-colors flex items-center gap-2"
            title={file.path}
          >
            <span class="text-xs font-bold opacity-60 w-4">{index + 1}</span>
            <Image size={14} class="flex-shrink-0 opacity-60" />
            <p class="text-xs truncate flex-1">{file.name}</p>
            <button
              onclick={() => removeFile(file.id)}
              class="opacity-0 group-hover:opacity-100 transition-opacity p-1 flex-shrink-0"
              style="color: var(--nord11);"
              title="Remove"
            >
              <Trash2 size={12} />
            </button>
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
      <span class="text-sm">{files.length > 0 ? 'Add More' : 'Add Images'}</span>
    </button>

    <!-- Convert Button -->
    <button
      onclick={handleConvert}
      disabled={!canConvert}
      class="px-4 py-3 rounded transition-colors disabled:opacity-50 hover:opacity-90 flex items-center justify-center gap-2"
      style="background-color: var(--nord14); color: var(--nord0);"
    >
      {#if isConverting}
        <div class="w-4 h-4 border-2 border-[var(--nord0)] border-t-transparent rounded-full animate-spin"></div>
        <span>Converting...</span>
      {:else}
        <FileText size={18} />
        <span>Convert to PDF</span>
      {/if}
    </button>
  </div>
</div>

<style>
  /* Orientation button hover effect */
  .orientation-btn .orientation-full {
    display: none;
  }
  .orientation-btn .orientation-short {
    display: inline;
  }
  .orientation-btn:hover .orientation-full {
    display: inline;
  }
  .orientation-btn:hover .orientation-short {
    display: none;
  }
</style>
