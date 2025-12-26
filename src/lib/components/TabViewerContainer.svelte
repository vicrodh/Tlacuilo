<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { open, save, confirm as tauriConfirm } from '@tauri-apps/plugin-dialog';
  import { copyFile } from '@tauri-apps/plugin-fs';
  import { FolderOpen, FileText } from 'lucide-svelte';
  import { MuPDFViewer } from '$lib/components/PDFViewer';
  import TabBar from './TabBar.svelte';
  import { getGlobalTabsStore, type TabsStore, type TabState } from '$lib/stores/tabs.svelte';
  import { registerFile, consumePendingOpenFile } from '$lib/stores/status.svelte';
  // import { useTranslations } from '$lib/i18n'; // Disabled for debugging

  interface Props {
    visible: boolean;
  }

  let { visible }: Props = $props();

  const MODULE = 'Viewer';
  const tabsStore = getGlobalTabsStore();

  // Temporarily use static strings to test if $derived causes the loop
  const t = {
    viewer: {
      title: 'PDF Viewer',
      description: 'Open a PDF to view, annotate, and edit.',
      openPdf: 'Open PDF'
    }
  };

  // Handle pending file from app menu
  function handlePendingFileReady() {
    const pending = consumePendingOpenFile();
    if (pending) {
      openFileInNewTab(pending);
    }
  }

  // Handle open-pdf-file event from MuPDFViewer toolbar
  function handleOpenPdfFile(e: CustomEvent<{ path: string; replaceTab?: string; autoAnalyzeFonts?: boolean }>) {
    if (e.detail.path) {
      if (e.detail.replaceTab) {
        // Replace the specified tab's file (used for OCR'd versions)
        console.log('[TabContainer] Replacing tab file:', e.detail.replaceTab, 'with:', e.detail.path, 'autoAnalyzeFonts:', e.detail.autoAnalyzeFonts);
        tabsStore.setTabFile(e.detail.replaceTab, e.detail.path, { autoAnalyzeFonts: e.detail.autoAnalyzeFonts });
      } else {
        // Open in new tab
        openFileInNewTab(e.detail.path);
      }
    }
  }

  // Global keyboard shortcuts for tabs
  function handleKeyDown(e: KeyboardEvent) {
    // Only handle when visible
    if (!visible) return;

    // Ctrl+T: New tab
    if (e.ctrlKey && !e.shiftKey && e.key === 't') {
      e.preventDefault();
      e.stopPropagation();
      tabsStore.createTab();
      return;
    }

    // Ctrl+W: Close current tab
    if (e.ctrlKey && !e.shiftKey && e.key === 'w') {
      e.preventDefault();
      e.stopPropagation();
      const activeTab = tabsStore.activeTab;
      if (activeTab) {
        handleCloseTab(activeTab.id);
      }
      return;
    }

    // Ctrl+Shift+T: Reopen last closed tab
    if (e.ctrlKey && e.shiftKey && e.key === 'T') {
      e.preventDefault();
      e.stopPropagation();
      if (tabsStore.canReopenTab) {
        tabsStore.reopenLastClosedTab();
      }
      return;
    }

    // Ctrl+Tab: Next tab
    if (e.ctrlKey && !e.shiftKey && e.key === 'Tab') {
      e.preventDefault();
      e.stopPropagation();
      tabsStore.nextTab();
      return;
    }

    // Ctrl+Shift+Tab: Previous tab
    if (e.ctrlKey && e.shiftKey && e.key === 'Tab') {
      e.preventDefault();
      e.stopPropagation();
      tabsStore.prevTab();
      return;
    }

    // Ctrl+1-9: Switch to tab by index
    if (e.ctrlKey && !e.shiftKey && e.key >= '1' && e.key <= '9') {
      e.preventDefault();
      e.stopPropagation();
      tabsStore.switchToTabIndex(parseInt(e.key));
      return;
    }
  }

  // Check for pending file on mount
  onMount(() => {
    const pending = consumePendingOpenFile();
    if (pending) {
      openFileInNewTab(pending);
    } else if (tabsStore.tabCount === 0) {
      // Create an initial empty tab if no tabs exist
      tabsStore.createTab();
    }

    // Global keyboard shortcuts
    window.addEventListener('keydown', handleKeyDown, true);
    // Listen for pending file from app menu
    window.addEventListener('pending-file-ready', handlePendingFileReady);
    // Listen for open-pdf-file event from MuPDFViewer toolbar
    window.addEventListener('open-pdf-file', handleOpenPdfFile as EventListener);
  });

  onDestroy(() => {
    window.removeEventListener('keydown', handleKeyDown, true);
    window.removeEventListener('pending-file-ready', handlePendingFileReady);
    window.removeEventListener('open-pdf-file', handleOpenPdfFile as EventListener);
  });

  function openFileInNewTab(filePath: string) {
    const fileName = filePath.split('/').pop() || 'Document';
    tabsStore.createTab(filePath);
    registerFile(filePath, fileName, MODULE);
  }

  async function handleOpenFile(tabId?: string) {
    try {
      const selected = await open({
        multiple: false,
        filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
      });

      if (selected && typeof selected === 'string') {
        if (tabId) {
          // Open in existing empty tab
          tabsStore.setTabFile(tabId, selected);
          const fileName = selected.split('/').pop() || 'Document';
          registerFile(selected, fileName, MODULE);
        } else {
          // Open in new tab
          openFileInNewTab(selected);
        }
      }
    } catch (err) {
      console.error('[TabViewerContainer] File dialog error:', err);
    }
  }

  function handleNewTab() {
    tabsStore.createTab();
  }

  async function handleCloseTab(tabId: string) {
    const tab = tabsStore.getTab(tabId);
    if (!tab) return;

    if (tab.annotationsDirty) {
      const confirmed = await tauriConfirm(
        `"${tab.fileName}" has unsaved changes. Close anyway?`,
        {
          title: 'Unsaved Changes',
          kind: 'warning',
          okLabel: 'Close',
          cancelLabel: 'Cancel',
        }
      );

      if (!confirmed) return;
    }

    tabsStore.closeTab(tabId, true);

    // Create a new empty tab if all tabs are closed
    if (tabsStore.tabCount === 0) {
      tabsStore.createTab();
    }
  }

  function handleTabClick(tabId: string) {
    tabsStore.switchTab(tabId);
  }

  function handleTabClose(tabId: string) {
    const tab = tabsStore.getTab(tabId);
    if (!tab) return;

    // Clear file from tab
    tab.filePath = null;
    tab.fileName = 'New Tab';
    tab.documentLoaded = false;
    tab.documentError = null;
  }

  async function handleTabSave(tabId: string) {
    const tab = tabsStore.getTab(tabId);
    if (!tab?.filePath || !tab.annotationsDirty) return;

    // Save logic will be handled by MuPDFViewer
    console.log('Save requested for tab:', tabId);
  }

  async function handleTabSaveAs(tabId: string) {
    const tab = tabsStore.getTab(tabId);
    if (!tab?.filePath) return;

    try {
      const savePath = await save({
        filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
        defaultPath: tab.fileName,
      });

      if (savePath) {
        await copyFile(tab.filePath, savePath);
        tabsStore.setTabFile(tabId, savePath);
        const fileName = savePath.split('/').pop() || 'Document';
        registerFile(savePath, fileName, MODULE);
        console.log('File saved as:', savePath);
      }
    } catch (err) {
      console.error('Failed to save file:', err);
    }
  }

  function handleAnnotationsDirtyChange(tabId: string, dirty: boolean) {
    tabsStore.setTabDirty(tabId, dirty);
  }
