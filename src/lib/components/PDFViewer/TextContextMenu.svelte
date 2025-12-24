<script lang="ts">
  import { Copy, Highlighter, Underline, Strikethrough, Search } from 'lucide-svelte';

  interface Props {
    visible: boolean;
    x: number;
    y: number;
    selectedText: string;
    onCopy: () => void;
    onHighlight: () => void;
    onUnderline: () => void;
    onStrikethrough: () => void;
    onSearch: () => void;
    onClose: () => void;
  }

  let {
    visible,
    x,
    y,
    selectedText,
    onCopy,
    onHighlight,
    onUnderline,
    onStrikethrough,
    onSearch,
    onClose,
  }: Props = $props();

  // Truncate text for display
  const displayText = $derived(
    selectedText.length > 20 ? selectedText.slice(0, 20) + '...' : selectedText
  );
</script>

{#if visible}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="context-menu"
    style="top: {y}px; left: {x}px;"
    onclick={(e) => e.stopPropagation()}
  >
    <button class="menu-item" onclick={onCopy}>
      <Copy size={14} />
      <span>Copy</span>
    </button>

    <div class="separator"></div>

    <button class="menu-item" onclick={onHighlight}>
      <span class="color-indicator" style="background-color: #FFEB3B;"></span>
      <Highlighter size={14} />
      <span>Highlight</span>
    </button>
    <button class="menu-item" onclick={onUnderline}>
      <span class="color-indicator" style="background-color: #2196F3;"></span>
      <Underline size={14} />
      <span>Underline</span>
    </button>
    <button class="menu-item" onclick={onStrikethrough}>
      <span class="color-indicator" style="background-color: #F44336;"></span>
      <Strikethrough size={14} />
      <span>Strikethrough</span>
    </button>

    <div class="separator"></div>
    <button class="menu-item" onclick={onSearch}>
      <Search size={14} />
      <span>Search "{displayText}"</span>
    </button>
  </div>
{/if}

<style>
  .context-menu {
    position: fixed;
    z-index: 99999;
    min-width: 160px;
    padding: 0.25rem 0;
    border-radius: 0.5rem;
    background-color: var(--nord1);
    border: 1px solid var(--nord3);
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
  }

  .menu-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.5rem 0.75rem;
    border: none;
    background: transparent;
    color: var(--nord4);
    font-size: 0.8125rem;
    text-align: left;
    cursor: pointer;
    transition: background-color 0.1s, color 0.1s;
  }

  .menu-item:hover {
    background-color: var(--nord2);
    color: var(--nord6);
  }

  .separator {
    height: 1px;
    margin: 0.25rem 0;
    background-color: var(--nord3);
  }

  .color-indicator {
    width: 8px;
    height: 8px;
    border-radius: 2px;
    flex-shrink: 0;
  }
</style>
