<script lang="ts">
  import { Home, Clock, Wrench, ListTodo, Settings, Merge, FileArchive, Edit, Scissors, Image, RotateCw, Download } from 'lucide-svelte';

  interface Props {
    isOpen: boolean;
    currentPage: string;
    onNavigate: (page: string) => void;
  }

  let { isOpen, currentPage, onNavigate }: Props = $props();

  const navigationItems = [
    { icon: Home, label: 'Home', page: 'home' },
    { icon: Clock, label: 'Recent files', page: 'recent' },
    { icon: Wrench, label: 'Tools', page: 'tools' },
    { icon: ListTodo, label: 'Tasks', page: 'tasks' },
    { icon: Settings, label: 'Settings', page: 'settings' },
  ];

  const favoriteItems = [
    { icon: Merge, label: 'Merge PDF', page: 'merge' },
    { icon: Scissors, label: 'Split PDF', page: 'split' },
    { icon: RotateCw, label: 'Rotate PDF', page: 'rotate' },
    { icon: Image, label: 'Images to PDF', page: 'convert' },
    { icon: Download, label: 'PDF to Images', page: 'export' },
    { icon: FileArchive, label: 'Compress PDF', page: 'compress' },
    { icon: Edit, label: 'Edit', page: 'edit' },
  ];
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
      <h3 class="mb-3 opacity-60 tracking-wider text-xs uppercase">Favorites</h3>
      <nav class="space-y-0.5">
        {#each favoriteItems as item}
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
  </aside>
{/if}
