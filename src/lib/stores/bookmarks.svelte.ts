/**
 * Persistent bookmarks store using Tauri's store plugin.
 * Handles user-created bookmarks for PDF documents.
 */

import { load, Store } from '@tauri-apps/plugin-store';

// User bookmark entry
export interface UserBookmark {
  id: string;
  page: number;
  y?: number; // Optional normalized Y position (0-1)
  title: string;
  createdAt: number; // timestamp
}

// Bookmarks storage shape - keyed by file path
export interface BookmarksData {
  [filePath: string]: UserBookmark[];
}

// Store instance
let store: Store | null = null;

// Reactive state
let bookmarksData = $state<BookmarksData>({});
let isLoaded = $state(false);

// Initialize the store
async function initStore(): Promise<void> {
  if (store) return;

  try {
    store = await load('bookmarks.json');
    const data = await store.get<BookmarksData>('bookmarks');
    bookmarksData = data ?? {};
    isLoaded = true;
  } catch (err) {
    console.error('[BookmarksStore] Failed to load bookmarks:', err);
    bookmarksData = {};
    isLoaded = true;
  }
}

// Save bookmarks for a specific file
async function saveBookmarks(filePath: string, bookmarks: UserBookmark[]): Promise<void> {
  if (!store) await initStore();
  if (!store) return;

  bookmarksData = { ...bookmarksData, [filePath]: bookmarks };
  await store.set('bookmarks', bookmarksData);
  await store.save();
}

// Generate unique ID
function generateId(): string {
  return `bm-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

// Get bookmarks for a file (reactive)
export function getBookmarksForFile(filePath: string): UserBookmark[] {
  if (!isLoaded && typeof window !== 'undefined') {
    initStore();
  }
  return bookmarksData[filePath] ?? [];
}

// Add a bookmark
export async function addBookmark(
  filePath: string,
  page: number,
  title?: string,
  y?: number
): Promise<UserBookmark> {
  if (!store) await initStore();

  const bookmark: UserBookmark = {
    id: generateId(),
    page,
    y,
    title: title || `Page ${page}`,
    createdAt: Date.now(),
  };

  const existing = bookmarksData[filePath] ?? [];
  // Insert sorted by page
  const updated = [...existing, bookmark].sort((a, b) => {
    if (a.page !== b.page) return a.page - b.page;
    return (a.y ?? 0) - (b.y ?? 0);
  });

  await saveBookmarks(filePath, updated);
  return bookmark;
}

// Update a bookmark
export async function updateBookmark(
  filePath: string,
  bookmarkId: string,
  updates: Partial<Pick<UserBookmark, 'title' | 'page' | 'y'>>
): Promise<void> {
  if (!store) await initStore();

  const existing = bookmarksData[filePath] ?? [];
  const updated = existing.map(bm =>
    bm.id === bookmarkId ? { ...bm, ...updates } : bm
  );

  // Re-sort if page changed
  if (updates.page !== undefined) {
    updated.sort((a, b) => {
      if (a.page !== b.page) return a.page - b.page;
      return (a.y ?? 0) - (b.y ?? 0);
    });
  }

  await saveBookmarks(filePath, updated);
}

// Delete a bookmark
export async function deleteBookmark(filePath: string, bookmarkId: string): Promise<void> {
  if (!store) await initStore();

  const existing = bookmarksData[filePath] ?? [];
  const updated = existing.filter(bm => bm.id !== bookmarkId);

  await saveBookmarks(filePath, updated);
}

// Check if a page has a bookmark
export function hasBookmarkOnPage(filePath: string, page: number): boolean {
  const bookmarks = bookmarksData[filePath] ?? [];
  return bookmarks.some(bm => bm.page === page);
}

// Get bookmark count for a file
export function getBookmarkCount(filePath: string): number {
  return (bookmarksData[filePath] ?? []).length;
}

// Ensure store is initialized
export async function ensureLoaded(): Promise<void> {
  if (!isLoaded) {
    await initStore();
  }
}

// Get the reactive loaded state
export function getIsLoaded(): boolean {
  return isLoaded;
}
