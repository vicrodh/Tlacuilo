<script lang="ts">
  import { Plus, X, FileText } from 'lucide-svelte';
  import type { TabsStore, TabState } from '$lib/stores/tabs.svelte';

  interface Props {
    tabsStore: TabsStore;
    onNewTab: () => void;
    onCloseTab: (tabId: string) => void;
    onTabClick: (tabId: string) => void;
  }

  let {
    tabsStore,
    onNewTab,
    onCloseTab,
    onTabClick,
  }: Props = $props();

  let draggedTabId: string | null = $state(null);
  let dragOverTabId: string | null = $state(null);

  function handleDragStart(e: DragEvent, tabId: string) {
    draggedTabId = tabId;
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', tabId);
    }
  }

  function handleDragOver(e: DragEvent, tabId: string) {
    e.preventDefault();
    if (draggedTabId && draggedTabId !== tabId) {
      dragOverTabId = tabId;
    }
  }

  function handleDragLeave() {
    dragOverTabId = null;
  }

  function handleDrop(e: DragEvent, targetTabId: string) {
    e.preventDefault();
    // Tab reordering would go here if needed
    draggedTabId = null;
    dragOverTabId = null;
  }

  function handleDragEnd() {
    draggedTabId = null;
    dragOverTabId = null;
  }

  function handleCloseClick(e: MouseEvent, tabId: string) {
    e.stopPropagation();
    onCloseTab(tabId);
  }

  function handleMiddleClick(e: MouseEvent, tabId: string) {
    if (e.button === 1) { // Middle click
      e.preventDefault();
      onCloseTab(tabId);
    }
  }
</script>

<div class="tab-bar">
  <div class="tabs-container">
    {#each tabsStore.tabs as tab (tab.id)}
      <div
        class="tab"
        class:active={tab.id === tabsStore.activeTabId}
        class:dirty={tab.annotationsDirty}
        class:drag-over={dragOverTabId === tab.id}
        class:dragging={draggedTabId === tab.id}
        draggable="true"
        role="tab"
        tabindex="0"
        aria-selected={tab.id === tabsStore.activeTabId}
        onclick={() => onTabClick(tab.id)}
        onkeydown={(e) => e.key === 'Enter' && onTabClick(tab.id)}
        onauxclick={(e) => handleMiddleClick(e, tab.id)}
        ondragstart={(e) => handleDragStart(e, tab.id)}
        ondragover={(e) => handleDragOver(e, tab.id)}
        ondragleave={handleDragLeave}
        ondrop={(e) => handleDrop(e, tab.id)}
        ondragend={handleDragEnd}
        title={tab.filePath || 'New Tab'}
      >
        <span class="tab-icon">
          <FileText size={14} />
        </span>
        <span class="tab-title">
          {#if tab.annotationsDirty}
            <span class="dirty-indicator">*</span>
          {/if}
          {tab.fileName}
        </span>
        <button
          class="close-btn"
          onclick={(e) => handleCloseClick(e, tab.id)}
          title="Close tab"
        >
          <X size={14} />
        </button>
      </div>
    {/each}
  </div>

  <button class="new-tab-btn" onclick={onNewTab} title="New tab (Ctrl+T)">
    <Plus size={16} />
  </button>
</div>

<style>
  .tab-bar {
    display: flex;
    align-items: center;
    background-color: #1a1a1a;
    border-bottom: 1px solid #333;
    height: 36px;
    padding: 0 4px;
    gap: 4px;
    flex-shrink: 0;
    user-select: none;
  }

  .tabs-container {
    display: flex;
    align-items: center;
    gap: 2px;
    flex: 1;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .tabs-container::-webkit-scrollbar {
    display: none;
  }

  .tab {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 8px;
    height: 28px;
    background-color: #252525;
    border: 1px solid transparent;
    border-radius: 6px 6px 0 0;
    color: #888;
    font-size: 12px;
    cursor: pointer;
    min-width: 100px;
    max-width: 200px;
    transition: all 0.15s ease;
    position: relative;
  }

  .tab:hover {
    background-color: #2a2a2a;
    color: #aaa;
  }

  .tab.active {
    background-color: #333;
    color: #fff;
    border-color: #444;
    border-bottom-color: #333;
  }

  .tab.dirty .tab-title {
    font-style: italic;
  }

  .tab.drag-over {
    border-left: 2px solid #4a9eff;
  }

  .tab.dragging {
    opacity: 0.5;
  }

  .tab-icon {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    opacity: 0.6;
  }

  .tab-title {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-align: left;
  }

  .dirty-indicator {
    color: #f59e0b;
    margin-right: 2px;
  }

  .close-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2px;
    background: transparent;
    border: none;
    border-radius: 4px;
    color: #666;
    cursor: pointer;
    opacity: 0;
    transition: all 0.15s ease;
    flex-shrink: 0;
  }

  .tab:hover .close-btn {
    opacity: 1;
  }

  .close-btn:hover {
    background-color: #3a3a3a;
    color: #f44336;
  }

  .tab.dirty .close-btn {
    opacity: 1;
  }

  .new-tab-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: transparent;
    border: none;
    border-radius: 4px;
    color: #666;
    cursor: pointer;
    transition: all 0.15s ease;
    flex-shrink: 0;
  }

  .new-tab-btn:hover {
    background-color: #333;
    color: #fff;
  }
</style>
