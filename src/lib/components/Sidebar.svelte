<script lang="ts">
  import {
    Home,
    Clock,
    Wrench,
    ListTodo,
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
    Star
  } from 'lucide-svelte';
  import { getSettings, getToolById, type Tool } from '$lib/stores/settings.svelte';

  interface Props {
    isOpen: boolean;
    currentPage: string;
    onNavigate: (page: string) => void;
  }

  let { isOpen, currentPage, onNavigate }: Props = $props();

  const settings = getSettings();

  // Icon mapping for dynamic rendering
  const iconMap: Record<string, typeof Merge> = {
    Merge, Scissors, RotateCw, FileArchive, Image, Images, FileText, FileOutput,
    Lock, Unlock, EyeOff, Droplet, Hash, Stamp, PenTool, Upload, ShieldCheck,
    ScanText, Download, Edit
  };

  const navigationItems = [
    { icon: Home, label: 'Home', page: 'home' },
    { icon: Clock, label: 'Recent Files', page: 'recent' },
    { icon: Wrench, label: 'All Tools', page: 'tools' },
    { icon: Settings, label: 'Settings', page: 'settings' },
  ];

  // Map tool ID to icon and page
  function getToolIcon(toolId: string): typeof Merge {
    const mapping: Record<string, typeof Merge> = {
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

{#if isOpen}
  <aside
    class="w-[14%] min-w-[180px] flex flex-col"
    style="background-color: var(--nord1);"
  >
    <!-- Navigation Section -->
    <div class="flex-1 p-4">
      <h3 class="mb-3 opacity-60 tracking-wider text-xs uppercase">Navigation</h3>
      <nav class="space-y-0.5">
        {#each navigationItems as item}
          <button
            onclick={() => onNavigate(item.page)}
            class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md transition-colors hover:bg-[var(--nord2)] text-left text-sm"
            style={currentPage === item.page ? 'background-color: var(--nord2);' : ''}
          >
            <item.icon size={16} />
            <span>{item.label}</span>
          </button>
        {/each}
      </nav>
    </div>

    <!-- Separator -->
    <div
      class="h-px mx-6"
      style="background-color: var(--nord3);"
    ></div>

    <!-- Favorites Section -->
    <div class="flex-1 p-4">
      <div class="flex items-center justify-between mb-3">
        <h3 class="opacity-60 tracking-wider text-xs uppercase">Favorites</h3>
        <Star size={12} class="opacity-40" />
      </div>
      <nav class="space-y-0.5">
        {#each settings.favorites as toolId}
          {@const Icon = getToolIcon(toolId)}
          {@const page = getToolPage(toolId)}
          {@const label = getToolLabel(toolId)}
          <button
            onclick={() => onNavigate(page)}
            class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md transition-colors hover:bg-[var(--nord2)] text-left text-sm"
            style={currentPage === page ? 'background-color: var(--nord2);' : ''}
          >
            <Icon size={16} />
            <span>{label}</span>
          </button>
        {/each}
        {#if settings.favorites.length === 0}
          <p class="text-xs opacity-40 px-2.5 py-2">
            No favorites yet. Add from Settings.
          </p>
        {/if}
      </nav>
    </div>
  </aside>
{/if}
