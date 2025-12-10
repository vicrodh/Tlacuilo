<svelte:head>
  <title>I H PDF</title>
</svelte:head>

<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import { open, save } from '@tauri-apps/plugin-dialog';

  type Tool = {
    label: string;
    icon: string;
    tip: string;
    action?: 'merge' | 'split' | 'rotate';
  };

  const quickTools: Tool[] = [
    { label: 'Create PDF', icon: 'C', tip: 'New PDF from images or blank canvas' },
    { label: 'Edit blocks', icon: 'E', tip: 'Limited text edits within detected blocks' },
    { label: 'Merge PDF', icon: 'M', tip: 'Join PDFs in order selected', action: 'merge' },
    { label: 'Split PDF', icon: 'S', tip: 'Split one PDF into single pages', action: 'split' },
    { label: 'Rotate 90°', icon: 'R', tip: 'Rotate all pages 90° clockwise', action: 'rotate' },
    { label: 'Convert', icon: 'V', tip: 'JPG ↔ PDF, PDF → images' },
    { label: 'Annotate', icon: 'A', tip: 'Highlights, shapes, notes, freehand' },
    { label: 'Protect', icon: 'P', tip: 'Encrypt, redact, remove metadata' },
    { label: 'Forms', icon: 'F', tip: 'Fill and save AcroForms' },
    { label: 'Compress', icon: 'O', tip: 'Optimize size via Ghostscript' }
  ];

  let status = 'Ready';

  async function handleTool(tool: Tool) {
    if (tool.action === 'merge') {
      status = '';
      const files = await open({
        multiple: true,
        filters: [{ name: 'PDF files', extensions: ['pdf'] }]
      });
      if (!files || (Array.isArray(files) && files.length < 2)) {
        status = 'Select at least two PDFs to merge.';
        return;
      }
      const inputs = Array.isArray(files) ? files.map(String) : [String(files)];
      const output = await save({
        defaultPath: 'merged.pdf',
        filters: [{ name: 'PDF files', extensions: ['pdf'] }]
      });
      if (!output) {
        status = 'Merge cancelled (no output selected).';
        return;
      }
      try {
        const result = await invoke<string>('merge_pdfs', { inputs, output });
        status = `Merged into ${result}`;
      } catch (err) {
        status = `Merge failed: ${err}`;
        console.error('merge_pdfs error', err);
      }
      return;
    }

    if (tool.action === 'split') {
      status = '';
      const file = await open({
        multiple: false,
        filters: [{ name: 'PDF files', extensions: ['pdf'] }]
      });
      if (!file) {
        status = 'Split cancelled (no input selected).';
        return;
      }
      const outputDir = await open({
        multiple: false,
        directory: true
      });
      if (!outputDir) {
        status = 'Split cancelled (no output directory).';
        return;
      }
      try {
        const results = await invoke<string[]>('split_pdf', { input: String(file), outputDir: String(outputDir) });
        status = `Split completed. Output in ${results[0]}.`;
      } catch (err) {
        status = `Split failed: ${err}`;
        console.error('split_pdf error', err);
      }
      return;
    }

    if (tool.action === 'rotate') {
      status = '';
      const file = await open({
        multiple: false,
        filters: [{ name: 'PDF files', extensions: ['pdf'] }]
      });
      if (!file) {
        status = 'Rotate cancelled (no input selected).';
        return;
      }
      const output = await save({
        defaultPath: 'rotated.pdf',
        filters: [{ name: 'PDF files', extensions: ['pdf'] }]
      });
      if (!output) {
        status = 'Rotate cancelled (no output selected).';
        return;
      }
      try {
        const result = await invoke<string>('rotate_pdf', { input: String(file), degrees: 90, output });
        status = `Rotated into ${result}`;
      } catch (err) {
        status = `Rotate failed: ${err}`;
        console.error('rotate_pdf error', err);
      }
      return;
    }

    status = `${tool.label} is not wired yet.`;
  }
</script>

