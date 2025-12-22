<script lang="ts">
  import {
    Home,
    Clock,
    Wrench,
    Settings,
    Merge,
    Scissors,
    FileArchive,
    Edit,
    RotateCw,
    Image,
    Images,
    Download,
    FileText,
    FileOutput,
    Lock,
    Unlock,
    EyeOff,
    Droplet,
    Hash,
    Stamp,
    PenTool,
    Upload,
    ShieldCheck,
    ScanText,
    Star,
    BookOpen,
    ChevronsLeft,
    ChevronsRight
  } from 'lucide-svelte';
  import { getSettings, type Tool } from '$lib/stores/settings.svelte';

  interface Props {
    isExpanded: boolean;
    currentPage: string;
    onNavigate: (page: string) => void;
    onToggle: () => void;
  }

  let { isExpanded, currentPage, onNavigate, onToggle }: Props = $props();

  const settings = getSettings();

  // Navigation items (without Settings - it goes at the bottom)
  const navigationItems = [
    { icon: Home, label: 'Home', page: 'home' },
    { icon: Clock, label: 'Recent Files', page: 'recent' },
    { icon: Wrench, label: 'All Tools', page: 'tools' },
  ];

  // Map tool ID to icon and page
  function getToolIcon(toolId: string): typeof Merge {
    const mapping: Record<string, typeof Merge> = {
      'viewer': BookOpen,
      'merge': Merge,
      'split': Scissors,
      'rotate': RotateCw,
      'compress': FileArchive,
      'ocr': ScanText,
      'convert-images-to-pdf': Image,
      'convert-pdf-to-images': Images,
      'convert-docs-to-pdf': FileText,
      'convert-pdf-to-docs': FileOutput,
      'protect-encrypt': Lock,
      'protect-decrypt': Unlock,
      'protect-redact': EyeOff,
      'annotate-watermark': Droplet,
      'annotate-page-numbers': Hash,
      'annotate-stamps': Stamp,
      'sign-draw': PenTool,
      'sign-upload': Upload,
      'sign-certificate': ShieldCheck,
    };
    return mapping[toolId] || FileText;
  }

  function getToolPage(toolId: string): string {
    const mapping: Record<string, string> = {
      'viewer': 'viewer',
      'merge': 'merge',
      'split': 'split',
      'rotate': 'rotate',
      'compress': 'compress',
      'ocr': 'ocr',
      'convert-images-to-pdf': 'convert',
      'convert-pdf-to-images': 'export',
      'convert-docs-to-pdf': 'convert-docs',
      'convert-pdf-to-docs': 'export-docs',
      'protect-encrypt': 'encrypt',
      'protect-decrypt': 'decrypt',
      'protect-redact': 'redact',
      'annotate-watermark': 'watermark',
      'annotate-page-numbers': 'page-numbers',
      'annotate-stamps': 'stamps',
      'sign-draw': 'sign-draw',
      'sign-upload': 'sign-upload',
      'sign-certificate': 'sign-cert',
    };
    return mapping[toolId] || toolId;
  }

  function getToolLabel(toolId: string): string {
    const mapping: Record<string, string> = {
      'viewer': 'Viewer',
      'merge': 'Merge PDF',
      'split': 'Split PDF',
      'rotate': 'Rotate PDF',
      'compress': 'Compress PDF',
      'ocr': 'OCR',
      'convert-images-to-pdf': 'Images → PDF',
      'convert-pdf-to-images': 'PDF → Images',
      'convert-docs-to-pdf': 'Docs → PDF',
      'convert-pdf-to-docs': 'PDF → Docs',
      'protect-encrypt': 'Encrypt',
      'protect-decrypt': 'Decrypt',
      'protect-redact': 'Redact',
      'annotate-watermark': 'Watermark',
      'annotate-page-numbers': 'Page Numbers',
      'annotate-stamps': 'Stamps',
      'sign-draw': 'Draw Signature',
      'sign-upload': 'Upload Signature',
      'sign-certificate': 'Certificate',
    };
    return mapping[toolId] || toolId;
  }
</script>

<aside
  class="relative flex flex-col h-full transition-all duration-200"
  style="background-color: var(--nord1); width: {isExpanded ? '200px' : '64px'};"
