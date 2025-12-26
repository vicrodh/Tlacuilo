<script lang="ts">
  import { FileSearch, Type, AlertCircle } from 'lucide-svelte';

  interface Props {
    open: boolean;
    onConfirm: (options: { analyzeFonts: boolean }) => void;
    onCancel: () => void;
  }

  let { open, onConfirm, onCancel }: Props = $props();

  let analyzeFonts = $state(false);

  function handleConfirm() {
    onConfirm({ analyzeFonts });
    analyzeFonts = false; // Reset for next time
  }

  function handleCancel() {
    onCancel();
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
          <FileSearch size={24} style="color: var(--nord6);" />
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
            <p class="mt-2 opacity-70">Some features (search, text selection, text editing) may not work properly without OCR.</p>
          </div>
        </div>

        <!-- Font analysis checkbox -->
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
              If you plan to edit this document, analyzing fonts will improve text matching. This will take longer but provide better editing results.
            </p>
          </div>
        </label>
      </div>

      <!-- Actions -->
      <div class="p-4 flex justify-end gap-2" style="border-top: 1px solid var(--nord2);">
        <button
          onclick={handleCancel}
          class="px-4 py-2 rounded-lg text-sm transition-colors hover:bg-[var(--nord2)]"
        >
          Skip
        </button>
        <button
          onclick={handleConfirm}
          class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          style="background-color: var(--nord10); color: var(--nord6);"
        >
          Apply OCR
        </button>
      </div>
    </div>
  </div>
{/if}
