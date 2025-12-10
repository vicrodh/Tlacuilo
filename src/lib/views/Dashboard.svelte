<script lang="ts">
  import { FilePlus, Edit3, GitMerge, Scissors, RotateCcw, RefreshCw, MessageSquare, Lock, FileText, Archive, File } from 'lucide-svelte';

  export let onNavigate: ((page: string) => void) | undefined;

  const quickTools = [
    { icon: FilePlus, label: 'Create PDF', page: 'create' },
    { icon: Edit3, label: 'Edit', page: 'edit' },
    { icon: GitMerge, label: 'Merge PDF', page: 'merge' },
    { icon: Scissors, label: 'Split PDF', page: 'split' },
    { icon: RotateCcw, label: 'Rotate', page: 'rotate' },
    { icon: RefreshCw, label: 'Convert', page: 'convert' },
    { icon: MessageSquare, label: 'Annotate', page: 'annotate' },
    { icon: Lock, label: 'Protect', page: 'protect' },
    { icon: FileText, label: 'Forms', page: 'forms' },
    { icon: Archive, label: 'Compress', page: 'compress' }
  ];

  const recentFiles = [
    { name: 'Project_Proposal_2024.pdf', date: '2025-12-10' },
    { name: 'Invoice_December.pdf', date: '2025-12-09' },
    { name: 'Meeting_Notes.pdf', date: '2025-12-08' },
    { name: 'Annual_Report.pdf', date: '2025-12-07' },
    { name: 'Contract_Final.pdf', date: '2025-12-06' },
    { name: 'Budget_Overview.pdf', date: '2025-12-05' },
    { name: 'Presentation_Slides.pdf', date: '2025-12-04' },
    { name: 'Technical_Documentation.pdf', date: '2025-12-03' }
  ];
</script>

<div class="flex-1 overflow-auto p-8">
  <div class="mb-8">
    <h2 class="mb-6 text-2xl" style="color: var(--nord6)">Quick Tools</h2>
    <div class="grid grid-cols-5 gap-4">
      {#each quickTools as tool}
        <button
          class="flex flex-col items-center justify-center gap-3 p-6 rounded-lg transition-all hover:scale-105"
          style="background: var(--nord1); border: 1px solid var(--nord3)"
          on:click={() => onNavigate?.(tool.page)}
        >
          <svelte:component this={tool.icon} size={32} style="color: var(--nord8)" />
          <span class="text-sm text-center">{tool.label}</span>
        </button>
      {/each}
    </div>
  </div>

  <div class="rounded-lg p-6" style="background: var(--nord1)">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl" style="color: var(--nord6)">Recent Files</h2>
      <button class="text-sm" style="color: var(--nord11)">Clear recent</button>
    </div>
    <div class="space-y-2">
      {#each recentFiles as file}
        <div class="flex items-center justify-between p-3 rounded-md transition-colors" style="background: var(--nord2)">
          <div class="flex items-center gap-3">
            <File size={20} style="color: var(--nord8)" />
            <span>{file.name}</span>
          </div>
          <span class="text-sm opacity-60">{file.date}</span>
        </div>
      {/each}
    </div>
  </div>
</div>
