/**
 * Persistent settings store using Tauri's store plugin.
 * Handles user preferences, favorites, and recent files.
 */

import { load, Store } from '@tauri-apps/plugin-store';

// Tool definition for the catalog
export interface Tool {
  id: string;
  label: string;
  icon: string;
  page: string;
  group?: string; // Parent group if it's a sub-tool
  description?: string;
}

// Recent file entry
export interface RecentFile {
  path: string;
  name: string;
  accessedAt: number; // timestamp
  module: string; // which module opened it
}

// Supported languages
export type Language = 'en' | 'es' | 'pt' | 'fr' | 'de';

export const LANGUAGES: { id: Language; label: string; native: string }[] = [
  { id: 'en', label: 'English', native: 'English' },
  { id: 'es', label: 'Spanish', native: 'Espanol' },
  { id: 'pt', label: 'Portuguese', native: 'Portugues' },
  { id: 'fr', label: 'French', native: 'Francais' },
  { id: 'de', label: 'German', native: 'Deutsch' },
];

// Author settings for annotation attribution
export interface AuthorSettings {
  name: string;
  surname: string;
  username: string;
  email: string;
  anonymousMode: boolean;
}

// Settings shape
export interface AppSettings {
  favorites: string[]; // tool IDs
  recentFiles: RecentFile[];
  recentFilesExpanded: boolean;
  showRecentFilesInHome: boolean;
  maxRecentFiles: number;
  theme: 'dark' | 'light' | 'system';
  language: Language;
  author: AuthorSettings;
}

// Default author settings
const DEFAULT_AUTHOR: AuthorSettings = {
  name: '',
  surname: '',
  username: '',
  email: '',
  anonymousMode: false,
};

// Default settings
const DEFAULT_SETTINGS: AppSettings = {
  favorites: ['viewer', 'merge', 'split', 'rotate', 'convert-images-to-pdf'],
  recentFiles: [],
  recentFilesExpanded: true,
  showRecentFilesInHome: true,
  maxRecentFiles: 10,
  theme: 'dark',
  language: 'en',
  author: { ...DEFAULT_AUTHOR },
};

// Complete tool catalog
export const TOOL_CATALOG: Tool[] = [
  // Viewer (first position)
  { id: 'viewer', label: 'Viewer', icon: 'BookOpen', page: 'viewer', description: 'View, annotate, and edit PDFs' },

  // Standalone tools
  { id: 'merge', label: 'Merge PDF', icon: 'Merge', page: 'merge', description: 'Combine multiple PDFs into one' },
  { id: 'split', label: 'Split PDF', icon: 'Scissors', page: 'split', description: 'Extract or separate pages' },
  { id: 'rotate', label: 'Rotate PDF', icon: 'RotateCw', page: 'rotate', description: 'Rotate pages in a PDF' },
  { id: 'compress', label: 'Compress PDF', icon: 'FileArchive', page: 'compress', description: 'Reduce PDF file size' },
  { id: 'ocr', label: 'OCR', icon: 'ScanText', page: 'ocr', description: 'Extract text from scanned PDFs' },

  // Convert group
  { id: 'convert-images-to-pdf', label: 'Images to PDF', icon: 'Image', page: 'convert', group: 'convert', description: 'Convert images to PDF' },
  { id: 'convert-pdf-to-images', label: 'PDF to Images', icon: 'Images', page: 'export', group: 'convert', description: 'Export PDF pages as images' },
  { id: 'convert-docs-to-pdf', label: 'Documents to PDF', icon: 'FileText', page: 'convert-docs', group: 'convert', description: 'Convert Office documents to PDF' },
  { id: 'convert-pdf-to-docs', label: 'PDF to Documents', icon: 'FileOutput', page: 'export-docs', group: 'convert', description: 'Export PDF to Office formats' },

  // Protect group (future)
  { id: 'protect-encrypt', label: 'Encrypt PDF', icon: 'Lock', page: 'encrypt', group: 'protect', description: 'Password protect a PDF' },
  { id: 'protect-decrypt', label: 'Decrypt PDF', icon: 'Unlock', page: 'decrypt', group: 'protect', description: 'Remove password from PDF' },
  { id: 'protect-redact', label: 'Redact', icon: 'EyeOff', page: 'redact', group: 'protect', description: 'Permanently remove sensitive content' },

  // Annotate group (future)
  { id: 'annotate-watermark', label: 'Watermark', icon: 'Droplet', page: 'watermark', group: 'annotate', description: 'Add text or image watermark' },
  { id: 'annotate-page-numbers', label: 'Page Numbers', icon: 'Hash', page: 'page-numbers', group: 'annotate', description: 'Add page numbers' },
  { id: 'annotate-stamps', label: 'Stamps', icon: 'Stamp', page: 'stamps', group: 'annotate', description: 'Add stamps (Confidential, Approved, etc.)' },

  // Sign group (future)
  { id: 'sign-draw', label: 'Draw Signature', icon: 'PenTool', page: 'sign-draw', group: 'sign', description: 'Draw your signature' },
  { id: 'sign-upload', label: 'Upload Signature', icon: 'Upload', page: 'sign-upload', group: 'sign', description: 'Upload signature image' },
  { id: 'sign-certificate', label: 'Digital Certificate', icon: 'ShieldCheck', page: 'sign-cert', group: 'sign', description: 'Sign with digital certificate' },
];

