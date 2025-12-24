<script lang="ts">
  import { Upload, Lock, FileText, Download, AlertCircle, CheckCircle, Eye, EyeOff, Shield } from 'lucide-svelte';
  import { listen } from '@tauri-apps/api/event';
  import { open, save } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';
  import { onMount, onDestroy } from 'svelte';
  import { log, logSuccess, logError, registerFile, unregisterModule } from '$lib/stores/status.svelte';

  const MODULE = 'Encrypt';

  interface EncryptResult {
    success: boolean;
    message: string;
  }

  let filePath = $state<string | null>(null);
  let fileName = $state<string>('');
  let isEncrypting = $state(false);
  let encryptResult = $state<EncryptResult | null>(null);
  let unlistenDrop: (() => void) | null = null;

  // Password fields
  let userPassword = $state('');
  let userPasswordConfirm = $state('');
  let ownerPassword = $state('');
  let ownerPasswordConfirm = $state('');
  let showUserPassword = $state(false);
  let showOwnerPassword = $state(false);

  // Permissions
  let allowPrinting = $state(true);
  let allowCopying = $state(true);
  let allowModifying = $state(false);

  // Validation
  let userPasswordMatch = $derived(userPassword === userPasswordConfirm);
  let ownerPasswordMatch = $derived(ownerPassword === ownerPasswordConfirm);
  let hasAnyPassword = $derived(userPassword.length > 0 || ownerPassword.length > 0);
  let canEncrypt = $derived(
    filePath &&
    hasAnyPassword &&
    (userPassword.length === 0 || userPasswordMatch) &&
    (ownerPassword.length === 0 || ownerPasswordMatch)
  );

  onMount(async () => {
    unlistenDrop = await listen<string[]>('tauri://file-drop', async (e) => {
      const pdfs = e.payload.filter((p: string) => p.toLowerCase().endsWith('.pdf'));
      if (pdfs.length > 0) {
        await loadFile(pdfs[0]);
      }
    });
  });

  onDestroy(() => {
    if (unlistenDrop) unlistenDrop();
    unregisterModule(MODULE);
  });

  async function selectFile() {
    const selected = await open({
      multiple: false,
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });
    if (selected) {
      await loadFile(selected as string);
    }
  }

  async function loadFile(path: string) {
    filePath = path;
    fileName = path.split('/').pop() || path;
    encryptResult = null;
    registerFile(MODULE, path);
    log(MODULE, `Selected: ${fileName}`);
  }

  async function encryptPdf() {
    if (!filePath || !canEncrypt) return;

    const defaultName = fileName.replace('.pdf', '-encrypted.pdf');
    const savePath = await save({
      defaultPath: defaultName,
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });

    if (!savePath) return;

    isEncrypting = true;
    encryptResult = null;

    try {
      log(MODULE, `Encrypting: ${fileName}`);
      const result = await invoke<EncryptResult>('pdf_encrypt', {
        input: filePath,
        output: savePath,
        userPassword: userPassword || null,
        ownerPassword: ownerPassword || null,
        allowPrinting,
        allowCopying,
        allowModifying,
      });

      encryptResult = result;

      if (result.success) {
        logSuccess(MODULE, `Encrypted and saved: ${savePath.split('/').pop()}`);
      } else {
        logError(MODULE, result.message);
      }
    } catch (err) {
      logError(MODULE, `Encryption failed: ${err}`);
      encryptResult = {
        success: false,
        message: String(err)
      };
    } finally {
      isEncrypting = false;
    }
  }

  function clearFile() {
    filePath = null;
    fileName = '';
    encryptResult = null;
    userPassword = '';
    userPasswordConfirm = '';
    ownerPassword = '';
    ownerPasswordConfirm = '';
    unregisterModule(MODULE);
  }
</script>

