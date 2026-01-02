<script lang="ts">
  import { Upload, Unlock, Lock, FileText, Download, AlertCircle, CheckCircle, Eye, EyeOff } from 'lucide-svelte';
  import { listen } from '@tauri-apps/api/event';
  import { open, save } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';
  import { onMount, onDestroy } from 'svelte';
  import { log, logSuccess, logError, registerFile, unregisterModule } from '$lib/stores/status.svelte';

  const MODULE = 'Unlock';

  interface SecurityInfo {
    is_encrypted: boolean;
    needs_password: boolean;
    has_restrictions: boolean;
    permissions: Record<string, boolean>;
    error?: string;
  }

  interface UnlockResult {
    success: boolean;
    was_encrypted: boolean;
    had_restrictions: boolean;
    message: string;
    needs_password?: boolean;
  }

  let filePath = $state<string | null>(null);
  let fileName = $state<string>('');
  let securityInfo = $state<SecurityInfo | null>(null);
  let isChecking = $state(false);
  let isUnlocking = $state(false);
  let password = $state('');
  let showPassword = $state(false);
  let unlockResult = $state<UnlockResult | null>(null);
  let unlockedPath = $state<string | null>(null);
  let unlistenDrop: (() => void) | null = null;

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
    securityInfo = null;
    unlockResult = null;
    unlockedPath = null;
    password = '';

    registerFile(MODULE, path);
    log(MODULE, `Checking security: ${fileName}`);

    isChecking = true;
    try {
      securityInfo = await invoke<SecurityInfo>('pdf_check_security', { input: path });
      log(MODULE, `Security check complete: encrypted=${securityInfo.is_encrypted}, needs_password=${securityInfo.needs_password}`);
    } catch (err) {
      logError(MODULE, `Failed to check security: ${err}`);
      securityInfo = {
        is_encrypted: false,
        needs_password: false,
        has_restrictions: false,
        permissions: {},
        error: String(err)
      };
    } finally {
      isChecking = false;
    }
  }

  async function unlockPdf() {
    if (!filePath) return;

    isUnlocking = true;
    unlockResult = null;

    try {
      log(MODULE, `Unlocking: ${fileName}`);
      const result = await invoke<UnlockResult>('pdf_unlock', {
        input: filePath,
        password: password || null,
      });

      unlockResult = result;

      if (result.success) {
        logSuccess(MODULE, result.message);
        // The output is in the cache dir, we'll save it when user clicks Save
        unlockedPath = filePath.replace('.pdf', '-unlocked.pdf');
      } else if (result.needs_password) {
        log(MODULE, 'Password required');
      } else {
        logError(MODULE, result.message);
      }
    } catch (err) {
      logError(MODULE, `Unlock failed: ${err}`);
      unlockResult = {
        success: false,
        was_encrypted: false,
        had_restrictions: false,
        message: String(err)
      };
    } finally {
      isUnlocking = false;
    }
  }

  async function saveUnlocked() {
    if (!filePath) return;

    const defaultName = fileName.replace('.pdf', '-unlocked.pdf');
    const savePath = await save({
      defaultPath: defaultName,
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });

    if (savePath) {
      try {
        log(MODULE, `Saving to: ${savePath}`);
        const result = await invoke<UnlockResult>('pdf_unlock', {
          input: filePath,
          output: savePath,
          password: password || null,
        });

        if (result.success) {
          logSuccess(MODULE, `Saved: ${savePath}`);
        } else {
          logError(MODULE, result.message);
        }
      } catch (err) {
        logError(MODULE, `Save failed: ${err}`);
      }
    }
  }

  function clearFile() {
    filePath = null;
    fileName = '';
    securityInfo = null;
    unlockResult = null;
    unlockedPath = null;
    password = '';
    unregisterModule(MODULE);
  }
</script>

