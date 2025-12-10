import * as pdfjsLib from 'pdfjs-dist';

// Configure worker for Vite/Tauri: use URL relative to this module.
(pdfjsLib as any).GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).toString();

export async function renderFirstPageThumbnail(filePath: string, maxWidth = 220): Promise<string> {
  const isAbsolute = filePath.startsWith('/');
  const url = isAbsolute ? `file://${filePath}` : filePath;
  const loadingTask = (pdfjsLib as any).getDocument({
    url,
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
