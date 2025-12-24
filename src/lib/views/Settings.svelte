<script lang="ts">
  import {
    Globe,
    Star,
    Clock,
    Trash2,
    HardDrive,
    ChevronRight,
    User,
    Palette
  } from 'lucide-svelte';
  import {
    getSettings,
    setLanguage,
    setPalette,
    setShowRecentFilesInHome,
    setFavorites,
    clearRecentFiles,
    updateAuthorField,
    LANGUAGES,
    PALETTES,
    TOOL_CATALOG,
    type Language,
    type PaletteId,
    type AuthorSettings
  } from '$lib/stores/settings.svelte';

  const settings = getSettings();

  // Local state for favorites editing
  let favoritesState = $state<Record<string, boolean>>({});

  // Initialize favorites state
  $effect(() => {
    const newState: Record<string, boolean> = {};
    for (const tool of TOOL_CATALOG) {
      newState[tool.id] = settings.favorites.includes(tool.id);
    }
    favoritesState = newState;
  });

  // Handle language change
  async function handleLanguageChange(lang: Language) {
    await setLanguage(lang);
  }

  // Handle palette change
  async function handlePaletteChange(palette: PaletteId) {
    await setPalette(palette);
  }

  // Handle favorite toggle
  async function handleFavoriteToggle(toolId: string) {
    favoritesState = { ...favoritesState, [toolId]: !favoritesState[toolId] };

    // Build new favorites list maintaining order
    const newFavorites: string[] = [];
    for (const tool of TOOL_CATALOG) {
      if (favoritesState[tool.id]) {
        newFavorites.push(tool.id);
      }
    }
    await setFavorites(newFavorites);
  }

  // Handle show recent files toggle
  async function handleShowRecentFilesToggle() {
    await setShowRecentFilesInHome(!settings.showRecentFilesInHome);
  }

  // Handle clear recent files
  async function handleClearRecentFiles() {
    await clearRecentFiles();
  }

  // Handle clear cache
  async function handleClearCache() {
    // Clear any cached data (localStorage, temp files, etc.)
    try {
      localStorage.clear();
      alert('Cache cleared successfully');
    } catch (err) {
      console.error('Failed to clear cache:', err);
    }
  }

  // Sections for better organization
  const sections = [
    { id: 'author', label: 'Author Info', icon: User },
    { id: 'appearance', label: 'Appearance', icon: Palette },
    { id: 'language', label: 'Language', icon: Globe },
    { id: 'favorites', label: 'Quick Tools', icon: Star },
    { id: 'recent', label: 'Recent Files', icon: Clock },
    { id: 'storage', label: 'Storage', icon: HardDrive },
  ];

  let activeSection = $state('author');
</script>

