<script lang="ts">
  import { LayoutList, MessageSquare, Bookmark, Search, Info, ChevronRight, ChevronLeft } from 'lucide-svelte';
  import type { AnnotationsStore } from '$lib/stores/annotations.svelte';
  import PagesTab from './sidebar/PagesTab.svelte';
  import AnnotationsTab from './sidebar/AnnotationsTab.svelte';
  import BookmarksTab from './sidebar/BookmarksTab.svelte';
  import SearchTab from './sidebar/SearchTab.svelte';
  import MetadataTab from './sidebar/MetadataTab.svelte';

  interface RenderedPage {
    data: string;
    width: number;
    height: number;
    page: number;
  }

  interface Props {
    filePath: string;
    currentPage: number;
    totalPages: number;
    annotationsStore: AnnotationsStore;
    loadedThumbnails: Map<number, RenderedPage>;
    loadingThumbnails: Set<number>;
    onNavigateToPage: (page: number) => void;
    onFocusOnResult?: (page: number, normalizedY: number) => void;
    onLoadThumbnail: (page: number) => void;
    onThumbnailScroll: () => void;
    onFileReload?: () => void;
    onRunOcr?: () => void; // Callback to trigger OCR with splash notification
    fileReloadVersion?: number; // Incremented when file is reloaded (e.g., after OCR)
    searchTrigger?: { text: string; timestamp: number } | null;
    onSearchStateChange?: (query: string, currentPage: number, currentIndex: number) => void;
  }

  let {
    filePath,
    currentPage,
    totalPages,
    annotationsStore,
    loadedThumbnails,
    loadingThumbnails,
    onNavigateToPage,
    onFocusOnResult,
    onLoadThumbnail,
    onThumbnailScroll,
    onFileReload,
    onRunOcr,
    fileReloadVersion = 0,
    searchTrigger = null,
    onSearchStateChange,
  }: Props = $props();

  // State for passing search query to SearchTab
  let externalSearchQuery = $state('');

  type TabId = 'pages' | 'annotations' | 'bookmarks' | 'search' | 'info';

  let activeTab = $state<TabId>('pages');
  let isCollapsed = $state(false);

  const tabs: { id: TabId; icon: typeof LayoutList; label: string }[] = [
    { id: 'pages', icon: LayoutList, label: 'Pages' },
    { id: 'annotations', icon: MessageSquare, label: 'Annotations' },
    { id: 'bookmarks', icon: Bookmark, label: 'Bookmarks' },
    { id: 'search', icon: Search, label: 'Search' },
    { id: 'info', icon: Info, label: 'Document Info' },
  ];

  function handleTabClick(tabId: TabId) {
    if (isCollapsed) {
      isCollapsed = false;
    }
    activeTab = tabId;
  }

  function toggleCollapse() {
    isCollapsed = !isCollapsed;
  }

  // React to external search trigger
  let lastSearchTimestamp = 0;
  $effect(() => {
    if (searchTrigger && searchTrigger.timestamp !== lastSearchTimestamp) {
      lastSearchTimestamp = searchTrigger.timestamp;
      // Switch to search tab and set query
      activeTab = 'search';
      isCollapsed = false;
      externalSearchQuery = searchTrigger.text;
    }
  });
</script>

<div class="sidebar" class:collapsed={isCollapsed}>
  <!-- Tab Content Area -->
  {#if !isCollapsed}
    <div class="tab-content">
      {#if activeTab === 'pages'}
        <PagesTab
          {currentPage}
          {totalPages}
          {loadedThumbnails}
          {loadingThumbnails}
          {fileReloadVersion}
          {onNavigateToPage}
          {onLoadThumbnail}
          {onThumbnailScroll}
        />
      {:else if activeTab === 'annotations'}
        <AnnotationsTab
          store={annotationsStore}
          {onNavigateToPage}
        />
      {:else if activeTab === 'bookmarks'}
        <BookmarksTab
          {filePath}
          {currentPage}
          {totalPages}
          {fileReloadVersion}
          {onNavigateToPage}
          {onFocusOnResult}
        />
      {:else if activeTab === 'search'}
        <SearchTab
          {filePath}
          {fileReloadVersion}
          {onNavigateToPage}
          {onFocusOnResult}
          {onFileReload}
          {onRunOcr}
          {externalSearchQuery}
          {onSearchStateChange}
        />
      {:else if activeTab === 'info'}
        <MetadataTab
          {filePath}
          {fileReloadVersion}
        />
      {/if}
    </div>
  {/if}

  <!-- Tab Bar -->
  <div class="tab-bar">
    <!-- Collapse Toggle -->
    <button
      class="collapse-btn"
      onclick={toggleCollapse}
      title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
    >
      {#if isCollapsed}
        <ChevronLeft size={16} />
      {:else}
        <ChevronRight size={16} />
      {/if}
    </button>

    <!-- Tab Buttons -->
    <div class="tabs">
      {#each tabs as tab (tab.id)}
        <button
          class="tab-btn"
          class:active={activeTab === tab.id && !isCollapsed}
          onclick={() => handleTabClick(tab.id)}
          title={tab.label}
        >
          <tab.icon size={18} />
        </button>
      {/each}
    </div>
  </div>
</div>

<style>
  .sidebar {
    display: flex;
    height: 100%;
    background-color: var(--nord1);
    border-left: 1px solid var(--nord3);
    transition: width 0.2s ease;
  }

  .sidebar:not(.collapsed) {
    width: 280px;
  }

  .sidebar.collapsed {
    width: 40px;
  }

  .tab-content {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .tab-bar {
    display: flex;
    flex-direction: column;
    width: 40px;
    background-color: var(--nord0);
    border-left: 1px solid var(--nord3);
  }

  .collapse-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 32px;
    background: transparent;
    border: none;
    color: var(--nord4);
    cursor: pointer;
    transition: all 0.15s;
  }

  .collapse-btn:hover {
    background-color: var(--nord2);
    color: var(--nord6);
  }

  .tabs {
    display: flex;
    flex-direction: column;
    flex: 1;
    padding-top: 0.5rem;
    gap: 0.25rem;
  }

  .tab-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    color: var(--nord4);
    cursor: pointer;
    transition: all 0.15s;
  }

  .tab-btn:hover {
    background-color: var(--nord2);
    color: var(--nord6);
  }

  .tab-btn.active {
    background-color: var(--nord2);
    color: var(--nord8);
    border-left-color: var(--nord8);
  }
</style>
