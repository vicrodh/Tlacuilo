<script lang="ts">
  import { onMount } from 'svelte';
  import { open, save } from '@tauri-apps/plugin-dialog';
  import { copyFile } from '@tauri-apps/plugin-fs';
  import { FolderOpen, FileText } from 'lucide-svelte';
  import { MuPDFViewer } from '$lib/components/PDFViewer';
  import { registerFile, consumePendingOpenFile } from '$lib/stores/status.svelte';
  import { useTranslations } from '$lib/i18n';

  const MODULE = 'Viewer';
  const t = $derived(useTranslations());

  let filePath = $state<string | null>(null);
  let fileName = $state<string>('');
  let hasUnsavedChanges = $state(false);

  // Check for pending file to open (from app menu)
  onMount(() => {
    const pending = consumePendingOpenFile();
    if (pending) {
      filePath = pending;
      fileName = pending.split('/').pop() || 'Document';
      registerFile(pending, fileName, MODULE);
    }
  });

  async function handleOpenFile() {
    console.log('[ViewerPage] Opening file dialog...');
    try {
      const selected = await open({
        multiple: false,
        filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
      });
      console.log('[ViewerPage] File dialog returned:', selected);

      if (selected && typeof selected === 'string') {
        filePath = selected;
        fileName = selected.split('/').pop() || 'Document';
        registerFile(selected, fileName, MODULE);
        console.log('[ViewerPage] File selected:', fileName);
      }
    } catch (err) {
      console.error('[ViewerPage] File dialog error:', err);
    }
  }

  function handleClose() {
    filePath = null;
    fileName = '';
  }

  async function handleSave() {
    if (!filePath) return;

    if (!hasUnsavedChanges) {
      console.log('No changes to save');
      return;
    }

    try {
      console.log('File saved:', filePath);
    } catch (err) {
      console.error('Failed to save file:', err);
    }
  }

  async function handleSaveAs() {
    if (!filePath) return;

    try {
      const savePath = await save({
        filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
        defaultPath: fileName,
      });

      if (savePath) {
        await copyFile(filePath, savePath);
        filePath = savePath;
        fileName = savePath.split('/').pop() || 'Document';
        registerFile(savePath, fileName, MODULE);
        console.log('File saved as:', savePath);
      }
    } catch (err) {
      console.error('Failed to save file:', err);
    }
  }
</script>

<div class="flex-1 flex flex-col overflow-hidden">
  {#if filePath}
    <MuPDFViewer
      {filePath}
      onClose={handleClose}
      onSave={handleSave}
      onSaveAs={handleSaveAs}
    />
  {:else}
    <!-- Empty state with open file button -->
    <div
      class="flex-1 flex flex-col items-center justify-center"
      style="background-color: var(--nord0);"
    >
      <div
        class="flex flex-col items-center gap-6 p-12 rounded-2xl"
        style="background-color: var(--nord1);"
      >
        <div
          class="w-20 h-20 rounded-2xl flex items-center justify-center"
          style="background-color: var(--nord2);"
        >
          <FileText size={40} style="color: var(--nord8);" />
        </div>

        <div class="text-center">
          <h2 class="text-xl mb-2" style="color: var(--nord6);">{t.viewer.title}</h2>
          <p class="text-sm opacity-60 max-w-xs">
            {t.viewer.description}
          </p>
        </div>

        <button
          onclick={handleOpenFile}
          class="flex items-center gap-3 px-6 py-3 rounded-xl transition-all hover:scale-[1.02] active:scale-[0.98]"
          style="background-color: var(--nord8); color: var(--on-primary);"
        >
          <FolderOpen size={20} />
          <span class="font-medium">{t.viewer.openPdf}</span>
        </button>

        <p class="text-xs opacity-40">
          Supports PDF files up to 100MB
        </p>
      </div>
    </div>
  {/if}
</div>