<div class="flex-1 overflow-auto p-8">
  <div class="max-w-2xl mx-auto">
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-2xl font-semibold mb-2" style="color: var(--nord6);">Unlock PDF</h1>
      <p class="text-sm" style="color: var(--nord4);">
        Remove password protection and restrictions from PDF files.
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
            <p class="text-sm opacity-60" style="color: var(--nord4);">Select a PDF to check and unlock</p>
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

        <!-- Security Status -->
        {#if isChecking}
          <div class="flex items-center gap-2 p-4 rounded-lg" style="background-color: var(--nord2);">
            <div class="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin" style="border-color: var(--nord8);"></div>
            <span style="color: var(--nord4);">Checking security status...</span>
          </div>
        {:else if securityInfo}
          <div class="space-y-3">
            <!-- Encryption Status -->
            <div class="flex items-center gap-3 p-4 rounded-lg" style="background-color: var(--nord2);">
              {#if securityInfo.needs_password}
                <Lock size={20} style="color: var(--nord11);" />
                <div>
                  <p class="font-medium" style="color: var(--nord11);">Password Protected</p>
                  <p class="text-sm opacity-70" style="color: var(--nord4);">This PDF requires a password to open</p>
                </div>
              {:else if securityInfo.has_restrictions || securityInfo.is_encrypted}
                <Lock size={20} style="color: var(--nord13);" />
                <div>
                  <p class="font-medium" style="color: var(--nord13);">Has Restrictions</p>
                  <p class="text-sm opacity-70" style="color: var(--nord4);">This PDF has printing/copying restrictions</p>
                </div>
              {:else}
                <Unlock size={20} style="color: var(--nord14);" />
                <div>
                  <p class="font-medium" style="color: var(--nord14);">No Protection</p>
                  <p class="text-sm opacity-70" style="color: var(--nord4);">This PDF is not encrypted</p>
                </div>
              {/if}
            </div>

            <!-- Permissions (if has restrictions) -->
            {#if securityInfo.is_encrypted && Object.keys(securityInfo.permissions).length > 0}
              <div class="p-4 rounded-lg" style="background-color: var(--nord2);">
                <p class="text-sm font-medium mb-2" style="color: var(--nord4);">Current Permissions:</p>
                <div class="grid grid-cols-2 gap-2 text-sm">
                  {#each Object.entries(securityInfo.permissions) as [perm, allowed]}
                    <div class="flex items-center gap-2">
                      {#if allowed}
                        <CheckCircle size={14} style="color: var(--nord14);" />
                      {:else}
                        <AlertCircle size={14} style="color: var(--nord11);" />
                      {/if}
                      <span class="capitalize" style="color: var(--nord4);">{perm}</span>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        {/if}
      </div>

      <!-- Password Input (if needed) -->
      {#if securityInfo?.needs_password || (unlockResult && unlockResult.needs_password)}
        <div class="rounded-xl p-6 mb-6" style="background-color: var(--nord1); border: 1px solid var(--nord3);">
          <label class="block mb-2 text-sm font-medium" style="color: var(--nord4);">
            Password Required
          </label>
          <div class="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              bind:value={password}
              placeholder="Enter PDF password"
              class="w-full px-4 py-3 pr-12 rounded-lg text-sm"
              style="background-color: var(--nord2); color: var(--nord5); border: 1px solid var(--nord3);"
            />
            <button
              onclick={() => showPassword = !showPassword}
              class="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded hover:bg-[var(--nord3)] transition-colors"
              title={showPassword ? 'Hide password' : 'Show password'}
            >
              {#if showPassword}
                <EyeOff size={18} style="color: var(--nord4);" />
              {:else}
                <Eye size={18} style="color: var(--nord4);" />
              {/if}
            </button>
          </div>
        </div>
      {/if}

      <!-- Result Message -->
      {#if unlockResult}
        <div
          class="rounded-xl p-4 mb-6 flex items-center gap-3"
          style="background-color: {unlockResult.success ? 'rgba(163, 190, 140, 0.1)' : 'rgba(191, 97, 106, 0.1)'}; border: 1px solid {unlockResult.success ? 'var(--nord14)' : 'var(--nord11)'};"
        >
          {#if unlockResult.success}
            <CheckCircle size={20} style="color: var(--nord14);" />
            <span style="color: var(--nord14);">{unlockResult.message}</span>
          {:else}
            <AlertCircle size={20} style="color: var(--nord11);" />
            <span style="color: var(--nord11);">{unlockResult.message}</span>
          {/if}
        </div>
      {/if}

      <!-- Action Buttons -->
      <div class="flex gap-3">
        {#if securityInfo?.is_encrypted || securityInfo?.has_restrictions || securityInfo?.needs_password}
          <button
            onclick={unlockPdf}
            disabled={isUnlocking || (securityInfo?.needs_password && !password)}
            class="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            style="background-color: var(--nord8); color: var(--on-primary);"
          >
            {#if isUnlocking}
              <div class="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin" style="border-color: var(--on-primary);"></div>
              Unlocking...
            {:else}
              <Unlock size={18} />
              Unlock PDF
            {/if}
          </button>
        {/if}

        {#if unlockResult?.success}
          <button
            onclick={saveUnlocked}
            class="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-medium transition-all"
            style="background-color: var(--nord14); color: var(--nord0);"
          >
            <Download size={18} />
            Save Unlocked PDF
          </button>
        {/if}
      </div>
    {/if}
  </div>
</div>
