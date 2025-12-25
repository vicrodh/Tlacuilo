<script lang="ts">
  import { PenTool, Upload, ShieldCheck, Image, Trash2, Plus, FileText, Download, X, Check, Edit2, Type } from 'lucide-svelte';
  import { open, save } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';
  import { listen } from '@tauri-apps/api/event';
  import { onMount, onDestroy } from 'svelte';
  import SignatureCanvas from '$lib/components/SignatureCanvas.svelte';
  import {
    getSignaturesStore,
    addSignature,
    addInitial,
    removeSignature,
    renameSignature,
    type SavedSignature,
    type SignatureCategory
  } from '$lib/stores/signatures.svelte';
  import { log, logSuccess, logError, registerFile, unregisterModule } from '$lib/stores/status.svelte';

  const MODULE = 'Signatures';

  interface Props {
    onNavigate?: (page: string) => void;
  }

  let { onNavigate }: Props = $props();

  const signaturesStore = getSignaturesStore();

  // State
  let activeTab = $state<'signatures' | 'initials'>('signatures');
  let activeSection = $state<'draw' | 'upload' | 'certificate' | null>(null);
  let selectedSignature = $state<SavedSignature | null>(null);
  let editingName = $state<string | null>(null);
  let newName = $state('');

  // File selection for applying signature
  let selectedPdf = $state<string | null>(null);
  let selectedPdfName = $state('');
  let isApplying = $state(false);
  let applyResult = $state<{ success: boolean; message: string } | null>(null);

  // Canvas ref
  let canvasComponent: SignatureCanvas;
  let initialsCanvasComponent: SignatureCanvas;

  // Drag and drop listener
  let unlistenDrop: (() => void) | null = null;

  const signatureOptions = [
    {
      id: 'draw',
      label: 'Draw Signature',
      description: 'Draw your signature using mouse or touchpad',
      icon: PenTool,
      status: 'ready',
    },
    {
      id: 'upload',
      label: 'Upload Image',
      description: 'Upload an image of your signature',
      icon: Upload,
      status: 'ready',
    },
    {
      id: 'certificate',
      label: 'Digital Certificate',
      description: 'Sign with a PKCS#7 certificate (PAdES)',
      icon: ShieldCheck,
      status: 'future',
    },
  ] as const;

  onMount(async () => {
    unlistenDrop = await listen<string[]>('tauri://file-drop', async (e) => {
      const files = e.payload;
      // Check for PDFs
      const pdfs = files.filter((p: string) => p.toLowerCase().endsWith('.pdf'));
      if (pdfs.length > 0) {
        selectedPdf = pdfs[0];
        selectedPdfName = pdfs[0].split('/').pop() || pdfs[0];
        registerFile(MODULE, pdfs[0]);
        log(MODULE, `Selected: ${selectedPdfName}`);
      }
      // Check for images (for signature upload)
      const images = files.filter((p: string) =>
        /\.(png|jpg|jpeg|webp)$/i.test(p)
      );
      if (images.length > 0 && activeSection === 'upload') {
        await handleImageUpload(images[0]);
      }
    });
  });

  onDestroy(() => {
    if (unlistenDrop) unlistenDrop();
    unregisterModule(MODULE);
  });

  function handleOptionClick(optionId: string) {
    if (optionId === 'certificate') return; // Future feature
    activeSection = optionId as typeof activeSection;
  }

  async function handleSaveDrawnSignature(dataUrl: string) {
    try {
      const sig = await addSignature(dataUrl, '', 'freehand', undefined, undefined, 'signature');
      logSuccess(MODULE, `Signature saved: ${sig.name}`);
      selectedSignature = sig;
      canvasComponent?.clearCanvas();
    } catch (err) {
      logError(MODULE, `Failed to save signature: ${err}`);
    }
  }

  async function handleSaveDrawnInitial(dataUrl: string) {
    try {
      const sig = await addInitial(dataUrl, '', 'freehand');
      logSuccess(MODULE, `Initial saved: ${sig.name}`);
      selectedSignature = sig;
      initialsCanvasComponent?.clearCanvas();
    } catch (err) {
      logError(MODULE, `Failed to save initial: ${err}`);
    }
  }

  async function handleImageUpload(path?: string, category: SignatureCategory = 'signature') {
    try {
      let imagePath = path;
      if (!imagePath) {
        const selected = await open({
          multiple: false,
          filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'webp'] }],
        });
        if (!selected) return;
        imagePath = selected as string;
      }

      // Read the image and convert to data URL
      const response = await fetch(`file://${imagePath}`);
      const blob = await response.blob();
      const dataUrl = await blobToDataUrl(blob);

      const label = category === 'initial' ? 'Initial' : 'Signature';
      const sig = category === 'initial'
        ? await addInitial(dataUrl, imagePath.split('/').pop() || 'Uploaded', 'image')
        : await addSignature(dataUrl, imagePath.split('/').pop() || 'Uploaded', 'image', undefined, undefined, 'signature');
      logSuccess(MODULE, `${label} uploaded: ${sig.name}`);
      selectedSignature = sig;
    } catch (err) {
      const label = category === 'initial' ? 'initial' : 'signature';
      logError(MODULE, `Failed to upload ${label}: ${err}`);
    }
  }

  function blobToDataUrl(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  async function handleDeleteSignature(sig: SavedSignature) {
    try {
      await removeSignature(sig.id);
      if (selectedSignature?.id === sig.id) {
        selectedSignature = null;
      }
      log(MODULE, `Deleted: ${sig.name}`);
    } catch (err) {
      logError(MODULE, `Failed to delete: ${err}`);
    }
  }

  async function handleRenameSignature(sig: SavedSignature) {
    if (!newName.trim()) return;
    try {
      await renameSignature(sig.id, newName.trim());
      editingName = null;
      newName = '';
    } catch (err) {
      logError(MODULE, `Failed to rename: ${err}`);
    }
  }

  async function selectPdf() {
    const selected = await open({
      multiple: false,
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });
    if (selected) {
      selectedPdf = selected as string;
      selectedPdfName = (selected as string).split('/').pop() || '';
      registerFile(MODULE, selectedPdf);
      log(MODULE, `Selected: ${selectedPdfName}`);
    }
  }

  async function applySignatureToPdf() {
    if (!selectedPdf || !selectedSignature) return;

    const defaultName = selectedPdfName.replace('.pdf', '-signed.pdf');
    const savePath = await save({
      defaultPath: defaultName,
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });

    if (!savePath) return;

    isApplying = true;
    applyResult = null;

    try {
      log(MODULE, 'Applying signature...');

      const result = await invoke<{
        success: boolean;
        message: string;
        warning?: string;
      }>('apply_graphical_signature', {
        input: selectedPdf,
        output: savePath,
        imageB64: selectedSignature.dataUrl,
        page: 0, // Last page would need document info
        x: 400, // Position from left
        y: 50,  // Position from bottom
        width: 150,
        fit: 'contain',
      });

      applyResult = result;

      if (result.success) {
        logSuccess(MODULE, result.message);
        if (result.warning) {
          log(MODULE, `Note: ${result.warning}`);
        }
      } else {
        logError(MODULE, result.message);
      }
    } catch (err) {
      logError(MODULE, `Failed to apply signature: ${err}`);
      applyResult = { success: false, message: String(err) };
    } finally {
      isApplying = false;
    }
  }

  function clearPdf() {
    selectedPdf = null;
    selectedPdfName = '';
    applyResult = null;
    unregisterModule(MODULE);
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
        <PenTool size={20} style="color: var(--nord6);" />
      </div>
      <div>
        <h1 class="text-lg font-semibold" style="color: var(--nord6);">Signatures & Initials</h1>
        <p class="text-xs opacity-60">Add graphical signatures and initials to PDF documents</p>
      </div>
    </div>

    <!-- Tab Selector -->
    <div class="flex rounded-lg overflow-hidden" style="background-color: var(--nord0);">
      <button
        onclick={() => { activeTab = 'signatures'; activeSection = null; }}
        class="px-4 py-2 text-sm font-medium transition-colors flex items-center gap-2"
        style="background-color: {activeTab === 'signatures' ? 'var(--nord10)' : 'transparent'};
               color: {activeTab === 'signatures' ? 'var(--nord6)' : 'var(--nord4)'};"
      >
        <PenTool size={14} />
        Signatures ({signaturesStore.signatureCount})
      </button>
      <button
        onclick={() => { activeTab = 'initials'; activeSection = null; }}
        class="px-4 py-2 text-sm font-medium transition-colors flex items-center gap-2"
        style="background-color: {activeTab === 'initials' ? 'var(--nord10)' : 'transparent'};
               color: {activeTab === 'initials' ? 'var(--nord6)' : 'var(--nord4)'};"
      >
        <Type size={14} />
        Initials ({signaturesStore.initialCount})
      </button>
    </div>
  </header>

  <!-- Content -->
  <div class="flex-1 overflow-auto p-6">
    <div class="max-w-4xl mx-auto">
      {#if activeTab === 'signatures'}
      <!-- SIGNATURES TAB -->
      <!-- Signature Options Grid -->
      <section class="mb-8">
        <h2 class="text-sm font-medium mb-4 opacity-60 uppercase tracking-wider">Sign Methods</h2>
        <div class="grid grid-cols-3 gap-4">
          {#each signatureOptions as option}
            <button
              onclick={() => handleOptionClick(option.id)}
              class="flex flex-col items-center gap-3 p-6 rounded-xl transition-all hover:scale-[1.02] active:scale-[0.98] relative"
              style="background-color: {activeSection === option.id ? 'var(--nord2)' : 'var(--nord1)'};
                     border: 1px solid {activeSection === option.id ? 'var(--nord8)' : 'var(--nord3)'};"
              disabled={option.status === 'future'}
            >
              {#if option.status === 'future'}
                <span
                  class="absolute top-2 right-2 text-[10px] px-2 py-0.5 rounded-full"
                  style="background-color: var(--nord13); color: var(--nord0);"
                >
                  Future
                </span>
              {/if}
              <div
                class="w-12 h-12 rounded-xl flex items-center justify-center"
                style="background-color: var(--nord2);"
              >
                <option.icon size={24} style="color: var(--nord8);" />
              </div>
              <div class="text-center">
                <h3 class="font-medium mb-1" style="color: var(--nord6);">{option.label}</h3>
                <p class="text-xs opacity-50">{option.description}</p>
              </div>
            </button>
          {/each}
        </div>
      </section>

      <!-- Active Section Content -->
      {#if activeSection === 'draw'}
        <section
          class="rounded-xl p-6 mb-8"
          style="background-color: var(--nord1); border: 1px solid var(--nord3);"
        >
          <h3 class="font-medium mb-4" style="color: var(--nord8);">Draw Your Signature</h3>
          <SignatureCanvas
            bind:this={canvasComponent}
            width={600}
            height={200}
            strokeColor="#2E3440"
            strokeWidth={2.5}
            onSave={handleSaveDrawnSignature}
          />
          <p class="text-xs opacity-40 mt-3">
            Use your mouse, touchpad, or stylus to draw. Click Save to add to your library.
          </p>
        </section>
      {:else if activeSection === 'upload'}
        <section
          class="rounded-xl p-6 mb-8"
          style="background-color: var(--nord1); border: 1px solid var(--nord3);"
        >
          <h3 class="font-medium mb-4" style="color: var(--nord8);">Upload Signature Image</h3>
          <button
            onclick={() => handleImageUpload()}
            class="w-full h-32 rounded-lg flex flex-col items-center justify-center gap-2 transition-colors hover:bg-[var(--nord2)]"
            style="background-color: var(--nord0); border: 2px dashed var(--nord3);"
          >
            <Upload size={32} style="color: var(--nord4);" />
            <p class="text-sm opacity-60">Click to upload or drag and drop</p>
            <p class="text-xs opacity-40">PNG, JPG, or WEBP with transparent background recommended</p>
          </button>
        </section>
      {:else if activeSection === 'certificate'}
        <section
          class="rounded-xl p-6 mb-8"
          style="background-color: var(--nord1); border: 1px solid var(--nord3);"
        >
          <h3 class="font-medium mb-4" style="color: var(--nord8);">Digital Certificate</h3>
          <p class="text-sm opacity-50">
            PAdES digital signatures will be available in a future release.
          </p>
        </section>
      {/if}

      <!-- Signature Library -->
      <section class="mb-8">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-medium opacity-60 uppercase tracking-wider">
            Saved Signatures ({signaturesStore.count})
          </h2>
        </div>

        <div
          class="rounded-xl p-4"
          style="background-color: var(--nord1); border: 1px solid var(--nord3);"
        >
          {#if signaturesStore.signatures.length === 0}
            <div class="py-8 text-center">
              <Image size={32} class="mx-auto mb-3 opacity-20" />
              <p class="text-sm opacity-40 mb-2">No saved signatures</p>
              <p class="text-xs opacity-30">
                Draw or upload a signature to get started
              </p>
            </div>
          {:else}
            <div class="grid grid-cols-3 gap-4">
              {#each signaturesStore.signatures as sig}
                <button
                  onclick={() => selectedSignature = sig}
                  class="relative p-4 rounded-lg transition-all hover:scale-[1.02] text-left"
                  style="background-color: {selectedSignature?.id === sig.id ? 'var(--nord2)' : 'var(--nord0)'};
                         border: 2px solid {selectedSignature?.id === sig.id ? 'var(--nord8)' : 'transparent'};"
                >
                  <!-- Signature preview -->
                  <div class="h-16 flex items-center justify-center mb-2 rounded" style="background-color: var(--nord6);">
                    <img
                      src={sig.thumbnail}
                      alt={sig.name}
                      class="max-h-full max-w-full object-contain"
                    />
                  </div>

                  <!-- Name (editable) -->
                  {#if editingName === sig.id}
                    <div class="flex items-center gap-1">
                      <input
                        type="text"
                        bind:value={newName}
                        class="flex-1 text-xs px-2 py-1 rounded"
                        style="background-color: var(--nord2); color: var(--nord5);"
                        onkeydown={(e) => e.key === 'Enter' && handleRenameSignature(sig)}
                      />
                      <button
                        onclick={() => handleRenameSignature(sig)}
                        class="p-1 rounded hover:bg-[var(--nord3)]"
                      >
                        <Check size={12} style="color: var(--nord14);" />
                      </button>
                      <button
                        onclick={() => { editingName = null; newName = ''; }}
                        class="p-1 rounded hover:bg-[var(--nord3)]"
                      >
                        <X size={12} style="color: var(--nord11);" />
                      </button>
                    </div>
                  {:else}
                    <div class="flex items-center justify-between">
                      <p class="text-xs truncate flex-1" style="color: var(--nord4);">{sig.name}</p>
                      <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onclick={(e) => { e.stopPropagation(); editingName = sig.id; newName = sig.name; }}
                          class="p-1 rounded hover:bg-[var(--nord3)]"
                          title="Rename"
                        >
                          <Edit2 size={10} style="color: var(--nord4);" />
                        </button>
                        <button
                          onclick={(e) => { e.stopPropagation(); handleDeleteSignature(sig); }}
                          class="p-1 rounded hover:bg-[var(--nord3)]"
                          title="Delete"
                        >
                          <Trash2 size={10} style="color: var(--nord11);" />
                        </button>
                      </div>
                    </div>
                  {/if}

                  <!-- Type badge -->
                  <span
                    class="absolute top-2 right-2 text-[9px] px-1.5 py-0.5 rounded"
                    style="background-color: var(--nord2); color: var(--nord4);"
                  >
                    {sig.type === 'freehand' ? 'Drawn' : 'Image'}
                  </span>
                </button>
              {/each}
            </div>
          {/if}
        </div>
      </section>

      <!-- Apply Signature to PDF -->
      {#if selectedSignature}
        <section
          class="rounded-xl p-6"
          style="background-color: var(--nord1); border: 1px solid var(--nord3);"
        >
          <h3 class="font-medium mb-4" style="color: var(--nord8);">Apply Signature to PDF</h3>

          <!-- Selected signature preview -->
          <div class="flex items-center gap-4 mb-4 p-3 rounded-lg" style="background-color: var(--nord2);">
            <div class="w-24 h-12 rounded flex items-center justify-center" style="background-color: var(--nord6);">
              <img
                src={selectedSignature.thumbnail}
                alt={selectedSignature.name}
                class="max-h-full max-w-full object-contain"
              />
            </div>
            <div class="flex-1">
              <p class="text-sm font-medium" style="color: var(--nord5);">{selectedSignature.name}</p>
              <p class="text-xs opacity-50">Selected for signing</p>
            </div>
            <button
              onclick={() => selectedSignature = null}
              class="p-2 rounded hover:bg-[var(--nord3)]"
            >
              <X size={16} style="color: var(--nord4);" />
            </button>
          </div>

          <!-- PDF Selection -->
          {#if !selectedPdf}
            <button
              onclick={selectPdf}
              class="w-full p-8 rounded-lg flex flex-col items-center gap-2 transition-colors hover:bg-[var(--nord2)]"
              style="background-color: var(--nord0); border: 2px dashed var(--nord3);"
            >
              <FileText size={32} style="color: var(--nord4);" />
              <p class="text-sm opacity-60">Select PDF to sign</p>
              <p class="text-xs opacity-40">or drag and drop a PDF file</p>
            </button>
          {:else}
            <div class="flex items-center gap-3 mb-4 p-3 rounded-lg" style="background-color: var(--nord2);">
              <FileText size={20} style="color: var(--nord8);" />
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium truncate" style="color: var(--nord5);">{selectedPdfName}</p>
                <p class="text-xs opacity-50 truncate">{selectedPdf}</p>
              </div>
              <button
                onclick={clearPdf}
                class="p-2 rounded hover:bg-[var(--nord3)]"
              >
                <X size={16} style="color: var(--nord4);" />
              </button>
            </div>

            <!-- Apply Button -->
            <button
              onclick={applySignatureToPdf}
              disabled={isApplying}
              class="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-medium transition-all disabled:opacity-50"
              style="background-color: var(--nord10); color: var(--nord6);"
            >
              {#if isApplying}
                <div class="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin" style="border-color: var(--nord6);"></div>
                Applying...
              {:else}
                <Download size={18} />
                Apply Signature & Save
              {/if}
            </button>

            <!-- Result -->
            {#if applyResult}
              <div
                class="mt-4 p-3 rounded-lg flex items-center gap-2"
                style="background-color: {applyResult.success ? 'rgba(163, 190, 140, 0.1)' : 'rgba(191, 97, 106, 0.1)'};
                       border: 1px solid {applyResult.success ? 'var(--nord14)' : 'var(--nord11)'};"
              >
                {#if applyResult.success}
                  <Check size={16} style="color: var(--nord14);" />
                {:else}
                  <X size={16} style="color: var(--nord11);" />
                {/if}
                <span style="color: {applyResult.success ? 'var(--nord14)' : 'var(--nord11)'};">
                  {applyResult.message}
                </span>
              </div>
            {/if}
          {/if}

          <!-- Warning about graphical signatures -->
          <p class="text-xs opacity-40 mt-4 text-center">
            Note: Graphical signatures are visual overlays only, not cryptographic digital signatures.
          </p>
        </section>
      {/if}

      {:else}
      <!-- INITIALS TAB -->
      <!-- Initials Creation Options -->
      <section class="mb-8">
        <h2 class="text-sm font-medium mb-4 opacity-60 uppercase tracking-wider">Create Initials</h2>
        <div class="grid grid-cols-2 gap-4">
          <button
            onclick={() => activeSection = 'draw'}
            class="flex flex-col items-center gap-3 p-6 rounded-xl transition-all hover:scale-[1.02] active:scale-[0.98]"
            style="background-color: {activeSection === 'draw' ? 'var(--nord2)' : 'var(--nord1)'};
                   border: 1px solid {activeSection === 'draw' ? 'var(--nord8)' : 'var(--nord3)'};"
          >
            <div class="w-12 h-12 rounded-xl flex items-center justify-center" style="background-color: var(--nord2);">
              <PenTool size={24} style="color: var(--nord8);" />
            </div>
            <div class="text-center">
              <h3 class="font-medium mb-1" style="color: var(--nord6);">Draw Initials</h3>
              <p class="text-xs opacity-50">Quick handwritten initials (e.g., JD)</p>
            </div>
          </button>
          <button
            onclick={() => activeSection = 'upload'}
            class="flex flex-col items-center gap-3 p-6 rounded-xl transition-all hover:scale-[1.02] active:scale-[0.98]"
            style="background-color: {activeSection === 'upload' ? 'var(--nord2)' : 'var(--nord1)'};
                   border: 1px solid {activeSection === 'upload' ? 'var(--nord8)' : 'var(--nord3)'};"
          >
            <div class="w-12 h-12 rounded-xl flex items-center justify-center" style="background-color: var(--nord2);">
              <Upload size={24} style="color: var(--nord8);" />
            </div>
            <div class="text-center">
              <h3 class="font-medium mb-1" style="color: var(--nord6);">Upload Image</h3>
              <p class="text-xs opacity-50">Upload initials image</p>
            </div>
          </button>
        </div>
      </section>

      <!-- Active Section Content for Initials -->
      {#if activeSection === 'draw'}
        <section
          class="rounded-xl p-6 mb-8"
          style="background-color: var(--nord1); border: 1px solid var(--nord3);"
        >
          <h3 class="font-medium mb-4" style="color: var(--nord8);">Draw Your Initials</h3>
          <SignatureCanvas
            bind:this={initialsCanvasComponent}
            width={300}
            height={150}
            strokeColor="#2E3440"
            strokeWidth={3}
            onSave={handleSaveDrawnInitial}
          />
          <p class="text-xs opacity-40 mt-3">
            Draw your initials (typically 2-3 letters). Click Save to add to your library.
          </p>
        </section>
      {:else if activeSection === 'upload'}
        <section
          class="rounded-xl p-6 mb-8"
          style="background-color: var(--nord1); border: 1px solid var(--nord3);"
        >
          <h3 class="font-medium mb-4" style="color: var(--nord8);">Upload Initials Image</h3>
          <button
            onclick={() => handleImageUpload(undefined, 'initial')}
            class="w-full h-24 rounded-lg flex flex-col items-center justify-center gap-2 transition-colors hover:bg-[var(--nord2)]"
            style="background-color: var(--nord0); border: 2px dashed var(--nord3);"
          >
            <Upload size={24} style="color: var(--nord4);" />
            <p class="text-sm opacity-60">Click to upload or drag and drop</p>
          </button>
        </section>
      {/if}

      <!-- Initials Library -->
      <section class="mb-8">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-medium opacity-60 uppercase tracking-wider">
            Saved Initials ({signaturesStore.initialCount})
          </h2>
        </div>

        <div
          class="rounded-xl p-4"
          style="background-color: var(--nord1); border: 1px solid var(--nord3);"
        >
          {#if signaturesStore.initials.length === 0}
            <div class="py-8 text-center">
              <Type size={32} class="mx-auto mb-3 opacity-20" />
              <p class="text-sm opacity-40 mb-2">No saved initials</p>
              <p class="text-xs opacity-30">
                Draw or upload initials to get started
              </p>
            </div>
          {:else}
            <div class="grid grid-cols-4 gap-4">
              {#each signaturesStore.initials as ini}
                <button
                  onclick={() => selectedSignature = ini}
                  class="relative p-3 rounded-lg transition-all hover:scale-[1.02] text-left"
                  style="background-color: {selectedSignature?.id === ini.id ? 'var(--nord2)' : 'var(--nord0)'};
                         border: 2px solid {selectedSignature?.id === ini.id ? 'var(--nord8)' : 'transparent'};"
                >
                  <!-- Initial preview -->
                  <div class="h-12 flex items-center justify-center mb-2 rounded" style="background-color: var(--nord6);">
                    <img
                      src={ini.thumbnail}
                      alt={ini.name}
                      class="max-h-full max-w-full object-contain"
                    />
                  </div>

                  <!-- Name and actions -->
                  {#if editingName === ini.id}
                    <div class="flex items-center gap-1">
                      <input
                        type="text"
                        bind:value={newName}
                        class="flex-1 text-xs px-1 py-0.5 rounded"
                        style="background-color: var(--nord2); color: var(--nord5);"
                        onkeydown={(e) => e.key === 'Enter' && handleRenameSignature(ini)}
                      />
                      <button
                        onclick={() => handleRenameSignature(ini)}
                        class="p-0.5 rounded hover:bg-[var(--nord3)]"
                      >
                        <Check size={10} style="color: var(--nord14);" />
                      </button>
                    </div>
                  {:else}
                    <div class="flex items-center justify-between">
                      <p class="text-[10px] truncate flex-1" style="color: var(--nord4);">{ini.name}</p>
                      <div class="flex items-center gap-0.5">
                        <button
                          onclick={(e) => { e.stopPropagation(); editingName = ini.id; newName = ini.name; }}
                          class="p-0.5 rounded hover:bg-[var(--nord3)] opacity-50 hover:opacity-100"
                          title="Rename"
                        >
                          <Edit2 size={8} style="color: var(--nord4);" />
                        </button>
                        <button
                          onclick={(e) => { e.stopPropagation(); handleDeleteSignature(ini); }}
                          class="p-0.5 rounded hover:bg-[var(--nord3)] opacity-50 hover:opacity-100"
                          title="Delete"
                        >
                          <Trash2 size={8} style="color: var(--nord11);" />
                        </button>
                      </div>
                    </div>
                  {/if}
                </button>
              {/each}
            </div>
          {/if}
        </div>
      </section>

      <!-- Apply Initial to PDF (similar to signatures) -->
      {#if selectedSignature && selectedSignature.category === 'initial'}
        <section
          class="rounded-xl p-6"
          style="background-color: var(--nord1); border: 1px solid var(--nord3);"
        >
          <h3 class="font-medium mb-4" style="color: var(--nord8);">Apply Initial to PDF</h3>

          <!-- Selected initial preview -->
          <div class="flex items-center gap-4 mb-4 p-3 rounded-lg" style="background-color: var(--nord2);">
            <div class="w-16 h-10 rounded flex items-center justify-center" style="background-color: var(--nord6);">
              <img
                src={selectedSignature.thumbnail}
                alt={selectedSignature.name}
                class="max-h-full max-w-full object-contain"
              />
            </div>
            <div class="flex-1">
              <p class="text-sm font-medium" style="color: var(--nord5);">{selectedSignature.name}</p>
              <p class="text-xs opacity-50">Selected for initialing</p>
            </div>
            <button
              onclick={() => selectedSignature = null}
              class="p-2 rounded hover:bg-[var(--nord3)]"
            >
              <X size={16} style="color: var(--nord4);" />
            </button>
          </div>

          <!-- PDF Selection -->
          {#if !selectedPdf}
            <button
              onclick={selectPdf}
              class="w-full p-6 rounded-lg flex flex-col items-center gap-2 transition-colors hover:bg-[var(--nord2)]"
              style="background-color: var(--nord0); border: 2px dashed var(--nord3);"
            >
              <FileText size={24} style="color: var(--nord4);" />
              <p class="text-sm opacity-60">Select PDF to initial</p>
            </button>
          {:else}
            <div class="flex items-center gap-3 mb-4 p-3 rounded-lg" style="background-color: var(--nord2);">
              <FileText size={20} style="color: var(--nord8);" />
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium truncate" style="color: var(--nord5);">{selectedPdfName}</p>
              </div>
              <button onclick={clearPdf} class="p-2 rounded hover:bg-[var(--nord3)]">
                <X size={16} style="color: var(--nord4);" />
              </button>
            </div>

            <button
              onclick={applySignatureToPdf}
              disabled={isApplying}
              class="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-medium transition-all disabled:opacity-50"
              style="background-color: var(--nord10); color: var(--nord6);"
            >
              {#if isApplying}
                <div class="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin" style="border-color: var(--nord6);"></div>
                Applying...
              {:else}
                <Download size={18} />
                Apply Initial & Save
              {/if}
            </button>

            {#if applyResult}
              <div
                class="mt-4 p-3 rounded-lg flex items-center gap-2"
                style="background-color: {applyResult.success ? 'rgba(163, 190, 140, 0.1)' : 'rgba(191, 97, 106, 0.1)'};
                       border: 1px solid {applyResult.success ? 'var(--nord14)' : 'var(--nord11)'};"
              >
                {#if applyResult.success}
                  <Check size={16} style="color: var(--nord14);" />
                {:else}
                  <X size={16} style="color: var(--nord11);" />
                {/if}
                <span style="color: {applyResult.success ? 'var(--nord14)' : 'var(--nord11)'};">
                  {applyResult.message}
                </span>
              </div>
            {/if}
          {/if}

          <p class="text-xs opacity-40 mt-4 text-center">
            Initials are typically used to acknowledge individual pages or sections.
          </p>
        </section>
      {/if}
      {/if}
    </div>
  </div>
</div>
