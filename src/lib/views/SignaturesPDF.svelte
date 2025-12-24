<script lang="ts">
  import { PenTool, Upload, ShieldCheck, Image, Trash2, Plus } from 'lucide-svelte';

  interface Props {
    onNavigate?: (page: string) => void;
  }

  let { onNavigate }: Props = $props();

  // Signature library (placeholder data structure for future implementation)
  interface SavedSignature {
    id: string;
    name: string;
    type: 'drawn' | 'image';
    preview: string; // base64 or path
    createdAt: number;
  }

  let savedSignatures = $state<SavedSignature[]>([]);
  let activeSection = $state<'draw' | 'upload' | 'certificate' | null>(null);

  const signatureOptions = [
    {
      id: 'draw',
      label: 'Draw Signature',
      description: 'Draw your signature using mouse or touchpad',
      icon: PenTool,
      status: 'planned',
    },
    {
      id: 'upload',
      label: 'Upload Image',
      description: 'Upload an image of your signature',
      icon: Upload,
      status: 'planned',
    },
    {
      id: 'certificate',
      label: 'Digital Certificate',
      description: 'Sign with a PKCS#7 certificate (PAdES)',
      icon: ShieldCheck,
      status: 'future',
    },
  ] as const;

  function handleOptionClick(optionId: string) {
    activeSection = optionId as typeof activeSection;
  }
</script>