<div class="flex-1 overflow-auto p-8">
  <div class="max-w-2xl mx-auto">
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-2xl font-semibold mb-2" style="color: var(--nord6);">Encrypt PDF</h1>
      <p class="text-sm" style="color: var(--nord4);">
        Add password protection and set permissions for PDF files.
      </p>
    </div>

    <!-- Drop Zone / File Info -->
    {#if !filePath}
      <button
        onclick={selectFile}
        class="w-full p-12 rounded-xl border-2 border-dashed transition-all hover:border-[var(--nord8)] hover:bg-[var(--nord1)] cursor-pointer"
        style="border-color: var(--nord3); background-color: var(--nord0);"
      >
        <div class="flex flex-col items-center gap-4">
          <div class="w-16 h-16 rounded-full flex items-center justify-center" style="background-color: var(--nord1);">
            <Upload size={32} style="color: var(--nord8);" />
          </div>
          <div class="text-center">
            <p class="font-medium mb-1" style="color: var(--nord4);">Drop PDF here or click to browse</p>
            <p class="text-sm opacity-60" style="color: var(--nord4);">Select a PDF to encrypt</p>
          </div>
        </div>
      </button>
    {:else}
      <!-- File Info Card -->
      <div class="rounded-xl p-6 mb-6" style="background-color: var(--nord1); border: 1px solid var(--nord3);">
        <div class="flex items-start justify-between mb-4">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-lg flex items-center justify-center" style="background-color: var(--nord2);">
              <FileText size={20} style="color: var(--nord8);" />
            </div>
            <div>
              <p class="font-medium truncate max-w-md" style="color: var(--nord5);">{fileName}</p>
              <p class="text-xs truncate max-w-md opacity-60" style="color: var(--nord4);">{filePath}</p>
            </div>
          </div>
          <button
            onclick={clearFile}
            class="p-2 rounded-lg hover:bg-[var(--nord2)] transition-colors"
            title="Remove file"
          >
            <span class="text-xs" style="color: var(--nord11);">Clear</span>
          </button>
        </div>
      </div>

      <!-- Password Settings -->
      <div class="rounded-xl p-6 mb-6" style="background-color: var(--nord1); border: 1px solid var(--nord3);">
        <h3 class="font-medium mb-4 flex items-center gap-2" style="color: var(--nord8);">
          <Lock size={18} />
          Password Protection
        </h3>

        <!-- User Password (to open) -->
        <div class="mb-4">
          <label class="block mb-2 text-sm" style="color: var(--nord4);">
            User Password <span class="opacity-50">(required to open)</span>
          </label>
          <div class="flex gap-2">
            <div class="relative flex-1">
              <input
                type={showUserPassword ? 'text' : 'password'}
                bind:value={userPassword}
                placeholder="Leave empty for no open password"
                class="w-full px-4 py-3 pr-12 rounded-lg text-sm"
                style="background-color: var(--nord2); color: var(--nord5); border: 1px solid var(--nord3);"
              />
              <button
                onclick={() => showUserPassword = !showUserPassword}
                class="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded hover:bg-[var(--nord3)] transition-colors"
              >
                {#if showUserPassword}
                  <EyeOff size={18} style="color: var(--nord4);" />
                {:else}
                  <Eye size={18} style="color: var(--nord4);" />
                {/if}
              </button>
            </div>
            <input
              type={showUserPassword ? 'text' : 'password'}
              bind:value={userPasswordConfirm}
              placeholder="Confirm"
              class="w-32 px-4 py-3 rounded-lg text-sm"
              style="background-color: var(--nord2); color: var(--nord5); border: 1px solid {userPassword && !userPasswordMatch ? 'var(--nord11)' : 'var(--nord3)'};"
            />
          </div>
          {#if userPassword && !userPasswordMatch}
            <p class="text-xs mt-1" style="color: var(--nord11);">Passwords don't match</p>
          {/if}
        </div>

        <!-- Owner Password (for permissions) -->
        <div>
          <label class="block mb-2 text-sm" style="color: var(--nord4);">
            Owner Password <span class="opacity-50">(required to change permissions)</span>
          </label>
          <div class="flex gap-2">
            <div class="relative flex-1">
              <input
                type={showOwnerPassword ? 'text' : 'password'}
                bind:value={ownerPassword}
                placeholder="Leave empty for no owner password"
                class="w-full px-4 py-3 pr-12 rounded-lg text-sm"
                style="background-color: var(--nord2); color: var(--nord5); border: 1px solid var(--nord3);"
              />
              <button
                onclick={() => showOwnerPassword = !showOwnerPassword}
                class="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded hover:bg-[var(--nord3)] transition-colors"
              >
                {#if showOwnerPassword}
                  <EyeOff size={18} style="color: var(--nord4);" />
                {:else}
                  <Eye size={18} style="color: var(--nord4);" />
                {/if}
              </button>
            </div>
            <input
              type={showOwnerPassword ? 'text' : 'password'}
              bind:value={ownerPasswordConfirm}
              placeholder="Confirm"
              class="w-32 px-4 py-3 rounded-lg text-sm"
              style="background-color: var(--nord2); color: var(--nord5); border: 1px solid {ownerPassword && !ownerPasswordMatch ? 'var(--nord11)' : 'var(--nord3)'};"
            />
          </div>
          {#if ownerPassword && !ownerPasswordMatch}
            <p class="text-xs mt-1" style="color: var(--nord11);">Passwords don't match</p>
          {/if}
        </div>
      </div>

      <!-- Permissions -->
      <div class="rounded-xl p-6 mb-6" style="background-color: var(--nord1); border: 1px solid var(--nord3);">
        <h3 class="font-medium mb-4 flex items-center gap-2" style="color: var(--nord8);">
          <Shield size={18} />
          Permissions
        </h3>

        <div class="space-y-3">
          <label class="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              bind:checked={allowPrinting}
              class="w-4 h-4 rounded"
            />
            <span style="color: var(--nord5);">Allow printing</span>
          </label>

          <label class="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              bind:checked={allowCopying}
              class="w-4 h-4 rounded"
            />
            <span style="color: var(--nord5);">Allow copying text and images</span>
          </label>

          <label class="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              bind:checked={allowModifying}
              class="w-4 h-4 rounded"
            />
            <span style="color: var(--nord5);">Allow modifying the document</span>
          </label>
        </div>

        <p class="text-xs opacity-50 mt-4" style="color: var(--nord4);">
          Note: These restrictions can be bypassed by software that ignores PDF permissions.
          For true security, use a strong user password.
        </p>
      </div>

      <!-- Result Message -->
      {#if encryptResult}
        <div
          class="rounded-xl p-4 mb-6 flex items-center gap-3"
          style="background-color: {encryptResult.success ? 'rgba(163, 190, 140, 0.1)' : 'rgba(191, 97, 106, 0.1)'}; border: 1px solid {encryptResult.success ? 'var(--nord14)' : 'var(--nord11)'};"
        >
          {#if encryptResult.success}
            <CheckCircle size={20} style="color: var(--nord14);" />
            <span style="color: var(--nord14);">{encryptResult.message}</span>
          {:else}
            <AlertCircle size={20} style="color: var(--nord11);" />
            <span style="color: var(--nord11);">{encryptResult.message}</span>
          {/if}
        </div>
      {/if}

      <!-- Action Button -->
      <button
        onclick={encryptPdf}
        disabled={isEncrypting || !canEncrypt}
        class="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        style="background-color: var(--nord10); color: var(--nord6);"
      >
        {#if isEncrypting}
          <div class="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin" style="border-color: var(--nord6);"></div>
          Encrypting...
        {:else}
          <Lock size={18} />
          Encrypt & Save PDF
        {/if}
      </button>

      {#if !hasAnyPassword}
        <p class="text-xs text-center mt-3" style="color: var(--nord13);">
          Set at least one password to encrypt the PDF
        </p>
      {/if}
    {/if}
  </div>
</div>
