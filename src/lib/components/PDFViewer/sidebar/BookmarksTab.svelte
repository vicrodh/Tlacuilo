<script lang="ts">
  import { Bookmark } from 'lucide-svelte';
</script>

<div class="bookmarks-tab">
  <div class="header">
    <span class="title">Bookmarks</span>
  </div>

  <div class="empty-state">
    <div class="icon-container">
      <Bookmark size={32} />
    </div>
    <p class="message">Bookmarks</p>
    <p class="hint">Coming soon</p>
  </div>
</div>

<style>
  .bookmarks-tab {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--nord3);
  }

  .title {
    font-size: 0.75rem;
    text-transform: uppercase;
    opacity: 0.6;
  }

  .empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    text-align: center;
  }

  .icon-container {
    color: var(--nord4);
    opacity: 0.3;
    margin-bottom: 0.75rem;
  }

  .message {
    font-size: 0.875rem;
    color: var(--nord4);
    opacity: 0.6;
    margin: 0;
  }

  .hint {
    font-size: 0.75rem;
    color: var(--nord4);
    opacity: 0.4;
    margin: 0.25rem 0 0 0;
  }
</style>