<div class="flex-1 flex flex-col overflow-hidden">
  <!-- Header -->
  <header
    class="flex items-center justify-between px-6 py-4 border-b"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <div class="flex items-center gap-3">
      <div
        class="w-10 h-10 rounded-lg flex items-center justify-center"
        style="background-color: var(--nord10);"
      >
        <PenTool size={20} style="color: var(--nord6);" />
      </div>
      <div>
        <h1 class="text-lg font-semibold" style="color: var(--nord6);">Signatures</h1>
        <p class="text-xs opacity-60">Sign PDF documents</p>
      </div>
    </div>
  </header>

  <!-- Content -->
  <div class="flex-1 overflow-auto p-6">
    <div class="max-w-4xl mx-auto">
      <!-- Signature Options Grid -->
      <section class="mb-8">
        <h2 class="text-sm font-medium mb-4 opacity-60 uppercase tracking-wider">Sign Methods</h2>
        <div class="grid grid-cols-3 gap-4">
          {#each signatureOptions as option}
            <button
              onclick={() => handleOptionClick(option.id)}
              class="flex flex-col items-center gap-3 p-6 rounded-xl transition-all hover:scale-[1.02] active:scale-[0.98] relative"
              style="background-color: {activeSection === option.id ? 'var(--nord2)' : 'var(--nord1)'};
                     border: 1px solid {activeSection === option.id ? 'var(--nord8)' : 'var(--nord3)'};"
            >
              {#if option.status === 'future'}
                <span
                  class="absolute top-2 right-2 text-[10px] px-2 py-0.5 rounded-full"
                  style="background-color: var(--nord13); color: var(--nord0);"
                >
                  Future
                </span>
              {:else if option.status === 'planned'}
                <span
                  class="absolute top-2 right-2 text-[10px] px-2 py-0.5 rounded-full"
                  style="background-color: var(--nord10); color: var(--nord6);"
                >
                  Planned
                </span>
              {/if}
              <div
                class="w-12 h-12 rounded-xl flex items-center justify-center"
                style="background-color: rgba(136, 192, 208, 0.1);"
              >
                <option.icon size={24} style="color: var(--nord8);" />
              </div>
              <div class="text-center">
                <h3 class="font-medium mb-1" style="color: var(--nord6);">{option.label}</h3>
                <p class="text-xs opacity-50">{option.description}</p>
              </div>
            </button>
          {/each}
        </div>
      </section>

      <!-- Signature Library (placeholder) -->
      <section class="mb-8">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-medium opacity-60 uppercase tracking-wider">Saved Signatures</h2>
          <button
            class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-colors opacity-50 cursor-not-allowed"
            style="background-color: var(--nord2);"
            disabled
          >
            <Plus size={14} />
            <span>New</span>
          </button>
        </div>

        <div
          class="rounded-xl p-8 text-center"
          style="background-color: var(--nord1); border: 1px dashed var(--nord3);"
        >
          {#if savedSignatures.length === 0}
            <Image size={32} class="mx-auto mb-3 opacity-20" />
            <p class="text-sm opacity-40 mb-2">No saved signatures</p>
            <p class="text-xs opacity-30">
              Your signature library will appear here once the feature is implemented.
            </p>
          {:else}
            <div class="grid grid-cols-4 gap-4">
              {#each savedSignatures as sig}
                <div
                  class="relative p-4 rounded-lg"
                  style="background-color: var(--nord2);"
                >
                  <img src={sig.preview} alt={sig.name} class="w-full h-16 object-contain" />
                  <p class="text-xs mt-2 truncate">{sig.name}</p>
                  <button
                    class="absolute top-1 right-1 p-1 rounded opacity-0 hover:opacity-100 transition-opacity"
                    style="background-color: var(--nord11);"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      </section>

      <!-- Active Section Content -->
      {#if activeSection}
        <section
          class="rounded-xl p-6"
          style="background-color: var(--nord1); border: 1px solid var(--nord3);"
        >
          {#if activeSection === 'draw'}
            <h3 class="font-medium mb-4" style="color: var(--nord8);">Draw Signature</h3>
            <div
              class="h-48 rounded-lg flex items-center justify-center"
              style="background-color: var(--nord0); border: 2px dashed var(--nord3);"
            >
              <div class="text-center">
                <PenTool size={32} class="mx-auto mb-2 opacity-20" />
                <p class="text-sm opacity-40">Canvas area (coming soon)</p>
                <p class="text-xs opacity-30 mt-1">Draw with mouse, stylus, or touchpad</p>
              </div>
            </div>
            <div class="flex gap-3 mt-4">
              <button
                class="px-4 py-2 rounded-lg text-sm opacity-50 cursor-not-allowed"
                style="background-color: var(--nord2);"
                disabled
              >
                Clear
              </button>
              <button
                class="px-4 py-2 rounded-lg text-sm opacity-50 cursor-not-allowed"
                style="background-color: var(--nord10);"
                disabled
              >
                Save to Library
              </button>
            </div>
          {:else if activeSection === 'upload'}
            <h3 class="font-medium mb-4" style="color: var(--nord8);">Upload Signature Image</h3>
            <div
              class="h-48 rounded-lg flex items-center justify-center cursor-not-allowed"
              style="background-color: var(--nord0); border: 2px dashed var(--nord3);"
            >
              <div class="text-center">
                <Upload size={32} class="mx-auto mb-2 opacity-20" />
                <p class="text-sm opacity-40">Drop image here or click to upload</p>
                <p class="text-xs opacity-30 mt-1">PNG, JPG with transparent background recommended</p>
              </div>
            </div>
          {:else if activeSection === 'certificate'}
            <h3 class="font-medium mb-4" style="color: var(--nord8);">Digital Certificate</h3>
            <div class="space-y-4">
              <div
                class="p-4 rounded-lg"
                style="background-color: var(--nord0);"
              >
                <p class="text-sm opacity-60 mb-2">Certificate File (.p12, .pfx)</p>
                <button
                  class="w-full py-3 rounded-lg text-sm opacity-50 cursor-not-allowed flex items-center justify-center gap-2"
                  style="background-color: var(--nord2); border: 1px dashed var(--nord3);"
                  disabled
                >
                  <ShieldCheck size={16} />
                  <span>Select Certificate</span>
                </button>
              </div>
              <p class="text-xs opacity-30 text-center">
                PKCS#7 / PAdES digital signatures require a valid certificate.
                This feature is planned for a future release.
              </p>
            </div>
          {/if}
        </section>
      {/if}

      <!-- Roadmap Info -->
      <section class="mt-8 p-4 rounded-lg" style="background-color: var(--nord2);">
        <h3 class="text-sm font-medium mb-2 opacity-60">Planned Features</h3>
        <ul class="text-xs opacity-50 space-y-1 list-disc list-inside">
          <li>Draw signature with customizable stroke width and color</li>
          <li>Upload signature image with background removal</li>
          <li>Signature library with multiple saved signatures</li>
          <li>Drag and drop to position signature on document</li>
          <li>Digital certificates (PKCS#7, PAdES) with timestamp</li>
          <li>Signature verification</li>
        </ul>
      </section>
    </div>
  </div>
</div>
