<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import { FileText, User, Calendar, Lock, RefreshCw, Copy, Check } from 'lucide-svelte';

  interface PdfMetadata {
    format: string | null;
    encryption: string | null;
    title: string | null;
    author: string | null;
    subject: string | null;
    keywords: string | null;
    creator: string | null;
    producer: string | null;
    creation_date: string | null;
    mod_date: string | null;
    page_count: number;
    file_size: number;
  }

  interface Props {
    filePath: string;
    fileReloadVersion?: number;
  }

  let { filePath, fileReloadVersion = 0 }: Props = $props();

  let metadata = $state<PdfMetadata | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let copiedField = $state<string | null>(null);

  async function loadMetadata() {
    if (!filePath) return;

    loading = true;
    error = null;

    try {
      metadata = await invoke<PdfMetadata>('pdf_get_metadata', { path: filePath });
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      metadata = null;
    } finally {
      loading = false;
    }
  }

  // Load metadata when filePath changes
  $effect(() => {
    if (filePath) {
      loadMetadata();
    }
  });

  // Reload when file version changes
  $effect(() => {
    if (fileReloadVersion > 0) {
      loadMetadata();
    }
  });

  function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
  }

  function formatPdfDate(dateStr: string | null): string | null {
    if (!dateStr) return null;

    // PDF date format: D:YYYYMMDDHHmmSSOHH'mm'
    const match = dateStr.match(/D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?/);
    if (!match) return dateStr;

    const [, year, month, day, hour = '00', minute = '00'] = match;
    const date = new Date(
      parseInt(year),
      parseInt(month) - 1,
      parseInt(day),
      parseInt(hour),
      parseInt(minute)
    );

    return date.toLocaleString();
  }

  function getFileName(): string {
    if (!filePath) return '';
    return filePath.split('/').pop() || filePath;
  }

  async function copyToClipboard(text: string, fieldName: string) {
    try {
      await navigator.clipboard.writeText(text);
      copiedField = fieldName;
      setTimeout(() => {
        copiedField = null;
      }, 1500);
    } catch (e) {
      console.error('Failed to copy:', e);
    }
  }

  interface MetadataField {
    label: string;
    value: string | null;
    icon: typeof FileText;
  }

  const fields = $derived.by(() => {
    if (!metadata) return [];

    const result: MetadataField[] = [
      { label: 'Title', value: metadata.title, icon: FileText },
      { label: 'Author', value: metadata.author, icon: User },
      { label: 'Subject', value: metadata.subject, icon: FileText },
      { label: 'Keywords', value: metadata.keywords, icon: FileText },
      { label: 'Creator', value: metadata.creator, icon: FileText },
      { label: 'Producer', value: metadata.producer, icon: FileText },
      { label: 'Created', value: formatPdfDate(metadata.creation_date), icon: Calendar },
      { label: 'Modified', value: formatPdfDate(metadata.mod_date), icon: Calendar },
    ];

    return result.filter((f) => f.value);
  });
</script>

