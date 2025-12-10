<script lang="ts">
  export let onNavigate: ((page: string) => void) | undefined;
</script>

<div class="flex min-h-screen bg-[var(--nord0)] text-[var(--nord6)]">
  <aside class="w-[14%] min-w-[180px] max-w-[240px] border-r border-[var(--nord2)] bg-[var(--nord1)] flex flex-col">
    <div class="px-4 py-4 border-b border-[var(--nord2)]">
      <div class="flex items-center gap-2">
        <div class="grid h-10 w-10 place-items-center rounded-lg bg-[var(--nord10)] text-lg font-bold text-[var(--nord6)]">IH</div>
        <div>
          <p class="text-lg font-semibold">I H PDF</p>
          <p class="text-xs text-[var(--nord4)]">H as in hate</p>
        </div>
      </div>
    </div>
    <div class="flex-1 overflow-y-auto">
      <div class="px-4 py-3 text-xs uppercase tracking-[0.1em] text-[var(--nord4)]">Navigation</div>
      <nav class="px-2 space-y-1 text-sm">
        <button class="w-full text-left rounded px-3 py-2 hover:bg-[var(--nord2)]" on:click={() => onNavigate?.('dashboard')}>Home</button>
        <button class="w-full text-left rounded px-3 py-2 hover:bg-[var(--nord2)]">Recent files</button>
        <button class="w-full text-left rounded px-3 py-2 hover:bg-[var(--nord2)]">Tools</button>
        <button class="w-full text-left rounded px-3 py-2 hover:bg-[var(--nord2)]">Tasks</button>
        <button class="w-full text-left rounded px-3 py-2 hover:bg-[var(--nord2)]">Settings</button>
      </nav>
      <div class="px-4 py-3 text-xs uppercase tracking-[0.1em] text-[var(--nord4)]">Favorites</div>
      <nav class="px-2 space-y-1 text-sm">
        <button class="w-full text-left rounded px-3 py-2 hover:bg-[var(--nord2)]" on:click={() => onNavigate?.('merge')}>Merge PDF</button>
        <button class="w-full text-left rounded px-3 py-2 hover:bg-[var(--nord2)]">Compress PDF</button>
        <button class="w-full text-left rounded px-3 py-2 hover:bg-[var(--nord2)]">Edit</button>
      </nav>
    </div>
  </aside>

  <div class="flex-1 flex flex-col min-h-screen">
    <header class="h-12 border-b border-[var(--nord2)] bg-[var(--nord1)] flex items-center px-4 text-sm">
      <div class="text-center flex-1 font-semibold">I H PDF</div>
      <div class="flex gap-3 text-[var(--nord4)] text-xs">
        <span>Offline first</span>
        <span>Svelte + Tauri</span>
        <span>Python backend</span>
      </div>
    </header>

    <main class="flex-1 overflow-auto bg-[var(--nord0)]">
      <slot />
    </main>

    <footer class="h-10 border-t border-[var(--nord2)] bg-[var(--nord1)] px-4 flex items-center justify-between text-sm text-[var(--nord4)]">
      <div>Status: Ready</div>
      <div>IH PDF · Offline toolkit</div>
    </footer>
  </div>
</div>
