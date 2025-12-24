<script lang="ts">
  import { onMount } from 'svelte';
  import { debugLog } from '$lib/stores/debugLog.svelte';

  interface RenderedPage {
    data: string;
    width: number;
    height: number;
    page: number;
  }

  interface Props {
    currentPage: number;
    totalPages: number;
    loadedThumbnails: Map<number, RenderedPage>;
    loadingThumbnails: Set<number>;
    fileReloadVersion?: number; // Incremented when file is reloaded (e.g., after OCR)
    onNavigateToPage: (page: number) => void;
    onLoadThumbnail: (page: number) => void;
    onThumbnailScroll: () => void;
  }

  let {
    currentPage,
    totalPages,
    loadedThumbnails,
    loadingThumbnails,
    fileReloadVersion = 0,
    onNavigateToPage,
    onLoadThumbnail,
    onThumbnailScroll,
  }: Props = $props();

  let thumbnailsContainer: HTMLDivElement;
  const THUMBNAIL_BUFFER = 5;
  let lastLoadedTotalPages = 0;

  // Load visible thumbnails based on scroll position
  function loadVisibleThumbnails() {
    debugLog('PagesTab', 'loadVisibleThumbnails() called', { totalPages, hasContainer: !!thumbnailsContainer });
    if (!thumbnailsContainer || totalPages === 0) {
      debugLog('PagesTab', 'loadVisibleThumbnails() early return', { reason: !thumbnailsContainer ? 'no container' : 'no pages' });
      return;
    }

    const scrollTop = thumbnailsContainer.scrollTop;
    const containerHeight = thumbnailsContainer.clientHeight;

    // Estimate thumbnail height (including gap)
    const estimatedThumbHeight = 120;

    const startIdx = Math.max(0, Math.floor(scrollTop / estimatedThumbHeight) - THUMBNAIL_BUFFER);
    const endIdx = Math.min(totalPages - 1, Math.ceil((scrollTop + containerHeight) / estimatedThumbHeight) + THUMBNAIL_BUFFER);

    debugLog('PagesTab', 'Loading thumbnails', { startIdx, endIdx });

    for (let i = startIdx; i <= endIdx; i++) {
      const pageNum = i + 1;
      // Check current state of maps (read from props)
      if (!loadedThumbnails.has(pageNum) && !loadingThumbnails.has(pageNum)) {
        onLoadThumbnail(pageNum);
      }
    }
    debugLog('PagesTab', 'loadVisibleThumbnails() completed');
  }

  function handleScroll() {
    loadVisibleThumbnails();
  }

  onMount(() => {
    debugLog('PagesTab', 'onMount() called', { totalPages });
    // Initial load after mount
    if (totalPages > 0) {
      debugLog('PagesTab', 'Scheduling initial thumbnail load');
      setTimeout(() => loadVisibleThumbnails(), 100);
    }
  });

  // Only reload when totalPages actually changes (new document)
  $effect(() => {
    if (totalPages > 0 && totalPages !== lastLoadedTotalPages) {
      debugLog('PagesTab', '$effect: totalPages changed', { from: lastLoadedTotalPages, to: totalPages });
      lastLoadedTotalPages = totalPages;
      // Delay to allow DOM to settle
      setTimeout(() => loadVisibleThumbnails(), 100);
    }
  });

  // Reload thumbnails when file is reloaded (e.g., after OCR)
  let lastReloadVersion = 0;
  $effect(() => {
    if (fileReloadVersion > 0 && fileReloadVersion !== lastReloadVersion) {
      debugLog('PagesTab', '$effect: fileReloadVersion changed', { from: lastReloadVersion, to: fileReloadVersion });
      lastReloadVersion = fileReloadVersion;
      // Delay to allow thumbnails map to clear, then reload
      setTimeout(() => loadVisibleThumbnails(), 100);
    }
  });
</script>

<div class="pages-tab">
  <div class="header">
    <span class="title">Pages</span>
    <span class="count">{totalPages}</span>
  </div>

  <div
    bind:this={thumbnailsContainer}
    class="thumbnails-container"
    onscroll={handleScroll}
  >
    {#each Array.from({ length: totalPages }, (_, i) => i + 1) as pageNum (pageNum)}
      {@const thumb = loadedThumbnails.get(pageNum)}
      {@const isLoading = loadingThumbnails.has(pageNum)}
      <button
        onclick={() => onNavigateToPage(pageNum)}
        class="thumbnail-btn"
      >
        <div
          class="thumbnail-frame"
          class:active={currentPage === pageNum}
        >
          <div
            class="thumbnail-inner"
            style={thumb ? `aspect-ratio: ${thumb.width} / ${thumb.height};` : 'aspect-ratio: 8.5 / 11;'}
          >
            {#if thumb}
              <img
                src="data:image/png;base64,{thumb.data}"
                alt="Page {pageNum}"
                class="thumbnail-img"
                width={thumb.width}
                height={thumb.height}
              />
            {:else if isLoading}
              <div class="loading-spinner"></div>
            {:else}
              <span class="placeholder">{pageNum}</span>
            {/if}
          </div>

          {#if currentPage === pageNum}
            <div class="active-indicator"></div>
          {/if}
        </div>

        <p class="page-number" class:active={currentPage === pageNum}>
          {pageNum}
        </p>
      </button>
    {/each}
  </div>
</div>

<style>
  .pages-tab {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--nord3);
  }

  .title {
    font-size: 0.75rem;
    text-transform: uppercase;
    opacity: 0.6;
  }

  .count {
    font-size: 0.75rem;
    padding: 0.125rem 0.5rem;
    border-radius: 9999px;
    background-color: var(--nord2);
    color: var(--nord4);
  }

  .thumbnails-container {
    flex: 1;
    overflow-y: auto;
    padding: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .thumbnail-btn {
    width: 100%;
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 0;
  }

  .thumbnail-frame {
    position: relative;
    border-radius: 0.25rem;
    overflow: hidden;
    border: 2px solid var(--nord3);
    transition: border-color 0.15s;
  }

  .thumbnail-frame.active {
    border-color: var(--nord8);
  }

  .thumbnail-frame:hover {
    border-color: var(--nord4);
  }

  .thumbnail-frame.active:hover {
    border-color: var(--nord8);
  }

  .thumbnail-inner {
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: white;
    /* aspect-ratio is set dynamically via inline style */
  }

  .thumbnail-img {
    width: 100%;
    height: 100%;
    object-fit: fill;
  }

  .loading-spinner {
    width: 1rem;
    height: 1rem;
    border: 2px solid var(--nord8);
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .placeholder {
    font-size: 0.75rem;
    opacity: 0.3;
  }

  .active-indicator {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 2px;
    background-color: var(--nord8);
  }

  .page-number {
    margin-top: 0.25rem;
    font-size: 0.75rem;
    text-align: center;
    color: var(--nord4);
    transition: color 0.15s;
  }

  .page-number.active {
    color: var(--nord8);
  }
</style>
