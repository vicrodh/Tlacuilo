<script lang="ts">
  import {
    BookOpen,
    Merge,
    Scissors,
    RotateCw,
    RefreshCw,
    Shield,
    Pencil,
    PenTool,
    FileArchive,
    ScanText,
    ChevronDown,
    ChevronUp,
    FileIcon,
    Trash2,
    Image,
    Images,
    FileText,
    FileOutput,
    Lock,
    Unlock,
    EyeOff,
    Droplet,
    Hash,
    Stamp,
    Upload,
    ShieldCheck,
    Type,
    X
  } from 'lucide-svelte';
  import { onMount } from 'svelte';
  import {
    getSettings,
    getToolsByGroup,
    clearRecentFiles,
    removeRecentFile,
    toggleRecentFilesExpanded,
    type RecentFile
  } from '$lib/stores/settings.svelte';
  import { setPendingOpenFile } from '$lib/stores/status.svelte';

  interface Props {
    onNavigate?: (page: string) => void;
  }

  let { onNavigate }: Props = $props();

  const settings = getSettings();

  // Icon mapping
  const iconMap: Record<string, typeof Merge> = {
    BookOpen, Merge, Scissors, RotateCw, RefreshCw, Shield, Pencil, PenTool,
    FileArchive, ScanText, Image, Images, FileText, FileOutput,
    Lock, Unlock, EyeOff, Droplet, Hash, Stamp, Upload, ShieldCheck, Type
  };

  // Tool groups with their children
  const toolGroups = [
    {
      id: 'convert',
      label: 'Convert',
      icon: RefreshCw,
      children: [
        { id: 'convert-images-to-pdf', label: 'Images → PDF', icon: Image, page: 'convert' },
        { id: 'convert-pdf-to-images', label: 'PDF → Images', icon: Images, page: 'export' },
        { id: 'convert-docs-to-pdf', label: 'Documents → PDF', icon: FileText, page: 'convert-docs' },
        { id: 'convert-pdf-to-docs', label: 'PDF → Documents', icon: FileOutput, page: 'export-docs' },
      ]
    },
    {
      id: 'protect',
      label: 'Protect',
      icon: Shield,
      children: [
        { id: 'protect-encrypt', label: 'Encrypt PDF', icon: Lock, page: 'encrypt' },
        { id: 'protect-decrypt', label: 'Decrypt PDF', icon: Unlock, page: 'decrypt' },
        { id: 'protect-redact', label: 'Redact Content', icon: EyeOff, page: 'redact' },
      ]
    },
    {
      id: 'annotate',
      label: 'Annotate',
      icon: Pencil,
      children: [
        { id: 'annotate-watermark', label: 'Watermark', icon: Droplet, page: 'watermark' },
        { id: 'annotate-page-numbers', label: 'Page Numbers', icon: Hash, page: 'page-numbers' },
        { id: 'annotate-stamps', label: 'Stamps', icon: Stamp, page: 'stamps' },
      ]
    },
    {
      id: 'sign',
      label: 'Sign',
      icon: PenTool,
      children: [
        { id: 'sign-draw', label: 'Draw Signature', icon: PenTool, page: 'sign-draw' },
        { id: 'sign-upload', label: 'Upload Signature', icon: Upload, page: 'sign-upload' },
        { id: 'sign-certificate', label: 'Digital Certificate', icon: ShieldCheck, page: 'sign-cert' },
      ]
    },
  ];

  // Standalone tools (no dropdown)
  const standaloneTools = [
    { id: 'viewer', label: 'Viewer', icon: BookOpen, page: 'viewer' },
    { id: 'merge', label: 'Merge', icon: Merge, page: 'merge' },
    { id: 'split', label: 'Split', icon: Scissors, page: 'split' },
    { id: 'rotate', label: 'Rotate', icon: RotateCw, page: 'rotate' },
    { id: 'compress', label: 'Compress', icon: FileArchive, page: 'compress' },
    { id: 'ocr', label: 'OCR', icon: ScanText, page: 'ocr' },
    { id: 'font-detect', label: 'Font Detection', icon: Type, page: 'font-detect' },
  ];

  // Expanded dropdown state
  let expandedGroup = $state<string | null>(null);
  let dropdownPosition = $state<{ x: number; y: number } | null>(null);

  function toggleGroup(groupId: string, event: MouseEvent) {
    if (expandedGroup === groupId) {
      expandedGroup = null;
      dropdownPosition = null;
    } else {
      expandedGroup = groupId;
      const target = event.currentTarget as HTMLElement;
      const rect = target.getBoundingClientRect();
      dropdownPosition = {
        x: rect.left + rect.width / 2,
        y: rect.bottom + 8,
      };
    }
  }

  function handleToolClick(page: string) {
    expandedGroup = null;
    dropdownPosition = null;
    onNavigate?.(page);
  }

  function handleRecentFileClick(file: RecentFile) {
    setPendingOpenFile(file.path);
    onNavigate?.('viewer');
    // Dispatch event for TabViewerContainer to handle the pending file
    window.dispatchEvent(new CustomEvent('pending-file-ready'));
  }

  function handleClickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (!target.closest('.tool-group') && !target.closest('.macos-dropdown')) {
      expandedGroup = null;
      dropdownPosition = null;
    }
  }

  function formatDate(timestamp: number): string {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) return 'Today';
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days} days ago`;
    return date.toLocaleDateString();
  }

  onMount(() => {
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  });
</script>

<div class="flex-1 overflow-auto p-8">
  <!-- Quick Tools Section -->
  <div class="mb-8">
    <h2 class="mb-6 text-xl font-medium" style="color: var(--nord6);">Quick Tools</h2>

    <div class="grid grid-cols-5 gap-3">
      <!-- Standalone tools -->
      {#each standaloneTools as tool}
        <button
          onclick={() => handleToolClick(tool.page)}
          class="tool-button flex flex-col items-center justify-center gap-2 p-5 rounded-xl transition-all hover:scale-[1.02] active:scale-[0.98]"
          style="background-color: var(--nord1); border: 1px solid var(--nord3);"
        >
          <tool.icon size={28} style="color: var(--nord8);" />
          <span class="text-sm">{tool.label}</span>
        </button>
      {/each}

      <!-- Tool groups with dropdowns -->
      {#each toolGroups as group}
        <button
          onclick={(e) => toggleGroup(group.id, e)}
          class="tool-group flex flex-col items-center justify-center gap-2 p-5 rounded-xl transition-all hover:scale-[1.02] active:scale-[0.98] relative"
          style="background-color: {expandedGroup === group.id ? 'var(--nord2)' : 'var(--nord1)'};
                 border: 1px solid {expandedGroup === group.id ? 'var(--nord8)' : 'var(--nord3)'};"
        >
          <group.icon size={28} style="color: var(--nord8);" />
          <div class="flex items-center gap-1">
            <span class="text-sm">{group.label}</span>
            <ChevronDown
              size={14}
              class="transition-transform {expandedGroup === group.id ? 'rotate-180' : ''}"
              style="color: var(--nord4);"
            />
          </div>
        </button>
      {/each}
    </div>
  </div>

  <!-- macOS-style Dropdown -->
  {#if expandedGroup && dropdownPosition}
    {@const group = toolGroups.find(g => g.id === expandedGroup)}
    {#if group}
      <div
        class="macos-dropdown fixed z-50"
        style="
          left: {dropdownPosition.x}px;
          top: {dropdownPosition.y}px;
          transform: translateX(-50%);
        "
      >
        <!-- Arrow -->
        <div
          class="absolute -top-2 left-1/2 -translate-x-1/2 w-4 h-4 rotate-45"
          style="background: var(--nord1);"
        ></div>

        <!-- Dropdown content -->
        <div
          class="relative rounded-xl overflow-hidden shadow-2xl"
          style="
            background: var(--nord1);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--nord3);
            min-width: 200px;
          "
        >
          <div class="p-2">
            {#each group.children as child, index}
              <button
                onclick={() => handleToolClick(child.page)}
                class="dropdown-item w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left"
                style="color: var(--nord5);"
              >
                <div
                  class="w-8 h-8 rounded-lg flex items-center justify-center"
                  style="background-color: var(--nord2);"
                >
                  <child.icon size={16} style="color: var(--nord8);" />
                </div>
                <span class="text-sm">{child.label}</span>
              </button>
              {#if index < group.children.length - 1}
                <div class="mx-3 my-1 h-px" style="background: var(--nord3);"></div>
              {/if}
            {/each}
          </div>
        </div>
      </div>
    {/if}
  {/if}

  <!-- Recent Files Section -->
  {#if settings.showRecentFilesInHome}
  <div
    class="rounded-xl overflow-hidden"
    style="background-color: var(--nord1);"
  >
    <!-- Header with toggle -->
    <div
      class="flex justify-between items-center px-5 py-3 hover:bg-[var(--nord2)] transition-colors cursor-pointer"
      role="button"
      tabindex="0"
      onclick={() => toggleRecentFilesExpanded()}
      onkeydown={(e) => e.key === 'Enter' && toggleRecentFilesExpanded()}
    >
      <div class="flex items-center gap-2">
        <h2 class="text-base font-medium" style="color: var(--nord6);">Recent Files</h2>
        <span class="text-xs px-2 py-0.5 rounded-full" style="background-color: var(--nord2); color: var(--nord4);">
          {settings.recentFiles.length}
        </span>
      </div>
      <div class="flex items-center gap-2">
        {#if settings.recentFiles.length > 0}
          <button
            onclick={(e) => { e.stopPropagation(); clearRecentFiles(); }}
            class="text-xs px-2 py-1 rounded hover:bg-[var(--nord3)] transition-colors"
            style="color: var(--nord11);"
          >
            Clear
          </button>
        {/if}
        {#if settings.recentFilesExpanded}
          <ChevronUp size={16} style="color: var(--nord4);" />
        {:else}
          <ChevronDown size={16} style="color: var(--nord4);" />
        {/if}
      </div>
    </div>

    <!-- Collapsible content -->
    {#if settings.recentFilesExpanded}
      <div class="px-3 pb-3">
        {#if settings.recentFiles.length === 0}
          <div class="py-6 text-center">
            <FileIcon size={24} class="mx-auto mb-2 opacity-30" />
            <p class="text-xs opacity-40">No recent files</p>
          </div>
        {:else}
          <div class="space-y-0.5">
            {#each settings.recentFiles as file}
              <div
                onclick={() => handleRecentFileClick(file)}
                onkeydown={(e) => e.key === 'Enter' && handleRecentFileClick(file)}
                class="flex items-center justify-between px-3 py-1.5 rounded-lg transition-colors hover:bg-[var(--nord2)] cursor-pointer group"
                role="button"
                tabindex="0"
              >
                <div class="flex items-center gap-2 min-w-0 flex-1">
                  <FileIcon size={14} style="color: var(--nord8);" class="flex-shrink-0" />
                  <span class="text-xs truncate" title={file.path}>{file.name}</span>
                </div>
                <div class="flex items-center gap-2">
                  <span class="text-[10px] opacity-40">{formatDate(file.accessedAt)}</span>
                  <button
                    onclick={(e) => { e.stopPropagation(); removeRecentFile(file.path); }}
                    class="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-[var(--nord3)] transition-all"
                    title="Remove"
                  >
                    <X size={10} style="color: var(--nord11);" />
                  </button>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  </div>
  {/if}
</div>

<style>
  .macos-dropdown {
    animation: dropdown-appear 0.15s ease-out;
  }

  @keyframes dropdown-appear {
    from {
      opacity: 0;
      transform: translateX(-50%) translateY(-4px) scale(0.96);
    }
    to {
      opacity: 1;
      transform: translateX(-50%) translateY(0) scale(1);
    }
  }

  .tool-button:hover,
  .tool-group:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  .dropdown-item:hover {
    background-color: var(--nord2);
  }
</style>
