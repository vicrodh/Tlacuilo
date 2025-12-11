<script lang="ts">
  /**
   * Resizable modal for previewing PDF pages with zoom.
   */
  import { X, ZoomIn, ZoomOut, ChevronLeft, ChevronRight } from 'lucide-svelte';
  import { renderPageForViewer } from '$lib/utils/pdfjs';
  import type { PageData } from '$lib/utils/pdfjs';

  interface Props {
    page: PageData | null;
    totalPages: number;
    onClose: () => void;
    onNavigate?: (pageNumber: number) => void;
  }

  let { page, totalPages, onClose, onNavigate }: Props = $props();

  let zoom = $state(100);
  let highResImage = $state<string>('');
  let isLoading = $state(false);

  const MIN_ZOOM = 50;
  const MAX_ZOOM = 400;

  // Load high-res image when page changes
  $effect(() => {
    if (page) {
      loadHighResImage();
    }
  });

  async function loadHighResImage() {
    if (!page) return;
    isLoading = true;
    try {
      highResImage = await renderPageForViewer(page.filePath, page.pageNumber, 1200);
    } catch (err) {
      console.error('Error loading high-res page:', err);
      highResImage = page.thumbnail; // Fallback to thumbnail
    }
    isLoading = false;
  }

  function zoomIn() {
    zoom = Math.min(zoom + 25, MAX_ZOOM);
  }

  function zoomOut() {
    zoom = Math.max(zoom - 25, MIN_ZOOM);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      onClose();
    } else if (e.key === 'ArrowLeft' && page && page.pageNumber > 1) {
      onNavigate?.(page.pageNumber - 1);
    } else if (e.key === 'ArrowRight' && page && page.pageNumber < totalPages) {
      onNavigate?.(page.pageNumber + 1);
    } else if (e.key === '+' || e.key === '=') {
      zoomIn();
    } else if (e.key === '-') {
      zoomOut();
    }
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if page}
  <!-- Backdrop -->
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-8"
    style="background-color: rgba(0, 0, 0, 0.8);"
    onclick={handleBackdropClick}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <!-- Modal Container -->
    <div
      class="relative flex flex-col rounded-lg overflow-hidden shadow-2xl"
      style="background-color: var(--nord0); max-width: 90vw; max-height: 90vh; min-width: 400px;"
    >
      <!-- Header -->
      <div
        class="flex items-center justify-between px-4 py-2 border-b"
        style="background-color: var(--nord1); border-color: var(--nord3);"
      >
        <div class="flex items-center gap-4">
          <!-- Navigation -->
          <div class="flex items-center gap-1">
            <button
              onclick={() => page && onNavigate?.(page.pageNumber - 1)}
              disabled={!page || page.pageNumber <= 1}
              class="p-1.5 rounded hover:bg-[var(--nord2)] transition-colors disabled:opacity-30"
            >
              <ChevronLeft size={18} />
            </button>
            <span class="text-sm">
              Page {page.pageNumber} of {totalPages}
            </span>
            <button
              onclick={() => page && onNavigate?.(page.pageNumber + 1)}
              disabled={!page || page.pageNumber >= totalPages}
              class="p-1.5 rounded hover:bg-[var(--nord2)] transition-colors disabled:opacity-30"
            >
              <ChevronRight size={18} />
            </button>
          </div>

          <!-- Separator -->
          <div class="w-px h-5" style="background-color: var(--nord3);"></div>

          <!-- Zoom -->
          <div class="flex items-center gap-1">
            <button
              onclick={zoomOut}
              disabled={zoom <= MIN_ZOOM}
              class="p-1.5 rounded hover:bg-[var(--nord2)] transition-colors disabled:opacity-30"
            >
              <ZoomOut size={18} />
            </button>
            <span class="text-sm min-w-[50px] text-center">{zoom}%</span>
            <button
              onclick={zoomIn}
              disabled={zoom >= MAX_ZOOM}
              class="p-1.5 rounded hover:bg-[var(--nord2)] transition-colors disabled:opacity-30"
            >
              <ZoomIn size={18} />
            </button>
          </div>
        </div>

        <button
          onclick={onClose}
          class="p-1.5 rounded hover:bg-[var(--nord2)] transition-colors"
        >
          <X size={18} />
        </button>
      </div>

      <!-- Content -->
      <div
        class="flex-1 overflow-auto p-4 flex items-center justify-center"
        style="background-color: var(--nord2); min-height: 400px;"
      >
        {#if isLoading}
          <div class="flex flex-col items-center gap-2">
            <div class="w-6 h-6 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin"></div>
            <p class="opacity-60 text-sm">Loading high resolution...</p>
          </div>
        {:else}
          <img
            src={highResImage || page.thumbnail}
            alt="Page {page.pageNumber}"
            class="shadow-lg rounded"
            style="transform: scale({zoom / 100}); transform-origin: center center; max-width: none;"
          />
        {/if}
      </div>

      <!-- Footer -->
      <div
        class="px-4 py-2 text-xs opacity-60 border-t"
        style="background-color: var(--nord1); border-color: var(--nord3);"
      >
        <span>{page.fileName}</span>
        <span class="mx-2">•</span>
        <span>Use arrow keys to navigate, +/- to zoom, Esc to close</span>
      </div>
    </div>
  </div>
{/if}
