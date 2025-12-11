<script lang="ts">
  /**
   * Reusable page selector component for Split, Rotate, Edit operations.
   * Supports three selection modes:
   * - 'all': All pages selected
   * - 'pages': Individual page selection
   * - 'groups': Group pages into separate outputs
   */
  import { Search, Plus, X, Check } from 'lucide-svelte';
  import type { PageData } from '$lib/utils/pdfjs';

  interface Props {
    pages: PageData[];
    mode: 'all' | 'pages' | 'groups';
    selectedPages?: Set<number>; // For 'pages' mode - page numbers (1-indexed)
    groups?: number[][]; // For 'groups' mode - array of page number arrays
    onSelectionChange?: (selected: Set<number>) => void;
    onGroupsChange?: (groups: number[][]) => void;
    onPreviewPage?: (page: PageData) => void;
    rotationValues?: Map<number, number>;
    rotationOptions?: number[];
    showRotationControls?: boolean;
    onRotationChange?: (pageNumber: number, degrees: number) => void;
    previewRotationForPage?: (pageNumber: number) => number | null;
  }

  let {
    pages,
    mode,
    selectedPages = $bindable(new Set<number>()),
    groups = $bindable<number[][]>([]),
    onSelectionChange,
    onGroupsChange,
    onPreviewPage,
    rotationValues = new Map<number, number>(),
    rotationOptions = [],
    showRotationControls = false,
    onRotationChange,
    previewRotationForPage,
  }: Props = $props();

  let activeGroupIndex = $state<number | null>(null);

  // Toggle page selection in 'pages' mode
  function togglePage(pageNumber: number) {
    if (mode !== 'pages') return;

    const newSelected = new Set(selectedPages);
    if (newSelected.has(pageNumber)) {
      newSelected.delete(pageNumber);
    } else {
      newSelected.add(pageNumber);
    }
    selectedPages = newSelected;
    onSelectionChange?.(newSelected);
  }

  // Select all pages
  function selectAll() {
    const allPages = new Set(pages.map(p => p.pageNumber));
    selectedPages = allPages;
    onSelectionChange?.(allPages);
  }

  // Deselect all pages
  function deselectAll() {
    selectedPages = new Set();
    onSelectionChange?.(new Set());
  }

  // Add a new group
  function addGroup() {
    groups = [...groups, []];
    activeGroupIndex = groups.length - 1;
    onGroupsChange?.(groups);
  }

  // Remove a group
  function removeGroup(index: number) {
    groups = groups.filter((_, i) => i !== index);
    if (activeGroupIndex === index) {
      activeGroupIndex = groups.length > 0 ? 0 : null;
    } else if (activeGroupIndex !== null && activeGroupIndex > index) {
      activeGroupIndex--;
    }
    onGroupsChange?.(groups);
  }

  // Toggle page in active group
  function togglePageInGroup(pageNumber: number) {
    if (mode !== 'groups' || activeGroupIndex === null) return;

    const group = [...groups[activeGroupIndex]];
    const idx = group.indexOf(pageNumber);

    if (idx >= 0) {
      group.splice(idx, 1);
    } else {
      // Remove from other groups first
      groups = groups.map((g, i) =>
        i === activeGroupIndex ? g : g.filter(p => p !== pageNumber)
      );
      group.push(pageNumber);
      group.sort((a, b) => a - b);
    }

    groups = groups.map((g, i) => i === activeGroupIndex ? group : g);
    onGroupsChange?.(groups);
  }

  // Check if page is in any group
  function getPageGroup(pageNumber: number): number | null {
    for (let i = 0; i < groups.length; i++) {
      if (groups[i].includes(pageNumber)) return i;
    }
    return null;
  }

  // Get group color
  function getGroupColor(index: number): string {
    const colors = [
      'var(--nord8)',  // cyan
      'var(--nord14)', // green
      'var(--nord13)', // yellow
      'var(--nord12)', // orange
      'var(--nord15)', // purple
      'var(--nord11)', // red
    ];
    return colors[index % colors.length];
  }

  // Check if page is selected based on mode
  function isPageSelected(pageNumber: number): boolean {
    if (mode === 'all') return true;
    if (mode === 'pages') return selectedPages.has(pageNumber);
    if (mode === 'groups') return getPageGroup(pageNumber) !== null;
    return false;
  }

  function rotationForPage(pageNumber: number): number | null {
    return previewRotationForPage ? previewRotationForPage(pageNumber) : null;
  }
</script>