// Tool groups for expandable menus
export const TOOL_GROUPS = {
  convert: { id: 'convert', label: 'Convert', icon: 'RefreshCw' },
  protect: { id: 'protect', label: 'Protect', icon: 'Shield' },
  annotate: { id: 'annotate', label: 'Annotate', icon: 'Pencil' },
  sign: { id: 'sign', label: 'Sign', icon: 'PenTool' },
};

// Store instance
let store: Store | null = null;

// Reactive state
let settings = $state<AppSettings>({ ...DEFAULT_SETTINGS });
let isLoaded = $state(false);

// Initialize the store
async function initStore(): Promise<void> {
  if (store) return;

  try {
    store = await load('settings.json');

    // Load each setting
    const favorites = await store.get<string[]>('favorites');
    const recentFiles = await store.get<RecentFile[]>('recentFiles');
    const recentFilesExpanded = await store.get<boolean>('recentFilesExpanded');
    const showRecentFilesInHome = await store.get<boolean>('showRecentFilesInHome');
    const maxRecentFiles = await store.get<number>('maxRecentFiles');
    const theme = await store.get<'dark' | 'light' | 'system'>('theme');
    const language = await store.get<Language>('language');
    const author = await store.get<AuthorSettings>('author');

    settings = {
      favorites: favorites ?? DEFAULT_SETTINGS.favorites,
      recentFiles: recentFiles ?? DEFAULT_SETTINGS.recentFiles,
      recentFilesExpanded: recentFilesExpanded ?? DEFAULT_SETTINGS.recentFilesExpanded,
      showRecentFilesInHome: showRecentFilesInHome ?? DEFAULT_SETTINGS.showRecentFilesInHome,
      maxRecentFiles: maxRecentFiles ?? DEFAULT_SETTINGS.maxRecentFiles,
      theme: theme ?? DEFAULT_SETTINGS.theme,
      language: language ?? DEFAULT_SETTINGS.language,
      author: author ?? { ...DEFAULT_AUTHOR },
    };

    isLoaded = true;
  } catch (err) {
    console.error('Failed to load settings:', err);
    settings = { ...DEFAULT_SETTINGS };
    isLoaded = true;
  }
}

// Save a setting
async function saveSetting<K extends keyof AppSettings>(key: K, value: AppSettings[K]): Promise<void> {
  if (!store) await initStore();
  if (!store) return;

  settings = { ...settings, [key]: value };
  await store.set(key, value);
  await store.save();
}

