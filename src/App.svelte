<svelte:head>
  <title>I H PDF</title>
</svelte:head>

<script lang="ts">
  import { Menu, Activity } from 'lucide-svelte';
  import Sidebar from './lib/components/Sidebar.svelte';
  import Dashboard from './lib/views/Dashboard.svelte';
  import MergePDF from './lib/views/MergePDF.svelte';
  import PlaceholderPage from './lib/views/PlaceholderPage.svelte';

  let sidebarOpen = $state(true);
  let currentPage = $state('home');

  function navigate(page: string) {
    currentPage = page;
  }

  function toggleSidebar() {
    sidebarOpen = !sidebarOpen;
  }

  const currentDate = new Date().toLocaleDateString();
</script>

<div class="h-screen flex flex-col" style="background-color: var(--nord0);">
  <!-- Header / Top Menu Bar -->
  <header
    class="h-14 flex items-center justify-between px-4 border-b"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <div class="flex items-center gap-4">
      <button
        onclick={toggleSidebar}
        class="p-2 rounded-md hover:bg-[var(--nord2)] transition-colors"
      >
        <Menu size={20} />
      </button>

      <div class="flex items-center gap-3">
        <div
          class="w-8 h-8 rounded flex items-center justify-center"
          style="background-color: var(--nord8);"
        >
          <span class="text-lg" style="color: var(--nord0);">H</span>
        </div>
        <div>
          <h1 class="leading-none" style="color: var(--nord6);">I H PDF</h1>
          <p class="text-xs opacity-60">H as in hate</p>
        </div>
      </div>
    </div>

    <div class="flex items-center gap-2">
      <span class="text-sm opacity-60">v1.0.0</span>
    </div>
  </header>

  <!-- Main Content Area -->
  <div class="flex-1 flex overflow-hidden">
    <Sidebar isOpen={sidebarOpen} {currentPage} onNavigate={navigate} />

    {#if currentPage === 'home'}
      <Dashboard onNavigate={navigate} />
    {:else if currentPage === 'merge'}
      <MergePDF />
    {:else}
      <PlaceholderPage pageName={currentPage} />
    {/if}
  </div>

  <!-- Status Bar / Footer -->
  <footer
    class="h-8 flex items-center justify-between px-4 text-xs border-t"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <div class="flex items-center gap-4">
      <div class="flex items-center gap-2">
        <Activity size={14} style="color: var(--nord14);" />
        <span>Ready</span>
      </div>
    </div>
    <div class="flex items-center gap-4 opacity-60">
      <span>No file selected</span>
      <span>•</span>
      <span>{currentDate}</span>
    </div>
  </footer>
</div>
