<script lang="ts">
  import { debugLogStore } from '$lib/stores/debugLog.svelte';

  interface Props {
    visible: boolean;
    title?: string;
  }

  let { visible, title = 'Loading...' }: Props = $props();

  // SVG animation values
  let rotation = $state(0);

  $effect(() => {
    if (!visible) return;

    const interval = setInterval(() => {
      rotation = (rotation + 3) % 360;
    }, 16);

    return () => clearInterval(interval);
  });

  const recentLogs = $derived(debugLogStore.logs.slice(-15));
</script>

{#if visible}
  <div class="overlay">
    <div class="content">
      <!-- Animated SVG Spinner -->
      <svg class="spinner" viewBox="0 0 100 100" width="80" height="80">
        <defs>
          <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color: #88c0d0; stop-opacity: 1" />
            <stop offset="100%" style="stop-color: #5e81ac; stop-opacity: 1" />
          </linearGradient>
        </defs>
        <g transform="translate(50, 50)">
          <!-- Outer ring -->
          <circle
            r="40"
            fill="none"
            stroke="var(--nord3)"
            stroke-width="4"
          />
          <!-- Animated arc -->
          <circle
            r="40"
            fill="none"
            stroke="url(#gradient)"
            stroke-width="4"
            stroke-linecap="round"
            stroke-dasharray="180 252"
            transform="rotate({rotation})"
          />
          <!-- Inner pulse -->
          <circle
            r="20"
            fill="none"
            stroke="var(--nord8)"
            stroke-width="2"
            opacity="0.5"
            transform="rotate({-rotation * 0.5})"
            stroke-dasharray="40 85"
          />
          <!-- Center icon -->
          <g transform="translate(-12, -12)">
            <path
              d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4z"
              fill="var(--nord8)"
              opacity="0.8"
            />
            <path
              d="M14 14h6v6h-6z"
              fill="var(--nord13)"
            />
          </g>
        </g>
      </svg>

      <h2 class="title">{title}</h2>

      <!-- Log output -->
      {#if debugLogStore.enabled}
        <div class="logs-container">
          <div class="logs-header">
            <span>Debug Log</span>
            <span class="log-count">{debugLogStore.logs.length} entries</span>
          </div>
          <div class="logs-scroll">
            {#each recentLogs as log (log.id)}
              <div class="log-entry" class:error={log.level === 'error'} class:warn={log.level === 'warn'}>
                <span class="log-time">
                  {log.timestamp.toLocaleTimeString()}.{log.timestamp.getMilliseconds().toString().padStart(3, '0')}
                </span>
                <span class="log-source">[{log.source}]</span>
                <span class="log-message">{log.message}</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .overlay {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: rgba(46, 52, 64, 0.95);
    z-index: 99999;
  }

  .content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1.5rem;
    max-width: 600px;
    width: 90%;
  }

  .spinner {
    filter: drop-shadow(0 0 10px rgba(136, 192, 208, 0.3));
  }

  .title {
    font-size: 1.25rem;
    color: var(--nord6);
    margin: 0;
    font-weight: 500;
  }

  .logs-container {
    width: 100%;
    background-color: var(--nord0);
    border: 1px solid var(--nord3);
    border-radius: 0.5rem;
    overflow: hidden;
  }

  .logs-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0.75rem;
    background-color: var(--nord1);
    border-bottom: 1px solid var(--nord3);
    font-size: 0.75rem;
    color: var(--nord4);
  }

  .log-count {
    opacity: 0.6;
  }

  .logs-scroll {
    max-height: 200px;
    overflow-y: auto;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.7rem;
  }

  .log-entry {
    display: flex;
    gap: 0.5rem;
    padding: 0.25rem 0.5rem;
    border-bottom: 1px solid var(--nord2);
    color: var(--nord4);
  }

  .log-entry:last-child {
    border-bottom: none;
  }

  .log-entry.error {
    background-color: rgba(191, 97, 106, 0.1);
    color: var(--nord11);
  }

  .log-entry.warn {
    background-color: rgba(235, 203, 139, 0.1);
    color: var(--nord13);
  }

  .log-time {
    opacity: 0.5;
    white-space: nowrap;
  }

  .log-source {
    color: var(--nord8);
    white-space: nowrap;
  }

  .log-message {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
