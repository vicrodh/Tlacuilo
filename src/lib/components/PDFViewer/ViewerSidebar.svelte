<script lang="ts">
  import { onMount } from 'svelte';
  import { ChevronLeft, Check } from 'lucide-svelte';
  import type { PDFDocumentProxy } from 'pdfjs-dist';

  interface Props {
    pdfDoc: PDFDocumentProxy | null;
    currentPage: number;
    selectedPages: Set<number>;
    mode?: 'view' | 'select' | 'annotate';
    onPageClick: (page: number) => void;
    onPageSelect: (page: number) => void;
    onCollapse: () => void;
  }

  let {
    pdfDoc,
    currentPage,
    selectedPages,
    mode = 'view',
    onPageClick,
    onPageSelect,
    onCollapse,
  }: Props = $props();

  interface Thumbnail {
    page: number;
    canvas: HTMLCanvasElement | null;
    isLoading: boolean;
  }

  let thumbnails = $state<Thumbnail[]>([]);
  let thumbnailContainer: HTMLDivElement;

  // Generate thumbnails
  async function generateThumbnails() {
    if (!pdfDoc) return;

    const newThumbnails: Thumbnail[] = [];
    for (let i = 1; i <= pdfDoc.numPages; i++) {
      newThumbnails.push({ page: i, canvas: null, isLoading: true });
    }
    thumbnails = newThumbnails;

    // Generate each thumbnail
    for (let i = 0; i < newThumbnails.length; i++) {
      try {
        const page = await pdfDoc.getPage(i + 1);
        const viewport = page.getViewport({ scale: 0.2 });

        const canvas = document.createElement('canvas');
        canvas.width = viewport.width;
        canvas.height = viewport.height;

        const context = canvas.getContext('2d');
        if (context) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          await page.render({
            canvasContext: context,
            viewport: viewport,
          } as any).promise;
        }

        thumbnails = thumbnails.map((t, idx) =>
          idx === i ? { ...t, canvas, isLoading: false } : t
        );
      } catch (err) {
        console.error(`Failed to render thumbnail ${i + 1}:`, err);
        thumbnails = thumbnails.map((t, idx) =>
          idx === i ? { ...t, isLoading: false } : t
        );
      }
    }
  }

  // Scroll to current page
  function scrollToCurrentPage() {
    if (!thumbnailContainer) return;
    const element = thumbnailContainer.querySelector(`[data-page="${currentPage}"]`);
    element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  // Handle click based on mode
  function handleThumbnailClick(page: number, e: MouseEvent) {
    if (mode === 'select' || e.ctrlKey || e.metaKey) {
      onPageSelect(page);
    } else {
      onPageClick(page);
    }
  }

  $effect(() => {
    if (pdfDoc) {
      generateThumbnails();
    }
  });

  $effect(() => {
    scrollToCurrentPage();
  });
</script>

<div
  class="w-40 flex flex-col border-r overflow-hidden"
  style="background-color: var(--nord1); border-color: var(--nord3);"
>
  <!-- Header -->
  <div
    class="flex items-center justify-between px-3 py-2 border-b"
    style="border-color: var(--nord3);"
  >
    <span class="text-xs uppercase opacity-60">Pages</span>
    <button
      onclick={onCollapse}
      class="p-1 rounded hover:bg-[var(--nord2)] transition-colors"
      title="Hide thumbnails"
    >
      <ChevronLeft size={14} />
    </button>
  </div>

  <!-- Thumbnails -->
  <div
    bind:this={thumbnailContainer}
    class="flex-1 overflow-y-auto p-2 space-y-2"
  >
    {#each thumbnails as thumb (thumb.page)}
      <button
        data-page={thumb.page}
        onclick={(e) => handleThumbnailClick(thumb.page, e)}
        class="w-full relative group"
      >
        <!-- Thumbnail container -->
        <div
          class="relative rounded overflow-hidden transition-all"
          style="
            border: 2px solid {currentPage === thumb.page ? 'var(--nord8)' : selectedPages.has(thumb.page) ? 'var(--nord14)' : 'var(--nord3)'};
            background-color: var(--nord2);
          "
        >
          {#if thumb.isLoading}
            <div class="aspect-[3/4] flex items-center justify-center">
              <div class="w-4 h-4 border-2 border-[var(--nord8)] border-t-transparent rounded-full animate-spin"></div>
            </div>
          {:else if thumb.canvas}
            <div class="aspect-[3/4] flex items-center justify-center bg-white">
              {@html thumb.canvas.outerHTML}
            </div>
          {:else}
            <div class="aspect-[3/4] flex items-center justify-center">
              <span class="text-xs opacity-40">Error</span>
            </div>
          {/if}

          <!-- Selection checkbox overlay -->
          {#if mode === 'select' || selectedPages.has(thumb.page)}
            <div
              class="absolute top-1 right-1 w-5 h-5 rounded flex items-center justify-center transition-all"
              style="background-color: {selectedPages.has(thumb.page) ? 'var(--nord14)' : 'var(--nord2)'};"
            >
              {#if selectedPages.has(thumb.page)}
                <Check size={12} style="color: var(--nord0);" />
              {/if}
            </div>
          {/if}

          <!-- Current page indicator -->
          {#if currentPage === thumb.page}
            <div
              class="absolute bottom-0 left-0 right-0 h-0.5"
              style="background-color: var(--nord8);"
            ></div>
          {/if}
        </div>

        <!-- Page number -->
        <p
          class="mt-1 text-xs text-center"
          style="color: {currentPage === thumb.page ? 'var(--nord8)' : 'var(--nord4)'};"
        >
          {thumb.page}
        </p>
      </button>
    {/each}
  </div>
</div>

<style>
  /* Style the embedded canvas */
  :global(.thumbnail-canvas) {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
</style>
