<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';

  interface NormalizedRect {
    x: number;
    y: number;
    width: number;
    height: number;
  }

  interface TextCharInfo {
    char: string;
    quad: number[]; // [x0,y0, x1,y1, x2,y2, x3,y3] normalized
  }

  interface TextLineInfo {
    text: string;
    rect: NormalizedRect;
    chars: TextCharInfo[];
  }

  interface TextBlockInfo {
    rect: NormalizedRect;
    lines: TextLineInfo[];
  }

  interface PageTextContent {
    page: number;
    blocks: TextBlockInfo[];
  }

  interface MatchRect {
    x: number;
    y: number;
    width: number;
    height: number;
    isCurrent: boolean;
  }

  interface Props {
    pdfPath: string;
    page: number;
    pageWidth: number;
    pageHeight: number;
    searchQuery: string;
    currentMatchPage: number;
    currentMatchIndex: number; // Index of current match on currentMatchPage
  }

  let { pdfPath, page, pageWidth, pageHeight, searchQuery, currentMatchPage, currentMatchIndex }: Props = $props();

  let textContent = $state<PageTextContent | null>(null);
  let loading = $state(false);

  // Track last loaded path/page to avoid redundant loads
  let lastLoadKey = '';

  // Load text content when page changes
  $effect(() => {
    const loadKey = `${pdfPath}-${page}`;
    if (loadKey !== lastLoadKey && searchQuery) {
      lastLoadKey = loadKey;
      loadTextContent();
    }
  });

  // Reload when search query changes
  $effect(() => {
    if (searchQuery && pdfPath && page) {
      loadTextContent();
    }
  });

  async function loadTextContent() {
    if (!pdfPath || !searchQuery) return;

    loading = true;
    try {
      const content = await invoke<PageTextContent>('pdf_get_text_blocks', {
        path: pdfPath,
        page: page,
      });
      textContent = content;
    } catch (e) {
      console.error(`[SearchHighlightLayer] Failed to load text for page ${page}:`, e);
      textContent = null;
    } finally {
      loading = false;
    }
  }

  // Find all matches and their quad positions
  const matchRects = $derived.by(() => {
    if (!textContent || !searchQuery || searchQuery.length < 2) return [];

    const query = searchQuery.toLowerCase();
    const rects: MatchRect[] = [];
    let matchIndexOnPage = 0;

    for (const block of textContent.blocks) {
      for (const line of block.lines) {
        const lineText = line.text.toLowerCase();
        let searchStart = 0;

        while (true) {
          const matchIndex = lineText.indexOf(query, searchStart);
          if (matchIndex === -1) break;

          // Find the character quads for this match
          const matchEnd = matchIndex + query.length;
          const matchQuads: number[][] = [];

          for (let i = matchIndex; i < matchEnd && i < line.chars.length; i++) {
            matchQuads.push(line.chars[i].quad);
          }

          if (matchQuads.length > 0) {
            // Merge quads into a single rect
            const merged = mergeQuadsToRect(matchQuads);
            const isCurrent = page === currentMatchPage && matchIndexOnPage === currentMatchIndex;
            rects.push({ ...merged, isCurrent });
            matchIndexOnPage++;
          }

          searchStart = matchIndex + 1;
        }
      }
    }

    return rects;
  });

  // Merge multiple character quads into a single rectangle
  function mergeQuadsToRect(quads: number[][]): { x: number; y: number; width: number; height: number } {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

    for (const quad of quads) {
      // quad: [x0,y0, x1,y1, x2,y2, x3,y3]
      const xs = [quad[0], quad[2], quad[4], quad[6]];
      const ys = [quad[1], quad[3], quad[5], quad[7]];

      minX = Math.min(minX, ...xs);
      maxX = Math.max(maxX, ...xs);
      minY = Math.min(minY, ...ys);
      maxY = Math.max(maxY, ...ys);
    }

    return {
      x: minX * pageWidth,
      y: minY * pageHeight,
      width: (maxX - minX) * pageWidth,
      height: (maxY - minY) * pageHeight,
    };
  }
</script>

{#if matchRects.length > 0}
  <svg
    class="absolute inset-0 pointer-events-none"
    style="width: {pageWidth}px; height: {pageHeight}px; z-index: 15;"
  >
    {#each matchRects as rect}
      <rect
        x={rect.x}
        y={rect.y}
        width={rect.width}
        height={rect.height}
        fill={rect.isCurrent ? 'rgba(255, 152, 0, 0.5)' : 'rgba(255, 235, 59, 0.4)'}
        rx="2"
      />
    {/each}
  </svg>
{/if}
