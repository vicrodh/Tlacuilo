/**
 * Thumbnail generation utilities for the application.
 * Provides consistent, memory-efficient thumbnail creation across all components.
 */

/** Default maximum dimension for thumbnails */
export const THUMBNAIL_MAX_SIZE = 200;

/** Default JPEG quality for thumbnails (0-1) */
export const THUMBNAIL_QUALITY = 0.7;

/**
 * Convert a Uint8Array to a base64 string efficiently using chunked processing.
 * Handles large files without stack overflow.
 */
export function arrayBufferToBase64(buffer: Uint8Array): string {
  let binary = '';
  const chunkSize = 8192;
  for (let i = 0; i < buffer.length; i += chunkSize) {
    const chunk = buffer.subarray(i, Math.min(i + chunkSize, buffer.length));
    binary += String.fromCharCode.apply(null, Array.from(chunk));
  }
  return btoa(binary);
}

/**
 * Get MIME type from file extension.
 */
export function getMimeType(ext: string): string {
  const normalized = ext.toLowerCase().replace('.', '');
  switch (normalized) {
    case 'jpg':
    case 'jpeg':
      return 'image/jpeg';
    case 'png':
      return 'image/png';
    case 'webp':
      return 'image/webp';
    case 'gif':
      return 'image/gif';
    case 'bmp':
      return 'image/bmp';
    case 'tiff':
    case 'tif':
      return 'image/tiff';
    default:
      return 'image/png';
  }
}

/**
 * Create a small thumbnail from a base64 data URL.
 * Resizes the image to fit within maxSize while maintaining aspect ratio.
 * Returns a compressed JPEG for optimal performance.
 *
 * @param base64DataUrl - Full data URL (data:image/...;base64,...)
 * @param maxSize - Maximum width or height in pixels (default: 200)
 * @param quality - JPEG quality 0-1 (default: 0.7)
 * @returns Promise resolving to thumbnail data URL
 */
export function createThumbnail(
  base64DataUrl: string,
  maxSize: number = THUMBNAIL_MAX_SIZE,
  quality: number = THUMBNAIL_QUALITY
): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new window.Image();

    img.onload = () => {
      // Calculate scaled dimensions maintaining aspect ratio
      let width = img.width;
      let height = img.height;

      if (width > height) {
        if (width > maxSize) {
          height = Math.round((height * maxSize) / width);
          width = maxSize;
        }
      } else {
        if (height > maxSize) {
          width = Math.round((width * maxSize) / height);
          height = maxSize;
        }
      }

      // Draw to canvas at reduced size
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;

      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('Could not get canvas context'));
        return;
      }

      ctx.drawImage(img, 0, 0, width, height);

      // Export as compressed JPEG for smaller size
      resolve(canvas.toDataURL('image/jpeg', quality));
    };

    img.onerror = () => reject(new Error('Failed to load image for thumbnail'));
    img.src = base64DataUrl;
  });
}

/**
 * Create a thumbnail from raw image bytes.
 * Convenience function that handles the full pipeline.
 *
 * @param buffer - Raw image bytes
 * @param extension - File extension (jpg, png, etc.)
 * @param maxSize - Maximum thumbnail dimension
 * @param quality - JPEG quality
 * @returns Promise resolving to thumbnail data URL
 */
export async function createThumbnailFromBuffer(
  buffer: Uint8Array,
  extension: string,
  maxSize: number = THUMBNAIL_MAX_SIZE,
  quality: number = THUMBNAIL_QUALITY
): Promise<string> {
  const mimeType = getMimeType(extension);
  const base64 = arrayBufferToBase64(buffer);
  const dataUrl = `data:${mimeType};base64,${base64}`;
  return createThumbnail(dataUrl, maxSize, quality);
}

/**
 * Load an image file and create a thumbnail.
 * Uses Tauri's fs plugin to read the file.
 *
 * @param path - File path
 * @param maxSize - Maximum thumbnail dimension
 * @param quality - JPEG quality
 * @returns Promise resolving to thumbnail data URL
 */
export async function loadImageThumbnail(
  path: string,
  maxSize: number = THUMBNAIL_MAX_SIZE,
  quality: number = THUMBNAIL_QUALITY
): Promise<string> {
  const { readFile } = await import('@tauri-apps/plugin-fs');
  const contents = await readFile(path);
  const ext = path.split('.').pop() || 'png';
  return createThumbnailFromBuffer(contents, ext, maxSize, quality);
}
