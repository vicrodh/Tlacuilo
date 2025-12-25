<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import { save } from '@tauri-apps/plugin-dialog';
  import { Paperclip, Download, FolderOpen, RefreshCw, FileText, Image, FileArchive, File, Check, AlertCircle, X, Eye } from 'lucide-svelte';

  interface AttachmentInfo {
    index: number;
    name: string;
    filename: string;
    size: number;
    length: number;
    created: string;
    modified: string;
    description: string;
  }

  interface AttachmentPreview {
    name: string;
    size: number;
    type: 'image' | 'text' | 'binary' | 'error';
    content: string | null;
    mime_type: string | null;
  }

  interface Props {
    filePath: string;
    fileReloadVersion?: number;
  }

  let { filePath, fileReloadVersion = 0 }: Props = $props();

  let attachments = $state<AttachmentInfo[]>([]);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let extracting = $state<number | null>(null);
  let extractSuccess = $state<number | null>(null);

  // Preview state
  let selectedAttachment = $state<AttachmentInfo | null>(null);
  let preview = $state<AttachmentPreview | null>(null);
  let previewLoading = $state(false);

  async function loadAttachments() {
    if (!filePath) return;

    loading = true;
    error = null;

    try {
      attachments = await invoke<AttachmentInfo[]>('attachments_list', { input: filePath });
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      attachments = [];
    } finally {
      loading = false;
    }
  }

  // Load attachments when filePath changes
  $effect(() => {
    if (filePath) {
      loadAttachments();
    }
  });

  // Reload when file version changes
  $effect(() => {
    if (fileReloadVersion > 0) {
      loadAttachments();
    }
  });

  function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
  }

  function getFileIcon(name: string): typeof File {
    const ext = name.split('.').pop()?.toLowerCase() || '';

    if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'tiff'].includes(ext)) {
      return Image;
    }
    if (['zip', 'rar', '7z', 'tar', 'gz', 'bz2'].includes(ext)) {
      return FileArchive;
    }
    if (['txt', 'md', 'json', 'xml', 'csv', 'log'].includes(ext)) {
      return FileText;
    }
    return File;
  }

  async function extractAttachment(attachment: AttachmentInfo) {
    extracting = attachment.index;
    extractSuccess = null;

    try {
      // Ask user where to save
      const savePath = await save({
        defaultPath: attachment.name,
        title: 'Save Attachment',
      });

      if (!savePath) {
        extracting = null;
        return;
      }

      await invoke('attachments_extract', {
        input: filePath,
        name: attachment.name,
        output: savePath,
      });

      extractSuccess = attachment.index;
      setTimeout(() => {
        extractSuccess = null;
      }, 2000);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      extracting = null;
    }
  }

  async function extractAll() {
    try {
      // Ask user for directory (using save dialog with a dummy filename)
      const savePath = await save({
        defaultPath: 'attachments',
        title: 'Choose folder for attachments',
      });

      if (!savePath) return;

      // Extract directory from path
      const outputDir = savePath.substring(0, savePath.lastIndexOf('/'));

      await invoke('attachments_extract_all', {
        input: filePath,
        outputDir,
      });

      extractSuccess = -1; // Special value for "all"
      setTimeout(() => {
        extractSuccess = null;
      }, 2000);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  function openInFileManager(path: string) {
    // On Linux, use xdg-open on the directory
    const dir = path.substring(0, path.lastIndexOf('/'));
    invoke('open_path', { path: dir }).catch(() => {
      // Fallback: do nothing
    });
  }

  async function loadPreview(attachment: AttachmentInfo) {
    if (selectedAttachment?.index === attachment.index && preview) {
      // Already loaded, toggle off
      closePreview();
      return;
    }

    selectedAttachment = attachment;
    previewLoading = true;
    preview = null;

    try {
      preview = await invoke<AttachmentPreview>('attachments_preview', {
        input: filePath,
        name: attachment.name,
      });
    } catch (e) {
      preview = {
        name: attachment.name,
        size: attachment.size,
        type: 'error',
        content: e instanceof Error ? e.message : String(e),
        mime_type: null,
      };
    } finally {
      previewLoading = false;
    }
  }

  function closePreview() {
    selectedAttachment = null;
    preview = null;
    previewLoading = false;
  }

  function isPreviewable(name: string): boolean {
    const ext = name.split('.').pop()?.toLowerCase() || '';
    const previewableExts = [
      'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp',
      'txt', 'md', 'json', 'xml', 'csv', 'log', 'html', 'css', 'js', 'ts', 'py', 'rs'
    ];
    return previewableExts.includes(ext);
  }
</script>

<div class="attachments-tab">
  <header class="tab-header">
    <div class="header-left">
      <h3>Attachments</h3>
      {#if attachments.length > 0}
        <span class="count">{attachments.length}</span>
      {/if}
    </div>
    <div class="header-actions">
      {#if attachments.length > 1}
        <button
          class="action-btn"
          onclick={extractAll}
          title="Extract all attachments"
        >
          <FolderOpen size={14} />
        </button>
      {/if}
      <button
        class="action-btn"
        onclick={() => loadAttachments()}
        disabled={loading}
        title="Refresh"
      >
        <RefreshCw size={14} class={loading ? 'spinning' : ''} />
      </button>
    </div>
  </header>

  {#if loading && attachments.length === 0}
    <div class="loading">
      <RefreshCw size={20} class="spinning" />
      <span>Loading...</span>
    </div>
  {:else if error}
    <div class="error">
      <AlertCircle size={16} />
      <p>{error}</p>
      <button class="retry-btn" onclick={() => loadAttachments()}>Retry</button>
    </div>
  {:else if attachments.length === 0}
    <div class="empty">
      <Paperclip size={24} class="opacity-20" />
      <p>No attachments</p>
      <span class="hint">This PDF has no embedded files</span>
    </div>
  {:else}
    <div class="attachments-list">
      {#each attachments as attachment (attachment.index)}
        {@const Icon = getFileIcon(attachment.name)}
        <div class="attachment-item" class:selected={selectedAttachment?.index === attachment.index}>
          <div class="attachment-icon">
            <Icon size={18} />
          </div>
          <div class="attachment-info">
            <span class="attachment-name" title={attachment.name}>
              {attachment.name}
            </span>
            <span class="attachment-size">
              {formatFileSize(attachment.size)}
              {#if attachment.description}
                <span class="separator">·</span>
                <span class="description" title={attachment.description}>
                  {attachment.description}
                </span>
              {/if}
            </span>
          </div>
          {#if isPreviewable(attachment.name)}
            <button
              class="preview-btn"
              onclick={() => loadPreview(attachment)}
              disabled={previewLoading && selectedAttachment?.index === attachment.index}
              title="Preview"
            >
              {#if previewLoading && selectedAttachment?.index === attachment.index}
                <RefreshCw size={14} class="spinning" />
              {:else}
                <Eye size={14} />
              {/if}
            </button>
          {/if}
          <button
            class="extract-btn"
            onclick={() => extractAttachment(attachment)}
            disabled={extracting === attachment.index}
            title="Extract"
          >
            {#if extracting === attachment.index}
              <RefreshCw size={14} class="spinning" />
            {:else if extractSuccess === attachment.index}
              <Check size={14} style="color: var(--nord14);" />
            {:else}
              <Download size={14} />
            {/if}
          </button>
        </div>
      {/each}
    </div>

    {#if extractSuccess === -1}
      <div class="success-toast">
        <Check size={14} />
        <span>All attachments extracted</span>
      </div>
    {/if}

    <!-- Preview Panel -->
    {#if preview}
      <div class="preview-panel">
        <div class="preview-header">
          <span class="preview-title" title={preview.name}>{preview.name}</span>
          <button class="close-preview-btn" onclick={closePreview} title="Close preview">
            <X size={14} />
          </button>
        </div>
        <div class="preview-content">
          {#if preview.type === 'image' && preview.content}
            <img
              src={`data:${preview.mime_type || 'image/png'};base64,${preview.content}`}
              alt={preview.name}
              class="preview-image"
            />
          {:else if preview.type === 'text' && preview.content}
            <pre class="preview-text">{preview.content}</pre>
          {:else if preview.type === 'binary'}
            <div class="preview-binary">
              <FileArchive size={24} class="opacity-40" />
              <p>Binary file - cannot preview</p>
              <span class="hint">Use extract to download</span>
            </div>
          {:else if preview.type === 'error'}
            <div class="preview-error">
              <AlertCircle size={20} />
              <p>{preview.content}</p>
            </div>
          {/if}
        </div>
      </div>
    {/if}
  {/if}
</div>

<style>
  .attachments-tab {
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

  .header-left {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .tab-header h3 {
    margin: 0;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--nord6);
  }

  .count {
    font-size: 0.625rem;
    padding: 0.125rem 0.375rem;
    border-radius: 9999px;
    background-color: var(--nord2);
    color: var(--nord4);
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .action-btn {
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

  .action-btn:hover:not(:disabled) {
    background-color: var(--nord2);
    color: var(--nord8);
  }

  .action-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .attachments-list {
    flex: 1;
    overflow-y: auto;
    padding: 0.5rem;
  }

  .attachment-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    background-color: var(--nord0);
    margin-bottom: 0.25rem;
    transition: all 0.15s;
  }

  .attachment-item:hover {
    background-color: var(--nord2);
  }

  .attachment-item.selected {
    background-color: var(--nord2);
    border-left: 2px solid var(--nord8);
    margin-left: -2px;
  }

  .attachment-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 6px;
    background-color: var(--nord2);
    color: var(--nord8);
    flex-shrink: 0;
  }

  .attachment-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .attachment-name {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--nord6);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .attachment-size {
    font-size: 0.625rem;
    color: var(--nord4);
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .separator {
    opacity: 0.5;
  }

  .description {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 80px;
  }

  .extract-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: 4px;
    color: var(--nord4);
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .extract-btn:hover:not(:disabled) {
    background-color: var(--nord3);
    color: var(--nord8);
  }

  .extract-btn:disabled {
    cursor: not-allowed;
  }

  .preview-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: 4px;
    color: var(--nord4);
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .preview-btn:hover:not(:disabled) {
    background-color: var(--nord3);
    color: var(--nord8);
  }

  .preview-btn:disabled {
    cursor: not-allowed;
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

  .empty .hint {
    font-size: 0.625rem;
    opacity: 0.6;
  }

  .error {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    padding: 1rem;
    text-align: center;
    color: var(--nord11);
  }

  .error p {
    font-size: 0.75rem;
    margin: 0;
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

  .success-toast {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.5rem;
    margin: 0.5rem;
    border-radius: 6px;
    background-color: rgba(163, 190, 140, 0.2);
    color: var(--nord14);
    font-size: 0.75rem;
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

  /* Preview Panel */
  .preview-panel {
    border-top: 1px solid var(--nord3);
    background-color: var(--nord0);
    max-height: 300px;
    display: flex;
    flex-direction: column;
  }

  .preview-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem 0.75rem;
    background-color: var(--nord1);
    border-bottom: 1px solid var(--nord3);
  }

  .preview-title {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--nord6);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }

  .close-preview-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: 4px;
    color: var(--nord4);
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .close-preview-btn:hover {
    background-color: var(--nord2);
    color: var(--nord11);
  }

  .preview-content {
    flex: 1;
    overflow: auto;
    padding: 0.5rem;
  }

  .preview-image {
    max-width: 100%;
    height: auto;
    border-radius: 4px;
    display: block;
    margin: 0 auto;
  }

  .preview-text {
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 0.625rem;
    line-height: 1.4;
    margin: 0;
    padding: 0.5rem;
    background-color: var(--nord1);
    border-radius: 4px;
    color: var(--nord5);
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }

  .preview-binary,
  .preview-error {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 1.5rem;
    text-align: center;
    color: var(--nord4);
  }

  .preview-binary p,
  .preview-error p {
    font-size: 0.75rem;
    margin: 0;
  }

  .preview-binary .hint {
    font-size: 0.625rem;
    opacity: 0.6;
  }

  .preview-error {
    color: var(--nord11);
  }
</style>
