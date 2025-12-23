<script lang="ts">
  import { X, Printer, FileText } from 'lucide-svelte';

  interface Props {
    visible: boolean;
    annotationCount: number;
    onPrint: (withAnnotations: boolean) => void;
    onCancel: () => void;
  }

  let { visible, annotationCount, onPrint, onCancel }: Props = $props();
  let includeAnnotations = $state(true);
</script>

{#if visible}
  <!-- Backdrop -->
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center"
    style="background-color: rgba(0, 0, 0, 0.6);"
    onclick={onCancel}
  >
    <!-- Dialog -->
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="relative rounded-lg shadow-2xl p-6 min-w-[320px] max-w-[400px]"
      style="background-color: var(--nord1); border: 1px solid var(--nord3);"
      onclick={(e) => e.stopPropagation()}
    >
      <!-- Header -->
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <Printer size={20} style="color: var(--nord8);" />
          <h2 class="text-lg font-semibold" style="color: var(--nord4);">Print Document</h2>
        </div>
        <button
          onclick={onCancel}
          class="p-1 rounded hover:bg-[var(--nord2)] transition-colors"
          title="Close"
        >
          <X size={18} style="color: var(--nord4);" />
        </button>
      </div>

      <!-- Content -->
      <div class="space-y-4">
        <!-- Include Annotations Option -->
        <label
          class="flex items-center gap-3 p-3 rounded cursor-pointer transition-colors hover:bg-[var(--nord2)]"
          style="border: 1px solid var(--nord3);"
        >
          <input
            type="checkbox"
            bind:checked={includeAnnotations}
            class="w-4 h-4 rounded accent-[var(--nord8)]"
          />
          <div class="flex-1">
            <div class="flex items-center gap-2">
              <FileText size={16} style="color: var(--nord4);" />
              <span style="color: var(--nord4);">Include Annotations</span>
            </div>
            {#if annotationCount > 0}
              <div class="text-sm mt-1" style="color: var(--nord10);">
                {annotationCount} annotation{annotationCount !== 1 ? 's' : ''} will be {includeAnnotations ? 'included' : 'excluded'}
              </div>
            {:else}
              <div class="text-sm mt-1 opacity-60" style="color: var(--nord4);">
                No annotations in document
              </div>
            {/if}
          </div>
        </label>

        <!-- Info text -->
        <p class="text-xs opacity-60" style="color: var(--nord4);">
          {#if includeAnnotations}
            Annotations will be embedded in the PDF before printing.
          {:else}
            The original PDF will be printed without any annotations.
          {/if}
        </p>
      </div>

      <!-- Actions -->
      <div class="flex justify-end gap-2 mt-6">
        <button
          onclick={onCancel}
          class="px-4 py-2 rounded transition-colors hover:bg-[var(--nord2)]"
          style="color: var(--nord4); border: 1px solid var(--nord3);"
        >
          Cancel
        </button>
        <button
          onclick={() => onPrint(includeAnnotations)}
          class="px-4 py-2 rounded transition-colors flex items-center gap-2"
          style="background-color: var(--nord8); color: var(--nord0);"
        >
          <Printer size={16} />
          Print
        </button>
      </div>
    </div>
  </div>
{/if}
