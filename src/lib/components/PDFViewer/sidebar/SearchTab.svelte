<script lang="ts">
  import { onMount } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';
  import { Search, CheckCircle, AlertTriangle, Loader2, FileText, XCircle } from 'lucide-svelte';
  import InlineNotification from '../InlineNotification.svelte';
  import { debugLog } from '$lib/stores/debugLog.svelte';

  interface Props {
    filePath: string;
    onNavigateToPage: (page: number) => void;
    onFileReload?: () => void;
  }

  let { filePath, onNavigateToPage, onFileReload }: Props = $props();

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

  // Search result type
  interface SearchResult {
    page: number;
    text: string;
    context: string;
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
      analyzeDocument();
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
    if (!searchQuery.trim()) {
      searchResults = [];
      return;
    }

    isSearching = true;
    searchResults = [];

    try {
      const results: SearchResult[] = [];
      const query = searchQuery.toLowerCase();

      // Search through each page
      for (let page = 1; page <= totalPages; page++) {
        try {
          const textContent = await invoke<{ page: number; blocks: { lines: { text: string }[] }[] }>(
            'pdf_get_text_blocks',
            { path: filePath, page }
          );

          // Extract all text from blocks
          const pageText = textContent.blocks
            .flatMap(block => block.lines.map(line => line.text))
            .join(' ');

          // Check if query matches
          const lowerText = pageText.toLowerCase();
          if (lowerText.includes(query)) {
            // Find context around match
            const matchIndex = lowerText.indexOf(query);
            const start = Math.max(0, matchIndex - 30);
            const end = Math.min(pageText.length, matchIndex + query.length + 30);
            const context = (start > 0 ? '...' : '') +
              pageText.slice(start, end).trim() +
              (end < pageText.length ? '...' : '');

            results.push({
              page,
              text: searchQuery,
              context,
            });
          }
        } catch {
          // Skip pages that fail to extract
        }
      }

      searchResults = results;
    } catch (err) {
      console.error('Search failed:', err);
    } finally {
      isSearching = false;
    }
  }

  function handleResultClick(result: SearchResult) {
    onNavigateToPage(result.page);
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      handleSearch();
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
        <div class="search-input-wrapper">
          <Search size={16} class="search-icon" />
          <input
            type="text"
            placeholder="Search in document..."
            bind:value={searchQuery}
            onkeydown={handleKeyDown}
            class="search-input"
          />
          {#if isSearching}
            <Loader2 size={16} class="loading-icon animate-spin" />
          {/if}
        </div>

        <button class="search-btn" onclick={handleSearch} disabled={isSearching}>
          Search
        </button>
      </div>

      <!-- Search Results -->
      {#if searchResults.length > 0}
        <div class="results-container">
          <p class="results-count">{searchResults.length} result{searchResults.length !== 1 ? 's' : ''}</p>
          <div class="results-list">
            {#each searchResults as result (result.page + result.context)}
              <button class="result-item" onclick={() => handleResultClick(result)}>
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
  }

  .search-input-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }

  .search-icon {
    position: absolute;
    left: 0.75rem;
    color: var(--nord4);
    opacity: 0.6;
  }

  .loading-icon {
    position: absolute;
    right: 0.75rem;
    color: var(--nord8);
  }

  .search-input {
    width: 100%;
    padding: 0.5rem 2rem 0.5rem 2.25rem;
    border-radius: 0.375rem;
    border: 1px solid var(--nord3);
    background-color: var(--nord0);
    color: var(--nord6);
    font-size: 0.875rem;
  }

  .search-input:focus {
    outline: none;
    border-color: var(--nord8);
  }

  .search-input::placeholder {
    color: var(--nord4);
    opacity: 0.6;
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
