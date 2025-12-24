<script lang="ts">
  import { onMount } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';
  import { Search, CheckCircle, AlertTriangle, Loader2, FileText, XCircle, ChevronUp, ChevronDown, X } from 'lucide-svelte';
  import InlineNotification from '../InlineNotification.svelte';
  import { debugLog } from '$lib/stores/debugLog.svelte';

  interface Props {
    filePath: string;
    fileReloadVersion?: number; // Incremented when file is reloaded (e.g., after OCR)
    onNavigateToPage: (page: number) => void;
    onFocusOnResult?: (page: number, normalizedY: number) => void;
    onFileReload?: () => void;
    onRunOcr?: () => void; // Callback to trigger OCR from parent (shows splash)
    externalSearchQuery?: string;
    onSearchStateChange?: (query: string, currentPage: number, currentIndex: number) => void;
  }

  let { filePath, fileReloadVersion = 0, onNavigateToPage, onFocusOnResult, onFileReload, onRunOcr, externalSearchQuery = '', onSearchStateChange }: Props = $props();

  // OCR Analysis result type
  interface OcrAnalysis {
    success: boolean;
    page_count?: number;
    has_text?: boolean;
    has_images?: boolean;
    needs_ocr?: boolean;
    recommendation?: string;
    error?: string;
  }

  // Search result type (frontend)
  interface SearchResult {
    page: number;
    text: string;
    context: string;
    normalizedY: number; // Y position on page (0-1)
  }

  // Native search result from Rust
  interface NativeSearchResult {
    page: number;
    y: number;
    rect: { x: number; y: number; width: number; height: number };
    context: string;
  }

  interface NativeSearchResults {
    query: string;
    total: number;
    results: NativeSearchResult[];
  }

  // State machine
  type SearchStateType = 'idle' | 'analyzing' | 'searchable' | 'needs-ocr' | 'processing-ocr' | 'error';

  let searchState = $state<SearchStateType>('idle');
  let analysisResult = $state<OcrAnalysis | null>(null);
  let errorMessage = $state<string | null>(null);
  let ocrProgress = $state<string>('');

  // Notification dismissal
  let showOcrNotification = $state(true);
  let showSuccessNotification = $state(false);
  let showErrorNotification = $state(true);

  // Search
  let searchQuery = $state('');
  let searchResults = $state<SearchResult[]>([]);
  let isSearching = $state(false);
  let totalPages = $state(0);
  let currentResultIndex = $state(-1);
  let searchTimeout: ReturnType<typeof setTimeout>;
  let currentSearchId = 0; // Used to cancel stale searches
  let searchInProgress = $state(false); // Prevent concurrent searches
  let lastSearchedQuery = ''; // Track what we already searched for
  const SEARCH_DEBOUNCE_MS = 1000; // 1 second delay
  const MIN_QUERY_LENGTH = 3;

  // Cache analysis by file path
  let analysisCache = new Map<string, OcrAnalysis>();

  let lastAnalyzedPath = '';

  // Analyze document on mount - but SearchTab only mounts when active
  onMount(() => {
    debugLog('SearchTab', 'onMount() called', { filePath });
    if (filePath && filePath !== lastAnalyzedPath) {
      lastAnalyzedPath = filePath;
      analyzeDocument();
    }
  });

  // Re-analyze if file path changes while tab is mounted
  $effect(() => {
    if (filePath && filePath !== lastAnalyzedPath) {
      debugLog('SearchTab', '$effect: filePath changed', { from: lastAnalyzedPath, to: filePath });
      lastAnalyzedPath = filePath;
      // Reset state for new file
      searchState = 'idle';
      showOcrNotification = true;
      showSuccessNotification = false;
      showErrorNotification = true;
      searchQuery = '';
      searchResults = [];
      currentResultIndex = -1;
      analyzeDocument();
    }
  });

  // Re-analyze when file is reloaded (e.g., after OCR)
  let lastReloadVersion = 0;
  $effect(() => {
    if (fileReloadVersion > 0 && fileReloadVersion !== lastReloadVersion) {
      debugLog('SearchTab', '$effect: fileReloadVersion changed', { from: lastReloadVersion, to: fileReloadVersion });
      lastReloadVersion = fileReloadVersion;
      // Clear cache for this file and re-analyze
      analysisCache.delete(filePath);
      lastAnalyzedPath = ''; // Force re-analysis
      searchState = 'idle';
      showSuccessNotification = false;
      searchQuery = '';
      searchResults = [];
      currentResultIndex = -1;
      analyzeDocument();
    }
  });

  // Debounced search - triggers when searchQuery changes
  // Only re-triggers after search completes if query actually changed
  $effect(() => {
    const query = searchQuery;
    const inProgress = searchInProgress;
    if (searchState !== 'searchable') return;

    clearTimeout(searchTimeout);

    // Only search if query changed and not currently searching
    if (query.length >= MIN_QUERY_LENGTH && !inProgress && query !== lastSearchedQuery) {
      searchTimeout = setTimeout(() => {
        handleSearch();
      }, SEARCH_DEBOUNCE_MS);
    } else if (query.length === 0) {
      searchResults = [];
      currentResultIndex = -1;
      lastSearchedQuery = '';
    }
  });

  // React to external search query (from context menu)
  let lastExternalQuery = '';
  $effect(() => {
    if (externalSearchQuery && externalSearchQuery !== lastExternalQuery) {
      lastExternalQuery = externalSearchQuery;
      searchQuery = externalSearchQuery;
      // Debounced search will trigger automatically
    }
  });

  async function analyzeDocument() {
    debugLog('SearchTab', 'analyzeDocument() called', { filePath });
    // Check cache first
    const cached = analysisCache.get(filePath);
    if (cached) {
      debugLog('SearchTab', 'Using cached analysis');
      applyAnalysisResult(cached);
      return;
    }

    searchState = 'analyzing';
    errorMessage = null;

    try {
      debugLog('SearchTab', 'Invoking ocr_analyze_pdf...');
      const result = await invoke<OcrAnalysis>('ocr_analyze_pdf', { input: filePath });
      debugLog('SearchTab', 'ocr_analyze_pdf completed', result);
      analysisCache.set(filePath, result);
      applyAnalysisResult(result);
    } catch (err) {
      debugLog('SearchTab', 'ocr_analyze_pdf FAILED', err, 'error');
      searchState = 'error';
      errorMessage = String(err);
    }
  }

  function applyAnalysisResult(result: OcrAnalysis) {
    debugLog('SearchTab', 'applyAnalysisResult()', result);
    analysisResult = result;
    totalPages = result.page_count || 0;

    if (!result.success) {
      searchState = 'error';
      errorMessage = result.error || 'Analysis failed';
    } else if (result.has_text) {
      searchState = 'searchable';
    } else if (result.needs_ocr) {
      searchState = 'needs-ocr';
    } else {
      // No text, no images - unusual case
      searchState = 'searchable'; // Allow search anyway
    }
    debugLog('SearchTab', 'State set to', { searchState });
  }

  async function runOcr() {
    // If parent provides OCR callback, use it (shows splash notification)
    if (onRunOcr) {
      showOcrNotification = false;
      onRunOcr();
      return;
    }

    // Fallback: run OCR directly (no splash)
    searchState = 'processing-ocr';
    ocrProgress = 'Starting OCR...';
    showOcrNotification = false;

    try {
      // Run OCR on the file (in place)
      const result = await invoke<{ success: boolean; output_path: string; error?: string }>('ocr_run', {
        input: filePath,
        output: null, // Overwrite original
        options: {
          language: 'eng+spa',
          deskew: true,
          rotate_pages: true,
          remove_background: false,
          clean: false,           // Requires 'unpaper' to be installed
          skip_text: false,       // Don't skip - we want full OCR
          force_ocr: true,        // Force OCR for Tagged PDFs
          redo_ocr: false,
          optimize: 1,
        },
      });

      if (result.success) {
        // Clear cache so we re-analyze
        analysisCache.delete(filePath);
        searchState = 'searchable';
        showSuccessNotification = true;

        // Reload the PDF to get the new text layer
        onFileReload?.();
      } else {
        searchState = 'error';
        errorMessage = result.error || 'OCR failed';
      }
    } catch (err) {
      searchState = 'error';
      errorMessage = String(err);
    }
  }

  async function handleSearch() {
    const query = searchQuery.trim();
    if (!query || query.length < MIN_QUERY_LENGTH) {
      searchResults = [];
      return;
    }

    // Don't start a new search while one is in progress
    if (searchInProgress) {
      console.log(`[Search] Skipping "${query}" - search already in progress`);
      return;
    }

    // Increment search ID to invalidate any previous search
    const thisSearchId = ++currentSearchId;
    lastSearchedQuery = query; // Track what we're searching for

    isSearching = true;
    searchInProgress = true;
    console.time(`[Search] "${query}"`);

    try {
      // Use MuPDF's native search - runs in background thread
      const nativeResults = await invoke<NativeSearchResults>('pdf_search_text', {
        path: filePath,
        query: query,
        maxResults: 500,
      });

      console.timeEnd(`[Search] "${query}"`);

      // Check if this search is still current (user may have typed more)
      if (thisSearchId !== currentSearchId) {
        console.log(`[Search] Discarding stale results for "${query}"`);
        return;
      }

      // Map native results to frontend format
      const results: SearchResult[] = nativeResults.results.map((r) => ({
        page: r.page,
        text: query,
        context: r.context,
        normalizedY: r.y,
      }));

      searchResults = results;
      // Auto-select first result
      if (results.length > 0) {
        currentResultIndex = 0;
      }
    } catch (err) {
      console.error('Search failed:', err);
      console.timeEnd(`[Search] "${query}"`);
    } finally {
      searchInProgress = false;
      // Only clear isSearching if this is still the current search
      if (thisSearchId === currentSearchId) {
        isSearching = false;
      }
    }
  }

  function focusOnResult(result: SearchResult) {
    if (onFocusOnResult) {
      onFocusOnResult(result.page, result.normalizedY);
    } else {
      onNavigateToPage(result.page);
    }
  }

  function handleResultClick(result: SearchResult, index: number) {
    currentResultIndex = index;
    focusOnResult(result);
  }

  function nextResult() {
    if (searchResults.length === 0) return;
    currentResultIndex = (currentResultIndex + 1) % searchResults.length;
    focusOnResult(searchResults[currentResultIndex]);
  }

  function prevResult() {
    if (searchResults.length === 0) return;
    currentResultIndex = currentResultIndex <= 0
      ? searchResults.length - 1
      : currentResultIndex - 1;
    focusOnResult(searchResults[currentResultIndex]);
  }

  function clearSearch() {
    searchQuery = '';
    searchResults = [];
    currentResultIndex = -1;
  }

  function handleKeyDown(e: KeyboardEvent) {
    // F3 or Enter: next result or trigger immediate search
    if (e.key === 'F3' || e.key === 'Enter') {
      e.preventDefault();
      if (searchResults.length > 0) {
        if (e.shiftKey) {
          prevResult();
        } else {
          nextResult();
        }
      } else if (e.key === 'Enter' && searchQuery.length >= MIN_QUERY_LENGTH) {
        // Cancel debounce and search immediately
        clearTimeout(searchTimeout);
        handleSearch();
      }
    }
    // Escape: clear search
    if (e.key === 'Escape') {
      clearSearch();
    }
  }

  function dismissOcrNotification() {
    showOcrNotification = false;
  }

  function dismissSuccessNotification() {
    showSuccessNotification = false;
  }

  function dismissErrorNotification() {
    showErrorNotification = false;
  }

  // Notify parent of search state changes for highlight layer
  $effect(() => {
    const query = searchQuery;
    const result = searchResults[currentResultIndex];
    const page = result?.page ?? 0;

    // Calculate match index on the current page
    let indexOnPage = 0;
    if (result) {
      for (let i = 0; i < currentResultIndex; i++) {
        if (searchResults[i].page === page) {
          indexOnPage++;
        }
      }
    }

    onSearchStateChange?.(query, page, indexOnPage);
  });
