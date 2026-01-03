<script lang="ts">
  import { FileSearch, Type, AlertCircle, Search, Edit3 } from 'lucide-svelte';

  export type OcrMode = 'searchable' | 'editable';

  export interface OcrDialogOptions {
    mode: OcrMode;
    analyzeFonts: boolean;
  }

  interface Props {
    open: boolean;
    onConfirm: (options: OcrDialogOptions) => void;
    onCancel: () => void;
  }

  let { open, onConfirm, onCancel }: Props = $props();

  let ocrMode = $state<OcrMode>('searchable');
  let analyzeFonts = $state(false);

  function handleConfirm() {
    onConfirm({ mode: ocrMode, analyzeFonts });
    // Reset for next time
    ocrMode = 'searchable';
    analyzeFonts = false;
  }

  function handleCancel() {
    onCancel();
    ocrMode = 'searchable';
    analyzeFonts = false;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      handleCancel();
    } else if (e.key === 'Enter') {
      handleConfirm();
    }
  }
</script>

{#if open}
  <!-- Backdrop -->
  <div
    class="fixed inset-0 z-[100] flex items-center justify-center bg-black/50"
    onclick={handleCancel}
    onkeydown={handleKeydown}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <!-- Dialog -->
    <div
      class="w-full max-w-md mx-4 rounded-xl shadow-2xl"
      style="background-color: var(--nord0);"
      onclick={(e) => e.stopPropagation()}
      role="document"
    >
      <!-- Header -->
      <div class="p-4 flex items-center gap-3" style="border-bottom: 1px solid var(--nord2);">
        <div class="p-2 rounded-lg" style="background-color: var(--nord10);">
          <FileSearch size={24} color="white" />
        </div>
        <div>
          <h2 class="font-semibold text-lg">OCR Recommended</h2>
          <p class="text-xs opacity-60">Optical Character Recognition</p>
        </div>
      </div>

      <!-- Content -->
      <div class="p-4 space-y-4">
        <div class="flex items-start gap-3 p-3 rounded-lg" style="background-color: var(--nord1);">
          <AlertCircle size={20} class="mt-0.5 flex-shrink-0" style="color: var(--nord13);" />
          <div class="text-sm">
            <p>This document appears to be scanned and has no searchable text.</p>
            <p class="mt-2 opacity-70">Choose how you want to process this document.</p>
          </div>
        </div>

        <!-- OCR Mode Selection -->
        <div class="space-y-2">
          <p class="text-xs font-medium opacity-70 uppercase tracking-wide">OCR Mode</p>

          <!-- Searchable option -->
          <label
            class="flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors"
            style="background-color: {ocrMode === 'searchable' ? 'var(--nord2)' : 'var(--nord1)'}; border: 1px solid {ocrMode === 'searchable' ? 'var(--nord10)' : 'transparent'};"
          >
            <input
              type="radio"
              name="ocrMode"
              value="searchable"
              bind:group={ocrMode}
              class="mt-1"
            />
            <div class="flex-1">
              <div class="flex items-center gap-2 text-sm font-medium">
                <Search size={16} style="color: var(--nord8);" />
                For text search
              </div>
              <p class="text-xs opacity-60 mt-1">
                Creates an invisible text layer. Enables search and text selection while preserving the original appearance. Faster processing.
              </p>
            </div>
          </label>

          <!-- Editable option -->
          <label
            class="flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors"
            style="background-color: {ocrMode === 'editable' ? 'var(--nord2)' : 'var(--nord1)'}; border: 1px solid {ocrMode === 'editable' ? 'var(--nord10)' : 'transparent'};"
          >
            <input
              type="radio"
              name="ocrMode"
              value="editable"
              bind:group={ocrMode}
              class="mt-1"
            />
            <div class="flex-1">
              <div class="flex items-center gap-2 text-sm font-medium">
                <Edit3 size={16} style="color: var(--nord14);" />
                For editing
              </div>
              <p class="text-xs opacity-60 mt-1">
                Creates real text objects with accurate positioning. Required if you plan to edit text in this document. Takes longer to process.
              </p>
            </div>
          </label>
        </div>

        <!-- Font analysis checkbox (only show for editable mode) -->
        {#if ocrMode === 'editable'}
          <label class="flex items-start gap-3 p-3 rounded-lg cursor-pointer hover:bg-[var(--nord1)] transition-colors">
            <input
              type="checkbox"
              bind:checked={analyzeFonts}
              class="mt-1 w-4 h-4 rounded"
            />
            <div class="flex-1">
              <div class="flex items-center gap-2 text-sm font-medium">
                <Type size={16} style="color: var(--nord8);" />
                Analyze embedded fonts
              </div>
              <p class="text-xs opacity-60 mt-1">
                Improves font matching for better editing results. Opens the Fonts panel after OCR completes.
              </p>
            </div>
          </label>
        {/if}
      </div>

      <!-- Actions -->
      <div class="p-4 flex justify-end gap-2" style="border-top: 1px solid var(--nord2);">
        <button
          onclick={handleCancel}
          class="px-4 py-2 rounded-lg text-sm transition-colors hover:bg-[var(--nord2)]"
          style="color: var(--nord4);"
        >
          Skip
        </button>
        <button
          onclick={handleConfirm}
          class="px-4 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-90"
          style="background-color: #5E81AC; color: white;"
        >
          Apply OCR
        </button>
      </div>
    </div>
  </div>
{/if}
