<script lang="ts">
  import {
    FilePlus,
    Edit,
    Merge,
    ScissorsLineDashed,
    RotateCw,
    RefreshCw,
    MessageSquare,
    Lock,
    FileText,
    Archive,
    FileIcon
  } from 'lucide-svelte';

  interface Props {
    onNavigate?: (page: string) => void;
  }

  let { onNavigate }: Props = $props();

  const quickTools = [
    { icon: FilePlus, label: 'Create PDF', page: 'create' },
    { icon: Edit, label: 'Edit', page: 'edit' },
    { icon: Merge, label: 'Merge PDF', page: 'merge' },
    { icon: ScissorsLineDashed, label: 'Split PDF', page: 'split' },
    { icon: RotateCw, label: 'Rotate', page: 'rotate' },
    { icon: RefreshCw, label: 'Convert', page: 'convert' },
    { icon: MessageSquare, label: 'Annotate', page: 'annotate' },
    { icon: Lock, label: 'Protect', page: 'protect' },
    { icon: FileText, label: 'Forms', page: 'forms' },
    { icon: Archive, label: 'Compress', page: 'compress' },
  ];

  const recentFiles = [
    { name: 'Project_Proposal_2024.pdf', date: '2025-12-10' },
    { name: 'Invoice_December.pdf', date: '2025-12-09' },
    { name: 'Meeting_Notes.pdf', date: '2025-12-08' },
    { name: 'Annual_Report.pdf', date: '2025-12-07' },
    { name: 'Contract_Final.pdf', date: '2025-12-06' },
    { name: 'Budget_Overview.pdf', date: '2025-12-05' },
    { name: 'Presentation_Slides.pdf', date: '2025-12-04' },
    { name: 'Technical_Documentation.pdf', date: '2025-12-03' },
  ];
</script>

<div class="flex-1 overflow-auto p-8">
  <!-- Quick Tools Section -->
  <div class="mb-8">
    <h2 class="mb-6 text-2xl" style="color: var(--nord6);">Quick Tools</h2>
    <div class="grid grid-cols-5 gap-4">
      {#each quickTools as tool}
        <button
          onclick={() => onNavigate?.(tool.page)}
          class="flex flex-col items-center justify-center gap-3 p-6 rounded-lg transition-all hover:scale-105"
          style="background-color: var(--nord1); border: 1px solid var(--nord3);"
        >
          <tool.icon size={32} style="color: var(--nord8);" />
          <span class="text-sm text-center">{tool.label}</span>
        </button>
      {/each}
    </div>
  </div>

  <!-- Recent Files Section -->
  <div
    class="rounded-lg p-6"
    style="background-color: var(--nord1);"
  >
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl" style="color: var(--nord6);">Recent Files</h2>
    </div>

    <div class="space-y-2">
      {#each recentFiles as file}
        <div
          class="flex items-center justify-between p-3 rounded-md transition-colors hover:bg-[var(--nord2)] cursor-pointer"
        >
          <div class="flex items-center gap-3">
            <FileIcon size={20} style="color: var(--nord8);" />
            <span>{file.name}</span>
          </div>
          <span class="text-sm opacity-60">{file.date}</span>
        </div>
      {/each}
    </div>

    <div class="flex justify-end mt-6">
      <button
        class="text-sm transition-colors hover:opacity-80"
        style="color: var(--nord11);"
      >
        Clear recent
      </button>
    </div>
  </div>
</div>
