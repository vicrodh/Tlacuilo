<svelte:head>
  <title>Tlacuilo</title>
</svelte:head>

<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { Activity, ChevronUp, ChevronDown, CheckCircle, AlertCircle, AlertTriangle, Info, Trash2 } from 'lucide-svelte';
  import { open } from '@tauri-apps/plugin-dialog';
  import { listen, type UnlistenFn } from '@tauri-apps/api/event';
  import Sidebar from './lib/components/Sidebar.svelte';
  import Dashboard from './lib/views/Dashboard.svelte';
  import MergePDF from './lib/views/MergePDF.svelte';
  import SplitPDF from './lib/views/SplitPDF.svelte';
  import RotatePDF from './lib/views/RotatePDF.svelte';
  import CompressPDF from './lib/views/CompressPDF.svelte';
  import OCRPDF from './lib/views/OCRPDF.svelte';
  import ConvertToPDF from './lib/views/ConvertToPDF.svelte';
  import ConvertFromPDF from './lib/views/ConvertFromPDF.svelte';
  import ViewerPage from './lib/views/ViewerPage.svelte';
  import Settings from './lib/views/Settings.svelte';
  import PlaceholderPage from './lib/views/PlaceholderPage.svelte';
  import { getStatus, toggleExpanded, clearLogs, setPendingOpenFile, type LogLevel } from './lib/stores/status.svelte';

  let sidebarExpanded = $state(true);
  let currentPage = $state('home');

  const status = getStatus();

  let unlistenMenuOpen: UnlistenFn | null = null;

  onMount(async () => {
    // Listen for File > Open from native menu
    unlistenMenuOpen = await listen('menu-open', handleMenuOpen);
  });

  onDestroy(() => {
    unlistenMenuOpen?.();
  });

  function navigate(page: string) {
    currentPage = page;
  }

  function toggleSidebar() {
    sidebarExpanded = !sidebarExpanded;
  }

  async function handleMenuOpen() {
    try {
      const selected = await open({
        multiple: false,
        filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
      });
      if (selected && typeof selected === 'string') {
        setPendingOpenFile(selected);
        navigate('viewer');
      }
    } catch (err) {
      console.error('[App] File dialog error:', err);
    }
  }

  const currentDate = new Date().toLocaleDateString();

  // Get color based on log level
  function getLevelColor(level: LogLevel): string {
    switch (level) {
      case 'success': return 'var(--nord14)';
      case 'error': return 'var(--nord11)';
      case 'warning': return 'var(--nord13)';
      default: return 'var(--nord8)';
    }
  }

  // Format timestamp
  function formatTime(date: Date): string {
    return date.toLocaleTimeString('en-US', { hour12: false });
  }

  // Get file display text
  const fileDisplayText = $derived(() => {
    if (status.fileCount === 0) return 'No file selected';
    if (status.fileCount === 1) return status.openFiles[0].name;
    return `${status.fileCount} files open`;
  });

  // Get tooltip for files
  const fileTooltip = $derived(() => {
    if (status.fileCount <= 1) return '';
    return status.openFiles.map(f => `${f.module}: ${f.name}`).join('\n');
  });
</script>

<div class="h-screen flex flex-col" style="background-color: var(--nord0);">
  <!-- Main Content Area (no header) -->
  <div class="flex-1 flex overflow-hidden">
    <Sidebar
      isExpanded={sidebarExpanded}
      {currentPage}
      onNavigate={navigate}
      onToggle={toggleSidebar}
    />

    <main class="flex-1 flex flex-col overflow-hidden">
      {#if currentPage === 'home'}
        <Dashboard onNavigate={navigate} />
      {:else if currentPage === 'merge'}
        <MergePDF onOpenInViewer={(path) => { setPendingOpenFile(path); navigate('viewer'); }} />
      {:else if currentPage === 'split'}
        <SplitPDF />
      {:else if currentPage === 'rotate'}
        <RotatePDF onOpenInViewer={(path) => { setPendingOpenFile(path); navigate('viewer'); }} />
      {:else if currentPage === 'compress'}
        <CompressPDF />
      {:else if currentPage === 'ocr'}
        <OCRPDF />
      {:else if currentPage === 'convert'}
        <ConvertToPDF />
      {:else if currentPage === 'export'}
        <ConvertFromPDF />
      {:else if currentPage === 'viewer'}
        <ViewerPage />
      {:else if currentPage === 'settings'}
        <Settings />
      {:else}
        <PlaceholderPage pageName={currentPage} />
      {/if}
    </main>
  </div>

  <!-- Log Panel (expandable) -->
  {#if status.isExpanded}
    <div
      class="border-t overflow-hidden"
      style="background-color: var(--nord0); border-color: var(--nord3); height: 150px;"
    >
      <div class="h-full flex flex-col">
        <div
          class="flex items-center justify-between px-4 py-1 border-b"
          style="background-color: var(--nord1); border-color: var(--nord3);"
        >
          <span class="text-xs opacity-60 uppercase">Log History</span>
          <button
            onclick={clearLogs}
            class="p-1 rounded hover:bg-[var(--nord2)] transition-colors opacity-60 hover:opacity-100"
            title="Clear logs"
          >
            <Trash2 size={12} />
          </button>
        </div>
        <div class="flex-1 overflow-auto p-2 space-y-1">
          {#each status.logs as entry (entry.id)}
            <div class="flex items-start gap-2 text-xs py-0.5">
              <span class="opacity-40 font-mono">{formatTime(entry.timestamp)}</span>
              {#if entry.level === 'success'}
                <CheckCircle size={12} style="color: var(--nord14); flex-shrink: 0; margin-top: 2px;" />
              {:else if entry.level === 'error'}
                <AlertCircle size={12} style="color: var(--nord11); flex-shrink: 0; margin-top: 2px;" />
              {:else if entry.level === 'warning'}
                <AlertTriangle size={12} style="color: var(--nord13); flex-shrink: 0; margin-top: 2px;" />
              {:else}
                <Info size={12} style="color: var(--nord8); flex-shrink: 0; margin-top: 2px;" />
              {/if}
              {#if entry.module}
                <span class="opacity-50">[{entry.module}]</span>
              {/if}
              <span style="color: {getLevelColor(entry.level)};">{entry.message}</span>
            </div>
          {:else}
            <div class="text-xs opacity-40 text-center py-4">No logs yet</div>
          {/each}
        </div>
      </div>
    </div>
  {/if}

  <!-- Status Bar / Footer -->
  <footer
    class="h-8 flex items-center justify-between px-4 text-xs border-t"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <div class="flex items-center gap-4">
      <button
        onclick={toggleExpanded}
        class="flex items-center gap-2 hover:bg-[var(--nord2)] px-2 py-1 rounded transition-colors"
      >
        {#if status.isExpanded}
          <ChevronDown size={14} class="opacity-60" />
        {:else}
          <ChevronUp size={14} class="opacity-60" />
        {/if}
        {#if status.level === 'success'}
          <CheckCircle size={14} style="color: var(--nord14);" />
        {:else if status.level === 'error'}
          <AlertCircle size={14} style="color: var(--nord11);" />
        {:else if status.level === 'warning'}
          <AlertTriangle size={14} style="color: var(--nord13);" />
        {:else}
          <Activity size={14} style="color: var(--nord8);" />
        {/if}
        <span style="color: {getLevelColor(status.level)};">{status.current}</span>
      </button>
    </div>
    <div class="flex items-center gap-4 opacity-60">
      <span title={fileTooltip()}>{fileDisplayText()}</span>
      <span>•</span>
      <span>{currentDate}</span>
    </div>
  </footer>
</div>