</script>

<div class="tab-viewer-container" class:hidden={!visible}>
  <TabBar
    {tabsStore}
    onNewTab={handleNewTab}
    onCloseTab={handleCloseTab}
    onTabClick={handleTabClick}
  />

  <div class="tabs-content">
    {#each tabsStore.tabs as tab (tab.id)}
      <div
        class="tab-panel"
        class:active={tab.id === tabsStore.activeTabId}
      >
        {#if tab.filePath}
          <MuPDFViewer
            filePath={tab.filePath}
            tabId={tab.id}
            isActive={tab.id === tabsStore.activeTabId && visible}
            onClose={() => handleTabClose(tab.id)}
            onSave={() => handleTabSave(tab.id)}
            onSaveAs={() => handleTabSaveAs(tab.id)}
            onAnnotationsDirtyChange={(dirty) => handleAnnotationsDirtyChange(tab.id, dirty)}
            autoAnalyzeFonts={tab.autoAnalyzeFonts}
          />
        {:else}
          <!-- Empty tab state -->
          <div class="empty-state">
            <div class="empty-state-card">
              <div class="empty-state-icon">
                <FileText size={40} style="color: var(--nord8);" />
              </div>

              <div class="empty-state-text">
                <h2>{t.viewer.title}</h2>
                <p>{t.viewer.description}</p>
              </div>

              <button
                onclick={() => handleOpenFile(tab.id)}
                class="open-file-btn"
              >
                <FolderOpen size={20} />
                <span>{t.viewer.openPdf}</span>
              </button>

              <p class="empty-state-hint">
                Supports PDF files up to 100MB
              </p>
            </div>
          </div>
        {/if}
      </div>
    {/each}
  </div>
</div>

<style>
  .tab-viewer-container {
    display: flex;
    flex-direction: column;
    flex: 1;
    overflow: hidden;
    background-color: var(--nord0);
  }

  .tab-viewer-container.hidden {
    display: none;
  }

  .tabs-content {
    flex: 1;
    position: relative;
    overflow: hidden;
  }

  .tab-panel {
    position: absolute;
    inset: 0;
    display: none;
    flex-direction: column;
    overflow: hidden;
  }

  .tab-panel.active {
    display: flex;
  }

  .empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background-color: var(--nord0);
  }

  .empty-state-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1.5rem;
    padding: 3rem;
    border-radius: 1rem;
    background-color: var(--nord1);
  }

  .empty-state-icon {
    width: 5rem;
    height: 5rem;
    border-radius: 1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--nord2);
  }

  .empty-state-text {
    text-align: center;
  }

  .empty-state-text h2 {
    font-size: 1.25rem;
    margin-bottom: 0.5rem;
    color: var(--nord6);
  }

  .empty-state-text p {
    font-size: 0.875rem;
    opacity: 0.6;
    max-width: 16rem;
  }

  .open-file-btn {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1.5rem;
    border-radius: 0.75rem;
    background-color: var(--nord8);
    color: var(--nord0);
    border: none;
    cursor: pointer;
    font-weight: 500;
    transition: transform 0.15s ease;
  }

  .open-file-btn:hover {
    transform: scale(1.02);
  }

  .open-file-btn:active {
    transform: scale(0.98);
  }

  .empty-state-hint {
    font-size: 0.75rem;
    opacity: 0.4;
  }
</style>