<div class="metadata-tab">
  <header class="tab-header">
    <h3>Document Info</h3>
    <button
      class="refresh-btn"
      onclick={() => loadMetadata()}
      disabled={loading}
      title="Refresh metadata"
    >
      <RefreshCw size={14} class={loading ? 'spinning' : ''} />
    </button>
  </header>

  {#if loading && !metadata}
    <div class="loading">
      <RefreshCw size={20} class="spinning" />
      <span>Loading...</span>
    </div>
  {:else if error}
    <div class="error">
      <p>{error}</p>
      <button class="retry-btn" onclick={() => loadMetadata()}>Retry</button>
    </div>
  {:else if metadata}
    <div class="metadata-content">
      <!-- File Info Section -->
      <section class="section">
        <h4 class="section-title">File</h4>
        <div class="field">
          <span class="field-label">Name</span>
          <span class="field-value filename" title={filePath}>{getFileName()}</span>
        </div>
        <div class="field">
          <span class="field-label">Size</span>
          <span class="field-value">{formatFileSize(metadata.file_size)}</span>
        </div>
        <div class="field">
          <span class="field-label">Pages</span>
          <span class="field-value">{metadata.page_count}</span>
        </div>
      </section>

      <!-- PDF Properties Section -->
      <section class="section">
        <h4 class="section-title">PDF</h4>
        <div class="field">
          <span class="field-label">Format</span>
          <span class="field-value">{metadata.format || 'Unknown'}</span>
        </div>
        {#if metadata.encryption}
          <div class="field">
            <span class="field-label">
              <Lock size={12} />
              Security
            </span>
            <span class="field-value">{metadata.encryption}</span>
          </div>
        {:else}
          <div class="field">
            <span class="field-label">Security</span>
            <span class="field-value muted">None</span>
          </div>
        {/if}
      </section>

      <!-- Document Metadata Section -->
      {#if fields.length > 0}
        <section class="section">
          <h4 class="section-title">Metadata</h4>
          {#each fields as field}
            <div class="field">
              <span class="field-label">{field.label}</span>
              <div class="field-value-container">
                <span class="field-value" title={field.value || ''}>
                  {field.value}
                </span>
                <button
                  class="copy-btn"
                  onclick={() => copyToClipboard(field.value || '', field.label)}
                  title="Copy"
                >
                  {#if copiedField === field.label}
                    <Check size={12} />
                  {:else}
                    <Copy size={12} />
                  {/if}
                </button>
              </div>
            </div>
          {/each}
        </section>
      {:else}
        <section class="section">
          <h4 class="section-title">Metadata</h4>
          <p class="no-metadata">No document metadata available</p>
        </section>
      {/if}
    </div>
  {:else}
    <div class="empty">
      <FileText size={24} class="opacity-20" />
      <p>No file loaded</p>
    </div>
  {/if}
</div>

<style>
  .metadata-tab {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .tab-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--nord3);
    background-color: var(--nord1);
  }

  .tab-header h3 {
    margin: 0;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--nord6);
  }

  .refresh-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: 4px;
    color: var(--nord4);
    cursor: pointer;
    transition: all 0.15s;
  }

  .refresh-btn:hover:not(:disabled) {
    background-color: var(--nord2);
    color: var(--nord8);
  }

  .refresh-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .metadata-content {
    flex: 1;
    overflow-y: auto;
    padding: 0.5rem;
  }

  .section {
    background-color: var(--nord0);
    border-radius: 6px;
    padding: 0.75rem;
    margin-bottom: 0.5rem;
  }

  .section-title {
    margin: 0 0 0.5rem 0;
    font-size: 0.625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--nord4);
  }

  .field {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.25rem 0;
  }

  .field:not(:last-child) {
    border-bottom: 1px solid var(--nord2);
  }

  .field-label {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.75rem;
    color: var(--nord4);
    flex-shrink: 0;
  }

  .field-value-container {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    max-width: 60%;
  }

  .field-value {
    font-size: 0.75rem;
    color: var(--nord6);
    text-align: right;
    word-break: break-word;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .field-value.filename {
    max-width: 120px;
    white-space: nowrap;
  }

  .field-value.muted {
    color: var(--nord4);
    font-style: italic;
  }

  .copy-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: 3px;
    color: var(--nord4);
    cursor: pointer;
    opacity: 0;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .field:hover .copy-btn {
    opacity: 1;
  }

  .copy-btn:hover {
    background-color: var(--nord2);
    color: var(--nord8);
  }

  .no-metadata {
    font-size: 0.75rem;
    color: var(--nord4);
    font-style: italic;
    text-align: center;
    padding: 0.5rem 0;
  }

  .loading,
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 2rem;
    color: var(--nord4);
  }

  .loading span,
  .empty p {
    font-size: 0.75rem;
    margin: 0;
  }

  .error {
    padding: 1rem;
    text-align: center;
  }

  .error p {
    font-size: 0.75rem;
    color: var(--nord11);
    margin: 0 0 0.5rem 0;
  }

  .retry-btn {
    padding: 0.25rem 0.75rem;
    font-size: 0.75rem;
    background-color: var(--nord2);
    border: none;
    border-radius: 4px;
    color: var(--nord6);
    cursor: pointer;
    transition: all 0.15s;
  }

  .retry-btn:hover {
    background-color: var(--nord3);
  }

  :global(.spinning) {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }
</style>
