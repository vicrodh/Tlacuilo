<script lang="ts">
  import {
    Upload,
    FolderOpen,
    Trash2,
    CheckCircle,
    AlertCircle,
    Wand2
  } from 'lucide-svelte';
  import { listen } from '@tauri-apps/api/event';
  import { open } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';
  import { onMount, onDestroy } from 'svelte';
  import { log, logSuccess, logError, registerFile, unregisterModule } from '$lib/stores/status.svelte';
  import OcrProgressSplash from '$lib/components/OcrProgressSplash.svelte';

  const MODULE = 'FontDetect';

  interface EngineAvailability {
    available: boolean;
    reason?: string | null;
  }

  interface FontDetectCheck {
    ok: boolean;
    cache_dir: string;
    engines: {
      baseline_render_compare: EngineAvailability;
      ml_embeddings: EngineAvailability;
    };
    catalog: {
      available: boolean;
      source?: string | null;
      path?: string | null;
    };
    indexed_fonts: number;
  }

  interface FontDetectIndex {
    ok: boolean;
    cache_dir: string;
    indexed_fonts: number;
    duration_ms: number;
    ml_indexed: boolean;
    cached?: boolean;
    ml_reason?: string;
  }

  interface ScoreBreakdown {
    ssim: number;
    histogram: number;
    template: number;
  }

  interface Candidate {
    family: string;
    style: string;
    category?: string;
    weight?: number;
    italic?: boolean;
    path: string;
    score: number;
    score_breakdown?: ScoreBreakdown | null;
    preview_sample?: string | null;
  }

  interface MatchResult {
    ok: boolean;
    requested_engine: string;
    engine_used: string;
    fallback: {
      used: boolean;
      reason?: string | null;
    };
    candidates: Candidate[];
    meta: {
      indexed_fonts: number;
      duration_ms: number;
    };
  }

  let filePath = $state<string | null>(null);
  let fileName = $state('');
  let inputKind = $state<'image' | 'pdf' | null>(null);
  let renderedImagePath = $state<string | null>(null);
  let checkResult = $state<FontDetectCheck | null>(null);
  let indexResult = $state<FontDetectIndex | null>(null);
  let matchResult = $state<MatchResult | null>(null);
  let selectedCandidate = $state<Candidate | null>(null);
  let isChecking = $state(false);
  let isIndexing = $state(false);
  let isMatching = $state(false);
  let engine = $state<'auto' | 'baseline' | 'ml'>('auto');
  let topk = $state(5);
  let unlistenDrop: (() => void) | null = null;
  let helperText = $state('Run Check, then Index, then Match to see results.');
  let isAutoChecking = $state(false);
  let isAutoIndexing = $state(false);

  const filePattern = /\.(png|jpe?g|bmp|tiff|pdf)$/i;

  onMount(async () => {
    unlistenDrop = await listen<string[]>('tauri://file-drop', async (e) => {
      const files = e.payload.filter((p: string) => filePattern.test(p));
      if (files.length > 0) {
        await loadFile(files[0]);
      }
    });

    await autoCheckAndIndex();
  });

  onDestroy(() => {
    if (unlistenDrop) unlistenDrop();
    unregisterModule(MODULE);
  });

  async function loadFile(path: string) {
    filePath = path;
    fileName = path.split('/').pop() || path;
    inputKind = path.toLowerCase().endsWith('.pdf') ? 'pdf' : 'image';
    renderedImagePath = null;
    matchResult = null;
    selectedCandidate = null;

    registerFile(path, fileName, MODULE);
    log(`Loaded ${fileName}`, 'info', MODULE);
    helperText = inputKind === 'pdf'
      ? 'Run Check, then Index, then Match. PDF will be rendered to an image automatically.'
      : 'Run Check, then Index, then Match to see results.';
  }

  async function handleFilePicker() {
    const selected = await open({
      multiple: false,
      filters: [{ name: 'Images or PDF', extensions: ['png', 'jpg', 'jpeg', 'bmp', 'tiff', 'pdf'] }],
    });
    if (selected) {
      await loadFile(selected as string);
    }
  }

  function removeFile() {
    filePath = null;
    fileName = '';
    inputKind = null;
    renderedImagePath = null;
    matchResult = null;
    selectedCandidate = null;
    unregisterModule(MODULE);
  }

  async function handleCheck() {
    isChecking = true;
    try {
      checkResult = await invoke<FontDetectCheck>('font_detect_check');
      if (checkResult.ok) {
        logSuccess('Font detection check complete', MODULE);
      }
    } catch (err) {
      console.error('Font detect check failed:', err);
      logError(`Check failed: ${err}`, MODULE);
    }
    isChecking = false;
  }

  async function handleIndex(force = false) {
    isIndexing = true;
    try {
      indexResult = await invoke<FontDetectIndex>('font_detect_index', { force });
      if (indexResult.ok) {
        const suffix = indexResult.cached ? ' (cached)' : '';
        logSuccess(`Index complete: ${indexResult.indexed_fonts} fonts${suffix}`, MODULE);
      }
      if (indexResult.ml_reason) {
        log(`ML index note: ${indexResult.ml_reason}`, 'warning', MODULE);
      }
    } catch (err) {
      console.error('Font detect index failed:', err);
      logError(`Index failed: ${err}`, MODULE);
    }
    isIndexing = false;
  }

  async function handleMatch() {
    if (!filePath) return;

    isMatching = true;
    matchResult = null;
    log('Matching font...', 'info', MODULE);

    try {
      const inputImage = await resolveMatchImage();
      matchResult = await invoke<MatchResult>('font_detect_match', {
        input: inputImage,
        engine,
        topk: Math.max(1, Number(topk) || 1),
      });
      if (matchResult.ok) {
        logSuccess(`Match complete: ${matchResult.candidates.length} candidates`, MODULE);
        selectedCandidate = matchResult.candidates[0] || null;
      }
    } catch (err) {
      console.error('Font detect match failed:', err);
      logError(`Match failed: ${err}`, MODULE);
    }

    isMatching = false;
  }

  const canMatch = $derived.by(() => filePath !== null && !isMatching);
  const splashVisible = $derived.by(() => isChecking || isIndexing || isMatching);
  const splashMessage = $derived.by(() => {
    if (isIndexing) return 'Indexing fonts...';
    if (isMatching) return 'Matching fonts...';
    if (isChecking) return 'Checking font engines...';
    return 'Processing...';
  });

  async function resolveMatchImage(): Promise<string> {
    if (!filePath) {
      throw new Error('No input file selected');
    }
    if (inputKind === 'image') {
      return filePath;
    }
    if (renderedImagePath) {
      return renderedImagePath;
    }

    const rendered = await invoke<{ data: string; width: number; height: number; page: number }>(
      'pdf_render_page',
      {
        path: filePath,
        page: 1,
        dpi: 200,
      }
    );

    if (!rendered?.data) {
      throw new Error('PDF render returned no image data');
    }

    const outputPath = await invoke<string>('font_detect_write_cache_image', {
      data: rendered.data,
      nameHint: fileName.replace(/[^a-z0-9._-]/gi, '_'),
    });

    renderedImagePath = outputPath;
    return outputPath;
  }

  async function autoCheckAndIndex() {
    isAutoChecking = true;
    helperText = 'Checking font engines...';
    try {
      checkResult = await invoke<FontDetectCheck>('font_detect_check');
      if (checkResult.indexed_fonts === 0) {
        isAutoIndexing = true;
        helperText = 'Indexing fonts for first use...';
        indexResult = await invoke<FontDetectIndex>('font_detect_index', { force: false });
        if (indexResult.ok) {
          logSuccess(`Index complete: ${indexResult.indexed_fonts} fonts`, MODULE);
        }
      }
    } catch (err) {
      console.error('Auto check/index failed:', err);
      logError(`Auto setup failed: ${err}`, MODULE);
    } finally {
      isAutoChecking = false;
      isAutoIndexing = false;
      helperText = inputKind === 'pdf'
        ? 'Run Match to identify fonts. PDF will be rendered to an image automatically.'
        : 'Run Match to identify fonts.';
    }
  }
