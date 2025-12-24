<script lang="ts">
  import { ScanText } from 'lucide-svelte';

  interface Props {
    visible: boolean;
    message?: string;
  }

  let { visible, message = 'Processing OCR...' }: Props = $props();
</script>

{#if visible}
  <div class="ocr-splash-overlay">
    <div class="ocr-splash-card">
      <div class="spinner-container">
        <div class="spinner"></div>
        <ScanText size={32} class="icon" />
      </div>
      <h3 class="title">{message}</h3>
      <p class="subtitle">This may take a few minutes depending on the document size</p>
      <div class="progress-bar">
        <div class="progress-fill"></div>
      </div>
      <p class="warning">Please do not close the application</p>
    </div>
  </div>
{/if}

<style>
  .ocr-splash-overlay {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: rgba(46, 52, 64, 0.9);
    backdrop-filter: blur(4px);
    z-index: 99999;
  }

  .ocr-splash-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 2.5rem 3rem;
    border-radius: 1rem;
    background-color: var(--nord1);
    border: 1px solid var(--nord3);
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    min-width: 320px;
  }

  .spinner-container {
    position: relative;
    width: 80px;
    height: 80px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 1.5rem;
  }

  .spinner {
    position: absolute;
    width: 100%;
    height: 100%;
    border: 3px solid var(--nord3);
    border-top-color: var(--nord8);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  .spinner-container :global(.icon) {
    color: var(--nord8);
    z-index: 1;
  }

  .title {
    font-size: 1.25rem;
    font-weight: 500;
    color: var(--nord6);
    margin: 0 0 0.5rem 0;
  }

  .subtitle {
    font-size: 0.875rem;
    color: var(--nord4);
    opacity: 0.8;
    margin: 0 0 1.5rem 0;
    text-align: center;
  }

  .progress-bar {
    width: 100%;
    height: 4px;
    background-color: var(--nord3);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 1rem;
  }

  .progress-fill {
    height: 100%;
    width: 30%;
    background-color: var(--nord8);
    border-radius: 2px;
    animation: progress-slide 1.5s ease-in-out infinite;
  }

  .warning {
    font-size: 0.75rem;
    color: var(--nord13);
    opacity: 0.8;
    margin: 0;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  @keyframes progress-slide {
    0% {
      transform: translateX(-100%);
    }
    50% {
      transform: translateX(200%);
    }
    100% {
      transform: translateX(400%);
    }
  }
</style>
