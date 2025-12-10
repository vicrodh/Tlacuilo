import * as pdfjsLib from 'pdfjs-dist';
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs';

// Configure worker
(pdfjsLib as any).GlobalWorkerOptions.workerSrc = workerSrc as unknown as string;

export async function renderFirstPageThumbnail(filePath: string, maxWidth = 220): Promise<string> {
  const loadingTask = (pdfjsLib as any).getDocument({ url: filePath, disableRange: true, disableAutoFetch: true });
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

  await page.render({ canvasContext: context, viewport: scaledViewport, canvas }).promise;
  const dataUrl = canvas.toDataURL('image/png');

  await pdf.destroy();
  return dataUrl;
}
