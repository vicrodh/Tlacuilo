<script lang="ts">
  import { X } from 'lucide-svelte';
  import { fade } from 'svelte/transition';

  interface Props {
    type?: 'info' | 'warning' | 'success' | 'error';
    dismissible?: boolean;
    onDismiss?: () => void;
    children?: import('svelte').Snippet;
  }

  let {
    type = 'info',
    dismissible = false,
    onDismiss,
    children,
  }: Props = $props();

  const colors = {
    info: {
      bg: 'rgba(136, 192, 208, 0.15)',
      border: 'var(--nord8)',
      text: 'var(--nord8)',
    },
    warning: {
      bg: 'rgba(235, 203, 139, 0.15)',
      border: 'var(--nord13)',
      text: 'var(--nord13)',
    },
    success: {
      bg: 'rgba(163, 190, 140, 0.15)',
      border: 'var(--nord14)',
      text: 'var(--nord14)',
    },
    error: {
      bg: 'rgba(191, 97, 106, 0.15)',
      border: 'var(--nord11)',
      text: 'var(--nord11)',
    },
  };

  const style = $derived(colors[type]);
</script>

<div
  class="notification"
  style="background-color: {style.bg}; border-left-color: {style.border};"
  transition:fade={{ duration: 150 }}
>
  <div class="notification-content" style="color: {style.text};">
    {@render children?.()}
  </div>

  {#if dismissible && onDismiss}
    <button
      class="dismiss-btn"
      onclick={onDismiss}
      title="Dismiss"
      style="color: {style.text};"
    >
      <X size={14} />
    </button>
  {/if}
</div>

<style>
  .notification {
    position: relative;
    padding: 0.75rem;
    padding-right: 2rem;
    border-radius: 0.5rem;
    border-left: 3px solid;
    margin: 0.5rem;
  }

  .notification-content {
    font-size: 0.875rem;
  }

  .notification-content :global(p) {
    margin: 0;
  }

  .notification-content :global(p + p) {
    margin-top: 0.25rem;
  }

  .notification-content :global(button) {
    margin-top: 0.5rem;
    padding: 0.375rem 0.75rem;
    border-radius: 0.375rem;
    font-size: 0.75rem;
    font-weight: 500;
    background-color: var(--nord8);
    color: var(--nord0);
    border: none;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .notification-content :global(button:hover) {
    opacity: 0.9;
  }

  .dismiss-btn {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    padding: 0.25rem;
    background: transparent;
    border: none;
    border-radius: 0.25rem;
    cursor: pointer;
    opacity: 0.6;
    transition: opacity 0.15s;
  }

  .dismiss-btn:hover {
    opacity: 1;
  }
</style>