<main class="min-h-screen bg-base-200 text-base-content">
  <header class="border-b border-base-300 bg-base-100">
    <div class="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
      <div class="flex items-center gap-3">
        <div class="grid h-10 w-10 place-items-center rounded-lg bg-primary text-lg font-bold text-primary-content">
          IH
        </div>
        <div>
          <p class="text-lg font-semibold">I H PDF</p>
          <p class="text-xs text-base-content/70">H as in hate</p>
        </div>
      </div>
      <div class="flex items-center gap-3 text-sm">
        <span class="badge badge-outline">Offline first</span>
        <span class="badge badge-outline">Svelte + Tauri</span>
        <span class="badge badge-outline">Python backend</span>
        <button class="btn btn-sm btn-ghost">App menu</button>
      </div>
    </div>
  </header>

  <div class="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-6 py-6 lg:grid-cols-[280px,1fr]">
    <aside class="flex flex-col gap-3 rounded-2xl border border-base-300 bg-base-100 p-4 shadow-sm">
      <p class="text-sm font-semibold text-base-content/70">Navigation</p>
      <nav class="space-y-2 text-sm">
        <button class="btn btn-block justify-start gap-2" type="button">Home</button>
        <button class="btn btn-block justify-start gap-2 btn-ghost" type="button">Recent files</button>
        <button class="btn btn-block justify-start gap-2 btn-ghost" type="button">Tools</button>
        <button class="btn btn-block justify-start gap-2 btn-ghost" type="button">Tasks</button>
        <button class="btn btn-block justify-start gap-2 btn-ghost" type="button">Preferences</button>
      </nav>
      <div class="divider my-2"></div>
      <div class="space-y-2">
        <p class="text-sm font-semibold text-base-content/70">Pinned tools</p>
        <div class="grid gap-2">
          <div class="flex items-center justify-between rounded-lg bg-base-200 px-3 py-2 text-sm">
            <span>Merge PDF</span>
            <span class="badge badge-primary badge-sm">Pages</span>
          </div>
          <div class="flex items-center justify-between rounded-lg bg-base-200 px-3 py-2 text-sm">
            <span>Compress PDF</span>
            <span class="badge badge-secondary badge-sm">Optimize</span>
          </div>
          <div class="flex items-center justify-between rounded-lg bg-base-200 px-3 py-2 text-sm">
            <span>Fill forms</span>
            <span class="badge badge-accent badge-sm">Forms</span>
          </div>
        </div>
      </div>
    </aside>

    <section class="space-y-6">
      <div class="grid gap-6 lg:grid-cols-[1.4fr,1fr]">
        <div class="rounded-2xl border border-base-300 bg-base-100 p-5 shadow-sm">
          <div class="flex items-center justify-between">
            <p class="text-base font-semibold">Quick tools</p>
            <p class="text-xs text-base-content/60">Square buttons, hover for details</p>
          </div>
          <div class="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            {#each quickTools as tool}
              <div class="tooltip" data-tip={tool.tip}>
                <button
                  class="btn h-28 w-full flex-col items-center justify-center gap-2 border border-base-300 bg-base-200/70 text-sm font-semibold"
                  on:click={() => handleTool(tool)}
                >
                  <span class="flex h-10 w-10 items-center justify-center rounded-full bg-base-100 text-base font-bold">
                    {tool.icon}
                  </span>
                  <span class="text-center leading-tight">{tool.label}</span>
                </button>
              </div>
            {/each}
          </div>
        </div>

        <div class="rounded-2xl border border-base-300 bg-base-100 p-5 shadow-sm">
          <div class="flex items-center justify-between">
            <p class="text-base font-semibold">Recent files</p>
            <button class="btn btn-sm btn-primary">Select PDF</button>
          </div>
          <div class="mt-4 grid gap-3 md:grid-cols-2">
            <div class="rounded-xl border border-base-200 bg-base-200/60 p-4">
              <p class="text-sm font-semibold text-base-content/80">Last opened</p>
              <ul class="mt-2 space-y-2 text-sm text-base-content/70">
                <li>contract_v3.pdf — yesterday</li>
                <li>report_q4.pdf — 2 days ago</li>
                <li>scanned_invoice.pdf — 3 days ago</li>
              </ul>
            </div>
            <div class="rounded-xl border border-base-200 bg-base-200/60 p-4">
              <p class="text-sm font-semibold text-base-content/80">In progress</p>
              <ul class="mt-2 space-y-2 text-sm text-base-content/70">
                <li>Merge + reorder pages</li>
                <li>Compress and export</li>
                <li>Annotate and redact</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>

  <footer class="fixed inset-x-0 bottom-0 border-t border-base-300 bg-base-100/95 backdrop-blur">
    <div class="mx-auto flex max-w-7xl items-center justify-between px-6 py-2 text-sm text-base-content/80">
      <div class="flex items-center gap-2">
        <span class="font-semibold">Status:</span>
        <span>{status}</span>
      </div>
      <div class="text-xs text-base-content/60">IH PDF · Offline toolkit</div>
    </div>
  </footer>
</main>
