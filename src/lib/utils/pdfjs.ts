/**
 * PDF utilities using pdfjs-dist with Tauri fs plugin.
 * This module is reusable across Merge, Split, Rotate, and Edit features.
 */

import * as pdfjsLib from 'pdfjs-dist';
import { readFile } from '@tauri-apps/plugin-fs';

// Configure worker for Vite/Tauri
(pdfjsLib as any).GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).toString();

// Cache for loaded PDF documents to avoid re-reading files
const pdfCache = new Map<string, any>();

/**
 * Load a PDF document from a file path using Tauri's fs plugin.
 * Results are cached for performance.
 */
async function loadPdf(filePath: string): Promise<any> {
  if (pdfCache.has(filePath)) {
    return pdfCache.get(filePath);
  }

  try {
    // Read file using Tauri's fs plugin
    const data = await readFile(filePath);

    const loadingTask = (pdfjsLib as any).getDocument({
      data,
      disableRange: true,
      disableAutoFetch: true,
    });

    const pdf = await loadingTask.promise;
    pdfCache.set(filePath, pdf);
    return pdf;
  } catch (err) {
    console.error(`Failed to load PDF: ${filePath}`, err);
    throw new Error(`Could not load PDF: ${err}`);
  }
}

/**
 * Clear a specific PDF from cache (call when file is removed from workspace)
 */
export function clearPdfCache(filePath: string): void {
  const pdf = pdfCache.get(filePath);
  if (pdf) {
    pdf.destroy();
    pdfCache.delete(filePath);
  }
}

/**
 * Clear all cached PDFs
 */
export function clearAllPdfCache(): void {
  for (const [path, pdf] of pdfCache) {
    pdf.destroy();
  }
  pdfCache.clear();
}

/**
 * Get the number of pages in a PDF file.
 * This is the foundation for page-based operations.
 */
export async function getPageCount(filePath: string): Promise<number> {
  const pdf = await loadPdf(filePath);
  return pdf.numPages;
}

/**
 * Information about a PDF file
 */
export interface PDFInfo {
  pageCount: number;
  filePath: string;
}

/**
 * Get basic info about a PDF file
 */
export async function getPdfInfo(filePath: string): Promise<PDFInfo> {
  const pdf = await loadPdf(filePath);
  return {
    pageCount: pdf.numPages,
    filePath,
  };
}

/**
 * Render a specific page to a data URL (base64 PNG image).
 * @param filePath - Path to the PDF file
 * @param pageNumber - 1-indexed page number
 * @param maxWidth - Maximum width for the rendered image
 */
export async function renderPage(
  filePath: string,
  pageNumber: number,
  maxWidth = 200
): Promise<string> {
  const pdf = await loadPdf(filePath);

  if (pageNumber < 1 || pageNumber > pdf.numPages) {
    throw new Error(`Invalid page number: ${pageNumber}. PDF has ${pdf.numPages} pages.`);
  }

  const page = await pdf.getPage(pageNumber);
  const viewport = page.getViewport({ scale: 1 });
  const scale = maxWidth / viewport.width;
  const scaledViewport = page.getViewport({ scale });

  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Canvas context not available');

  canvas.height = scaledViewport.height;
  canvas.width = scaledViewport.width;

  await page.render({
    canvasContext: context,
    viewport: scaledViewport,
  }).promise;

  // Use JPEG with 0.7 quality for smaller thumbnails
  return canvas.toDataURL('image/jpeg', 0.7);
}

/**
 * Render the first page as a thumbnail (convenience function)
 */
export async function renderFirstPageThumbnail(
  filePath: string,
  maxWidth = 160
): Promise<string> {
  return renderPage(filePath, 1, maxWidth);
}

/**
 * Render all pages of a PDF as thumbnails
 * @param filePath - Path to the PDF file
 * @param maxWidth - Maximum width for thumbnails
 * @param onProgress - Optional callback for progress updates
 */
export async function renderAllPages(
  filePath: string,
  maxWidth = 120,
  onProgress?: (current: number, total: number) => void
): Promise<string[]> {
  const pdf = await loadPdf(filePath);
  const thumbnails: string[] = [];

  for (let i = 1; i <= pdf.numPages; i++) {
    const thumbnail = await renderPage(filePath, i, maxWidth);
    thumbnails.push(thumbnail);
    onProgress?.(i, pdf.numPages);
  }

  return thumbnails;
}

/**
 * Page data structure used across the application
 */
export interface PageData {
  id: string;
  fileId: string;
  filePath: string;
  fileName: string;
  pageNumber: number;
  thumbnail: string;
}

/**
 * Load all pages from a PDF file with their thumbnails.
 * This is the main function for initializing page-based views.
 */
export async function loadPdfPages(
  filePath: string,
  fileId: string,
  fileName: string,
  maxWidth = 120,
  onProgress?: (current: number, total: number) => void
): Promise<PageData[]> {
  const pdf = await loadPdf(filePath);
  const pages: PageData[] = [];

  for (let i = 1; i <= pdf.numPages; i++) {
    const thumbnail = await renderPage(filePath, i, maxWidth);
    pages.push({
      id: `${fileId}-page-${i}`,
      fileId,
      filePath,
      fileName,
      pageNumber: i,
      thumbnail,
    });
    onProgress?.(i, pdf.numPages);
  }

  return pages;
}

/**
 * Render a page for the main viewer (larger size)
 */
export async function renderPageForViewer(
  filePath: string,
  pageNumber: number,
  maxWidth = 800
): Promise<string> {
  return renderPage(filePath, pageNumber, maxWidth);
}

// Legacy exports for backward compatibility
export { renderAllPages as renderAllPageThumbnails };
