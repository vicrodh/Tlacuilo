<svelte:head>
  <title>I H PDF</title>
</svelte:head>

<main class="min-h-screen bg-base-200 text-base-content">
  <header class="border-b border-base-300 bg-base-100">
    <div class="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
      <div class="flex items-center gap-2">
        <div class="grid h-10 w-10 place-items-center rounded-lg bg-primary text-lg font-bold text-primary-content">
          IH
        </div>
        <div>
          <p class="text-lg font-semibold">I H PDF</p>
          <p class="text-sm text-base-content/70">H as in hate</p>
        </div>
      </div>
      <div class="flex items-center gap-3 text-sm">
        <span class="badge badge-outline">Offline first</span>
        <span class="badge badge-outline">Svelte + Tauri</span>
        <span class="badge badge-outline">Python backend</span>
      </div>
    </div>
  </header>

  <section class="mx-auto max-w-6xl px-6 py-10">
    <div class="grid gap-8 lg:grid-cols-[1.5fr,1fr]">
      <div class="space-y-6">
        <div class="space-y-2">
          <p class="text-sm uppercase tracking-[0.2em] text-primary">Sprint 0</p>
          <h1 class="text-4xl font-semibold leading-tight">Desktop PDF toolkit for Linux, built to stay offline.</h1>
          <p class="text-base text-base-content/80">
            This is the base shell for I H PDF. The initial goal is a solid Tauri + Svelte skeleton with Tailwind/DaisyUI,
            ready for Python-backed PDF operations (PyMuPDF, pikepdf) and the annotation/editor work planned in the roadmap.
          </p>
        </div>
        <div class="grid gap-4 md:grid-cols-2">
          <div class="rounded-xl border border-base-300 bg-base-100 p-4 shadow-sm">
            <p class="text-sm font-semibold text-base-content/80">Sprint 0 Objectives</p>
            <ul class="mt-2 space-y-2 text-sm text-base-content/80">
              <li>Set up Svelte + Tailwind + DaisyUI shell.</li>
              <li>Add Tauri scaffold with a minimal command surface.</li>
              <li>Prepare Python 3.12 environment for PDF tooling.</li>
            </ul>
          </div>
          <div class="rounded-xl border border-base-300 bg-base-100 p-4 shadow-sm">
            <p class="text-sm font-semibold text-base-content/80">Next Steps</p>
            <ul class="mt-2 space-y-2 text-sm text-base-content/80">
              <li>Implement the Python bridge for core PDF actions.</li>
              <li>Lay down annotation and text-edit limited UX.</li>
              <li>Start Sprint 1: page operations and merging.</li>
            </ul>
          </div>
        </div>
      </div>

      <div class="rounded-2xl border border-base-300 bg-base-100 p-6 shadow-sm">
        <h2 class="text-lg font-semibold">Initial toolset (planned)</h2>
        <div class="mt-4 space-y-3">
          <div class="flex items-start gap-3">
            <div class="badge badge-primary mt-0.5">Pages</div>
            <div>
              <p class="font-medium text-base-content">Merge, split, reorder, rotate</p>
              <p class="text-sm text-base-content/70">Backed by PyMuPDF/pikepdf for fast page manipulation.</p>
            </div>
          </div>
          <div class="flex items-start gap-3">
            <div class="badge badge-secondary mt-0.5">Convert</div>
            <div>
              <p class="font-medium text-base-content">JPG ↔ PDF</p>
              <p class="text-sm text-base-content/70">Minimal image pipeline first; compression and PDF/A later.</p>
            </div>
          </div>
          <div class="flex items-start gap-3">
            <div class="badge badge-accent mt-0.5">Edit</div>
            <div>
              <p class="font-medium text-base-content">Annotations + limited text edits</p>
              <p class="text-sm text-base-content/70">Canvas for annotations now; OCR-aware text replacement next.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</main>