>
  <!-- App Branding -->
  <div class="p-3 {isExpanded ? 'px-4' : 'px-2'}">
    <button
      onclick={() => onNavigate('home')}
      class="flex items-center gap-3 w-full rounded-lg p-2 hover:bg-[var(--nord2)] transition-colors"
      title="Tlacuilo"
    >
      <div
        class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
        style="background-color: var(--nord8);"
      >
        <span class="text-xl font-bold" style="color: var(--nord0);">T</span>
      </div>
      {#if isExpanded}
        <div class="text-left overflow-hidden">
          <h1 class="font-semibold leading-tight truncate" style="color: var(--nord6);">Tlacuilo</h1>
          <p class="text-[10px] opacity-50 truncate">PDF Toolkit</p>
        </div>
      {/if}
    </button>
  </div>

  <!-- Separator -->
  <div class="h-px mx-3" style="background-color: var(--nord3);"></div>

  <!-- Navigation Section -->
  <div class="flex-1 p-2 overflow-y-auto">
    <nav class="space-y-1">
      {#each navigationItems as item}
        <button
          onclick={() => onNavigate(item.page)}
          class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors hover:bg-[var(--nord2)] {isExpanded ? 'justify-start' : 'justify-center'}"
          style={currentPage === item.page ? 'background-color: var(--nord2);' : ''}
          title={isExpanded ? '' : item.label}
        >
          <item.icon size={20} style={currentPage === item.page ? 'color: var(--nord8);' : ''} />
          {#if isExpanded}
            <span class="text-sm truncate" style={currentPage === item.page ? 'color: var(--nord8);' : ''}>{item.label}</span>
          {/if}
        </button>
      {/each}
    </nav>

    <!-- Favorites Section -->
    {#if settings.favorites.length > 0}
      <div class="mt-4">
        {#if isExpanded}
          <div class="flex items-center gap-2 px-3 mb-2">
            <Star size={12} class="opacity-40" />
            <span class="text-[10px] opacity-40 uppercase tracking-wider">Favorites</span>
          </div>
        {:else}
          <div class="h-px mx-2 my-2" style="background-color: var(--nord3);"></div>
        {/if}
        <nav class="space-y-1">
          {#each settings.favorites as toolId}
            {@const Icon = getToolIcon(toolId)}
            {@const page = getToolPage(toolId)}
            {@const label = getToolLabel(toolId)}
            <button
              onclick={() => onNavigate(page)}
              class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors hover:bg-[var(--nord2)] {isExpanded ? 'justify-start' : 'justify-center'}"
              style={currentPage === page ? 'background-color: var(--nord2);' : ''}
              title={isExpanded ? '' : label}
            >
              <Icon size={20} style={currentPage === page ? 'color: var(--nord8);' : ''} />
              {#if isExpanded}
                <span class="text-sm truncate" style={currentPage === page ? 'color: var(--nord8);' : ''}>{label}</span>
              {/if}
            </button>
          {/each}
        </nav>
      </div>
    {/if}
  </div>

  <!-- Settings at Bottom -->
  <div class="p-2 border-t" style="border-color: var(--nord3);">
    <button
      onclick={() => onNavigate('settings')}
      class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors hover:bg-[var(--nord2)] {isExpanded ? 'justify-start' : 'justify-center'}"
      style={currentPage === 'settings' ? 'background-color: var(--nord2);' : ''}
      title={isExpanded ? '' : 'Settings'}
    >
      <Settings size={20} style={currentPage === 'settings' ? 'color: var(--nord8);' : ''} />
      {#if isExpanded}
        <span class="text-sm" style={currentPage === 'settings' ? 'color: var(--nord8);' : ''}>Settings</span>
      {/if}
    </button>
  </div>

  <!-- Floating Toggle Button -->
  <button
    onclick={onToggle}
    class="absolute top-1/2 -translate-y-1/2 -right-4 w-8 h-8 rounded-lg flex items-center justify-center transition-all hover:scale-105 z-10 shadow-md"
    style="background-color: var(--nord2); border: 1px solid var(--nord3);"
    title={isExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
  >
    {#if isExpanded}
      <ChevronsLeft size={16} />
    {:else}
      <ChevronsRight size={16} />
    {/if}
  </button>
</aside>
