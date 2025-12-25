<script lang="ts">
  import {
    Shield,
    FileUp,
    AlertTriangle,
    CheckCircle,
    RefreshCw,
    Download,
    X,
    Trash2,
    FileCode,
    Paperclip,
    Link,
    MessageSquare,
    Info,
  } from 'lucide-svelte';
  import { invoke } from '@tauri-apps/api/core';
  import { open, save } from '@tauri-apps/plugin-dialog';

  interface SanitizationInfo {
    has_metadata: boolean;
    metadata_fields: string[];
    has_javascript: boolean;
    javascript_count: number;
    has_embedded_files: boolean;
    embedded_files_count: number;
    has_links: boolean;
    links_count: number;
    error: string | null;
  }

  interface SanitizationResult {
    success: boolean;
    message: string;
    removed: {
      metadata: boolean;
      javascript: number;
      embedded_files: number;
      links: number;
      annotations: number;
    };
  }

  let filePath = $state<string | null>(null);
  let fileName = $state('');
  let info = $state<SanitizationInfo | null>(null);

  // Options
  let removeMetadata = $state(true);
  let removeJavascript = $state(true);
  let removeEmbeddedFiles = $state(true);
  let removeLinks = $state(false);
  let removeAnnotations = $state(false);

  let isLoading = $state(false);
  let isProcessing = $state(false);
  let error = $state<string | null>(null);
  let successMessage = $state<string | null>(null);

  async function selectFile() {
    const selected = await open({
      multiple: false,
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });

    if (selected) {
      filePath = selected;
      fileName = selected.split('/').pop() || selected;
      error = null;
      successMessage = null;
      info = null;
      await analyzeFile();
    }
  }

  async function analyzeFile() {
    if (!filePath) return;

    isLoading = true;
    error = null;

    try {
      info = await invoke<SanitizationInfo>('pdf_sanitization_info', {
        input: filePath,
      });

      if (info.error) {
        error = info.error;
        info = null;
      }
    } catch (err) {
      error = String(err);
    } finally {
      isLoading = false;
    }
  }

  async function sanitize() {
    if (!filePath) return;

    const outputPath = await save({
      defaultPath: filePath.replace('.pdf', '_sanitized.pdf'),
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });

    if (!outputPath) return;

    isProcessing = true;
    error = null;
    successMessage = null;

    try {
      const result = await invoke<SanitizationResult>('pdf_sanitize', {
        input: filePath,
        output: outputPath,
        removeMetadata,
        removeJavascript,
        removeEmbeddedFiles,
        removeLinks,
        removeAnnotations,
      });

      if (result.success) {
        successMessage = result.message + `. Saved to ${outputPath.split('/').pop()}`;
      } else {
        error = result.message;
      }
    } catch (err) {
      error = String(err);
    } finally {
      isProcessing = false;
    }
  }

  // Check if there's anything to sanitize
  let hasContent = $derived(
    info &&
      (info.has_metadata || info.has_javascript || info.has_embedded_files || info.has_links)
  );

  // Check if at least one option is selected
  let canSanitize = $derived(
    filePath &&
      (removeMetadata || removeJavascript || removeEmbeddedFiles || removeLinks || removeAnnotations)
  );
</script>

