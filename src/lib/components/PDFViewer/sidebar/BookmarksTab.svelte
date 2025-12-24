<script lang="ts">
  import { onMount } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';
  import { Bookmark, ChevronRight, ChevronDown, FileText, BookMarked, Loader2 } from 'lucide-svelte';

  interface OutlineEntry {
    title: string;
    page: number | null;
    y: number | null;
    children: OutlineEntry[];
  }

  interface Props {
    filePath: string;
    onNavigateToPage: (page: number) => void;
    onFocusOnResult?: (page: number, normalizedY: number) => void;
    fileReloadVersion?: number;
  }

  let { filePath, onNavigateToPage, onFocusOnResult, fileReloadVersion = 0 }: Props = $props();

  let outlines = $state<OutlineEntry[]>([]);
  let isLoading = $state(true);
  let error = $state<string | null>(null);
  let expandedItems = $state<Set<string>>(new Set());

  // Load outlines when file changes
  $effect(() => {
    if (filePath) {
      // Also depend on fileReloadVersion to reload after OCR
      const _ = fileReloadVersion;
      loadOutlines();
    }
  });

  async function loadOutlines() {
    if (!filePath) return;

    isLoading = true;
    error = null;

    try {
      const result = await invoke<OutlineEntry[]>('pdf_get_outlines', { path: filePath });
      outlines = result;
      // Auto-expand first level
      outlines.forEach((_, index) => {
        expandedItems.add(`0-${index}`);
      });
    } catch (e) {
      console.error('[BookmarksTab] Failed to load outlines:', e);
      error = e instanceof Error ? e.message : String(e);
      outlines = [];
    } finally {
      isLoading = false;
    }
  }

  function toggleExpand(path: string) {
    if (expandedItems.has(path)) {
      expandedItems.delete(path);
    } else {
      expandedItems.add(path);
    }
    expandedItems = new Set(expandedItems); // Trigger reactivity
  }

  function handleItemClick(entry: OutlineEntry) {
    if (entry.page !== null) {
      if (entry.y !== null && onFocusOnResult) {
        // Use focus on result for precise Y positioning
        onFocusOnResult(entry.page, entry.y);
      } else {
        // Fall back to simple page navigation
        onNavigateToPage(entry.page);
      }
    }
  }

  function countTotalItems(entries: OutlineEntry[]): number {
    return entries.reduce((count, entry) => {
      return count + 1 + countTotalItems(entry.children);
    }, 0);
  }
</script>

{#snippet outlineTree(entries: OutlineEntry[], depth: number, parentPath: string)}
  {#each entries as entry, index}
    {@const path = `${parentPath}-${index}`}
    {@const hasChildren = entry.children.length > 0}
    {@const isExpanded = expandedItems.has(path)}

    <div class="outline-item" style="--depth: {depth}">
      <div class="outline-row">
        {#if hasChildren}
          <button
            class="expand-btn"
            onclick={() => toggleExpand(path)}
            title={isExpanded ? 'Collapse' : 'Expand'}
          >
            {#if isExpanded}
              <ChevronDown size={14} />
            {:else}
              <ChevronRight size={14} />
            {/if}
          </button>
        {:else}
          <span class="expand-placeholder"></span>
        {/if}

        <button
          class="outline-button"
          class:has-page={entry.page !== null}
          onclick={() => handleItemClick(entry)}
          title={entry.page !== null ? `Go to page ${entry.page}` : entry.title}
        >
          <span class="outline-title">{entry.title}</span>

          {#if entry.page !== null}
            <span class="page-number">{entry.page}</span>
          {/if}
        </button>
      </div>
    </div>

    {#if hasChildren && isExpanded}
      {@render outlineTree(entry.children, depth + 1, path)}
    {/if}
  {/each}
{/snippet}

<div class="bookmarks-tab">
  <div class="header">
    <span class="title">Table of Contents</span>
    {#if outlines.length > 0}
      <span class="count">{countTotalItems(outlines)}</span>
    {/if}
  </div>

  <div class="content">
    {#if isLoading}
      <div class="loading-state">
        <Loader2 size={24} class="spinner" />
        <p>Loading outline...</p>
      </div>
    {:else if error}
      <div class="error-state">
        <FileText size={32} />
        <p class="message">Failed to load outline</p>
        <p class="hint">{error}</p>
      </div>
    {:else if outlines.length === 0}
      <div class="empty-state">
        <div class="icon-container">
          <BookMarked size={32} />
        </div>
        <p class="message">No Table of Contents</p>
        <p class="hint">This PDF doesn't have a document outline</p>
      </div>
    {:else}
      <div class="outline-list">
        {@render outlineTree(outlines, 0, '0')}
      </div>
    {/if}
  </div>
</div>

<style>
  .bookmarks-tab {
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
    font-size: 0.7rem;
    padding: 0.125rem 0.375rem;
    background-color: var(--nord3);
    border-radius: 0.25rem;
    color: var(--nord5);
  }

  .content {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
  }

  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    gap: 0.75rem;
    color: var(--nord4);
  }

  .loading-state :global(.spinner) {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .error-state,
  .empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    text-align: center;
  }

  .icon-container {
    color: var(--nord4);
    opacity: 0.3;
    margin-bottom: 0.75rem;
  }

  .error-state {
    color: var(--nord11);
  }

  .message {
    font-size: 0.875rem;
    color: var(--nord4);
    opacity: 0.6;
    margin: 0;
  }

  .hint {
    font-size: 0.75rem;
    color: var(--nord4);
    opacity: 0.4;
    margin: 0.25rem 0 0 0;
    max-width: 200px;
    word-break: break-word;
  }

  .outline-list {
    padding: 0.5rem 0;
  }

  .outline-item {
    padding-left: calc(var(--depth) * 1rem);
  }

  .outline-row {
    display: flex;
    align-items: center;
    gap: 0.125rem;
  }

  .outline-row:hover {
    background-color: var(--nord2);
  }

  .expand-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 28px;
    padding: 0;
    margin-left: 0.25rem;
    background: transparent;
    border: none;
    color: var(--nord4);
    cursor: pointer;
    opacity: 0.6;
    flex-shrink: 0;
  }

  .expand-btn:hover {
    opacity: 1;
    color: var(--nord6);
  }

  .expand-placeholder {
    width: 20px;
    margin-left: 0.25rem;
    flex-shrink: 0;
  }

  .outline-button {
    display: flex;
    align-items: center;
    flex: 1;
    min-width: 0;
    padding: 0.375rem 0.5rem;
    padding-right: 0.75rem;
    background: transparent;
    border: none;
    color: var(--nord4);
    font-size: 0.8125rem;
    text-align: left;
    cursor: pointer;
    gap: 0.5rem;
    transition: color 0.1s ease;
  }

  .outline-button:hover {
    color: var(--nord6);
  }

  .outline-button.has-page:hover {
    color: var(--nord8);
  }

  .outline-title {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .page-number {
    font-size: 0.6875rem;
    padding: 0.125rem 0.375rem;
    background-color: var(--nord2);
    border-radius: 0.25rem;
    color: var(--nord5);
    opacity: 0.7;
    flex-shrink: 0;
  }

  .outline-button:hover .page-number {
    opacity: 1;
    background-color: var(--nord3);
  }
</style>
