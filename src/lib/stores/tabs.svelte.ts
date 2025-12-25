/**
 * Tabs Store
 *
 * Manages multiple PDF viewer tabs with state persistence and resource optimization.
 * Each tab maintains its own viewer state and annotations.
 */

import { getContext, setContext } from 'svelte';
import { createAnnotationsStore, type AnnotationsStore } from './annotations.svelte';

// Maximum number of open tabs
const MAX_TABS = 10;

// Maximum number of tabs to keep "active" (with loaded pages in memory)
const MAX_ACTIVE_TABS = 3;

// Recently closed tabs cache (for Ctrl+Shift+T restore)
const RECENTLY_CLOSED_MAX = 5;
const RECENTLY_CLOSED_TTL = 2 * 60 * 1000; // 2 minutes

interface RecentlyClosedTab {
  filePath: string;
  fileName: string;
  closedAt: number;
}

export interface RenderedPage {
  pageNum: number;
  base64: string;
  width: number;
  height: number;
}

export interface TabState {
  id: string;
  filePath: string | null;      // null = empty tab
  fileName: string;

  // Viewer state
  currentPage: number;
  totalPages: number;
  zoom: number;
  rotation: number;
  scrollPosition: number;       // Preserve scroll position

  // Annotations
  annotationsStore: AnnotationsStore;
  annotationsDirty: boolean;

  // UI state
  showAnnotationTools: boolean;
  sidebarCollapsed: boolean;

  // Resource management
  isActive: boolean;            // Currently focused tab
  isSuspended: boolean;         // Resources cleared to save memory
  loadedPages: Map<number, RenderedPage>;
  loadedThumbnails: Map<number, RenderedPage>;

  // Document state
  documentLoaded: boolean;
  documentError: string | null;
}

const TABS_KEY = Symbol('tabs');

