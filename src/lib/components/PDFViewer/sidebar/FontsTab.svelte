<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import { ask } from '@tauri-apps/plugin-dialog';
  import {
    Type,
    AlertTriangle,
    CheckCircle,
    XCircle,
    RefreshCw,
    ChevronDown,
    ChevronRight,
  } from 'lucide-svelte';

  interface FontMatch {
    name: string;
    similarity: number;
  }

  interface FontInfo {
    name: string;
    originalName: string;
    type: string;
    bold: boolean;
    italic: boolean;
    embedded: boolean;
    subset: boolean;
    pages: number[];
    pageCount: number;
    matches: FontMatch[];
    bestMatch: FontMatch | null;
    bestMatchScore: number;
    status: string;
  }

  interface FontAnalysisSummary {
    total: number;
    embedded: number;
    missing: number;
    low_match: number;
  }

  interface FontAnalysisResult {
    success: boolean;
    fonts: FontInfo[];
    summary: FontAnalysisSummary;
    error: string | null;
  }

  interface Props {
    filePath: string;
    autoAnalyze?: boolean;
  }

  let { filePath, autoAnalyze = false }: Props = $props();

  let result = $state<FontAnalysisResult | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let expandedFonts = $state<Set<string>>(new Set());
  let hasAutoAnalyzed = $state(false);

  // Core analysis function (no confirmation dialog)
  async function runAnalysis() {
    loading = true;
    error = null;
    result = null;

    try {
      result = await invoke<FontAnalysisResult>('pdf_analyze_fonts', {
        input: filePath,
      });

      if (!result.success) {
        error = result.error || 'Unknown error';
        result = null;
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      result = null;
    } finally {
      loading = false;
    }
  }

  async function analyzefonts() {
    // Show confirmation dialog
    const confirmed = await ask(
      'Font analysis scans all pages to identify fonts used in the document. This may take a moment for large files.\n\nContinue?',
      {
        title: 'Analyze Document Fonts',
        kind: 'info',
        okLabel: 'Analyze',
        cancelLabel: 'Cancel',
      }
    );

    if (!confirmed) return;

    await runAnalysis();
  }

  // Auto-analyze when prop is set (e.g., after OCR with font analysis checkbox)
  $effect(() => {
    if (autoAnalyze && !hasAutoAnalyzed && !loading && !result) {
      hasAutoAnalyzed = true;
      runAnalysis();
    }
  });

  function toggleExpanded(fontName: string) {
    const newSet = new Set(expandedFonts);
    if (newSet.has(fontName)) {
      newSet.delete(fontName);
    } else {
      newSet.add(fontName);
    }
    expandedFonts = newSet;
  }

  function getStatusIcon(status: string) {
    switch (status) {
      case 'ok':
        return CheckCircle;
      case 'low_match':
        return AlertTriangle;
      case 'missing':
        return XCircle;
      default:
        return AlertTriangle;
    }
  }

  function getStatusColor(status: string) {
    switch (status) {
      case 'ok':
        return 'var(--nord14)';
      case 'low_match':
        return 'var(--nord13)';
      case 'missing':
        return 'var(--nord11)';
      default:
        return 'var(--nord4)';
    }
  }

  function getFontTypeLabel(type: string) {
    switch (type) {
      case 'serif':
        return 'Serif';
      case 'sans':
        return 'Sans-serif';
      case 'mono':
        return 'Monospace';
      default:
        return type;
    }
  }
</script>

<div class="h-full flex flex-col" style="background-color: var(--nord0);">
  <!-- Header -->
  <div class="p-3 flex items-center justify-between" style="border-bottom: 1px solid var(--nord2);">
    <div class="flex items-center gap-2">
      <Type size={16} style="color: var(--nord8);" />
      <span class="font-medium text-sm">Document Fonts</span>
    </div>
    {#if result}
      <button
        onclick={analyzefonts}
        class="p-1.5 rounded hover:bg-[var(--nord2)] transition-colors"
        title="Re-analyze fonts"
        disabled={loading}
      >
        <RefreshCw size={14} class={loading ? 'animate-spin' : ''} />
      </button>
    {/if}
  </div>

  <div class="flex-1 overflow-auto p-3">
    {#if loading}
      <!-- Loading splash -->
      <div class="flex flex-col items-center justify-center h-full gap-4 text-center">
        <div class="relative">
          <Type size={48} style="color: var(--nord3);" />
          <div
            class="absolute inset-0 flex items-center justify-center"
          >
            <RefreshCw size={24} class="animate-spin" style="color: var(--nord8);" />
          </div>
        </div>
        <div>
          <p class="font-medium">Analyzing fonts...</p>
          <p class="text-xs opacity-60 mt-1">Scanning all pages for font information</p>
        </div>
      </div>
    {:else if error}
      <!-- Error state -->
      <div class="flex flex-col items-center justify-center h-full gap-3 text-center">
        <XCircle size={32} style="color: var(--nord11);" />
        <div>
          <p class="font-medium" style="color: var(--nord11);">Analysis failed</p>
          <p class="text-xs opacity-60 mt-1 max-w-[200px]">{error}</p>
        </div>
        <button
          onclick={analyzefonts}
          class="px-3 py-1.5 rounded text-sm transition-colors"
          style="background-color: var(--nord3);"
        >
          Try again
        </button>
      </div>
    {:else if result}
      <!-- Results -->
      <div class="space-y-4">
        <!-- Summary -->
        <div
          class="p-3 rounded-lg"
          style="background-color: var(--nord1);"
        >
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="flex items-center gap-2">
              <span class="opacity-60">Total:</span>
              <span class="font-medium">{result.summary.total}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="opacity-60">Embedded:</span>
              <span class="font-medium">{result.summary.embedded}</span>
            </div>
            {#if result.summary.low_match > 0}
              <div class="flex items-center gap-2" style="color: var(--nord13);">
                <AlertTriangle size={12} />
                <span>{result.summary.low_match} low match</span>
              </div>
            {/if}
            {#if result.summary.missing > 0}
              <div class="flex items-center gap-2" style="color: var(--nord11);">
                <XCircle size={12} />
                <span>{result.summary.missing} missing</span>
              </div>
            {/if}
          </div>
        </div>

        <!-- Font list -->
        <div class="space-y-1">
          {#each result.fonts as font (font.name)}
            {@const StatusIcon = getStatusIcon(font.status)}
            {@const isExpanded = expandedFonts.has(font.name)}

            <div
              class="rounded-lg overflow-hidden"
              style="background-color: var(--nord1);"
            >
              <!-- Font header -->
              <button
                onclick={() => toggleExpanded(font.name)}
                class="w-full p-2 flex items-center gap-2 text-left hover:bg-[var(--nord2)] transition-colors"
              >
                {#if isExpanded}
                  <ChevronDown size={14} class="opacity-60" />
                {:else}
                  <ChevronRight size={14} class="opacity-60" />
                {/if}

                <StatusIcon size={14} style="color: {getStatusColor(font.status)};" />

                <div class="flex-1 min-w-0">
                  <div class="text-sm font-medium truncate">{font.name}</div>
                  <div class="text-xs opacity-60 flex items-center gap-2">
                    <span>{getFontTypeLabel(font.type)}</span>
                    {#if font.bold}<span class="font-bold">B</span>{/if}
                    {#if font.italic}<span class="italic">I</span>{/if}
                  </div>
                </div>

                <div class="text-right">
                  <div
                    class="text-xs font-medium"
                    style="color: {font.bestMatchScore >= 85 ? 'var(--nord14)' : font.bestMatchScore >= 50 ? 'var(--nord13)' : 'var(--nord11)'};"
                  >
                    {font.bestMatchScore}%
                  </div>
                  <div class="text-[10px] opacity-60">
                    {font.pageCount} pg{font.pageCount !== 1 ? 's' : ''}
                  </div>
                </div>
              </button>

              <!-- Expanded details -->
              {#if isExpanded}
                <div class="px-3 pb-3 pt-1 text-xs space-y-2" style="border-top: 1px solid var(--nord2);">
                  <!-- Original name -->
                  {#if font.originalName !== font.name}
                    <div class="flex gap-2">
                      <span class="opacity-60 w-16">Original:</span>
                      <span class="font-mono text-[10px] break-all">{font.originalName}</span>
                    </div>
                  {/if}

                  <!-- Status info -->
                  <div class="flex gap-2">
                    <span class="opacity-60 w-16">Status:</span>
                    <span>
                      {#if font.embedded}Embedded{:else}Not embedded{/if}
                      {#if font.subset}(subset){/if}
                    </span>
                  </div>

                  <!-- Pages -->
                  <div class="flex gap-2">
                    <span class="opacity-60 w-16">Pages:</span>
                    <span class="break-all">
                      {font.pages.length <= 5
                        ? font.pages.join(', ')
                        : font.pages.slice(0, 5).join(', ') + '...'}
                    </span>
                  </div>

                  <!-- Best matches -->
                  <div>
                    <span class="opacity-60">Best matches:</span>
                    <div class="mt-1 space-y-1">
                      {#each font.matches as match, i}
                        <div
                          class="flex items-center justify-between px-2 py-1 rounded"
                          style="background-color: var(--nord2);"
                        >
                          <span class:font-medium={i === 0}>{match.name}</span>
                          <span
                            class="text-[10px]"
                            style="color: {match.similarity >= 85 ? 'var(--nord14)' : match.similarity >= 50 ? 'var(--nord13)' : 'var(--nord11)'};"
                          >
                            {match.similarity}%
                          </span>
                        </div>
                      {/each}
                    </div>
                  </div>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {:else}
      <!-- Initial state - prompt to analyze -->
      <div class="flex flex-col items-center justify-center h-full gap-4 text-center">
        <Type size={48} style="color: var(--nord3);" />
        <div>
          <p class="font-medium">Font Analysis</p>
          <p class="text-xs opacity-60 mt-1 max-w-[200px]">
            Analyze document fonts to identify typefaces and find matching system fonts.
          </p>
        </div>
        <button
          onclick={analyzefonts}
          class="px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
          style="background-color: var(--nord10); color: var(--nord6);"
        >
          <Type size={16} />
          Analyze Fonts
        </button>
      </div>
    {/if}
  </div>
</div>