<div class="flex-1 flex overflow-hidden" style="background-color: var(--nord0);">
  <!-- Sidebar -->
  <div
    class="w-56 flex flex-col border-r"
    style="background-color: var(--nord1); border-color: var(--nord3);"
  >
    <div class="p-4 border-b" style="border-color: var(--nord3);">
      <h1 class="text-lg font-medium" style="color: var(--nord6);">Settings</h1>
    </div>

    <nav class="flex-1 p-2 space-y-1">
      {#each sections as section}
        <button
          onclick={() => activeSection = section.id}
          class="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors text-left"
          style="background-color: {activeSection === section.id ? 'var(--nord2)' : 'transparent'};
                 color: {activeSection === section.id ? 'var(--nord8)' : 'var(--nord4)'};"
        >
          <section.icon size={18} />
          <span>{section.label}</span>
        </button>
      {/each}
    </nav>
  </div>

  <!-- Main content -->
  <div class="flex-1 overflow-auto p-6">
    {#if activeSection === 'author'}
      <!-- Author Info Section -->
      <div class="max-w-2xl">
        <h2 class="text-lg font-medium mb-1" style="color: var(--nord6);">Author Info</h2>
        <p class="text-sm opacity-60 mb-6">Your identity for annotations. This info is embedded in PDF annotations you create.</p>

        <div class="space-y-4">
          <!-- Name and Surname row -->
          <div class="grid grid-cols-2 gap-4">
            <!-- Name -->
            <div
              class="px-4 py-3 rounded-xl"
              style="background-color: var(--nord1); border: 1px solid var(--nord3);"
            >
              <label class="block text-xs opacity-60 mb-1">First Name</label>
              <input
                type="text"
                value={settings.author.name}
                oninput={(e) => updateAuthorField('name', e.currentTarget.value)}
                placeholder="Enter your first name"
                class="w-full bg-transparent outline-none text-sm"
                style="color: var(--nord6);"
              />
            </div>

            <!-- Surname -->
            <div
              class="px-4 py-3 rounded-xl"
              style="background-color: var(--nord1); border: 1px solid var(--nord3);"
            >
              <label class="block text-xs opacity-60 mb-1">Last Name</label>
              <input
                type="text"
                value={settings.author.surname}
                oninput={(e) => updateAuthorField('surname', e.currentTarget.value)}
                placeholder="Enter your last name"
                class="w-full bg-transparent outline-none text-sm"
                style="color: var(--nord6);"
              />
            </div>
          </div>

          <!-- Username -->
          <div
            class="px-4 py-3 rounded-xl"
            style="background-color: var(--nord1); border: 1px solid var(--nord3);"
          >
            <label class="block text-xs opacity-60 mb-1">Username</label>
            <input
              type="text"
              value={settings.author.username}
              oninput={(e) => updateAuthorField('username', e.currentTarget.value)}
              placeholder="Enter a username (optional)"
              class="w-full bg-transparent outline-none text-sm"
              style="color: var(--nord6);"
            />
          </div>

          <!-- Email -->
          <div
            class="px-4 py-3 rounded-xl"
            style="background-color: var(--nord1); border: 1px solid var(--nord3);"
          >
            <label class="block text-xs opacity-60 mb-1">Email</label>
            <input
              type="email"
              value={settings.author.email}
              oninput={(e) => updateAuthorField('email', e.currentTarget.value)}
              placeholder="Enter your email (optional)"
              class="w-full bg-transparent outline-none text-sm"
              style="color: var(--nord6);"
            />
          </div>

          <!-- Anonymous Mode Toggle -->
          <div
            class="flex items-center justify-between px-4 py-4 rounded-xl"
            style="background-color: var(--nord1); border: 1px solid var(--nord3);"
          >
            <div>
              <p class="text-sm font-medium">Anonymous Mode</p>
              <p class="text-xs opacity-60">Hide your identity in annotations (shows "Anonymous" instead)</p>
            </div>
            <button
              onclick={() => updateAuthorField('anonymousMode', !settings.author.anonymousMode)}
              class="relative w-12 h-6 rounded-full transition-colors"
              style="background-color: {settings.author.anonymousMode ? 'var(--nord14)' : 'var(--nord3)'};"
            >
              <div
                class="absolute top-1 w-4 h-4 rounded-full transition-all"
                style="background-color: var(--nord6);
                       left: {settings.author.anonymousMode ? '28px' : '4px'};"
              ></div>
            </button>
          </div>

          <!-- Preview -->
          <div
            class="px-4 py-3 rounded-xl"
            style="background-color: var(--nord2); border: 1px solid var(--nord3);"
          >
            <p class="text-xs opacity-60 mb-1">Author name in annotations:</p>
            <p class="text-sm font-medium" style="color: var(--nord8);">
              {#if settings.author.anonymousMode}
                Anonymous
              {:else if settings.author.name || settings.author.surname}
                {`${settings.author.name} ${settings.author.surname}`.trim()}
              {:else if settings.author.username}
                {settings.author.username}
              {:else if settings.author.email}
                {settings.author.email}
              {:else}
                <span class="opacity-50 italic">No author info configured</span>
              {/if}
            </p>
          </div>
        </div>
      </div>

    {:else if activeSection === 'appearance'}
      <!-- Appearance Section -->
      <div class="max-w-2xl">
        <h2 class="text-lg font-medium mb-1" style="color: var(--nord6);">Appearance</h2>
        <p class="text-sm opacity-60 mb-6">Choose your preferred color palette for the interface.</p>

        <div class="space-y-2">
          {#each PALETTES as palette}
            <button
              onclick={() => handlePaletteChange(palette.id)}
              class="w-full flex items-center justify-between px-4 py-3 rounded-lg transition-colors"
              style="background-color: {settings.palette === palette.id ? 'var(--nord2)' : 'var(--nord1)'};
                     border: 1px solid {settings.palette === palette.id ? 'var(--nord8)' : 'var(--nord3)'};"
            >
              <div class="flex items-center gap-3">
                <div class="text-left">
                  <p class="text-sm font-medium">{palette.label}</p>
                </div>
              </div>
              {#if settings.palette === palette.id}
                <div
                  class="w-5 h-5 rounded-full flex items-center justify-center"
                  style="background-color: var(--nord8);"
                >
                  <div class="w-2 h-2 rounded-full" style="background-color: var(--nord0);"></div>
                </div>
              {:else}
                <div
                  class="w-5 h-5 rounded-full border-2"
                  style="border-color: var(--nord3);"
                ></div>
              {/if}
            </button>
          {/each}
        </div>

        <p class="text-xs opacity-40 mt-4">
          Color changes apply immediately. Your preference is saved automatically.
        </p>
      </div>

    {:else if activeSection === 'language'}
      <!-- Language Section -->
      <div class="max-w-2xl">
        <h2 class="text-lg font-medium mb-1" style="color: var(--nord6);">Language</h2>
        <p class="text-sm opacity-60 mb-6">Choose your preferred language for the interface.</p>

        <div class="space-y-2">
          {#each LANGUAGES as lang}
            <button
              onclick={() => handleLanguageChange(lang.id)}
              class="w-full flex items-center justify-between px-4 py-3 rounded-lg transition-colors"
              style="background-color: {settings.language === lang.id ? 'var(--nord2)' : 'var(--nord1)'};
                     border: 1px solid {settings.language === lang.id ? 'var(--nord8)' : 'var(--nord3)'};"
            >
              <div class="flex items-center gap-3">
                <span class="text-lg">{lang.id === 'en' ? '🇺🇸' : lang.id === 'es' ? '🇲🇽' : lang.id === 'pt' ? '🇧🇷' : lang.id === 'fr' ? '🇫🇷' : '🇩🇪'}</span>
                <div class="text-left">
                  <p class="text-sm font-medium">{lang.label}</p>
                  <p class="text-xs opacity-60">{lang.native}</p>
                </div>
              </div>
              {#if settings.language === lang.id}
                <div
                  class="w-5 h-5 rounded-full flex items-center justify-center"
                  style="background-color: var(--nord8);"
                >
                  <div class="w-2 h-2 rounded-full" style="background-color: var(--nord0);"></div>
                </div>
              {:else}
                <div
                  class="w-5 h-5 rounded-full border-2"
                  style="border-color: var(--nord3);"
                ></div>
              {/if}
            </button>
          {/each}
        </div>

        <p class="text-xs opacity-40 mt-4">
          Note: Language support is being expanded. Some text may appear in English.
        </p>
      </div>

    {:else if activeSection === 'favorites'}
      <!-- Favorites Section -->
      <div class="max-w-2xl">
        <h2 class="text-lg font-medium mb-1" style="color: var(--nord6);">Quick Tools</h2>
        <p class="text-sm opacity-60 mb-6">Choose which tools appear in the sidebar favorites section.</p>

        <div
          class="rounded-xl overflow-hidden"
          style="background-color: var(--nord1); border: 1px solid var(--nord3);"
        >
          <!-- Header -->
          <div
            class="flex items-center px-4 py-2 border-b text-xs uppercase opacity-60"
            style="border-color: var(--nord3); background-color: var(--nord2);"
          >
            <span class="flex-1">Tool</span>
            <span class="w-32 text-center">Show in Favorites</span>
          </div>

          <!-- Tool list -->
          <div class="divide-y" style="border-color: var(--nord3);">
            {#each TOOL_CATALOG as tool}
              <div
                class="flex items-center px-4 py-3 hover:bg-[var(--nord2)] transition-colors"
              >
                <div class="flex-1">
                  <p class="text-sm">{tool.label}</p>
                  {#if tool.description}
                    <p class="text-xs opacity-50">{tool.description}</p>
                  {/if}
                </div>
                <div class="w-32 flex justify-center">
                  <button
                    onclick={() => handleFavoriteToggle(tool.id)}
                    class="relative w-12 h-6 rounded-full transition-colors"
                    style="background-color: {favoritesState[tool.id] ? 'var(--nord14)' : 'var(--nord3)'};"
                  >
                    <div
                      class="absolute top-1 w-4 h-4 rounded-full transition-all"
                      style="background-color: var(--nord6);
                             left: {favoritesState[tool.id] ? '28px' : '4px'};"
                    ></div>
                  </button>
                </div>
              </div>
            {/each}
          </div>
        </div>
      </div>

    {:else if activeSection === 'recent'}
      <!-- Recent Files Section -->
      <div class="max-w-2xl">
        <h2 class="text-lg font-medium mb-1" style="color: var(--nord6);">Recent Files</h2>
        <p class="text-sm opacity-60 mb-6">Manage how recent files are displayed and stored.</p>

        <div class="space-y-4">
          <!-- Show in Home toggle -->
          <div
            class="flex items-center justify-between px-4 py-4 rounded-xl"
            style="background-color: var(--nord1); border: 1px solid var(--nord3);"
          >
            <div>
              <p class="text-sm font-medium">Show Recent Files in Home</p>
              <p class="text-xs opacity-60">Display recently opened files on the dashboard</p>
            </div>
            <button
              onclick={handleShowRecentFilesToggle}
              class="relative w-12 h-6 rounded-full transition-colors"
              style="background-color: {settings.showRecentFilesInHome ? 'var(--nord14)' : 'var(--nord3)'};"
            >
              <div
                class="absolute top-1 w-4 h-4 rounded-full transition-all"
                style="background-color: var(--nord6);
                       left: {settings.showRecentFilesInHome ? '28px' : '4px'};"
              ></div>
            </button>
          </div>

          <!-- Clear Recent Files -->
          <div
            class="flex items-center justify-between px-4 py-4 rounded-xl"
            style="background-color: var(--nord1); border: 1px solid var(--nord3);"
          >
            <div>
              <p class="text-sm font-medium">Clear Recent Files</p>
              <p class="text-xs opacity-60">
                {settings.recentFiles.length} file{settings.recentFiles.length !== 1 ? 's' : ''} in history
              </p>
            </div>
            <button
              onclick={handleClearRecentFiles}
              disabled={settings.recentFiles.length === 0}
              class="flex items-center gap-2 px-4 py-2 rounded-lg transition-colors disabled:opacity-40"
              style="background-color: var(--nord11); color: var(--nord6);"
            >
              <Trash2 size={16} />
              <span class="text-sm">Clear</span>
            </button>
          </div>
        </div>
      </div>

    {:else if activeSection === 'storage'}
      <!-- Storage Section -->
      <div class="max-w-2xl">
        <h2 class="text-lg font-medium mb-1" style="color: var(--nord6);">Storage</h2>
        <p class="text-sm opacity-60 mb-6">Manage cached data and temporary files.</p>

        <div class="space-y-4">
          <!-- Clear Cache -->
          <div
            class="flex items-center justify-between px-4 py-4 rounded-xl"
            style="background-color: var(--nord1); border: 1px solid var(--nord3);"
          >
            <div>
              <p class="text-sm font-medium">Clear Cache</p>
              <p class="text-xs opacity-60">Remove cached thumbnails and temporary data</p>
            </div>
            <button
              onclick={handleClearCache}
              class="flex items-center gap-2 px-4 py-2 rounded-lg transition-colors hover:opacity-80"
              style="background-color: var(--nord2); color: var(--nord6);"
            >
              <HardDrive size={16} />
              <span class="text-sm">Clear Cache</span>
            </button>
          </div>
        </div>
      </div>
    {/if}
  </div>
</div>
