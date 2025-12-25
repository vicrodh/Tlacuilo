<script lang="ts">
  import { Layers, Eye, EyeOff, RefreshCw } from 'lucide-svelte';
  import { invoke } from '@tauri-apps/api/core';
  import { onMount } from 'svelte';

  interface Props {
    filePath: string | null;
    onReload?: () => void;
  }

  let { filePath, onReload }: Props = $props();

  interface LayerInfo {
    xref: number;
    name: string;
    on: boolean;
    intent: string[];
    usage: string;
  }

  interface LayersResult {
    has_layers: boolean;
    layers: LayerInfo[];
    error?: string;
  }

  let layers = $state<LayerInfo[]>([]);
  let hasLayers = $state(false);
  let isLoading = $state(false);
  let error = $state<string | null>(null);
  let pendingChanges = $state<Map<number, boolean>>(new Map());

  $effect(() => {
    if (filePath) {
      loadLayers();
    } else {
      layers = [];
      hasLayers = false;
    }
  });

  async function loadLayers() {
    if (!filePath) return;

    isLoading = true;
    error = null;

    try {
      const result = await invoke<LayersResult>('pdf_get_layers', {
        input: filePath
      });

      if (result.error) {
        error = result.error;
      } else {
        hasLayers = result.has_layers;
        layers = result.layers;
      }
    } catch (err) {
      error = String(err);
    } finally {
      isLoading = false;
    }
  }

  async function toggleLayer(layer: LayerInfo) {
    if (!filePath) return;

    const newVisibility = !layer.on;

    // Update local state optimistically
    layers = layers.map(l =>
      l.xref === layer.xref ? { ...l, on: newVisibility } : l
    );

    // Track pending change
    pendingChanges.set(layer.xref, newVisibility);
    pendingChanges = new Map(pendingChanges);

    try {
      const result = await invoke<{ success: boolean; message: string }>('pdf_set_layer', {
        input: filePath,
        output: filePath, // Save in place
        layerXref: layer.xref,
        visible: newVisibility
      });

      if (!result.success) {
        // Revert on failure
        layers = layers.map(l =>
          l.xref === layer.xref ? { ...l, on: !newVisibility } : l
        );
        error = result.message;
      } else {
        // Trigger reload to show updated rendering
        onReload?.();
      }
    } catch (err) {
      // Revert on error
      layers = layers.map(l =>
        l.xref === layer.xref ? { ...l, on: !newVisibility } : l
      );
      error = String(err);
    } finally {
      pendingChanges.delete(layer.xref);
      pendingChanges = new Map(pendingChanges);
    }
  }

  function showAllLayers() {
    layers.forEach(layer => {
      if (!layer.on) toggleLayer(layer);
    });
  }

  function hideAllLayers() {
    layers.forEach(layer => {
      if (layer.on) toggleLayer(layer);
    });
  }
</script>

<div class="flex flex-col h-full">
  <!-- Header -->
  <div
    class="flex items-center justify-between px-3 py-2 border-b"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <div class="flex items-center gap-2">
      <Layers size={14} style="color: var(--nord8);" />
      <span class="text-sm font-medium">Layers</span>
      {#if hasLayers}
        <span class="text-xs opacity-50">({layers.length})</span>
      {/if}
    </div>
    <button
      onclick={loadLayers}
      class="p-1 rounded hover:bg-[var(--nord2)] transition-colors"
      title="Refresh"
      disabled={isLoading}
    >
      <RefreshCw size={12} class={isLoading ? 'animate-spin' : ''} />
    </button>
  </div>

  <!-- Content -->
  <div class="flex-1 overflow-auto">
    {#if isLoading}
      <div class="flex items-center justify-center h-full">
        <div class="flex items-center gap-2 text-xs opacity-50">
          <RefreshCw size={14} class="animate-spin" />
          <span>Loading layers...</span>
        </div>
      </div>
    {:else if error}
      <div class="p-3">
        <div class="text-xs p-2 rounded" style="background-color: rgba(191, 97, 106, 0.1); color: var(--nord11);">
          {error}
        </div>
      </div>
    {:else if !hasLayers}
      <div class="flex flex-col items-center justify-center h-full px-4">
        <Layers size={32} class="opacity-20 mb-2" />
        <p class="text-xs opacity-40 text-center">No layers in this document</p>
      </div>
    {:else}
      <!-- Quick actions -->
      <div class="flex gap-2 px-3 py-2" style="border-bottom: 1px solid var(--nord3);">
        <button
          onclick={showAllLayers}
          class="flex-1 flex items-center justify-center gap-1 px-2 py-1 rounded text-xs transition-colors hover:bg-[var(--nord2)]"
          style="background-color: var(--nord1);"
        >
          <Eye size={12} />
          Show All
        </button>
        <button
          onclick={hideAllLayers}
          class="flex-1 flex items-center justify-center gap-1 px-2 py-1 rounded text-xs transition-colors hover:bg-[var(--nord2)]"
          style="background-color: var(--nord1);"
        >
          <EyeOff size={12} />
          Hide All
        </button>
      </div>

      <!-- Layers list -->
      <div class="p-2 space-y-1">
        {#each layers as layer}
          <button
            onclick={() => toggleLayer(layer)}
            class="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition-colors hover:bg-[var(--nord2)]"
            style="background-color: var(--nord1);"
            disabled={pendingChanges.has(layer.xref)}
          >
            <div class="flex-shrink-0">
              {#if pendingChanges.has(layer.xref)}
                <RefreshCw size={14} class="animate-spin opacity-50" />
              {:else if layer.on}
                <Eye size={14} style="color: var(--nord14);" />
              {:else}
                <EyeOff size={14} style="color: var(--nord4); opacity: 0.4;" />
              {/if}
            </div>
            <span
              class="text-xs truncate flex-1"
              style="color: {layer.on ? 'var(--nord5)' : 'var(--nord4)'}; opacity: {layer.on ? 1 : 0.5};"
            >
              {layer.name}
            </span>
          </button>
        {/each}
      </div>
    {/if}
  </div>
</div>
