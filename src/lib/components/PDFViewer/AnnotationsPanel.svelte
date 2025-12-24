<script lang="ts">
  import {
    MessageSquare,
    Highlighter,
    Underline,
    Strikethrough,
    Trash2,
    ChevronDown,
    ChevronRight,
    ChevronLeft,
    Type,
    Pencil,
    Square,
    Circle,
    Minus,
    ArrowRight,
    Hash,
    MoreVertical,
    Palette,
    Navigation,
  } from 'lucide-svelte';
  import { ask } from '@tauri-apps/plugin-dialog';
  import type { AnnotationsStore, Annotation } from '$lib/stores/annotations.svelte';
  import { HIGHLIGHT_COLORS } from '$lib/stores/annotations.svelte';

  interface Props {
    store: AnnotationsStore;
    onNavigateToPage: (page: number) => void;
  }

  let { store, onNavigateToPage }: Props = $props();

  // Dropdown menu state
  let openMenuId = $state<string | null>(null);
  let showColorPicker = $state<string | null>(null);

  // Group annotations by page
  const annotationsByPage = $derived(() => {
    const grouped = new Map<number, Annotation[]>();
    const all = store.getAllAnnotations();

    for (const ann of all) {
      const pageAnns = grouped.get(ann.page) || [];
      pageAnns.push(ann);
      grouped.set(ann.page, pageAnns);
    }

    return grouped;
  });

  const totalCount = $derived(store.getAllAnnotations().length);

  // Collapsed pages state
  let collapsedPages = $state<Set<number>>(new Set());

  function togglePage(page: number) {
    if (collapsedPages.has(page)) {
      collapsedPages.delete(page);
    } else {
      collapsedPages.add(page);
    }
    collapsedPages = new Set(collapsedPages);
  }

  function handleAnnotationClick(annotation: Annotation) {
    onNavigateToPage(annotation.page);
    store.selectAnnotation(annotation.id);
  }

  function toggleMenu(e: MouseEvent, id: string) {
    e.stopPropagation();
    openMenuId = openMenuId === id ? null : id;
    showColorPicker = null;
  }

  function handleGoTo(e: MouseEvent, annotation: Annotation) {
    e.stopPropagation();
    onNavigateToPage(annotation.page);
    store.selectAnnotation(annotation.id);
    openMenuId = null;
  }

  function handleChangeColor(e: MouseEvent, id: string) {
    e.stopPropagation();
    showColorPicker = showColorPicker === id ? null : id;
  }

  function applyColor(e: MouseEvent, id: string, color: string) {
    e.stopPropagation();
    store.updateAnnotation(id, { color });
    showColorPicker = null;
    openMenuId = null;
  }

  async function handleDelete(e: MouseEvent, id: string) {
    e.stopPropagation();
    openMenuId = null;

    const confirmed = await ask('Delete this annotation?', {
      title: 'Delete Annotation',
      kind: 'warning',
    });
    if (confirmed) {
      store.deleteAnnotation(id);
    }
  }

  // Close menu when clicking outside
  function handleClickOutside() {
    openMenuId = null;
    showColorPicker = null;
  }

  function getIcon(type: Annotation['type']) {
    switch (type) {
      case 'highlight': return Highlighter;
      case 'comment': return MessageSquare;
      case 'underline': return Underline;
      case 'strikethrough': return Strikethrough;
      case 'freetext': return Type;
      case 'ink': return Pencil;
      case 'rectangle': return Square;
      case 'ellipse': return Circle;
      case 'line': return Minus;
      case 'arrow': return ArrowRight;
      case 'sequenceNumber': return Hash;
      default: return MessageSquare;
    }
  }

  function getLabel(type: Annotation['type']) {
    switch (type) {
      case 'highlight': return 'Highlight';
      case 'comment': return 'Comment';
      case 'underline': return 'Underline';
      case 'strikethrough': return 'Strikethrough';
      case 'freetext': return 'Typewriter';
      case 'ink': return 'Freehand';
      case 'rectangle': return 'Rectangle';
      case 'ellipse': return 'Ellipse';
      case 'line': return 'Line';
      case 'arrow': return 'Arrow';
      case 'sequenceNumber': return 'Sequence #';
      default: return 'Annotation';
    }
  }

  function formatTime(date: Date) {
    return new Date(date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
</script>

<div class="h-full flex flex-col" style="background-color: var(--nord1);">
  <!-- Header -->
  <div
    class="flex items-center justify-between px-3 py-2 border-b"
    style="border-color: var(--nord3);"
  >
    <span class="text-sm font-medium">Annotations</span>
    <span
      class="text-xs px-2 py-0.5 rounded-full"
      style="background-color: var(--nord2); color: var(--nord4);"
    >
      {totalCount}
    </span>
  </div>

  <!-- Content -->
  <div class="flex-1 overflow-y-auto">
    {#if totalCount === 0}
      <div class="flex flex-col items-center justify-center h-full px-4 text-center">
        <MessageSquare size={32} class="opacity-30 mb-2" />
        <p class="text-sm opacity-60">No annotations yet</p>
        <p class="text-xs opacity-40 mt-1">
          Use the annotation tools to add highlights and comments
        </p>
      </div>
    {:else}
      <div class="py-2">
        {#each [...annotationsByPage().entries()].sort((a, b) => a[0] - b[0]) as [page, annotations]}
          <!-- Page group -->
          <div class="mb-1">
            <button
              onclick={() => togglePage(page)}
              class="w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-[var(--nord2)] transition-colors"
            >
              {#if collapsedPages.has(page)}
                <ChevronRight size={12} class="opacity-60" />
              {:else}
                <ChevronDown size={12} class="opacity-60" />
              {/if}
              <span class="font-medium">Page {page}</span>
              <span class="opacity-40">({annotations.length})</span>
            </button>

            {#if !collapsedPages.has(page)}
              <div class="ml-2">
                {#each annotations as annotation (annotation.id)}
                  {@const Icon = getIcon(annotation.type)}
                  <!-- svelte-ignore a11y_click_events_have_key_events -->
                  <!-- svelte-ignore a11y_no_static_element_interactions -->
                  <div
                    onclick={() => handleAnnotationClick(annotation)}
                    class="w-full flex items-start gap-2 px-3 py-2 text-left hover:bg-[var(--nord2)] transition-colors group cursor-pointer"
                    class:bg-[var(--nord2)]={store.selectedId === annotation.id}
                  >
                    <!-- Icon with color -->
                    <div
                      class="w-5 h-5 rounded flex items-center justify-center flex-shrink-0 mt-0.5"
                      style="background-color: {annotation.color}20;"
                    >
                      <Icon size={12} style="color: {annotation.color};" />
                    </div>

                    <!-- Content -->
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2 flex-wrap">
                        <span class="text-xs font-medium">{getLabel(annotation.type)}</span>
                        <span class="text-[10px] opacity-40">{formatTime(annotation.createdAt)}</span>
                        {#if annotation.author}
                          <span class="text-[10px] opacity-50 italic">by {annotation.author}</span>
                        {/if}
                      </div>

                      {#if (annotation.type === 'comment' || annotation.type === 'freetext') && annotation.text}
                        <p
                          class="text-xs mt-1 line-clamp-2"
                          style="color: var(--nord4);"
                        >
                          {annotation.text}
                        </p>
                      {:else if annotation.type === 'sequenceNumber' && annotation.sequenceNumber}
                        <p
                          class="text-xs mt-1"
                          style="color: var(--nord4);"
                        >
                          #{annotation.sequenceNumber}
                        </p>
                      {/if}
                    </div>

                    <!-- Actions menu -->
                    <div class="relative flex-shrink-0">
                      <button
                        onclick={(e) => toggleMenu(e, annotation.id)}
                        class="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-[var(--nord3)] transition-all"
                        title="Actions"
                      >
                        <MoreVertical size={12} />
                      </button>

                      {#if openMenuId === annotation.id}
                        <div
                          class="absolute right-0 top-full mt-1 rounded-lg shadow-lg py-1 z-50"
                          style="background-color: var(--nord1); border: 1px solid var(--nord3); min-width: 140px;"
                        >
                          <!-- Go to -->
                          <button
                            onclick={(e) => handleGoTo(e, annotation)}
                            class="w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-[var(--nord2)] transition-colors text-left"
                          >
                            <Navigation size={12} />
                            <span>Go to</span>
                          </button>

                          <!-- Change color -->
                          <div class="relative">
                            <button
                              onclick={(e) => handleChangeColor(e, annotation.id)}
                              class="w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-[var(--nord2)] transition-colors text-left"
                            >
                              <ChevronLeft size={10} class="opacity-50" />
                              <Palette size={12} />
                              <span>Change color</span>
                            </button>

                            {#if showColorPicker === annotation.id}
                              <div
                                class="absolute right-full top-0 mr-1 rounded-lg shadow-lg p-2 z-50"
                                style="background-color: var(--nord1); border: 1px solid var(--nord3);"
                              >
                                <div class="grid grid-cols-4 gap-1">
                                  {#each HIGHLIGHT_COLORS as color}
                                    <button
                                      onclick={(e) => applyColor(e, annotation.id, color.value)}
                                      class="w-5 h-5 rounded border transition-transform hover:scale-110"
                                      style="background-color: {color.value}; border-color: {annotation.color === color.value ? 'var(--nord6)' : 'var(--nord3)'};"
                                      title={color.name}
                                    ></button>
                                  {/each}
                                </div>
                              </div>
                            {/if}
                          </div>

                          <!-- Separator -->
                          <div class="h-px my-1" style="background-color: var(--nord3);"></div>

                          <!-- Delete -->
                          <button
                            onclick={(e) => handleDelete(e, annotation.id)}
                            class="w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-[var(--nord11)] hover:text-white transition-colors text-left"
                          >
                            <Trash2 size={12} />
                            <span>Delete</span>
                          </button>
                        </div>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<!-- Close menu when clicking outside -->
<svelte:window onclick={handleClickOutside} />
