<script lang="ts">
  /**
   * RedactionOverlay - Renders pending redaction marks on a PDF page
   *
   * This overlay shows redaction rectangles that will permanently remove content
   * when applied. Redactions are destructive operations.
   */

  import { X } from 'lucide-svelte';
  import type { RedactionMark } from '$lib/stores/redactions.svelte';

  interface Props {
    marks: RedactionMark[];
    pageWidth: number;
    pageHeight: number;
    scale: number;
    interactive?: boolean;
    onRemoveMark?: (id: string) => void;
  }

  let { marks, pageWidth, pageHeight, scale, interactive = true, onRemoveMark }: Props = $props();

  // Convert normalized coords to pixel coords
  function toPixels(mark: RedactionMark): { x: number; y: number; width: number; height: number } {
    return {
      x: mark.rect.x * scale,
      y: mark.rect.y * scale,
      width: mark.rect.width * scale,
      height: mark.rect.height * scale,
    };
  }
</script>

<div
  class="absolute inset-0 pointer-events-none"
  style="width: {pageWidth * scale}px; height: {pageHeight * scale}px;"
>
  {#each marks as mark}
    {@const px = toPixels(mark)}
    <div
      class="absolute flex items-center justify-center group"
      class:pointer-events-auto={interactive}
      style="
        left: {px.x}px;
        top: {px.y}px;
        width: {px.width}px;
        height: {px.height}px;
        background-color: rgba(191, 97, 106, 0.3);
        border: 2px solid var(--nord11);
        box-sizing: border-box;
      "
    >
      <!-- Diagonal lines pattern to indicate redaction -->
      <svg
        class="absolute inset-0 w-full h-full opacity-30"
        preserveAspectRatio="none"
      >
        <pattern
          id="redact-pattern-{mark.id}"
          width="10"
          height="10"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(45)"
        >
          <line x1="0" y1="0" x2="0" y2="10" stroke="var(--nord11)" stroke-width="2" />
        </pattern>
        <rect width="100%" height="100%" fill="url(#redact-pattern-{mark.id})" />
      </svg>

      <!-- Remove button -->
      {#if interactive && onRemoveMark}
        <button
          onclick={() => onRemoveMark(mark.id)}
          class="absolute -top-2 -right-2 w-5 h-5 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
          style="background-color: var(--nord11); color: var(--nord6);"
          title="Remove redaction mark"
        >
          <X size={12} />
        </button>
      {/if}

      <!-- Label -->
      <span
        class="text-[10px] font-bold uppercase px-1 rounded opacity-80"
        style="background-color: var(--nord11); color: var(--nord6);"
      >
        REDACT
      </span>
    </div>
  {/each}
</div>
