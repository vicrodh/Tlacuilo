<script lang="ts">
  import { open } from '@tauri-apps/plugin-dialog';
  import { FolderOpen, FileText } from 'lucide-svelte';
  import { PDFViewer } from '$lib/components/PDFViewer';
  import { registerFile } from '$lib/stores/status.svelte';

  const MODULE = 'Viewer';

  let filePath = $state<string | null>(null);
  let fileName = $state<string>('');

  async function handleOpenFile() {
    const selected = await open({
      multiple: false,
      filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
    });

    if (selected && typeof selected === 'string') {
      filePath = selected;
      fileName = selected.split('/').pop() || 'Document';
      registerFile(selected, fileName, MODULE);
    }
  }

  function handleClose() {
    filePath = null;
    fileName = '';
  }
</script>

<div class="flex-1 flex flex-col overflow-hidden">
  {#if filePath}
    <PDFViewer
      {filePath}
      showToolbar={true}
      showSidebar={true}
      showDetachButton={true}
      onClose={handleClose}
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
          <h2 class="text-xl mb-2" style="color: var(--nord6);">PDF Viewer</h2>
          <p class="text-sm opacity-60 max-w-xs">
            Open a PDF to view, annotate, and edit. Use the tools in the toolbar to highlight, draw, add text, and more.
          </p>
        </div>

        <button
          onclick={handleOpenFile}
          class="flex items-center gap-3 px-6 py-3 rounded-xl transition-all hover:scale-[1.02] active:scale-[0.98]"
          style="background-color: var(--nord8); color: var(--nord0);"
        >
          <FolderOpen size={20} />
          <span class="font-medium">Open PDF</span>
        </button>

        <p class="text-xs opacity-40">
          Supports PDF files up to 100MB
        </p>
      </div>
    </div>
  {/if}
</div>
