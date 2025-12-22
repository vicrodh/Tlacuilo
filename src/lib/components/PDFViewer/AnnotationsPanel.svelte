<script lang="ts">
  import {
    MessageSquare,
    Highlighter,
    Underline,
    Strikethrough,
    Trash2,
    ChevronDown,
    ChevronRight,
  } from 'lucide-svelte';
  import type { AnnotationsStore, Annotation } from '$lib/stores/annotations.svelte';

  interface Props {
    store: AnnotationsStore;
    onNavigateToPage: (page: number) => void;
  }

  let { store, onNavigateToPage }: Props = $props();

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

  function handleDelete(e: MouseEvent, id: string) {
    e.stopPropagation();
    store.deleteAnnotation(id);
  }

  function getIcon(type: Annotation['type']) {
    switch (type) {
      case 'highlight': return Highlighter;
      case 'comment': return MessageSquare;
      case 'underline': return Underline;
      case 'strikethrough': return Strikethrough;
    }
  }

  function getLabel(type: Annotation['type']) {
    switch (type) {
      case 'highlight': return 'Highlight';
      case 'comment': return 'Comment';
      case 'underline': return 'Underline';
      case 'strikethrough': return 'Strikethrough';
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
                      <div class="flex items-center gap-2">
                        <span class="text-xs font-medium">{getLabel(annotation.type)}</span>
                        <span class="text-[10px] opacity-40">{formatTime(annotation.createdAt)}</span>
                      </div>

                      {#if annotation.type === 'comment' && annotation.text}
                        <p
                          class="text-xs mt-1 line-clamp-2"
                          style="color: var(--nord4);"
                        >
                          {annotation.text}
                        </p>
                      {/if}
                    </div>

                    <!-- Delete button -->
                    <button
                      onclick={(e) => handleDelete(e, annotation.id)}
                      class="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-[var(--nord11)] hover:text-white transition-all flex-shrink-0"
                      title="Delete"
                    >
                      <Trash2 size={12} />
                    </button>
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
