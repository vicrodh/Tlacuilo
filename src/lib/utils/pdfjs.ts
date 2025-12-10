import * as pdfjsLib from 'pdfjs-dist';

// Configure worker for Vite/Tauri: use URL relative to this module.
(pdfjsLib as any).GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).toString();

export async function renderFirstPageThumbnail(filePath: string, maxWidth = 220): Promise<string> {
  // Read file via fetch(file://...) in Tauri context
  const url = filePath.startsWith('file://') ? filePath : `file://${filePath}`;
  const res = await fetch(url);
  const buf = await res.arrayBuffer();
  const data = new Uint8Array(buf);
  const loadingTask = (pdfjsLib as any).getDocument({
    data,
    disableRange: true,
    disableAutoFetch: true
  });
  const pdf = await loadingTask.promise;
  const page = await pdf.getPage(1);
  const viewport = page.getViewport({ scale: 1 });
  const scale = maxWidth / viewport.width;
  const scaledViewport = page.getViewport({ scale });

  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Canvas context not available');

  canvas.height = scaledViewport.height;
  canvas.width = scaledViewport.width;

  await page
    .render({
      canvasContext: context,
      viewport: scaledViewport,
      canvas
    })
    .promise;
  const dataUrl = canvas.toDataURL('image/png');

  await pdf.destroy();
  return dataUrl;
}

export async function renderAllPageThumbnails(filePath: string, maxWidth = 160): Promise<string[]> {
  const url = filePath.startsWith('file://') ? filePath : `file://${filePath}`;
  const res = await fetch(url);
  const buf = await res.arrayBuffer();
  const data = new Uint8Array(buf);
  const loadingTask = (pdfjsLib as any).getDocument({
    data,
    disableRange: true,
    disableAutoFetch: true
  });
  const pdf = await loadingTask.promise;
  const thumbs: string[] = [];

  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const viewport = page.getViewport({ scale: 1 });
    const scale = maxWidth / viewport.width;
    const scaledViewport = page.getViewport({ scale });
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) continue;
    canvas.height = scaledViewport.height;
    canvas.width = scaledViewport.width;
    await page.render({ canvasContext: ctx, viewport: scaledViewport, canvas }).promise;
    thumbs.push(canvas.toDataURL('image/png'));
  }

  await pdf.destroy();
  return thumbs;
}

export async function getPageCount(filePath: string): Promise<number> {
  const url = filePath.startsWith('file://') ? filePath : `file://${filePath}`;
  const res = await fetch(url);
  const buf = await res.arrayBuffer();
  const data = new Uint8Array(buf);
  const loadingTask = (pdfjsLib as any).getDocument({
    data,
    disableRange: true,
    disableAutoFetch: true
  });
  const pdf = await loadingTask.promise;
  const numPages = pdf.numPages;
  await pdf.destroy();
  return numPages;
}

export async function renderPageForViewer(
  filePath: string,
  pageNumber: number,
  maxWidth = 800
): Promise<string> {
  const url = filePath.startsWith('file://') ? filePath : `file://${filePath}`;
  const res = await fetch(url);
  const buf = await res.arrayBuffer();
  const data = new Uint8Array(buf);
  const loadingTask = (pdfjsLib as any).getDocument({
    data,
    disableRange: true,
    disableAutoFetch: true
  });
  const pdf = await loadingTask.promise;

  if (pageNumber < 1 || pageNumber > pdf.numPages) {
    await pdf.destroy();
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
    canvas
  }).promise;

  const dataUrl = canvas.toDataURL('image/png');
  await pdf.destroy();
  return dataUrl;
}