// Favorites management
export async function addFavorite(toolId: string): Promise<void> {
  if (!settings.favorites.includes(toolId)) {
    await saveSetting('favorites', [...settings.favorites, toolId]);
  }
}

export async function removeFavorite(toolId: string): Promise<void> {
  await saveSetting('favorites', settings.favorites.filter(id => id !== toolId));
}

export async function reorderFavorites(newOrder: string[]): Promise<void> {
  await saveSetting('favorites', newOrder);
}

export async function setFavorites(favorites: string[]): Promise<void> {
  await saveSetting('favorites', favorites);
}

// Recent files management
export async function addRecentFile(path: string, name: string, module: string): Promise<void> {
  const existing = settings.recentFiles.filter(f => f.path !== path);
  const newEntry: RecentFile = { path, name, accessedAt: Date.now(), module };
  const updated = [newEntry, ...existing].slice(0, settings.maxRecentFiles);
  await saveSetting('recentFiles', updated);
}

export async function removeRecentFile(path: string): Promise<void> {
  await saveSetting('recentFiles', settings.recentFiles.filter(f => f.path !== path));
}

export async function clearRecentFiles(): Promise<void> {
  await saveSetting('recentFiles', []);
}

export async function toggleRecentFilesExpanded(): Promise<void> {
  await saveSetting('recentFilesExpanded', !settings.recentFilesExpanded);
}

export async function setShowRecentFilesInHome(value: boolean): Promise<void> {
  await saveSetting('showRecentFilesInHome', value);
}

export async function setLanguage(language: Language): Promise<void> {
  await saveSetting('language', language);
}

export async function setTheme(theme: 'dark' | 'light' | 'system'): Promise<void> {
  await saveSetting('theme', theme);
}

// Author settings management
export async function setAuthor(author: AuthorSettings): Promise<void> {
  await saveSetting('author', author);
}

export async function updateAuthorField<K extends keyof AuthorSettings>(
  field: K,
  value: AuthorSettings[K]
): Promise<void> {
  const newAuthor = { ...settings.author, [field]: value };
  await saveSetting('author', newAuthor);
}

// Get author display string for annotations
export function getAuthorString(): string {
  const { name, surname, username, email, anonymousMode } = settings.author;

  if (anonymousMode) return 'Anonymous';

  // Prefer full name
  if (name || surname) {
    return `${name} ${surname}`.trim();
  }

  // Fall back to username
  if (username) return username;

  // Fall back to email
  if (email) return email;

  // No author info configured
  return '';
}

// Get settings (reactive)
export function getSettings() {
  // Initialize on first access
  if (!isLoaded && typeof window !== 'undefined') {
    initStore();
  }

  return {
    get favorites() { return settings.favorites; },
    get recentFiles() { return settings.recentFiles; },
    get recentFilesExpanded() { return settings.recentFilesExpanded; },
    get showRecentFilesInHome() { return settings.showRecentFilesInHome; },
    get maxRecentFiles() { return settings.maxRecentFiles; },
    get theme() { return settings.theme; },
    get language() { return settings.language; },
    get author() { return settings.author; },
    get isLoaded() { return isLoaded; },
  };
}

// Helper to get tool by ID
export function getToolById(id: string): Tool | undefined {
  return TOOL_CATALOG.find(t => t.id === id);
}

// Get tools by group
export function getToolsByGroup(groupId: string): Tool[] {
  return TOOL_CATALOG.filter(t => t.group === groupId);
}

// Get standalone tools (no group)
export function getStandaloneTools(): Tool[] {
  return TOOL_CATALOG.filter(t => !t.group);
}

// Get favorite tools as full Tool objects
export function getFavoriteTools(): Tool[] {
  return settings.favorites
    .map(id => getToolById(id))
    .filter((t): t is Tool => t !== undefined);
}
