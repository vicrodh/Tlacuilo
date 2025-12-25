/**
 * Signature and Initials vault store using Tauri's store plugin.
 * Stores user's saved graphical signatures and initials locally.
 */

import { load, Store } from '@tauri-apps/plugin-store';

// Category type for signatures vs initials
export type SignatureCategory = 'signature' | 'initial';

// Saved signature/initial entry
export interface SavedSignature {
  id: string;
  name: string;
  type: 'freehand' | 'image';
  category: SignatureCategory;
  dataUrl: string; // Full resolution PNG as data URL
  thumbnail: string; // Smaller version for list display
  createdAt: number;
  strokeColor?: string;
  strokeWidth?: number;
}

// Store instance
let store: Store | null = null;

// Reactive state
let signatures = $state<SavedSignature[]>([]);
let isLoaded = $state(false);

// Generate unique ID
function generateId(category: SignatureCategory): string {
  const prefix = category === 'initial' ? 'ini' : 'sig';
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

// Create thumbnail from data URL
function createThumbnail(dataUrl: string, maxSize: number = 100): Promise<string> {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        resolve(dataUrl);
        return;
      }

      // Calculate thumbnail dimensions maintaining aspect ratio
      let width = img.width;
      let height = img.height;
      if (width > height) {
        if (width > maxSize) {
          height = (height * maxSize) / width;
          width = maxSize;
        }
      } else {
        if (height > maxSize) {
          width = (width * maxSize) / height;
          height = maxSize;
        }
      }

      canvas.width = width;
      canvas.height = height;
      ctx.drawImage(img, 0, 0, width, height);
      resolve(canvas.toDataURL('image/png'));
    };
    img.onerror = () => resolve(dataUrl);
    img.src = dataUrl;
  });
}

// Initialize the store
async function initStore(): Promise<void> {
  if (store) return;

  try {
    store = await load('signatures.json');
    const saved = await store.get<SavedSignature[]>('signatures');

    // Migrate old entries that don't have category field
    if (saved) {
      signatures = saved.map(s => ({
        ...s,
        category: s.category ?? 'signature' as SignatureCategory,
      }));
      // Save migrated data if any entries were missing category
      if (saved.some(s => !s.category)) {
        await saveToStore();
      }
    } else {
      signatures = [];
    }

    isLoaded = true;
  } catch (err) {
    console.error('Failed to load signatures:', err);
    signatures = [];
    isLoaded = true;
  }
}

// Save signatures to store
async function saveToStore(): Promise<void> {
  if (!store) await initStore();
  if (!store) return;

  await store.set('signatures', signatures);
  await store.save();
}

// Add a new signature or initial
export async function addSignature(
  dataUrl: string,
  name: string,
  type: 'freehand' | 'image',
  strokeColor?: string,
  strokeWidth?: number,
  category: SignatureCategory = 'signature'
): Promise<SavedSignature> {
  if (!store) await initStore();

  const thumbnail = await createThumbnail(dataUrl);
  const defaultName = category === 'initial'
    ? `Initial ${signatures.filter(s => s.category === 'initial').length + 1}`
    : `Signature ${signatures.filter(s => s.category === 'signature').length + 1}`;

  const signature: SavedSignature = {
    id: generateId(category),
    name: name || defaultName,
    type,
    category,
    dataUrl,
    thumbnail,
    createdAt: Date.now(),
    strokeColor,
    strokeWidth,
  };

  signatures = [signature, ...signatures];
  await saveToStore();
  return signature;
}

// Convenience function to add an initial
export async function addInitial(
  dataUrl: string,
  name: string,
  type: 'freehand' | 'image',
  strokeColor?: string,
  strokeWidth?: number
): Promise<SavedSignature> {
  return addSignature(dataUrl, name, type, strokeColor, strokeWidth, 'initial');
}

// Remove a signature by ID
export async function removeSignature(id: string): Promise<void> {
  if (!store) await initStore();
  signatures = signatures.filter(s => s.id !== id);
  await saveToStore();
}

// Rename a signature
export async function renameSignature(id: string, newName: string): Promise<void> {
  if (!store) await initStore();
  signatures = signatures.map(s =>
    s.id === id ? { ...s, name: newName } : s
  );
  await saveToStore();
}

// Get a signature by ID
export function getSignatureById(id: string): SavedSignature | undefined {
  return signatures.find(s => s.id === id);
}

// Export a signature for use
export function exportSignature(id: string): { dataUrl: string; name: string } | null {
  const sig = getSignatureById(id);
  if (!sig) return null;
  return { dataUrl: sig.dataUrl, name: sig.name };
}

// Clear all signatures (with confirmation in UI)
export async function clearAllSignatures(): Promise<void> {
  if (!store) await initStore();
  signatures = [];
  await saveToStore();
}

// Get signatures store (reactive)
export function getSignaturesStore() {
  // Initialize on first access
  if (!isLoaded && typeof window !== 'undefined') {
    initStore();
  }

  return {
    get all() { return signatures; },
    get signatures() { return signatures.filter(s => s.category === 'signature'); },
    get initials() { return signatures.filter(s => s.category === 'initial'); },
    get isLoaded() { return isLoaded; },
    get count() { return signatures.length; },
    get signatureCount() { return signatures.filter(s => s.category === 'signature').length; },
    get initialCount() { return signatures.filter(s => s.category === 'initial').length; },
  };
}

// Re-export for convenience
export { initStore as initSignaturesStore };
