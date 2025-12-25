<script lang="ts">
  import { Droplet, Type, Image, Upload, X, Check, FileText, Download, RotateCcw } from 'lucide-svelte';
  import { open, save } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';
  import { listen } from '@tauri-apps/api/event';
  import { onMount, onDestroy } from 'svelte';

  interface Props {
    onNavigate?: (page: string) => void;
  }

  let { onNavigate }: Props = $props();

  // State
  let selectedPdf = $state<string | null>(null);
  let selectedPdfName = $state('');
  let watermarkType = $state<'text' | 'image'>('text');

  // Text watermark options
  let watermarkText = $state('CONFIDENTIAL');
  let fontSize = $state(48);
  let fontColor = $state('#808080');
  let textOpacity = $state(0.3);
  let textRotation = $state(-45);

  // Image watermark options
  let imagePath = $state<string | null>(null);
  let imageOpacity = $state(0.3);
  let imageScale = $state(0.5);
  let imageRotation = $state(0);

  // Common options
  let position = $state<'center' | 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right' | 'tile'>('center');
  let pages = $state('all');
  let layer = $state<'under' | 'over'>('under');

  // Processing state
  let isProcessing = $state(false);
  let result = $state<{ success: boolean; message: string } | null>(null);

  // Drag and drop listener
  let unlistenDrop: (() => void) | null = null;

  const positions = [
    { value: 'center', label: 'Center' },
    { value: 'top-left', label: 'Top Left' },
    { value: 'top-right', label: 'Top Right' },
    { value: 'bottom-left', label: 'Bottom Left' },
    { value: 'bottom-right', label: 'Bottom Right' },
    { value: 'tile', label: 'Tile (Repeat)' },
  ];

  const presetTexts = [
    'CONFIDENTIAL',
    'DRAFT',
    'COPY',
    'SAMPLE',
    'DO NOT COPY',
    'APPROVED',
  ];

  onMount(async () => {
    unlistenDrop = await listen<{ paths: string[] }>('tauri://drag-drop', (event) => {
      const paths = event.payload.paths;
      if (paths.length > 0 && paths[0].toLowerCase().endsWith('.pdf')) {
        selectPdfFile(paths[0]);
      }
    });
  });

  onDestroy(() => {
    unlistenDrop?.();
  });

  async function selectPdf() {
    const selected = await open({
      multiple: false,
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });
    if (selected) {
      selectPdfFile(selected as string);
    }
  }

  function selectPdfFile(path: string) {
    selectedPdf = path;
    selectedPdfName = path.split('/').pop() || path;
    result = null;
  }

  async function selectImage() {
    const selected = await open({
      multiple: false,
      filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'webp'] }],
    });
    if (selected) {
      imagePath = selected as string;
    }
  }

  function hexToRgb(hex: string): number[] {
    const r = parseInt(hex.slice(1, 3), 16) / 255;
    const g = parseInt(hex.slice(3, 5), 16) / 255;
    const b = parseInt(hex.slice(5, 7), 16) / 255;
    return [r, g, b];
  }

  async function applyWatermark() {
    if (!selectedPdf) return;

    const outputPath = await save({
      defaultPath: selectedPdfName.replace('.pdf', '_watermarked.pdf'),
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });

    if (!outputPath) return;

    isProcessing = true;
    result = null;

    try {
      if (watermarkType === 'text') {
        const res = await invoke<{ success: boolean; message: string }>('pdf_watermark_text', {
          input: selectedPdf,
          output: outputPath,
          text: watermarkText,
          options: {
            font_size: fontSize,
            font_color: hexToRgb(fontColor),
            opacity: textOpacity,
            rotation: textRotation,
            position,
            pages,
            layer,
          },
        });
        result = res;
      } else {
        if (!imagePath) {
          result = { success: false, message: 'Please select an image first' };
          isProcessing = false;
          return;
        }

        const res = await invoke<{ success: boolean; message: string }>('pdf_watermark_image', {
          input: selectedPdf,
          output: outputPath,
          imagePath,
          options: {
            opacity: imageOpacity,
            scale: imageScale,
            rotation: imageRotation,
            position,
            pages,
            layer,
          },
        });
        result = res;
      }
    } catch (err) {
      result = { success: false, message: String(err) };
    }

    isProcessing = false;
  }

  function clearSelection() {
    selectedPdf = null;
    selectedPdfName = '';
    result = null;
  }