<div class="flex flex-col h-full">
  <!-- Mode-specific controls -->
  {#if mode === 'pages'}
    <div class="flex items-center gap-2 mb-3 text-xs">
      <button
        onclick={selectAll}
        class="px-2 py-1 rounded hover:bg-[var(--nord2)] transition-colors"
        style="border: 1px solid var(--nord3);"
      >
        Select All
      </button>
      <button
        onclick={deselectAll}
        class="px-2 py-1 rounded hover:bg-[var(--nord2)] transition-colors"
        style="border: 1px solid var(--nord3);"
      >
        Deselect All
      </button>
      <span class="opacity-60 ml-auto">{selectedPages.size} selected</span>
    </div>
  {:else if mode === 'groups'}
    <div class="flex flex-col gap-2 mb-3">
      <div class="flex items-center gap-2 flex-wrap">
        {#each groups as group, idx}
          <div
            class="flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors group/btn cursor-pointer"
            style="background-color: {activeGroupIndex === idx ? getGroupColor(idx) : 'var(--nord2)'};
                   color: {activeGroupIndex === idx ? 'var(--nord0)' : 'var(--nord4)'};"
            role="button"
            tabindex="0"
            onclick={() => activeGroupIndex = idx}
            onkeydown={(e) => e.key === 'Enter' && (activeGroupIndex = idx)}
          >
            <span>Group {idx + 1}</span>
            <span class="opacity-70">({group.length})</span>
            <button
              onclick={(e) => { e.stopPropagation(); removeGroup(idx); }}
              class="ml-1 opacity-0 group-hover/btn:opacity-100 transition-opacity"
            >
              <X size={12} />
            </button>
          </div>
        {/each}
        <button
          onclick={addGroup}
          class="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-[var(--nord2)] transition-colors"
          style="border: 1px dashed var(--nord3);"
        >
          <Plus size={12} />
          <span>New Group</span>
        </button>
      </div>
      {#if activeGroupIndex !== null}
        <p class="text-xs opacity-60">
          Click pages to add/remove from Group {activeGroupIndex + 1}
        </p>
      {:else if groups.length > 0}
        <p class="text-xs opacity-60">
          Select a group to edit
        </p>
      {/if}
    </div>
  {:else if mode === 'all'}
    <div class="flex items-center gap-2 mb-3 text-xs">
      <span class="opacity-60">All {pages.length} pages will be split into separate files</span>
    </div>
  {/if}

  <!-- Pages Grid -->
  <div class="flex-1 overflow-auto">
    <div class="grid grid-cols-4 gap-3">
      {#each pages as page (page.id)}
        {@const isSelected = isPageSelected(page.pageNumber)}
        {@const groupIdx = mode === 'groups' ? getPageGroup(page.pageNumber) : null}
        <div class="relative group">
          <button
            onclick={() => {
              if (mode === 'pages') togglePage(page.pageNumber);
              else if (mode === 'groups') togglePageInGroup(page.pageNumber);
            }}
            disabled={mode === 'all'}
            class="w-full rounded overflow-hidden transition-all"
            style="outline: {isSelected ? '3px solid ' + (groupIdx !== null ? getGroupColor(groupIdx) : 'var(--nord8)') : '2px solid var(--nord3)'};"
          >
            <!-- Thumbnail -->
            <div
              class="aspect-[3/4] flex items-center justify-center overflow-hidden"
              style="background-color: var(--nord2);"
            >
              {#if page.thumbnail}
                <img
                  src={page.thumbnail}
                  alt="Page {page.pageNumber}"
                  class="max-w-full max-h-full object-contain"
                  class:opacity-50={!isSelected && mode !== 'all'}
                  style={`transform: rotate(${rotationForPage(page.pageNumber) ?? 0}deg); transition: transform 120ms ease;`}
                />
              {:else}
                <span class="text-xs opacity-60">P{page.pageNumber}</span>
              {/if}
            </div>

            {#if showRotationControls && mode !== 'all' && rotationOptions.length > 0}
              <div
                class="w-full px-2 py-1 flex items-center justify-between text-[11px]"
                style="background-color: var(--nord0); border-top: 1px solid var(--nord3);"
              >
                <span class="opacity-60">Rotate</span>
                <select
                  class="bg-[var(--nord2)] border border-[var(--nord3)] rounded px-1 py-0.5 text-[11px]"
                  value={rotationValues.get(page.pageNumber) ?? ''}
                  onchange={(e) => {
                    const deg = Number((e.target as HTMLSelectElement).value || 0);
                    onRotationChange?.(page.pageNumber, deg);
                  }}
                >
                  <option value="">Default</option>
                  {#each rotationOptions as deg}
                    <option value={deg}>{deg}°</option>
                  {/each}
                </select>
              </div>
            {/if}

            <!-- Selection indicator -->
            {#if isSelected && mode !== 'all'}
              <div
                class="absolute top-1 left-1 w-5 h-5 rounded-full flex items-center justify-center"
                style="background-color: {groupIdx !== null ? getGroupColor(groupIdx) : 'var(--nord8)'};"
              >
                {#if mode === 'groups' && groupIdx !== null}
                  <span class="text-xs font-bold" style="color: var(--nord0);">{groupIdx + 1}</span>
                {:else}
                  <Check size={12} style="color: var(--nord0);" />
                {/if}
              </div>
            {/if}
          </button>

          <!-- Page number & preview button -->
          <div class="flex items-center justify-between mt-1 px-1">
            <span class="text-xs opacity-60">Page {page.pageNumber}</span>
            <button
              onclick={() => onPreviewPage?.(page)}
              class="p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity hover:bg-[var(--nord2)]"
              title="Preview page"
            >
              <Search size={14} />
            </button>
          </div>
        </div>
      {/each}
    </div>
  </div>
</div>