function generateTabId(): string {
  return `tab-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

function getFileNameFromPath(path: string): string {
  const parts = path.split('/');
  return parts[parts.length - 1] || 'Untitled';
}

export function createTabsStore() {
  // Core state
  let tabs = $state<TabState[]>([]);
  let activeTabId = $state<string | null>(null);

  // LRU tracking for resource management
  let tabAccessOrder: string[] = [];

  // Recently closed tabs (for restore functionality)
  let recentlyClosed = $state<RecentlyClosedTab[]>([]);

  // Clean up expired entries periodically
  function cleanupRecentlyClosed() {
    const now = Date.now();
    recentlyClosed = recentlyClosed.filter(t => (now - t.closedAt) < RECENTLY_CLOSED_TTL);
  }

  // Add to recently closed
  function addToRecentlyClosed(filePath: string, fileName: string) {
    cleanupRecentlyClosed();

    // Don't add duplicates
    recentlyClosed = recentlyClosed.filter(t => t.filePath !== filePath);

    // Add new entry
    recentlyClosed = [
      { filePath, fileName, closedAt: Date.now() },
      ...recentlyClosed,
    ].slice(0, RECENTLY_CLOSED_MAX);
  }

  function updateLRU(tabId: string) {
    tabAccessOrder = tabAccessOrder.filter(id => id !== tabId);
    tabAccessOrder.push(tabId);

    // Suspend old tabs if we have too many active
    if (tabAccessOrder.length > MAX_ACTIVE_TABS) {
      const tabsToSuspend = tabAccessOrder.slice(0, -MAX_ACTIVE_TABS);
      tabsToSuspend.forEach(id => {
        const tab = tabs.find(t => t.id === id);
        if (tab && !tab.isSuspended) {
          suspendTab(id);
        }
      });
    }
  }

  function createEmptyTabState(id: string): TabState {
    return {
      id,
      filePath: null,
      fileName: 'New Tab',
      currentPage: 1,
      totalPages: 0,
      zoom: 1,
      rotation: 0,
      scrollPosition: 0,
      annotationsStore: createAnnotationsStore(),
      annotationsDirty: false,
      showAnnotationTools: false,
      sidebarCollapsed: false,
      isActive: false,
      isSuspended: false,
      loadedPages: new Map(),
      loadedThumbnails: new Map(),
      documentLoaded: false,
      documentError: null,
    };
  }

  /**
   * Create a new tab (empty or with file)
   */
  function createTab(filePath?: string): string {
    if (tabs.length >= MAX_TABS) {
      console.warn(`Maximum number of tabs (${MAX_TABS}) reached`);
      return activeTabId || '';
    }

    // Check if file is already open
    if (filePath) {
      const existingTab = tabs.find(t => t.filePath === filePath);
      if (existingTab) {
        switchTab(existingTab.id);
        return existingTab.id;
      }
    }

    const id = generateTabId();
    const newTab = createEmptyTabState(id);

    if (filePath) {
      newTab.filePath = filePath;
      newTab.fileName = getFileNameFromPath(filePath);
    }

    tabs = [...tabs, newTab];
    switchTab(id);

    return id;
  }

  /**
   * Close a tab (returns false if cancelled due to unsaved changes)
   */
  function closeTab(tabId: string, force = false): boolean {
    const tabIndex = tabs.findIndex(t => t.id === tabId);
    if (tabIndex === -1) return true;

    const tab = tabs[tabIndex];

    // Check for unsaved changes (unless forced)
    if (!force && tab.annotationsDirty) {
      // This will be handled by the UI component showing a confirmation dialog
      return false;
    }

    // Save to recently closed if it has a file
    if (tab.filePath) {
      addToRecentlyClosed(tab.filePath, tab.fileName);
    }

    // Remove from LRU
    tabAccessOrder = tabAccessOrder.filter(id => id !== tabId);

    // Remove tab
    tabs = tabs.filter(t => t.id !== tabId);

    // If this was the active tab, switch to another
    if (activeTabId === tabId) {
      if (tabs.length > 0) {
        // Switch to the tab that was at the same index, or the last tab
        const newIndex = Math.min(tabIndex, tabs.length - 1);
        switchTab(tabs[newIndex].id);
      } else {
        activeTabId = null;
      }
    }

    return true;
  }

  /**
   * Reopen the most recently closed tab
   */
  function reopenLastClosedTab(): string | null {
    cleanupRecentlyClosed();

    if (recentlyClosed.length === 0) return null;

    const [lastClosed, ...rest] = recentlyClosed;
    recentlyClosed = rest;

    // Open the tab
    return createTab(lastClosed.filePath);
  }

  /**
   * Switch to a tab
   */
  function switchTab(tabId: string): void {
    const tab = tabs.find(t => t.id === tabId);
    if (!tab) return;

    // Deactivate previous tab
    if (activeTabId && activeTabId !== tabId) {
      const prevTab = tabs.find(t => t.id === activeTabId);
      if (prevTab) {
        prevTab.isActive = false;
      }
    }

    // Activate new tab
    tab.isActive = true;
    activeTabId = tabId;

    // Resume if suspended
    if (tab.isSuspended) {
      resumeTab(tabId);
    }

    // Update LRU
    updateLRU(tabId);

    // Trigger reactivity
    tabs = [...tabs];
  }

  /**
   * Suspend a tab to free memory (clear loaded pages)
   */
  function suspendTab(tabId: string): void {
    const tab = tabs.find(t => t.id === tabId);
    if (!tab || tab.isSuspended) return;

    // Clear rendered pages and thumbnails
    tab.loadedPages.clear();
    tab.loadedThumbnails.clear();
    tab.isSuspended = true;

    // Trigger reactivity
    tabs = [...tabs];

    console.log(`Tab ${tab.fileName} suspended`);
  }

  /**
   * Resume a suspended tab (mark for reload)
   */
  function resumeTab(tabId: string): void {
    const tab = tabs.find(t => t.id === tabId);
    if (!tab || !tab.isSuspended) return;

    tab.isSuspended = false;
    // The actual page loading will be triggered by MuPDFViewer when it detects isActive change

    // Trigger reactivity
    tabs = [...tabs];

    console.log(`Tab ${tab.fileName} resumed`);
  }

  /**
   * Update tab state (used by MuPDFViewer to sync state)
   */
  function updateTabState(tabId: string, updates: Partial<Omit<TabState, 'id' | 'annotationsStore'>>): void {
    const tab = tabs.find(t => t.id === tabId);
    if (!tab) return;

    Object.assign(tab, updates);

    // Trigger reactivity
    tabs = [...tabs];
  }

  /**
   * Mark tab as having unsaved changes
   */
  function setTabDirty(tabId: string, dirty: boolean): void {
    const tab = tabs.find(t => t.id === tabId);
    if (!tab) return;

    tab.annotationsDirty = dirty;
    tabs = [...tabs];
  }

  /**
   * Set the file for a tab (for empty tabs when opening a file)
   */
  function setTabFile(tabId: string, filePath: string): void {
    // Check if file is already open in another tab
    const existingTab = tabs.find(t => t.filePath === filePath && t.id !== tabId);
    if (existingTab) {
      // Close the empty tab and switch to existing
      closeTab(tabId, true);
      switchTab(existingTab.id);
      return;
    }

    const tab = tabs.find(t => t.id === tabId);
    if (!tab) return;

    tab.filePath = filePath;
    tab.fileName = getFileNameFromPath(filePath);
    tab.documentLoaded = false;
    tab.documentError = null;

    tabs = [...tabs];
  }

  /**
   * Get tab by ID
   */
  function getTab(tabId: string): TabState | undefined {
    return tabs.find(t => t.id === tabId);
  }

  /**
   * Get the active tab
   */
  function getActiveTab(): TabState | undefined {
    return tabs.find(t => t.id === activeTabId);
  }

  /**
   * Get all tabs with unsaved changes
   */
  function getUnsavedTabs(): TabState[] {
    return tabs.filter(t => t.annotationsDirty);
  }

  /**
   * Check if there are any unsaved changes
   */
  function hasUnsavedChanges(): boolean {
    return tabs.some(t => t.annotationsDirty);
  }

  /**
   * Navigate to next tab
   */
  function nextTab(): void {
    if (tabs.length <= 1) return;

    const currentIndex = tabs.findIndex(t => t.id === activeTabId);
    const nextIndex = (currentIndex + 1) % tabs.length;
    switchTab(tabs[nextIndex].id);
  }

  /**
   * Navigate to previous tab
   */
  function prevTab(): void {
    if (tabs.length <= 1) return;

    const currentIndex = tabs.findIndex(t => t.id === activeTabId);
    const prevIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    switchTab(tabs[prevIndex].id);
  }

  /**
   * Switch to tab by index (1-based for Ctrl+1-9)
   */
  function switchToTabIndex(index: number): void {
    if (index < 1 || index > tabs.length) return;
    switchTab(tabs[index - 1].id);
  }

  /**
   * Close all tabs (returns false if any have unsaved changes and weren't forced)
   */
  function closeAllTabs(force = false): boolean {
    if (!force && hasUnsavedChanges()) {
      return false;
    }

    tabs = [];
    activeTabId = null;
    tabAccessOrder = [];

    return true;
  }

  /**
   * Store loaded pages for a tab (called from MuPDFViewer)
   */
  function setLoadedPages(tabId: string, pages: Map<number, RenderedPage>): void {
    const tab = tabs.find(t => t.id === tabId);
    if (!tab) return;

    tab.loadedPages = pages;
    // Don't trigger full reactivity for performance
  }

  /**
   * Store loaded thumbnails for a tab (called from MuPDFViewer)
   */
  function setLoadedThumbnails(tabId: string, thumbnails: Map<number, RenderedPage>): void {
    const tab = tabs.find(t => t.id === tabId);
    if (!tab) return;

    tab.loadedThumbnails = thumbnails;
    // Don't trigger full reactivity for performance
  }

  return {
    // Reactive getters
    get tabs() { return tabs; },
    get activeTabId() { return activeTabId; },
    get activeTab() { return getActiveTab(); },
    get tabCount() { return tabs.length; },
    get hasUnsavedChanges() { return hasUnsavedChanges(); },
    get recentlyClosed() { return recentlyClosed; },
    get canReopenTab() { cleanupRecentlyClosed(); return recentlyClosed.length > 0; },

    // Tab operations
    createTab,
    closeTab,
    switchTab,
    suspendTab,
    resumeTab,
    updateTabState,
    setTabDirty,
    setTabFile,
    getTab,
    getActiveTab,
    getUnsavedTabs,
    reopenLastClosedTab,

    // Navigation
    nextTab,
    prevTab,
    switchToTabIndex,

    // Bulk operations
    closeAllTabs,

    // Resource management (for MuPDFViewer)
    setLoadedPages,
    setLoadedThumbnails,
  };
}

export type TabsStore = ReturnType<typeof createTabsStore>;

// Singleton instance for app-wide usage
let globalTabsStore: TabsStore | null = null;

export function getGlobalTabsStore(): TabsStore {
  if (!globalTabsStore) {
    globalTabsStore = createTabsStore();
  }
  return globalTabsStore;
}

// Context-based access (for components that need it)
export function setTabsContext(store: TabsStore) {
  setContext(TABS_KEY, store);
}

export function getTabsContext(): TabsStore {
  return getContext(TABS_KEY);
}