</script>

<div class="flex-1 flex flex-col overflow-hidden">
  <!-- Header -->
  <header
    class="flex items-center justify-between px-6 py-4 border-b"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <div class="flex items-center gap-3">
      <div
        class="w-10 h-10 rounded-lg flex items-center justify-center"
        style="background-color: var(--nord10);"
      >
        <Droplet size={20} style="color: var(--nord6);" />
      </div>
      <div>
        <h1 class="text-lg font-semibold" style="color: var(--nord6);">Watermark</h1>
        <p class="text-xs opacity-60">Add text or image watermarks to PDF documents</p>
      </div>
    </div>
  </header>

  <!-- Content -->
  <div class="flex-1 overflow-auto p-6">
    <div class="max-w-3xl mx-auto">
      <!-- File Selection -->
      <section class="mb-6">
        {#if !selectedPdf}
          <button
            onclick={selectPdf}
            class="w-full h-32 rounded-xl flex flex-col items-center justify-center gap-2 transition-colors hover:bg-[var(--nord2)]"
            style="background-color: var(--nord1); border: 2px dashed var(--nord3);"
          >
            <Upload size={32} style="color: var(--nord4);" />
            <p class="text-sm opacity-60">Click to select PDF or drag and drop</p>
          </button>
        {:else}
          <div
            class="flex items-center gap-3 p-4 rounded-xl"
            style="background-color: var(--nord1); border: 1px solid var(--nord3);"
          >
            <FileText size={24} style="color: var(--nord8);" />
            <div class="flex-1 min-w-0">
              <p class="font-medium truncate" style="color: var(--nord5);">{selectedPdfName}</p>
            </div>
            <button
              onclick={clearSelection}
              class="p-2 rounded hover:bg-[var(--nord3)]"
            >
              <X size={16} style="color: var(--nord4);" />
            </button>
          </div>
        {/if}
      </section>

      {#if selectedPdf}
        <!-- Watermark Type -->
        <section class="mb-6">
          <h2 class="text-sm font-medium mb-3 opacity-60 uppercase tracking-wider">Watermark Type</h2>
          <div class="flex gap-2">
            <button
              onclick={() => watermarkType = 'text'}
              class="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg transition-colors"
              style="background-color: {watermarkType === 'text' ? 'var(--nord10)' : 'var(--nord1)'};
                     color: {watermarkType === 'text' ? 'var(--nord6)' : 'var(--nord4)'};"
            >
              <Type size={18} />
              <span class="font-medium">Text</span>
            </button>
            <button
              onclick={() => watermarkType = 'image'}
              class="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg transition-colors"
              style="background-color: {watermarkType === 'image' ? 'var(--nord10)' : 'var(--nord1)'};
                     color: {watermarkType === 'image' ? 'var(--nord6)' : 'var(--nord4)'};"
            >
              <Image size={18} />
              <span class="font-medium">Image</span>
            </button>
          </div>
        </section>

        <!-- Watermark Options -->
        <section
          class="mb-6 rounded-xl p-5"
          style="background-color: var(--nord1); border: 1px solid var(--nord3);"
        >
          {#if watermarkType === 'text'}
            <!-- Text Options -->
            <div class="space-y-4">
              <!-- Text Input -->
              <div>
                <label class="block text-xs opacity-60 uppercase mb-2">Text</label>
                <input
                  type="text"
                  bind:value={watermarkText}
                  class="w-full px-3 py-2 rounded-lg text-sm"
                  style="background-color: var(--nord2); color: var(--nord5); border: 1px solid var(--nord3);"
                  placeholder="Enter watermark text..."
                />
                <div class="flex flex-wrap gap-1 mt-2">
                  {#each presetTexts as preset}
                    <button
                      onclick={() => watermarkText = preset}
                      class="px-2 py-1 rounded text-xs transition-colors hover:bg-[var(--nord3)]"
                      style="background-color: {watermarkText === preset ? 'var(--nord10)' : 'var(--nord2)'};
                             color: {watermarkText === preset ? 'var(--nord6)' : 'var(--nord4)'};"
                    >
                      {preset}
                    </button>
                  {/each}
                </div>
              </div>

              <!-- Font Size & Color -->
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs opacity-60 uppercase mb-2">Font Size: {fontSize}pt</label>
                  <input
                    type="range"
                    min="12"
                    max="120"
                    bind:value={fontSize}
                    class="w-full"
                  />
                </div>
                <div>
                  <label class="block text-xs opacity-60 uppercase mb-2">Color</label>
                  <div class="flex items-center gap-2">
                    <input
                      type="color"
                      bind:value={fontColor}
                      class="w-10 h-10 rounded cursor-pointer"
                    />
                    <span class="text-sm opacity-60">{fontColor}</span>
                  </div>
                </div>
              </div>

              <!-- Opacity & Rotation -->
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs opacity-60 uppercase mb-2">Opacity: {Math.round(textOpacity * 100)}%</label>
                  <input
                    type="range"
                    min="0.1"
                    max="1"
                    step="0.1"
                    bind:value={textOpacity}
                    class="w-full"
                  />
                </div>
                <div>
                  <label class="block text-xs opacity-60 uppercase mb-2">Rotation: {textRotation}°</label>
                  <input
                    type="range"
                    min="-90"
                    max="90"
                    step="15"
                    bind:value={textRotation}
                    class="w-full"
                  />
                </div>
              </div>
            </div>
          {:else}
            <!-- Image Options -->
            <div class="space-y-4">
              <!-- Image Selection -->
              <div>
                <label class="block text-xs opacity-60 uppercase mb-2">Watermark Image</label>
                {#if !imagePath}
                  <button
                    onclick={selectImage}
                    class="w-full h-24 rounded-lg flex flex-col items-center justify-center gap-2 transition-colors hover:bg-[var(--nord2)]"
                    style="background-color: var(--nord0); border: 2px dashed var(--nord3);"
                  >
                    <Image size={24} style="color: var(--nord4);" />
                    <p class="text-xs opacity-60">Click to select image (PNG, JPG)</p>
                  </button>
                {:else}
                  <div
                    class="flex items-center gap-3 p-3 rounded-lg"
                    style="background-color: var(--nord2);"
                  >
                    <Image size={20} style="color: var(--nord8);" />
                    <span class="flex-1 text-sm truncate" style="color: var(--nord5);">
                      {imagePath.split('/').pop()}
                    </span>
                    <button
                      onclick={() => imagePath = null}
                      class="p-1 rounded hover:bg-[var(--nord3)]"
                    >
                      <X size={14} style="color: var(--nord4);" />
                    </button>
                  </div>
                {/if}
              </div>

              <!-- Scale & Opacity -->
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs opacity-60 uppercase mb-2">Scale: {Math.round(imageScale * 100)}%</label>
                  <input
                    type="range"
                    min="0.1"
                    max="1"
                    step="0.1"
                    bind:value={imageScale}
                    class="w-full"
                  />
                </div>
                <div>
                  <label class="block text-xs opacity-60 uppercase mb-2">Opacity: {Math.round(imageOpacity * 100)}%</label>
                  <input
                    type="range"
                    min="0.1"
                    max="1"
                    step="0.1"
                    bind:value={imageOpacity}
                    class="w-full"
                  />
                </div>
              </div>

              <!-- Rotation -->
              <div>
                <label class="block text-xs opacity-60 uppercase mb-2">Rotation: {imageRotation}°</label>
                <input
                  type="range"
                  min="-180"
                  max="180"
                  step="15"
                  bind:value={imageRotation}
                  class="w-full"
                />
              </div>
            </div>
          {/if}
        </section>

        <!-- Common Options -->
        <section
          class="mb-6 rounded-xl p-5"
          style="background-color: var(--nord1); border: 1px solid var(--nord3);"
        >
          <h3 class="text-sm font-medium mb-4" style="color: var(--nord8);">Placement</h3>

          <div class="space-y-4">
            <!-- Position -->
            <div>
              <label class="block text-xs opacity-60 uppercase mb-2">Position</label>
              <div class="grid grid-cols-3 gap-2">
                {#each positions as pos}
                  <button
                    onclick={() => position = pos.value as typeof position}
                    class="px-3 py-2 rounded text-xs transition-colors"
                    style="background-color: {position === pos.value ? 'var(--nord10)' : 'var(--nord2)'};
                           color: {position === pos.value ? 'var(--nord6)' : 'var(--nord4)'};"
                  >
                    {pos.label}
                  </button>
                {/each}
              </div>
            </div>

            <!-- Pages -->
            <div>
              <label class="block text-xs opacity-60 uppercase mb-2">Pages</label>
              <div class="flex gap-2">
                <button
                  onclick={() => pages = 'all'}
                  class="px-4 py-2 rounded text-sm transition-colors"
                  style="background-color: {pages === 'all' ? 'var(--nord10)' : 'var(--nord2)'};
                         color: {pages === 'all' ? 'var(--nord6)' : 'var(--nord4)'};"
                >
                  All Pages
                </button>
                <input
                  type="text"
                  bind:value={pages}
                  placeholder="e.g., 1-3, 5, 7"
                  class="flex-1 px-3 py-2 rounded text-sm"
                  style="background-color: var(--nord2); color: var(--nord5); border: 1px solid var(--nord3);"
                />
              </div>
            </div>

            <!-- Layer -->
            <div>
              <label class="block text-xs opacity-60 uppercase mb-2">Layer</label>
              <div class="flex gap-2">
                <button
                  onclick={() => layer = 'under'}
                  class="flex-1 px-4 py-2 rounded text-sm transition-colors"
                  style="background-color: {layer === 'under' ? 'var(--nord10)' : 'var(--nord2)'};
                         color: {layer === 'under' ? 'var(--nord6)' : 'var(--nord4)'};"
                >
                  Under Content
                </button>
                <button
                  onclick={() => layer = 'over'}
                  class="flex-1 px-4 py-2 rounded text-sm transition-colors"
                  style="background-color: {layer === 'over' ? 'var(--nord10)' : 'var(--nord2)'};
                         color: {layer === 'over' ? 'var(--nord6)' : 'var(--nord4)'};"
                >
                  Over Content
                </button>
              </div>
            </div>
          </div>
        </section>

        <!-- Apply Button -->
        <button
          onclick={applyWatermark}
          disabled={isProcessing || (watermarkType === 'image' && !imagePath)}
          class="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-medium transition-all disabled:opacity-50"
          style="background-color: var(--nord10); color: var(--nord6);"
        >
          {#if isProcessing}
            <div class="w-5 h-5 border-2 border-t-transparent rounded-full animate-spin" style="border-color: var(--nord6);"></div>
            Processing...
          {:else}
            <Download size={18} />
            Apply Watermark & Save
          {/if}
        </button>

        <!-- Result -->
        {#if result}
          <div
            class="mt-4 p-4 rounded-lg flex items-center gap-3"
            style="background-color: {result.success ? 'rgba(163, 190, 140, 0.1)' : 'rgba(191, 97, 106, 0.1)'};
                   border: 1px solid {result.success ? 'var(--nord14)' : 'var(--nord11)'};"
          >
            {#if result.success}
              <Check size={20} style="color: var(--nord14);" />
            {:else}
              <X size={20} style="color: var(--nord11);" />
            {/if}
            <span style="color: {result.success ? 'var(--nord14)' : 'var(--nord11)'};">
              {result.message}
            </span>
          </div>
        {/if}
      {/if}
    </div>
  </div>
</div>