<div class="flex flex-col h-full" style="background-color: var(--nord0);">
  <!-- Header -->
  <div
    class="flex items-center gap-3 px-4 py-3 border-b"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <div class="p-2 rounded-lg" style="background-color: var(--nord14);">
      <Shield size={20} style="color: var(--nord0);" />
    </div>
    <div>
      <h1 class="text-lg font-semibold" style="color: var(--nord6);">Sanitize PDF</h1>
      <p class="text-xs opacity-60">Remove metadata, scripts, and hidden content</p>
    </div>
  </div>

  <!-- Alerts -->
  {#if error}
    <div
      class="mx-4 mt-4 p-3 rounded-lg flex items-center gap-2"
      style="background-color: rgba(191, 97, 106, 0.15); border: 1px solid var(--nord11);"
    >
      <AlertTriangle size={16} style="color: var(--nord11);" />
      <span class="text-sm" style="color: var(--nord11);">{error}</span>
      <button onclick={() => (error = null)} class="ml-auto p-1 hover:opacity-70">
        <X size={14} style="color: var(--nord11);" />
      </button>
    </div>
  {/if}

  {#if successMessage}
    <div
      class="mx-4 mt-4 p-3 rounded-lg flex items-center gap-2"
      style="background-color: rgba(163, 190, 140, 0.15); border: 1px solid var(--nord14);"
    >
      <CheckCircle size={16} style="color: var(--nord14);" />
      <span class="text-sm" style="color: var(--nord14);">{successMessage}</span>
      <button onclick={() => (successMessage = null)} class="ml-auto p-1 hover:opacity-70">
        <X size={14} style="color: var(--nord14);" />
      </button>
    </div>
  {/if}

  <!-- Content -->
  <div class="flex-1 overflow-auto p-4">
    {#if !filePath}
      <!-- File Selection -->
      <div class="flex items-center justify-center h-full">
        <button
          onclick={selectFile}
          class="flex flex-col items-center gap-4 p-8 rounded-xl border-2 border-dashed transition-all hover:border-[var(--nord8)] hover:bg-[var(--nord1)]"
          style="border-color: var(--nord3);"
        >
          <div class="p-4 rounded-full" style="background-color: var(--nord1);">
            <FileUp size={32} style="color: var(--nord8);" />
          </div>
          <div class="text-center">
            <p class="text-lg font-medium" style="color: var(--nord6);">Select PDF to Sanitize</p>
            <p class="text-sm opacity-50 mt-1">Click to choose a file</p>
          </div>
        </button>
      </div>
    {:else}
      <div class="max-w-2xl mx-auto space-y-6">
        <!-- File Info -->
        <div class="p-4 rounded-lg" style="background-color: var(--nord1);">
          <div class="flex items-center gap-3">
            <Shield size={24} style="color: var(--nord8);" />
            <div class="flex-1 min-w-0">
              <p class="font-medium truncate" style="color: var(--nord6);">{fileName}</p>
              <button onclick={selectFile} class="text-xs hover:underline" style="color: var(--nord8);">
                Change file
              </button>
            </div>
            <button
              onclick={analyzeFile}
              class="p-2 rounded hover:bg-[var(--nord2)] transition-colors"
              title="Re-analyze"
              disabled={isLoading}
            >
              <RefreshCw size={16} class={isLoading ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        {#if isLoading}
          <div class="flex items-center justify-center py-8">
            <RefreshCw size={24} class="animate-spin opacity-50" />
          </div>
        {:else if info}
          <!-- Analysis Results -->
          <div class="p-4 rounded-lg space-y-4" style="background-color: var(--nord1);">
            <h3 class="font-medium flex items-center gap-2">
              <Info size={16} style="color: var(--nord8);" />
              Document Analysis
            </h3>

            <div class="grid grid-cols-2 gap-3">
              <!-- Metadata -->
              <div
                class="p-3 rounded flex items-center gap-3"
                style="background-color: var(--nord2);"
              >
                <Trash2
                  size={18}
                  style="color: {info.has_metadata ? 'var(--nord13)' : 'var(--nord4)'};"
                />
                <div class="flex-1">
                  <p class="text-sm font-medium">Metadata</p>
                  <p class="text-xs opacity-60">
                    {info.has_metadata ? info.metadata_fields.join(', ') : 'None found'}
                  </p>
                </div>
              </div>

              <!-- JavaScript -->
              <div
                class="p-3 rounded flex items-center gap-3"
                style="background-color: var(--nord2);"
              >
                <FileCode
                  size={18}
                  style="color: {info.has_javascript ? 'var(--nord11)' : 'var(--nord4)'};"
                />
                <div class="flex-1">
                  <p class="text-sm font-medium">JavaScript</p>
                  <p class="text-xs opacity-60">
                    {info.has_javascript ? `${info.javascript_count} action(s)` : 'None found'}
                  </p>
                </div>
              </div>

              <!-- Embedded Files -->
              <div
                class="p-3 rounded flex items-center gap-3"
                style="background-color: var(--nord2);"
              >
                <Paperclip
                  size={18}
                  style="color: {info.has_embedded_files ? 'var(--nord13)' : 'var(--nord4)'};"
                />
                <div class="flex-1">
                  <p class="text-sm font-medium">Embedded Files</p>
                  <p class="text-xs opacity-60">
                    {info.has_embedded_files
                      ? `${info.embedded_files_count} file(s)`
                      : 'None found'}
                  </p>
                </div>
              </div>

              <!-- Links -->
              <div
                class="p-3 rounded flex items-center gap-3"
                style="background-color: var(--nord2);"
              >
                <Link
                  size={18}
                  style="color: {info.has_links ? 'var(--nord8)' : 'var(--nord4)'};"
                />
                <div class="flex-1">
                  <p class="text-sm font-medium">External Links</p>
                  <p class="text-xs opacity-60">
                    {info.has_links ? `${info.links_count} link(s)` : 'None found'}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <!-- Options -->
          <div class="p-4 rounded-lg space-y-3" style="background-color: var(--nord1);">
            <h3 class="font-medium">Sanitization Options</h3>

            <label class="flex items-center gap-3 p-2 rounded hover:bg-[var(--nord2)] cursor-pointer">
              <input
                type="checkbox"
                bind:checked={removeMetadata}
                class="w-4 h-4 rounded"
                style="accent-color: var(--nord8);"
              />
              <Trash2 size={16} />
              <span class="text-sm">Remove Metadata</span>
              <span class="text-xs opacity-50 ml-auto">Author, dates, creator, etc.</span>
            </label>

            <label class="flex items-center gap-3 p-2 rounded hover:bg-[var(--nord2)] cursor-pointer">
              <input
                type="checkbox"
                bind:checked={removeJavascript}
                class="w-4 h-4 rounded"
                style="accent-color: var(--nord8);"
              />
              <FileCode size={16} />
              <span class="text-sm">Remove JavaScript</span>
              <span class="text-xs opacity-50 ml-auto">Scripts and actions</span>
            </label>

            <label class="flex items-center gap-3 p-2 rounded hover:bg-[var(--nord2)] cursor-pointer">
              <input
                type="checkbox"
                bind:checked={removeEmbeddedFiles}
                class="w-4 h-4 rounded"
                style="accent-color: var(--nord8);"
              />
              <Paperclip size={16} />
              <span class="text-sm">Remove Embedded Files</span>
              <span class="text-xs opacity-50 ml-auto">Attachments</span>
            </label>

            <label class="flex items-center gap-3 p-2 rounded hover:bg-[var(--nord2)] cursor-pointer">
              <input
                type="checkbox"
                bind:checked={removeLinks}
                class="w-4 h-4 rounded"
                style="accent-color: var(--nord8);"
              />
              <Link size={16} />
              <span class="text-sm">Remove External Links</span>
              <span class="text-xs opacity-50 ml-auto">URLs, file launches</span>
            </label>

            <label class="flex items-center gap-3 p-2 rounded hover:bg-[var(--nord2)] cursor-pointer">
              <input
                type="checkbox"
                bind:checked={removeAnnotations}
                class="w-4 h-4 rounded"
                style="accent-color: var(--nord8);"
              />
              <MessageSquare size={16} />
              <span class="text-sm">Remove All Annotations</span>
              <span class="text-xs opacity-50 ml-auto">Comments, highlights, etc.</span>
            </label>
          </div>

          <!-- Action -->
          <button
            onclick={sanitize}
            disabled={!canSanitize || isProcessing}
            class="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-colors disabled:opacity-40"
            style="background-color: var(--nord14); color: var(--nord0);"
          >
            {#if isProcessing}
              <RefreshCw size={18} class="animate-spin" />
              Sanitizing...
            {:else}
              <Download size={18} />
              Sanitize & Save
            {/if}
          </button>

          {#if !hasContent}
            <p class="text-xs text-center opacity-50">
              This document appears clean. You can still apply sanitization to ensure removal.
            </p>
          {/if}
        {/if}
      </div>
    {/if}
  </div>
</div>