</script>

<OcrProgressSplash visible={splashVisible} message={splashMessage} />

<div class="flex-1 flex overflow-hidden">
  <div class="flex-1 flex flex-col overflow-y-auto p-6">
    {#if !filePath}
      <div
        class="flex-1 flex flex-col items-center justify-center rounded-xl border-2 border-dashed cursor-pointer transition-colors hover:border-[var(--nord8)]"
        style="border-color: var(--nord3); background-color: var(--nord1);"
        role="button"
        tabindex="0"
        onclick={handleFilePicker}
        onkeydown={(e) => e.key === 'Enter' && handleFilePicker()}
      >
        <Wand2 size={64} class="opacity-30 mb-4" />
        <p class="text-xl opacity-60 mb-2">Font Detection</p>
        <p class="text-sm opacity-40 mb-6">Drop an image or PDF sample here or click to browse</p>
        <button
          class="flex items-center gap-2 px-6 py-3 rounded-lg transition-colors hover:opacity-90"
          style="background-color: var(--nord8); color: var(--nord0);"
        >
          <FolderOpen size={20} />
          <span>Select File</span>
        </button>
      </div>
    {:else}
      <div class="flex-1 flex flex-col gap-6">
        <div class="rounded-xl p-6" style="background-color: var(--nord1);">
          <div class="flex items-start gap-4">
            <div class="flex-1 min-w-0">
              <p class="text-sm opacity-60 mb-1">Loaded File</p>
              <p class="text-lg font-medium truncate">{fileName}</p>
              <p class="text-xs opacity-40 truncate">{filePath}</p>
              {#if inputKind === 'pdf'}
                <p class="text-xs opacity-40">Using first page for matching</p>
              {/if}
            </div>
            <button
              class="p-2 rounded-lg transition-colors hover:bg-[var(--nord2)]"
              onclick={removeFile}
              title="Remove file"
            >
              <Trash2 size={18} />
            </button>
          </div>
        </div>

        <div class="text-sm opacity-60">
          {helperText}
        </div>

        <div class="grid grid-cols-3 gap-4">
          <div class="rounded-xl p-5" style="background-color: var(--nord1);">
            <p class="text-sm opacity-60 mb-2">Engine</p>
            <select
              class="w-full px-3 py-2 rounded-lg"
              style="background-color: var(--nord2);"
              bind:value={engine}
            >
              <option value="auto">Auto</option>
              <option value="baseline">Baseline</option>
              <option value="ml">ML</option>
            </select>
          </div>
          <div class="rounded-xl p-5" style="background-color: var(--nord1);">
            <p class="text-sm opacity-60 mb-2">Top-K</p>
            <input
              type="number"
              min="1"
              max="20"
              class="w-full px-3 py-2 rounded-lg"
              style="background-color: var(--nord2);"
              bind:value={topk}
            />
          </div>
          <div class="rounded-xl p-5 flex flex-col gap-2" style="background-color: var(--nord1);">
            <button
              class="flex items-center justify-center gap-2 px-3 py-2 rounded-lg transition-colors"
              style="background-color: var(--nord8); color: var(--nord0);"
              onclick={handleCheck}
              disabled={isChecking}
            >
              <CheckCircle size={16} />
              <span>{isChecking ? 'Checking...' : 'Check'}</span>
            </button>
            <button
              class="flex items-center justify-center gap-2 px-3 py-2 rounded-lg transition-colors"
              style="background-color: var(--nord10); color: var(--nord0);"
              onclick={() => handleIndex(true)}
              disabled={isIndexing}
            >
              <Upload size={16} />
              <span>{isIndexing ? 'Indexing...' : 'Rebuild'}</span>
            </button>
          </div>
        </div>

        {#if checkResult || indexResult}
          <div class="rounded-xl p-5 text-sm" style="background-color: var(--nord1);">
            {#if checkResult}
              <p class="opacity-60 mb-2">Engines</p>
              <div class="flex flex-wrap gap-4">
                <span>
                  Baseline: {checkResult.engines.baseline_render_compare.available ? 'available' : 'unavailable'}
                </span>
                <span>
                  ML: {checkResult.engines.ml_embeddings.available ? 'available' : 'unavailable'}
                </span>
              </div>
              {#if checkResult.engines.ml_embeddings.reason}
                <p class="text-xs opacity-50 mt-2">ML reason: {checkResult.engines.ml_embeddings.reason}</p>
              {/if}
              {#if checkResult.catalog}
                <p class="text-xs opacity-50 mt-2">
                  Catalog: {checkResult.catalog.available ? checkResult.catalog.source : 'not found'}
                </p>
              {/if}
            {/if}
            {#if indexResult}
              <p class="opacity-60 mt-3">Index</p>
              <p>Fonts indexed: {indexResult.indexed_fonts}</p>
              <p class="text-xs opacity-50">Cache: {indexResult.cache_dir}</p>
            {/if}
          </div>
        {/if}

        <div class="rounded-xl p-6" style="background-color: var(--nord1);">
          <div class="flex items-center justify-between mb-4">
            <div>
              <p class="text-sm opacity-60">Match</p>
              <p class="text-lg font-medium">Font Candidates</p>
            </div>
            <button
              class="flex items-center gap-2 px-4 py-2 rounded-lg transition-colors"
              style="background-color: var(--nord8); color: var(--nord0);"
              onclick={handleMatch}
              disabled={!canMatch}
            >
              <CheckCircle size={16} />
              <span>{isMatching ? 'Matching...' : 'Match'}</span>
            </button>
          </div>

          <p class="text-sm opacity-60">Run a match to see candidates in the sidebar.</p>
        </div>
      </div>
    {/if}
  </div>

  {#if filePath}
    <!-- TODO: replace with shared viewer sidebar once QuickTool proves out. -->
    <aside class="w-80 border-l overflow-y-auto" style="background-color: var(--nord1); border-color: var(--nord3);">
      <div class="p-4 space-y-4">
        <div>
          <p class="text-xs opacity-60 uppercase">Font Detection</p>
          {#if matchResult}
            <div class="text-xs opacity-60 mt-2">
              <div>Engine: {matchResult.engine_used}</div>
              <div>Duration: {matchResult.meta.duration_ms} ms</div>
              {#if matchResult.fallback.used}
                <div>Fallback: {matchResult.fallback.reason}</div>
              {/if}
            </div>
          {:else}
            <p class="text-xs opacity-60 mt-2">No results yet.</p>
          {/if}
        </div>

        {#if matchResult}
          {#if matchResult.candidates.length === 0}
            <div class="flex items-center gap-2 text-sm opacity-60">
              <AlertCircle size={16} />
              <span>No candidates found.</span>
            </div>
          {:else}
            <div class="space-y-2">
              {#each matchResult.candidates as candidate}
                <button
                  class="w-full text-left rounded-lg px-3 py-2 transition-colors"
                  style="background-color: {selectedCandidate === candidate ? 'var(--nord2)' : 'var(--nord0)'};"
                  onclick={() => selectedCandidate = candidate}
                >
                  <div class="flex items-center justify-between">
                    <span class="text-sm font-medium">{candidate.family}</span>
                    <span class="text-xs opacity-60">{candidate.score.toFixed(3)}</span>
                  </div>
                  <div class="text-xs opacity-50">{candidate.style} · {candidate.category}</div>
                </button>
              {/each}
            </div>
          {/if}
        {/if}

        {#if selectedCandidate}
          <div class="rounded-lg p-3" style="background-color: var(--nord2);">
            <p class="text-sm font-medium mb-1">{selectedCandidate.family} · {selectedCandidate.style}</p>
            <p class="text-xs opacity-60">
              {selectedCandidate.category} · {selectedCandidate.weight}{selectedCandidate.italic ? ' italic' : ''}
            </p>
            <p class="text-xs opacity-60 mt-1">Score: {selectedCandidate.score.toFixed(3)}</p>
            {#if selectedCandidate.score_breakdown}
              <p class="text-xs opacity-50 mt-1">
                ssim {selectedCandidate.score_breakdown.ssim.toFixed(2)} · hist {selectedCandidate.score_breakdown.histogram.toFixed(2)} · tmpl {selectedCandidate.score_breakdown.template.toFixed(2)}
              </p>
            {/if}
            {#if selectedCandidate.preview_sample}
              <img
                class="mt-3 rounded border"
                style="border-color: var(--nord3);"
                src={`data:image/png;base64,${selectedCandidate.preview_sample}`}
                alt="Font sample preview"
              />
            {/if}
          </div>
        {/if}
      </div>
    </aside>
  {/if}
</div>
