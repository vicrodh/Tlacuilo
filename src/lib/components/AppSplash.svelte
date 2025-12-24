<script lang="ts">
  // Splash screen - shown while app initializes
  // No props needed - parent controls visibility via {#if}

  let rotation = $state(0);

  $effect(() => {
    const interval = setInterval(() => {
      rotation = (rotation + 2) % 360;
    }, 16);

    return () => clearInterval(interval);
  });
</script>

<div class="splash">
  <div class="content">
    <!-- App Logo SVG Animation -->
    <svg class="logo" viewBox="0 0 120 120" width="120" height="120">
      <defs>
        <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color: #88c0d0" />
          <stop offset="50%" style="stop-color: #81a1c1" />
          <stop offset="100%" style="stop-color: #5e81ac" />
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
          <feMerge>
            <feMergeNode in="coloredBlur"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
      </defs>

      <g transform="translate(60, 60)">
        <!-- Background circle -->
        <circle r="55" fill="var(--nord1)" stroke="var(--nord3)" stroke-width="2" />

        <!-- Rotating outer ring -->
        <circle
          r="48"
          fill="none"
          stroke="url(#logoGradient)"
          stroke-width="3"
          stroke-linecap="round"
          stroke-dasharray="100 202"
          transform="rotate({rotation})"
          filter="url(#glow)"
        />

        <!-- PDF icon stylized -->
        <g transform="translate(-25, -30)">
          <!-- Document shape -->
          <path
            d="M10 0 L40 0 L50 10 L50 60 L0 60 L0 10 Z"
            fill="var(--nord2)"
            stroke="var(--nord4)"
            stroke-width="1.5"
          />
          <!-- Fold corner -->
          <path
            d="M40 0 L40 10 L50 10"
            fill="none"
            stroke="var(--nord4)"
            stroke-width="1.5"
          />
          <!-- Text lines -->
          <rect x="8" y="18" width="34" height="3" rx="1" fill="var(--nord8)" opacity="0.8" />
          <rect x="8" y="26" width="28" height="3" rx="1" fill="var(--nord4)" opacity="0.5" />
          <rect x="8" y="34" width="32" height="3" rx="1" fill="var(--nord4)" opacity="0.5" />
          <rect x="8" y="42" width="20" height="3" rx="1" fill="var(--nord4)" opacity="0.5" />
          <!-- Highlight marker -->
          <rect x="8" y="50" width="24" height="4" rx="1" fill="var(--nord13)" opacity="0.7" />
        </g>

        <!-- Inner rotating element -->
        <circle
          r="8"
          cx="15"
          cy="20"
          fill="var(--nord8)"
          opacity="0.3"
          transform="rotate({-rotation * 0.5})"
        />
      </g>
    </svg>

    <h1 class="title">Tlacuilo</h1>
    <p class="subtitle">PDF Annotation Tool</p>

    <div class="loading-dots">
      <span class="dot" style="animation-delay: 0s"></span>
      <span class="dot" style="animation-delay: 0.2s"></span>
      <span class="dot" style="animation-delay: 0.4s"></span>
    </div>

    <p class="loading-text">Initializing...</p>
  </div>
</div>

<style>
  .splash {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--nord0);
    z-index: 999999;
  }

  .content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
  }

  .logo {
    filter: drop-shadow(0 4px 20px rgba(136, 192, 208, 0.2));
  }

  .title {
    font-size: 2rem;
    font-weight: 600;
    color: var(--nord6);
    margin: 0;
    letter-spacing: 0.05em;
  }

  .subtitle {
    font-size: 0.875rem;
    color: var(--nord4);
    margin: 0;
    opacity: 0.7;
  }

  .loading-dots {
    display: flex;
    gap: 0.5rem;
    margin-top: 1rem;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: var(--nord8);
    animation: bounce 1s ease-in-out infinite;
  }

  .loading-text {
    font-size: 0.75rem;
    color: var(--nord4);
    opacity: 0.5;
    margin: 0;
  }

  @keyframes bounce {
    0%, 100% {
      transform: translateY(0);
      opacity: 0.4;
    }
    50% {
      transform: translateY(-8px);
      opacity: 1;
    }
  }
</style>
