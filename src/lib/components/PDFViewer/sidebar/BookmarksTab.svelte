<script lang="ts">
  import { onMount } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';
  import {
    Bookmark,
    ChevronRight,
    ChevronDown,
    FileText,
    BookMarked,
    Loader2,
    Plus,
    Trash2,
    Pencil,
    Check,
    X
  } from 'lucide-svelte';
  import {
    getBookmarksForFile,
    addBookmark,
    updateBookmark,
    deleteBookmark,
    ensureLoaded,
    type UserBookmark
  } from '$lib/stores/bookmarks.svelte';

  interface OutlineEntry {
    title: string;
    page: number | null;
    y: number | null;
    children: OutlineEntry[];
  }

  interface Props {
    filePath: string;
    currentPage: number;
    totalPages: number;
    onNavigateToPage: (page: number) => void;
    onFocusOnResult?: (page: number, normalizedY: number) => void;
    fileReloadVersion?: number;
  }

  let {
    filePath,
    currentPage,
    totalPages,
    onNavigateToPage,
    onFocusOnResult,
    fileReloadVersion = 0
  }: Props = $props();

  // PDF Outlines state
  let outlines = $state<OutlineEntry[]>([]);
  let isLoadingOutlines = $state(true);
  let outlineError = $state<string | null>(null);
  let expandedItems = $state<Set<string>>(new Set());

  // User bookmarks state
  let userBookmarks = $state<UserBookmark[]>([]);
  let isLoadingBookmarks = $state(true);
  let editingBookmarkId = $state<string | null>(null);
  let editingTitle = $state('');

  // Section visibility
  let outlinesExpanded = $state(true);
  let bookmarksExpanded = $state(true);

  // Load both outlines and bookmarks when file changes
  $effect(() => {
    if (filePath) {
      const _ = fileReloadVersion;
      loadOutlines();
      loadUserBookmarks();
    }
  });

  async function loadOutlines() {
    if (!filePath) return;

    isLoadingOutlines = true;
    outlineError = null;

    try {
      const result = await invoke<OutlineEntry[]>('pdf_get_outlines', { path: filePath });
      outlines = result;
      // Auto-expand first level
      expandedItems = new Set();
      outlines.forEach((_, index) => {
        expandedItems.add(`0-${index}`);
      });
    } catch (e) {
      console.error('[BookmarksTab] Failed to load outlines:', e);
      outlineError = e instanceof Error ? e.message : String(e);
      outlines = [];
    } finally {
      isLoadingOutlines = false;
    }
  }

  async function loadUserBookmarks() {
    if (!filePath) return;

    isLoadingBookmarks = true;
    try {
      await ensureLoaded();
      userBookmarks = getBookmarksForFile(filePath);
    } catch (e) {
      console.error('[BookmarksTab] Failed to load user bookmarks:', e);
      userBookmarks = [];
    } finally {
      isLoadingBookmarks = false;
    }
  }

  function toggleOutlineExpand(path: string) {
    if (expandedItems.has(path)) {
      expandedItems.delete(path);
    } else {
      expandedItems.add(path);
    }
    expandedItems = new Set(expandedItems);
  }

  function handleOutlineClick(entry: OutlineEntry) {
    if (entry.page !== null) {
      if (entry.y !== null && onFocusOnResult) {
        onFocusOnResult(entry.page, entry.y);
      } else {
        onNavigateToPage(entry.page);
      }
    }
  }

  function handleBookmarkClick(bookmark: UserBookmark) {
    if (bookmark.y !== undefined && onFocusOnResult) {
      onFocusOnResult(bookmark.page, bookmark.y);
    } else {
      onNavigateToPage(bookmark.page);
    }
  }

  async function handleAddBookmark() {
    try {
      const newBookmark = await addBookmark(filePath, currentPage);
      userBookmarks = getBookmarksForFile(filePath);
      // Start editing the new bookmark
      editingBookmarkId = newBookmark.id;
      editingTitle = newBookmark.title;
    } catch (e) {
      console.error('[BookmarksTab] Failed to add bookmark:', e);
    }
  }

  function startEditing(bookmark: UserBookmark) {
    editingBookmarkId = bookmark.id;
    editingTitle = bookmark.title;
  }

  async function saveEditing() {
    if (!editingBookmarkId || !editingTitle.trim()) return;

    try {
      await updateBookmark(filePath, editingBookmarkId, { title: editingTitle.trim() });
      userBookmarks = getBookmarksForFile(filePath);
    } catch (e) {
      console.error('[BookmarksTab] Failed to update bookmark:', e);
    } finally {
      editingBookmarkId = null;
      editingTitle = '';
    }
  }

  function cancelEditing() {
    editingBookmarkId = null;
    editingTitle = '';
  }

  async function handleDeleteBookmark(bookmarkId: string) {
    try {
      await deleteBookmark(filePath, bookmarkId);
      userBookmarks = getBookmarksForFile(filePath);
    } catch (e) {
      console.error('[BookmarksTab] Failed to delete bookmark:', e);
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      saveEditing();
    } else if (e.key === 'Escape') {
      cancelEditing();
    }
  }

  function countOutlineItems(entries: OutlineEntry[]): number {
    return entries.reduce((count, entry) => {
      return count + 1 + countOutlineItems(entry.children);
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
            onclick={() => toggleOutlineExpand(path)}
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
          onclick={() => handleOutlineClick(entry)}
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
  <div class="content">
    <!-- User Bookmarks Section -->
    <div class="section">
      <div class="section-header">
        <button
          class="section-toggle-btn"
          onclick={() => bookmarksExpanded = !bookmarksExpanded}
        >
          <span class="section-toggle">
            {#if bookmarksExpanded}
              <ChevronDown size={14} />
            {:else}
              <ChevronRight size={14} />
            {/if}
          </span>
          <Bookmark size={14} class="section-icon" />
          <span class="section-title">Bookmarks</span>
          {#if userBookmarks.length > 0}
            <span class="count">{userBookmarks.length}</span>
          {/if}
        </button>
        <button
          class="add-btn"
          onclick={handleAddBookmark}
          title="Add bookmark for current page"
        >
          <Plus size={14} />
        </button>
      </div>

      {#if bookmarksExpanded}
        <div class="section-content">
          {#if isLoadingBookmarks}
            <div class="loading-inline">
              <Loader2 size={16} class="spinner" />
              <span>Loading...</span>
            </div>
          {:else if userBookmarks.length === 0}
            <div class="empty-section">
              <p>No bookmarks yet</p>
              <button class="add-bookmark-btn" onclick={handleAddBookmark}>
                <Plus size={14} />
                <span>Add bookmark</span>
              </button>
            </div>
          {:else}
            <div class="bookmark-list">
              {#each userBookmarks as bookmark (bookmark.id)}
                <div class="bookmark-item" class:active={bookmark.page === currentPage}>
                  {#if editingBookmarkId === bookmark.id}
                    <div class="bookmark-edit">
                      <input
                        type="text"
                        bind:value={editingTitle}
                        onkeydown={handleKeydown}
                        class="edit-input"
                        autofocus
                      />
                      <button class="edit-action save" onclick={saveEditing} title="Save">
                        <Check size={14} />
                      </button>
                      <button class="edit-action cancel" onclick={cancelEditing} title="Cancel">
                        <X size={14} />
                      </button>
                    </div>
                  {:else}
                    <button
                      class="bookmark-button"
                      onclick={() => handleBookmarkClick(bookmark)}
                      title={`Go to page ${bookmark.page}`}
                    >
                      <Bookmark size={14} class="bookmark-icon" />
                      <span class="bookmark-title">{bookmark.title}</span>
                      <span class="page-number">{bookmark.page}</span>
                    </button>
                    <div class="bookmark-actions">
                      <button
                        class="action-btn"
                        onclick={(e) => { e.stopPropagation(); startEditing(bookmark); }}
                        title="Edit"
                      >
                        <Pencil size={12} />
                      </button>
                      <button
                        class="action-btn delete"
                        onclick={(e) => { e.stopPropagation(); handleDeleteBookmark(bookmark.id); }}
                        title="Delete"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- PDF Outlines Section -->
    <div class="section">
      <div class="section-header">
        <button
          class="section-toggle-btn"
          onclick={() => outlinesExpanded = !outlinesExpanded}
        >
          <span class="section-toggle">
            {#if outlinesExpanded}
              <ChevronDown size={14} />
            {:else}
              <ChevronRight size={14} />
            {/if}
          </span>
          <BookMarked size={14} class="section-icon" />
          <span class="section-title">Table of Contents</span>
          {#if outlines.length > 0}
            <span class="count">{countOutlineItems(outlines)}</span>
          {/if}
        </button>
      </div>

      {#if outlinesExpanded}
        <div class="section-content">
          {#if isLoadingOutlines}
            <div class="loading-inline">
              <Loader2 size={16} class="spinner" />
              <span>Loading...</span>
            </div>
          {:else if outlineError}
            <div class="error-inline">
              <FileText size={16} />
              <span>Failed to load</span>
            </div>
          {:else if outlines.length === 0}
            <div class="empty-section">
              <p>No table of contents</p>
            </div>
          {:else}
            <div class="outline-list">
              {@render outlineTree(outlines, 0, '0')}
            </div>
          {/if}
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .bookmarks-tab {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .content {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
  }

  /* Section styles */
  .section {
    border-bottom: 1px solid var(--nord2);
  }

  .section-header {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding-right: 0.5rem;
  }

  .section-header:hover {
    background-color: var(--nord2);
  }

  .section-toggle-btn {
    display: flex;
    align-items: center;
    flex: 1;
    padding: 0.625rem 0.75rem;
    background: transparent;
    border: none;
    color: var(--nord4);
    cursor: pointer;
    gap: 0.375rem;
  }

  .section-toggle {
    display: flex;
    align-items: center;
    opacity: 0.5;
  }

  .section-toggle-btn :global(.section-icon) {
    opacity: 0.6;
  }

  .section-title {
    flex: 1;
    font-size: 0.75rem;
    text-transform: uppercase;
    text-align: left;
    opacity: 0.8;
  }

  .count {
    font-size: 0.65rem;
    padding: 0.125rem 0.375rem;
    background-color: var(--nord3);
    border-radius: 0.25rem;
    color: var(--nord5);
  }

  .add-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    background: transparent;
    border: none;
    border-radius: 4px;
    color: var(--nord4);
    cursor: pointer;
    opacity: 0.6;
    transition: all 0.1s;
    flex-shrink: 0;
  }

  .add-btn:hover {
    opacity: 1;
    background-color: var(--nord8);
    color: var(--nord0);
  }

  .section-content {
    padding: 0.25rem 0;
  }

  /* Loading and empty states */
  .loading-inline,
  .error-inline,
  .empty-section {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 1rem;
    color: var(--nord4);
    opacity: 0.5;
    font-size: 0.75rem;
  }

  .empty-section {
    flex-direction: column;
    gap: 0.75rem;
  }

  .loading-inline :global(.spinner) {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .add-bookmark-btn {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    background-color: var(--nord3);
    border: none;
    border-radius: 4px;
    color: var(--nord5);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.1s;
  }

  .add-bookmark-btn:hover {
    background-color: var(--nord8);
    color: var(--nord0);
  }

  /* Bookmark list */
  .bookmark-list {
    padding: 0 0.25rem;
  }

  .bookmark-item {
    display: flex;
    align-items: center;
    margin: 0.125rem 0;
    border-radius: 4px;
  }

  .bookmark-item:hover,
  .bookmark-item.active {
    background-color: var(--nord2);
  }

  .bookmark-item:hover .bookmark-actions {
    opacity: 1;
  }

  .bookmark-button {
    display: flex;
    align-items: center;
    flex: 1;
    min-width: 0;
    padding: 0.375rem 0.5rem;
    background: transparent;
    border: none;
    color: var(--nord4);
    font-size: 0.8125rem;
    text-align: left;
    cursor: pointer;
    gap: 0.375rem;
    transition: color 0.1s;
  }

  .bookmark-button:hover {
    color: var(--nord8);
  }

  .bookmark-button :global(.bookmark-icon) {
    flex-shrink: 0;
    opacity: 0.6;
  }

  .bookmark-title {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .bookmark-actions {
    display: flex;
    gap: 0.125rem;
    padding-right: 0.375rem;
    opacity: 0;
    transition: opacity 0.1s;
  }

  .action-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    background: transparent;
    border: none;
    border-radius: 3px;
    color: var(--nord4);
    cursor: pointer;
    transition: all 0.1s;
  }

  .action-btn:hover {
    background-color: var(--nord3);
    color: var(--nord6);
  }

  .action-btn.delete:hover {
    background-color: var(--nord11);
    color: var(--nord6);
  }

  /* Bookmark editing */
  .bookmark-edit {
    display: flex;
    align-items: center;
    flex: 1;
    padding: 0.25rem 0.375rem;
    gap: 0.25rem;
  }

  .edit-input {
    flex: 1;
    padding: 0.25rem 0.375rem;
    background-color: var(--nord0);
    border: 1px solid var(--nord3);
    border-radius: 4px;
    color: var(--nord6);
    font-size: 0.8125rem;
    outline: none;
  }

  .edit-input:focus {
    border-color: var(--nord8);
  }

  .edit-action {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    background: transparent;
    border: none;
    border-radius: 3px;
    color: var(--nord4);
    cursor: pointer;
    transition: all 0.1s;
  }

  .edit-action.save:hover {
    background-color: var(--nord14);
    color: var(--nord0);
  }

  .edit-action.cancel:hover {
    background-color: var(--nord11);
    color: var(--nord6);
  }

  /* Outline list styles */
  .outline-list {
    padding: 0 0.25rem;
  }

  .outline-item {
    padding-left: calc(var(--depth) * 0.75rem);
  }

  .outline-row {
    display: flex;
    align-items: center;
    gap: 0.125rem;
    border-radius: 4px;
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

  .outline-button:hover .page-number,
  .bookmark-button:hover .page-number {
    opacity: 1;
    background-color: var(--nord3);
  }
</style>