</script>

<div class="search-tab">
  <div class="header">
    <span class="title">Search</span>
    {#if searchState === 'searchable'}
      <span class="status-badge searchable" title="Document has searchable text">
        <CheckCircle size={12} />
      </span>
    {/if}
  </div>

  <div class="content">
    <!-- Analyzing State -->
    {#if searchState === 'analyzing'}
      <div class="status-container">
        <Loader2 size={24} class="animate-spin" />
        <p class="status-text">Analyzing document...</p>
      </div>
    {/if}

    <!-- Idle State -->
    {#if searchState === 'idle'}
      <div class="status-container">
        <Loader2 size={24} class="animate-spin" />
        <p class="status-text">Loading...</p>
      </div>
    {/if}

    <!-- Needs OCR State -->
    {#if searchState === 'needs-ocr' && showOcrNotification}
      <InlineNotification type="warning" dismissible onDismiss={dismissOcrNotification}>
        <p class="font-medium">Document needs OCR</p>
        <p class="text-hint">This appears to be a scanned document without searchable text.</p>
        <button onclick={runOcr}>Process with OCR</button>
      </InlineNotification>
    {/if}

    {#if searchState === 'needs-ocr' && !showOcrNotification}
      <div class="empty-state">
        <FileText size={32} class="icon" />
        <p class="message">No searchable text</p>
        <button class="ocr-btn" onclick={runOcr}>Process with OCR</button>
      </div>
    {/if}

    <!-- Processing OCR State -->
    {#if searchState === 'processing-ocr'}
      <div class="status-container">
        <Loader2 size={24} class="animate-spin" />
        <p class="status-text">Processing OCR...</p>
        <p class="status-hint">{ocrProgress}</p>
      </div>
    {/if}

    <!-- Error State -->
    {#if searchState === 'error' && showErrorNotification}
      <InlineNotification type="error" dismissible onDismiss={dismissErrorNotification}>
        <p class="font-medium">Analysis failed</p>
        <p class="text-hint">{errorMessage}</p>
      </InlineNotification>
    {/if}

    <!-- Searchable State -->
    {#if searchState === 'searchable'}
      {#if showSuccessNotification}
        <InlineNotification type="success" dismissible onDismiss={dismissSuccessNotification}>
          <p class="font-medium">OCR completed</p>
          <p class="text-hint">Document is now searchable.</p>
        </InlineNotification>
      {/if}

      <div class="search-container">
        <div class="search-input-box">
          <div class="search-icon-container">
            <Search size={14} />
          </div>
          <input
            type="text"
            placeholder="Search (min 3 chars)..."
            bind:value={searchQuery}
            onkeydown={handleKeyDown}
            class="search-input-field"
          />
          {#if isSearching}
            <div class="search-action-icon">
              <Loader2 size={14} class="animate-spin" />
            </div>
          {:else if searchQuery.length > 0}
            <button class="search-clear-btn" onclick={clearSearch} title="Clear search (Esc)">
              <X size={14} />
            </button>
          {/if}
        </div>

        <!-- Navigation bar with result count and prev/next -->
        {#if searchResults.length > 0}
          <div class="nav-bar">
            <span class="result-indicator">
              {currentResultIndex >= 0 ? currentResultIndex + 1 : 0} / {searchResults.length}
            </span>
            <div class="nav-buttons">
              <button
                class="nav-btn"
                onclick={prevResult}
                title="Previous result (Shift+F3)"
                disabled={searchResults.length === 0}
              >
                <ChevronUp size={14} />
              </button>
              <button
                class="nav-btn"
                onclick={nextResult}
                title="Next result (F3)"
                disabled={searchResults.length === 0}
              >
                <ChevronDown size={14} />
              </button>
            </div>
          </div>
        {/if}
      </div>

      <!-- Search Results -->
      {#if searchResults.length > 0}
        <div class="results-container">
          <div class="results-list">
            {#each searchResults as result, index (result.page + '-' + index)}
              <button
                class="result-item"
                class:active={index === currentResultIndex}
                onclick={() => handleResultClick(result, index)}
              >
                <span class="result-page">Page {result.page}</span>
                <span class="result-context">{result.context}</span>
              </button>
            {/each}
          </div>
        </div>
      {:else if searchQuery && !isSearching}
        <div class="no-results">
          <p>No results found for "{searchQuery}"</p>
        </div>
      {/if}
    {/if}
  </div>
</div>

<style>
  .search-tab {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--nord3);
  }

  .title {
    font-size: 0.75rem;
    text-transform: uppercase;
    opacity: 0.6;
  }

  .status-badge {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0.125rem;
    border-radius: 9999px;
  }

  .status-badge.searchable {
    color: var(--nord14);
  }

  .content {
    flex: 1;
    overflow-y: auto;
    padding: 0.5rem;
  }

  .status-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 0.75rem;
    color: var(--nord4);
  }

  .status-text {
    font-size: 0.875rem;
    margin: 0;
  }

  .status-hint {
    font-size: 0.75rem;
    opacity: 0.6;
    margin: 0;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 0.75rem;
    text-align: center;
    padding: 1rem;
  }

  .empty-state .icon {
    color: var(--nord4);
    opacity: 0.3;
  }

  .empty-state .message {
    font-size: 0.875rem;
    color: var(--nord4);
    opacity: 0.6;
    margin: 0;
  }

  .ocr-btn {
    margin-top: 0.5rem;
    padding: 0.5rem 1rem;
    border-radius: 0.375rem;
    font-size: 0.75rem;
    font-weight: 500;
    background-color: var(--nord8);
    color: var(--nord0);
    border: none;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .ocr-btn:hover {
    opacity: 0.9;
  }

  .search-container {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
    padding: 0 0.25rem;
  }

  .search-input-box {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    border-radius: 0.375rem;
    border: 1px solid var(--nord3);
    background-color: var(--nord0);
    transition: border-color 0.15s;
  }

  .search-input-box:focus-within {
    border-color: var(--nord8);
  }

  .search-icon-container {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--nord4);
    opacity: 0.5;
    flex-shrink: 0;
  }

  .search-input-field {
    flex: 1;
    border: none;
    background: transparent;
    color: var(--nord6);
    font-size: 0.875rem;
    outline: none;
    min-width: 0;
  }

  .search-input-field::placeholder {
    color: var(--nord4);
    opacity: 0.6;
  }

  .search-action-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--nord8);
    flex-shrink: 0;
  }

  .search-clear-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0.25rem;
    border: none;
    background: transparent;
    color: var(--nord4);
    opacity: 0.6;
    cursor: pointer;
    border-radius: 0.25rem;
    transition: opacity 0.15s, background-color 0.15s;
    flex-shrink: 0;
  }

  .search-clear-btn:hover {
    opacity: 1;
    background-color: var(--nord2);
  }

  .nav-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.25rem 0;
  }

  .result-indicator {
    font-size: 0.75rem;
    color: var(--nord4);
    opacity: 0.8;
  }

  .nav-buttons {
    display: flex;
    gap: 0.25rem;
  }

  .nav-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0.25rem;
    border: none;
    background-color: var(--nord2);
    color: var(--nord4);
    cursor: pointer;
    border-radius: 0.25rem;
    transition: background-color 0.15s, color 0.15s;
  }

  .nav-btn:hover:not(:disabled) {
    background-color: var(--nord3);
    color: var(--nord6);
  }

  .nav-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .search-btn {
    padding: 0.5rem 1rem;
    border-radius: 0.375rem;
    font-size: 0.75rem;
    font-weight: 500;
    background-color: var(--nord8);
    color: var(--nord0);
    border: none;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .search-btn:hover:not(:disabled) {
    opacity: 0.9;
  }

  .search-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .results-container {
    margin-top: 0.5rem;
  }

  .results-count {
    font-size: 0.75rem;
    color: var(--nord4);
    opacity: 0.6;
    margin: 0 0 0.5rem 0;
  }

  .results-list {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .result-item {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    padding: 0.5rem;
    border-radius: 0.375rem;
    background-color: var(--nord2);
    border: none;
    cursor: pointer;
    text-align: left;
    transition: background-color 0.15s;
  }

  .result-item:hover {
    background-color: var(--nord3);
  }

  .result-item.active {
    background-color: var(--nord3);
    border-left: 2px solid var(--nord8);
  }

  .result-page {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--nord8);
  }

  .result-context {
    font-size: 0.75rem;
    color: var(--nord4);
    margin-top: 0.25rem;
    line-height: 1.4;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    word-break: break-word;
    max-width: 100%;
  }

  .no-results {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem 1rem;
    text-align: center;
  }

  .no-results p {
    font-size: 0.875rem;
    color: var(--nord4);
    opacity: 0.6;
    margin: 0;
  }

  .text-hint {
    font-size: 0.75rem;
    opacity: 0.7;
  }

  .font-medium {
    font-weight: 500;
  }

  :global(.animate-spin) {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
