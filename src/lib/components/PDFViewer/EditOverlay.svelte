<script lang="ts">
  /**
   * EditOverlay - Renders and handles content editing operations
   *
   * This overlay allows users to:
   * - Draw new text boxes, images, and shapes
   * - Select and move existing edit operations
   * - Resize operations using handles
   * - Edit text content inline
   * - Click existing PDF text blocks to edit them
   */

  import { X, Move, Type, Check } from 'lucide-svelte';
  import { invoke } from '@tauri-apps/api/core';
  import { onMount } from 'svelte';
  import type {
    EditsStore,
    EditorOp,
    NormalizedRect,
    InsertTextOp,
    InsertImageOp,
    DrawShapeOp,
    ReplaceTextOp,
    OriginalLineInfo,
  } from '$lib/stores/edits.svelte';

  // Types for text blocks with font info from Tauri
  interface SpanInfo {
    text: string;
    font: string;
    size: number;
    color: string;
    bold: boolean;
    italic: boolean;
    serif?: boolean;  // From PyMuPDF font flags (bit 2)
    mono?: boolean;   // From PyMuPDF font flags (bit 3)
    rect: NormalizedRect;
  }

  interface TextLineInfo {
    text: string;
    rect: NormalizedRect;
    spans: SpanInfo[];
    rotation?: number; // Rotation angle in degrees from line direction
  }

  interface TextBlockInfo {
    rect: NormalizedRect;
    lines: TextLineInfo[];
    text: string;
    dominantFont: string | null;
    dominantSize: number | null;
    dominantColor: string | null;
    isSerif?: boolean;   // Aggregated: >50% of chars are serif
    isMono?: boolean;    // Aggregated: >50% of chars are monospace
    rotation?: number;   // Average rotation across lines
  }

  interface PageTextContent {
    success: boolean;
    page: number;
    blocks: TextBlockInfo[];
    pageWidth: number;
    pageHeight: number;
    error?: string;
  }

  interface Props {
    store: EditsStore;
    page: number;
    pageWidth: number;      // Rendered page width in pixels
    pageHeight: number;     // Rendered page height in pixels
    pdfPageWidth?: number;  // Original PDF page width in points
    pdfPageHeight?: number; // Original PDF page height in points
    pdfPath: string;
    scale?: number;
    interactive?: boolean;
    hasPreview?: boolean; // When true, hide operation visuals (preview image shows them)
    refreshKey?: number;  // Increment to force re-fetch text blocks
    hideBlockHighlights?: boolean;  // Hide clickable text block/line highlights (Preview mode)
  }

  let { store, page, pageWidth, pageHeight, pdfPageWidth, pdfPageHeight, pdfPath, scale = 1, interactive = true, hasPreview = false, refreshKey = 0, hideBlockHighlights = false }: Props = $props();

  // Calculate the scale factor from PDF points to rendered pixels
  // PDF uses points (1/72 inch), rendered at specific DPI
  const pdfToPixelScale = $derived(pdfPageWidth ? pageWidth / pdfPageWidth : 150 / 72);

  // Font size scale factor to match PyMuPDF built-in font metrics
  // Must match the scale factor in backend/pdf_edit.py
  const FONT_SIZE_SCALE = 1.08;

  /**
   * Calculate the correct font size for display.
   * For OCR fonts (GlyphLessFont), we calculate from bounding box height
   * because the OCR text layer has different metrics than the visual text.
   */
  function calculateDisplayFontSize(
    reportedFontSize: number,
    rectHeight: number, // normalized (0-1)
    text: string,
    fontFamily: string
  ): number {
    // Calculate actual height in PDF points
    const rectHeightPts = rectHeight * (pdfPageHeight || 792);

    // Count actual text lines
    const lines = text.split('\n').filter(l => l.trim());
    const numLines = Math.max(1, lines.length);

    // Calculate font size from bounding box
    // For single line: font size ≈ rect height (with small padding factor)
    // For multi-line: distribute evenly
    const calculatedSize = rectHeightPts / (numLines * 1.15);

    // Detect OCR fonts
    const isOcrFont = fontFamily.toLowerCase().includes('glyphless') ||
                      fontFamily.toLowerCase().includes('ocr');

    if (isOcrFont) {
      // For OCR fonts, always use calculated size
      return calculatedSize;
    } else {
      // For regular fonts, use the larger of scaled vs calculated
      const scaledSize = reportedFontSize * FONT_SIZE_SCALE;
      return Math.max(scaledSize, calculatedSize * 0.95);
    }
  }

  /**
   * Calculate line-height ratio from block metrics.
   * This ensures the textarea matches OCR line spacing.
   */
  function calculateLineHeight(block: TextBlockInfo | null, numLines: number): number {
    if (!block || numLines <= 1) return 1.15; // Single line: tight spacing

    // For multi-line blocks, calculate actual line spacing
    // block.rect.height contains all lines, so spacing = height / numLines
    const blockHeightPts = block.rect.height * (pdfPageHeight || 792);
    const avgLineHeight = blockHeightPts / numLines;

    // Calculate dominant font size
    const fontSize = block.dominantSize || 12;

    // Line height ratio = line spacing / font size
    const ratio = avgLineHeight / fontSize;

    // Clamp to reasonable values (1.0 - 2.0)
    return Math.max(1.0, Math.min(2.0, ratio));
  }

  let overlayElement: HTMLDivElement;

  // Drawing state
  let isDrawing = $state(false);
  let drawStart = $state<{ x: number; y: number } | null>(null);
  let drawEnd = $state<{ x: number; y: number } | null>(null);

  // Dragging state
  let isDragging = $state(false);
  let dragOffset = $state<{ x: number; y: number } | null>(null);

  // Editing text state
  let editingTextId = $state<string | null>(null);
  let editingTextContent = $state('');

  // Undo history for text editing (Ctrl+Z support)
  let textUndoHistory = $state<string[]>([]);
  let textRedoHistory = $state<string[]>([]);
  const MAX_UNDO_HISTORY = 50;

  // Track text changes for undo
  function pushTextUndo(text: string) {
    textUndoHistory = [...textUndoHistory.slice(-MAX_UNDO_HISTORY + 1), text];
    textRedoHistory = []; // Clear redo on new change
  }

  function undoText(): boolean {
    if (textUndoHistory.length === 0) return false;
    const current = editingTextContent;
    const previous = textUndoHistory[textUndoHistory.length - 1];
    textUndoHistory = textUndoHistory.slice(0, -1);
    textRedoHistory = [...textRedoHistory, current];
    editingTextContent = previous;
    return true;
  }

  function redoText(): boolean {
    if (textRedoHistory.length === 0) return false;
    const current = editingTextContent;
    const next = textRedoHistory[textRedoHistory.length - 1];
    textRedoHistory = textRedoHistory.slice(0, -1);
    textUndoHistory = [...textUndoHistory, current];
    editingTextContent = next;
    return true;
  }

  // PDF text blocks (existing text in the document)
  let textBlocks = $state<TextBlockInfo[]>([]);
  let isLoadingBlocks = $state(false);
  let showTextBlocks = $state(true); // Toggle to show/hide existing text highlights

  // Operations for this page
  const pageOps = $derived(store.getOpsForPage(page));

  // Fetch text blocks with font info from the PDF
  async function fetchTextBlocks() {
    if (!pdfPath) return;

    isLoadingBlocks = true;
    try {
      // Use font-aware command to get detailed font info
      // Note: Tauri command uses "input" parameter, not "path"
      const result = await invoke<PageTextContent>('pdf_get_text_blocks_with_fonts', {
        input: pdfPath,
        page: page - 1, // 0-indexed for backend
      });
      if (result.success) {
        textBlocks = result.blocks;
      } else {
        console.error('[EditOverlay] Failed to fetch text blocks:', result.error);
        textBlocks = [];
      }
    } catch (e) {
      console.error('[EditOverlay] Failed to fetch text blocks:', e);
      textBlocks = [];
    } finally {
      isLoadingBlocks = false;
    }
  }

  // Get combined text from a block
  function getBlockText(block: TextBlockInfo): string {
    // Use the pre-extracted text if available
    if (block.text) return block.text;
    // Fallback: reconstruct from lines
    return block.lines.map(line =>
      line.spans ? line.spans.map(s => s.text).join('') : line.text
    ).join('\n');
  }

  // Map PDF font names to CSS-friendly font families
  // PRIORITY: Font name detection > isSerif flag > isMono flag
  // (PyMuPDF mono flag is unreliable for OCR documents)
  function mapFontFamily(pdfFont: string | null, isSerif?: boolean, isMono?: boolean): string {
    // Clean font name (remove subset prefix like "ABCDEF+")
    const cleanFont = pdfFont ? pdfFont.replace(/^[A-Z]{6}\+/, '') : null;
    const fontLower = pdfFont?.toLowerCase() ?? '';

    // STEP 1: Check font name first (most reliable, even for OCR)
    // Known monospace fonts - only trust mono if font name confirms it
    const isMonoByName = fontLower.includes('courier') ||
                         fontLower.includes('consol') ||
                         fontLower.includes('mono') ||
                         fontLower.includes('fixed');

    if (isMonoByName) {
      return cleanFont
        ? `"${cleanFont}", "Courier New", Courier, monospace`
        : '"Courier New", Courier, monospace';
    }

    // Known serif fonts by name
    const isSerifByName = fontLower.includes('times') ||
                          fontLower.includes('tiro') ||
                          fontLower.includes('georgia') ||
                          fontLower.includes('palatino') ||
                          fontLower.includes('garamond') ||
                          fontLower.includes('cambria') ||
                          fontLower.includes('roman') ||
                          (fontLower.includes('serif') && !fontLower.includes('sans'));

    if (isSerifByName) {
      return cleanFont
        ? `"${cleanFont}", "Times New Roman", Times, Georgia, serif`
        : '"Times New Roman", Times, Georgia, serif';
    }

    // Known sans-serif fonts by name
    const isSansByName = fontLower.includes('arial') ||
                         fontLower.includes('helv') ||
                         fontLower.includes('helvetica') ||
                         fontLower.includes('verdana') ||
                         fontLower.includes('calibri') ||
                         fontLower.includes('sans') ||
                         fontLower.includes('gothic');

    if (isSansByName) {
      return cleanFont
        ? `"${cleanFont}", Arial, Helvetica, sans-serif`
        : 'Arial, Helvetica, sans-serif';
    }

    // STEP 2: Fall back to PyMuPDF flags (but prioritize serif over mono)
    // For OCR documents, serif flag is more reliable than mono flag
    if (isSerif === true) {
      return cleanFont
        ? `"${cleanFont}", "Times New Roman", Times, Georgia, serif`
        : '"Times New Roman", Times, Georgia, serif';
    }

    // Only use mono flag if serif is explicitly false AND mono is true
    // (reduces false positives from OCR)
    if (isMono === true && isSerif === false) {
      return cleanFont
        ? `"${cleanFont}", "Courier New", Courier, monospace`
        : '"Courier New", Courier, monospace';
    }

    // isSerif === false and isMono === false -> sans-serif
    if (isSerif === false) {
      return cleanFont
        ? `"${cleanFont}", Arial, Helvetica, sans-serif`
        : 'Arial, Helvetica, sans-serif';
    }

    // STEP 3: No reliable info - use font name or default
    if (!pdfFont) return '"Times New Roman", Times, Georgia, serif'; // Default to serif for documents

    // OCRmyPDF invisible text layer font - use system sans-serif
    if (fontLower.includes('glyphless') || fontLower === 'none' || fontLower === '[none]') {
      return 'Arial, Helvetica, sans-serif';
    }

    // Exact "sans" font (common in OCR'd PDFs) - use sans-serif stack
    if (fontLower === 'sans' || fontLower === 'sans-serif') {
      return 'Arial, Helvetica, sans-serif';
    }

    // Sans-serif fonts
    if (fontLower.includes('arial')) {
      return `"${cleanFont}", Arial, Helvetica, sans-serif`;
    }
    if (fontLower.includes('helv') || fontLower.includes('helvetica')) {
      return `"${cleanFont}", Helvetica, Arial, sans-serif`;
    }
    if (fontLower.includes('calibri')) {
      return `"${cleanFont}", Calibri, Arial, sans-serif`;
    }
    if (fontLower.includes('verdana')) {
      return `"${cleanFont}", Verdana, Geneva, sans-serif`;
    }
    if (fontLower.includes('tahoma')) {
      return `"${cleanFont}", Tahoma, Geneva, sans-serif`;
    }
    if (fontLower.includes('trebuchet')) {
      return `"${cleanFont}", "Trebuchet MS", sans-serif`;
    }

    // Serif fonts
    if (fontLower.includes('times') || fontLower.includes('tiro')) {
      return `"${cleanFont}", "Times New Roman", Times, serif`;
    }
    if (fontLower.includes('georgia')) {
      return `"${cleanFont}", Georgia, serif`;
    }
    if (fontLower.includes('palatino')) {
      return `"${cleanFont}", "Palatino Linotype", "Book Antiqua", serif`;
    }
    if (fontLower.includes('garamond')) {
      return `"${cleanFont}", Garamond, serif`;
    }
    if (fontLower.includes('cambria')) {
      return `"${cleanFont}", Cambria, Georgia, serif`;
    }

    // Monospace fonts
    if (fontLower.includes('courier')) {
      return `"${cleanFont}", "Courier New", Courier, monospace`;
    }
    if (fontLower.includes('consol')) {
      return `"${cleanFont}", Consolas, "Courier New", monospace`;
    }

    // OCR-specific fonts (Tesseract/OCRmyPDF)
    if (fontLower.includes('freeserif')) {
      return `"${cleanFont}", "Times New Roman", Times, serif`;
    }
    if (fontLower.includes('freesans')) {
      return `"${cleanFont}", Arial, Helvetica, sans-serif`;
    }
    if (fontLower.includes('freemono')) {
      return `"${cleanFont}", "Courier New", Courier, monospace`;
    }
    if (fontLower.includes('dejavu')) {
      if (fontLower.includes('serif') && !fontLower.includes('sans')) {
        return `"${cleanFont}", "DejaVu Serif", "Times New Roman", serif`;
      }
      if (fontLower.includes('mono')) {
        return `"${cleanFont}", "DejaVu Sans Mono", "Courier New", monospace`;
      }
      return `"${cleanFont}", "DejaVu Sans", Arial, sans-serif`;
    }
    if (fontLower.includes('liberation')) {
      if (fontLower.includes('serif') && !fontLower.includes('sans')) {
        return `"${cleanFont}", "Liberation Serif", "Times New Roman", serif`;
      }
      if (fontLower.includes('mono')) {
        return `"${cleanFont}", "Liberation Mono", "Courier New", monospace`;
      }
      return `"${cleanFont}", "Liberation Sans", Arial, sans-serif`;
    }
    if (fontLower.includes('noto')) {
      if (fontLower.includes('serif') && !fontLower.includes('sans')) {
        return `"${cleanFont}", "Noto Serif", "Times New Roman", serif`;
      }
      if (fontLower.includes('mono')) {
        return `"${cleanFont}", "Noto Mono", "Courier New", monospace`;
      }
      return `"${cleanFont}", "Noto Sans", Arial, sans-serif`;
    }

    // Detect font category from name
    if (fontLower.includes('sans')) {
      return `"${cleanFont}", Arial, Helvetica, sans-serif`;
    }
    if (fontLower.includes('serif')) {
      return `"${cleanFont}", "Times New Roman", Times, serif`;
    }
    if (fontLower.includes('mono')) {
      return `"${cleanFont}", "Courier New", Courier, monospace`;
    }
    if (fontLower.includes('gothic')) {
      return `"${cleanFont}", Arial, sans-serif`;
    }
    if (fontLower.includes('roman')) {
      return `"${cleanFont}", "Times New Roman", serif`;
    }

    // Default: try the original font first, then fall back to sans-serif
    return `"${cleanFont}", Arial, Helvetica, sans-serif`;
  }

  // Check if block has bold text
  function hasBlockBold(block: TextBlockInfo): boolean {
    for (const line of block.lines) {
      if (line.spans) {
        for (const span of line.spans) {
          if (span.bold && span.text.trim()) return true;
        }
      }
    }
    return false;
  }

  // Check if block has italic text
  function hasBlockItalic(block: TextBlockInfo): boolean {
    for (const line of block.lines) {
      if (line.spans) {
        for (const span of line.spans) {
          if (span.italic && span.text.trim()) return true;
        }
      }
    }
    return false;
  }

  // Check if a block is already being edited (has a ReplaceTextOp)
  function isBlockBeingEdited(block: TextBlockInfo): boolean {
    return pageOps.some(op => {
      if (op.type !== 'replace_text') return false;
      // Check if the op rect overlaps significantly with the block
      const overlap = rectsOverlap(op.rect, block.rect);
      return overlap > 0.5; // 50% overlap threshold
    });
  }

  // Check if a specific line is being edited
  function isLineBeingEdited(block: TextBlockInfo, lineIndex: number): boolean {
    const line = block.lines[lineIndex];
    if (!line?.rect) return false;
    return pageOps.some(op => {
      if (op.type !== 'replace_text') return false;
      const overlap = rectsOverlap(op.rect, line.rect);
      return overlap > 0.5;
    });
  }

  // Calculate overlap ratio between two rects
  function rectsOverlap(a: NormalizedRect, b: NormalizedRect): number {
    const x0 = Math.max(a.x, b.x);
    const y0 = Math.max(a.y, b.y);
    const x1 = Math.min(a.x + a.width, b.x + b.width);
    const y1 = Math.min(a.y + a.height, b.y + b.height);

    if (x1 <= x0 || y1 <= y0) return 0;

    const overlapArea = (x1 - x0) * (y1 - y0);
    const blockArea = b.width * b.height;
    return blockArea > 0 ? overlapArea / blockArea : 0;
  }

  // Handle click on an existing text block
  function handleTextBlockClick(block: TextBlockInfo) {
    if (!interactive) return;
    if (store.activeTool !== 'select' && store.activeTool !== 'text' && store.activeTool !== null) return;

    // Create a ReplaceTextOp for this block
    const text = getBlockText(block);

    // Extract original line positions for precise Apply
    const originalLines: OriginalLineInfo[] = block.lines.map(line => ({
      text: line.spans ? line.spans.map(s => s.text).join('') : line.text,
      rect: line.rect,
    }));

    // Use the block's font info if available, otherwise fall back to toolbar defaults
    // Pass isSerif/isMono flags for accurate font type detection
    const style = {
      fontFamily: mapFontFamily(block.dominantFont, block.isSerif, block.isMono),
      fontSize: block.dominantSize || store.activeTextStyle.fontSize,
      color: block.dominantColor || store.activeTextStyle.color,
      bold: hasBlockBold(block),
      italic: hasBlockItalic(block),
      align: store.activeTextStyle.align, // Keep alignment from toolbar
      rotation: block.rotation || 0, // Text rotation from scanned documents
    };

    // Add small buffer to block width for font rendering differences
    const editorRect: NormalizedRect = {
      x: block.rect.x,
      y: block.rect.y,
      width: block.rect.width * 1.05,  // 5% buffer
      height: block.rect.height,
    };

    console.log('[EditOverlay] Block font info:', {
      dominantFont: block.dominantFont,
      dominantSize: block.dominantSize,
      dominantColor: block.dominantColor,
      isSerif: block.isSerif,
      isMono: block.isMono,
      rotation: block.rotation,
      mappedStyle: style,
      originalLines: originalLines.length,
    });

    const op = store.addOp<ReplaceTextOp>({
      type: 'replace_text',
      page,
      rect: editorRect,
      originalText: text,
      originalLines,  // Store original line positions
      text: text, // Start with original text
      style,
    });

    // Initialize undo history and start editing
    textUndoHistory = [];
    textRedoHistory = [];
    pushTextUndo(text);
    editingTextId = op.id;
    editingTextContent = text;
    lastInputTime = Date.now();
    store.selectOp(op.id);
  }

  // Handle click on a single line (line-level editing)
  function handleLineClick(block: TextBlockInfo, line: TextLineInfo, lineIndex: number) {
    if (!interactive) return;
    if (store.activeTool !== 'select' && store.activeTool !== 'text' && store.activeTool !== null) return;

    // Get line text
    const lineText = line.spans ? line.spans.map(s => s.text).join('') : (line.text || '');

    // Store just this line's position
    const originalLines: OriginalLineInfo[] = [{
      text: lineText,
      rect: line.rect,
    }];

    // Calculate editor width: OCR bbox is often too tight, extend to block's right edge
    // This ensures the editor is wide enough for the text content
    const blockRightEdge = block.rect.x + block.rect.width;
    const lineRightEdge = line.rect.x + line.rect.width;
    // Use the max of: line width, distance to block's right edge, or line width + 10% buffer
    const extendedWidth = Math.max(
      line.rect.width * 1.1,  // 10% buffer for font rendering differences
      blockRightEdge - line.rect.x  // Extend to block's right edge
    );

    // Editor rect: keep line's position but use extended width
    const editorRect: NormalizedRect = {
      x: line.rect.x,
      y: line.rect.y,
      width: extendedWidth,
      height: line.rect.height,
    };

    // Use the block's font info for styling
    const style = {
      fontFamily: mapFontFamily(block.dominantFont, block.isSerif, block.isMono),
      fontSize: block.dominantSize || store.activeTextStyle.fontSize,
      color: block.dominantColor || store.activeTextStyle.color,
      bold: hasBlockBold(block),
      italic: hasBlockItalic(block),
      align: store.activeTextStyle.align,
      rotation: line.rotation || block.rotation || 0,
    };

    console.log('[EditOverlay] Line click:', {
      lineIndex,
      lineText: lineText.substring(0, 50),
      lineRect: line.rect,
      editorRect,
    });

    const op = store.addOp<ReplaceTextOp>({
      type: 'replace_text',
      page,
      rect: editorRect,  // Use extended rect for editing
      originalText: lineText,
      originalLines,  // Keep original line position for Apply
      text: lineText,
      style,
    });

    // Initialize undo history and start editing
    textUndoHistory = [];
    textRedoHistory = [];
    pushTextUndo(lineText);
    editingTextId = op.id;
    editingTextContent = lineText;
    lastInputTime = Date.now();
    store.selectOp(op.id);
  }

  // Fetch blocks when page, path, or refreshKey changes
  $effect(() => {
    // Dependencies: pdfPath, page, refreshKey
    const _ = refreshKey; // Explicit dependency
    if (pdfPath && page) {
      fetchTextBlocks();
    }
  });

  // Convert normalized coords to pixels
  function toPixels(rect: NormalizedRect): { x: number; y: number; width: number; height: number } {
    return {
      x: rect.x * pageWidth * scale,
      y: rect.y * pageHeight * scale,
      width: rect.width * pageWidth * scale,
      height: rect.height * pageHeight * scale,
    };
  }

  // Convert pixel coords to normalized
  function toNormalized(x: number, y: number, width: number, height: number): NormalizedRect {
    return {
      x: x / (pageWidth * scale),
      y: y / (pageHeight * scale),
      width: width / (pageWidth * scale),
      height: height / (pageHeight * scale),
    };
  }

  // Get mouse position relative to overlay
  function getMousePos(e: MouseEvent): { x: number; y: number } {
    const rect = overlayElement.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    };
  }

  // Cursor style based on tool
  const cursorStyle = $derived(() => {
    if (!interactive) return 'default';
    if (isDragging) return 'grabbing';
    if (!store.activeTool) return 'default';
    if (store.activeTool === 'select') return 'default';
    if (store.activeTool === 'text') return 'text';
    return 'crosshair';
  });

  function handleMouseDown(e: MouseEvent) {
    if (e.button !== 0 || !interactive) return;

    // Stop propagation to prevent document panning
    e.stopPropagation();

    const pos = getMousePos(e);

    // If we're editing text and clicked outside the textarea, confirm the edit
    if (editingTextId) {
      const editingOp = store.getOpById(editingTextId);
      if (editingOp) {
        const px = toPixels(editingOp.rect);
        const isOutsideEdit = pos.x < px.x || pos.x > px.x + Math.max(px.width, 300) ||
                              pos.y < px.y || pos.y > px.y + Math.max(px.height, 100) + 40; // +40 for Done button
        if (isOutsideEdit) {
          confirmTextEdit(editingOp);
          return;
        }
      }
    }

    // Handle select tool - check if clicking on an operation
    if (store.activeTool === 'select' || !store.activeTool) {
      const clickedOp = findOpAtPosition(pos);
      if (clickedOp) {
        store.selectOp(clickedOp.id);
        isDragging = true;
        const px = toPixels(clickedOp.rect);
        dragOffset = { x: pos.x - px.x, y: pos.y - px.y };
        return;
      } else {
        store.selectOp(null);
      }
      return;
    }

    // Start drawing for other tools
    if (store.activeTool === 'text' || store.activeTool === 'image' ||
        store.activeTool === 'shape-rect' || store.activeTool === 'shape-ellipse' ||
        store.activeTool === 'line') {
      isDrawing = true;
      drawStart = pos;
      drawEnd = pos;
    }
  }

  function handleMouseMove(e: MouseEvent) {
    if (!interactive) return;

    const pos = getMousePos(e);

    if (isDrawing && drawStart) {
      drawEnd = pos;
    }

    if (isDragging && store.selectedId && dragOffset) {
      const op = store.getOpById(store.selectedId);
      if (op) {
        const newX = (pos.x - dragOffset.x) / (pageWidth * scale);
        const newY = (pos.y - dragOffset.y) / (pageHeight * scale);
        store.updateOp(store.selectedId, {
          rect: { ...op.rect, x: newX, y: newY },
        });
      }
    }
  }

  function handleMouseUp(e: MouseEvent) {
    if (!interactive) return;

    if (isDragging) {
      isDragging = false;
      dragOffset = null;
      return;
    }

    if (isDrawing && drawStart && drawEnd) {
      const minSize = 10; // Minimum size in pixels

      const x = Math.min(drawStart.x, drawEnd.x);
      const y = Math.min(drawStart.y, drawEnd.y);
      const width = Math.abs(drawEnd.x - drawStart.x);
      const height = Math.abs(drawEnd.y - drawStart.y);

      // Only create if big enough
      if (width >= minSize || height >= minSize) {
        const rect = toNormalized(x, y, Math.max(width, minSize), Math.max(height, minSize));

        if (store.activeTool === 'text') {
          const op = store.addOp<InsertTextOp>({
            type: 'insert_text',
            page,
            rect,
            text: '',
            style: { ...store.activeTextStyle },
          });
          // Start editing immediately
          editingTextId = op.id;
          editingTextContent = '';
        } else if (store.activeTool === 'image') {
          store.addOp<InsertImageOp>({
            type: 'insert_image',
            page,
            rect,
            keepAspect: true,
          });
        } else if (store.activeTool === 'shape-rect') {
          store.addOp<DrawShapeOp>({
            type: 'draw_shape',
            page,
            rect,
            shape: 'rect',
            strokeColor: store.activeStrokeColor,
            strokeWidth: store.activeStrokeWidth,
            fillColor: store.activeFillEnabled ? store.activeFillColor : undefined,
          });
        } else if (store.activeTool === 'shape-ellipse') {
          store.addOp<DrawShapeOp>({
            type: 'draw_shape',
            page,
            rect,
            shape: 'ellipse',
            strokeColor: store.activeStrokeColor,
            strokeWidth: store.activeStrokeWidth,
            fillColor: store.activeFillEnabled ? store.activeFillColor : undefined,
          });
        } else if (store.activeTool === 'line') {
          store.addOp<DrawShapeOp>({
            type: 'draw_shape',
            page,
            rect,
            shape: 'line',
            strokeColor: store.activeStrokeColor,
            strokeWidth: store.activeStrokeWidth,
          });
        }
      }
    }

    isDrawing = false;
    drawStart = null;
    drawEnd = null;
  }

  function findOpAtPosition(pos: { x: number; y: number }): EditorOp | undefined {
    // Search in reverse order (topmost first)
    for (let i = pageOps.length - 1; i >= 0; i--) {
      const op = pageOps[i];
      const px = toPixels(op.rect);
      if (
        pos.x >= px.x &&
        pos.x <= px.x + px.width &&
        pos.y >= px.y &&
        pos.y <= px.y + px.height
      ) {
        return op;
      }
    }
    return undefined;
  }

  function handleTextBlur(op: EditorOp) {
    // Don't blur if clicking on the Done button (handled separately)
    // The blur fires before click, so we use a small delay to check
    setTimeout(() => {
      if ((op.type === 'insert_text' || op.type === 'replace_text') && editingTextId === op.id) {
        confirmTextEdit(op);
      }
    }, 100);
  }

  // Confirm and apply the text edit
  function confirmTextEdit(op: EditorOp) {
    if ((op.type === 'insert_text' || op.type === 'replace_text') && editingTextId === op.id) {
      const existingOp = store.getOpById(op.id);
      if (existingOp) {
        store.updateOp(op.id, { text: editingTextContent });
      }
      // Clear undo/redo history when confirming
      textUndoHistory = [];
      textRedoHistory = [];
      editingTextId = null;
      editingTextContent = '';
    }
  }

  // Handle clicking the Done button
  function handleDoneClick(e: MouseEvent, op: EditorOp) {
    e.preventDefault();
    e.stopPropagation();
    confirmTextEdit(op);
  }

  function handleTextKeydown(e: KeyboardEvent) {
    // Ctrl+Z: Undo
    if (e.ctrlKey && !e.shiftKey && e.key === 'z') {
      e.preventDefault();
      e.stopPropagation();
      undoText();
      return;
    }

    // Ctrl+Y or Ctrl+Shift+Z: Redo
    if ((e.ctrlKey && e.key === 'y') || (e.ctrlKey && e.shiftKey && e.key === 'Z')) {
      e.preventDefault();
      e.stopPropagation();
      redoText();
      return;
    }

    if (e.key === 'Escape') {
      // Stop propagation to prevent closing the tab
      e.preventDefault();
      e.stopPropagation();

      const op = editingTextId ? store.getOpById(editingTextId) : null;

      if (op) {
        if (op.type === 'replace_text') {
          const replaceOp = op as ReplaceTextOp;
          // Always remove if text wasn't changed from original
          // (canceling the edit restores original state)
          if (editingTextContent === replaceOp.originalText || editingTextContent === replaceOp.text) {
            store.removeOp(op.id);
          } else {
            // Text was changed but user pressed Escape - restore original and remove
            store.removeOp(op.id);
          }
        } else if (op.type === 'insert_text') {
          // Remove empty insert_text operations
          if (!editingTextContent.trim()) {
            store.removeOp(op.id);
          } else {
            // Save the text before clearing
            store.updateOp(op.id, { text: editingTextContent });
          }
        }
      }

      // Clear undo/redo history when exiting edit mode
      textUndoHistory = [];
      textRedoHistory = [];
      editingTextId = null;
      editingTextContent = '';
    }
  }

  // Track text input for undo history (debounced to avoid flooding)
  let lastInputTime = 0;
  const INPUT_DEBOUNCE_MS = 500;

  function handleTextInput(e: Event) {
    const target = e.target as HTMLTextAreaElement;
    const now = Date.now();

    // Save undo state periodically (not on every keystroke)
    if (now - lastInputTime > INPUT_DEBOUNCE_MS && editingTextContent !== target.value) {
      pushTextUndo(editingTextContent);
      lastInputTime = now;
    }
  }

  function startEditingText(op: EditorOp) {
    if (op.type === 'insert_text' || op.type === 'replace_text') {
      // Get the latest version of the op from the store
      const currentOp = store.getOpById(op.id);
      if (!currentOp) return;

      const textOp = currentOp as InsertTextOp;

      // Initialize undo history with the current text
      textUndoHistory = [];
      textRedoHistory = [];
      pushTextUndo(textOp.text);

      // Select the op so toolbar shows correct styles
      store.selectOp(op.id);

      // Set the active text style to match the op's style
      store.setTextStyle(textOp.style);

      editingTextId = op.id;
      editingTextContent = textOp.text;
      lastInputTime = Date.now();
    }
  }

  // Preview rect while drawing
  const previewRect = $derived.by(() => {
    if (!isDrawing || !drawStart || !drawEnd) return null;
    return {
      x: Math.min(drawStart.x, drawEnd.x),
      y: Math.min(drawStart.y, drawEnd.y),
      width: Math.abs(drawEnd.x - drawStart.x),
      height: Math.abs(drawEnd.y - drawStart.y),
    };
  });
</script>

<div
  bind:this={overlayElement}
  class="absolute inset-0"
  class:pointer-events-none={!interactive}
  style="
    width: {pageWidth * scale}px;
    height: {pageHeight * scale}px;
    z-index: 30;
    cursor: {cursorStyle()};
  "
  onmousedown={handleMouseDown}
  onmousemove={handleMouseMove}
  onmouseup={handleMouseUp}
  onmouseleave={handleMouseUp}
  role="application"
  aria-label="Edit overlay"
>
  <!-- Render existing PDF text blocks/lines (clickable to edit) -->
  {#if showTextBlocks && !hideBlockHighlights && interactive && (store.activeTool === 'select' || store.activeTool === 'text' || store.activeTool === null)}
    {#if store.editGranularity === 'line'}
      <!-- LINE MODE: Render individual lines -->
      {#each textBlocks as block}
        {#each block.lines as line, lineIndex}
          {@const lineRect = line.rect}
          {@const px = toPixels(lineRect)}
          {@const lineText = line.spans ? line.spans.map(s => s.text).join('') : (line.text || '')}
          {#if !isLineBeingEdited(block, lineIndex)}
            <button
              type="button"
              class="absolute transition-all duration-150 cursor-pointer group"
              style="
                left: {px.x}px;
                top: {px.y}px;
                width: {px.width}px;
                height: {px.height}px;
              "
              onclick={() => handleLineClick(block, line, lineIndex)}
              title="Click to edit this line"
            >
              <!-- Subtle highlight on hover -->
              <div
                class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity"
                style="
                  background-color: rgba(163, 190, 140, 0.2);
                  border: 1px dashed var(--nord14);
                "
              ></div>
            </button>
          {/if}
        {/each}
      {/each}
    {:else}
      <!-- BLOCK MODE: Render entire blocks (default) -->
      {#each textBlocks as block}
        {#if !isBlockBeingEdited(block)}
          {@const px = toPixels(block.rect)}
          <button
            type="button"
            class="absolute transition-all duration-150 cursor-pointer group"
            style="
              left: {px.x}px;
              top: {px.y}px;
              width: {px.width}px;
              height: {px.height}px;
            "
            onclick={() => handleTextBlockClick(block)}
            title="Click to edit this text"
          >
            <!-- Subtle highlight on hover -->
            <div
              class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity"
              style="
                background-color: rgba(136, 192, 208, 0.15);
                border: 1px dashed var(--nord8);
              "
            ></div>
            <!-- Edit indicator on hover -->
            <div
              class="absolute -top-5 left-0 opacity-0 group-hover:opacity-100 transition-opacity text-xs px-1 py-0.5 rounded flex items-center gap-1"
              style="background-color: var(--nord10); color: var(--nord6);"
            >
              <Type size={10} />
              <span>Edit</span>
            </div>
          </button>
        {/if}
      {/each}
    {/if}
  {/if}

  <!-- Render existing operations -->
  {#each pageOps as op}
    {@const px = toPixels(op.rect)}
    {@const isSelected = store.selectedId === op.id}
    {@const isActivelyEditing = editingTextId === op.id}
    {@const isTextOp = op.type === 'insert_text' || op.type === 'replace_text'}
    {@const textOpWithContent = isTextOp && (op as InsertTextOp).text}
    <!-- Show visuals unless in preview mode (hideBlockHighlights) which shows only rendered result -->
    <!-- When preview mode is ON: hide all edit visuals, show only the background preview image -->
    {@const showVisuals = !hideBlockHighlights && (!hasPreview || isActivelyEditing || textOpWithContent)}
    <!-- Border + padding that will expand OUTWARD from content area -->
    {@const borderWidth = 1}
    {@const paddingH = 2}  <!-- horizontal padding -->
    {@const paddingV = 1}  <!-- vertical padding -->
    <!-- Offset position so content stays in place, chrome expands outward -->
    {@const offsetX = isActivelyEditing ? (borderWidth + paddingH) : 0}
    {@const offsetY = isActivelyEditing ? (borderWidth + paddingV) : 0}

    <div
      class="absolute"
      class:ring-2={isSelected && showVisuals && !isActivelyEditing}
      class:ring-[var(--nord8)]={isSelected && showVisuals && !isActivelyEditing}
      class:z-50={isActivelyEditing}
      style="
        left: {px.x - offsetX}px;
        top: {px.y - offsetY}px;
        width: {px.width}px;
        min-height: {px.height}px;
        height: {isActivelyEditing ? 'auto' : px.height + 'px'};
      "
    >
      {#if op.type === 'insert_text' || op.type === 'replace_text'}
        {@const textOp = op as InsertTextOp}
        {@const isReplaceOp = op.type === 'replace_text'}
        {@const textContent = textOp.text || editingTextContent}
        {@const numLines = textContent.split('\n').filter((l: string) => l.trim()).length || 1}
        {@const calculatedFontSize = calculateDisplayFontSize(
          textOp.style.fontSize,
          op.rect.height,
          textContent,
          textOp.style.fontFamily
        )}
        <!-- Find original block for line-height calculation -->
        {@const matchingBlock = textBlocks.find(b => rectsOverlap(op.rect, b.rect) > 0.5)}
        {@const lineHeightRatio = calculateLineHeight(matchingBlock, numLines)}
        <!-- Text box - always show textarea when actively editing -->
        {#if editingTextId === op.id}
          {@const scaledFontSize = calculatedFontSize * pdfToPixelScale}
          <div class="relative">
            <textarea
              class="outline-none resize-none"
              style="
                box-sizing: content-box;
                width: {px.width}px;
                min-height: {px.height}px;
                font-family: {textOp.style.fontFamily};
                font-size: {scaledFontSize}px;
                color: {textOp.style.color};
                font-weight: {textOp.style.bold ? 'bold' : 'normal'};
                font-style: {textOp.style.italic ? 'italic' : 'normal'};
                text-align: {textOp.style.align || 'left'};
                text-decoration: none;
                background-color: rgba(255, 255, 255, 0.97);
                border: {borderWidth}px solid var(--nord10);
                border-radius: 1px;
                padding: {paddingV}px {paddingH}px;
                line-height: {lineHeightRatio};
              "
              bind:value={editingTextContent}
              onkeydown={(e) => handleTextKeydown(e)}
              oninput={(e) => handleTextInput(e)}
              onmousedown={(e) => e.stopPropagation()}
              onfocus={() => { store.selectOp(op.id); }}
            ></textarea>
            <!-- Done button - small, positioned outside bottom-right -->
            <button
              type="button"
              class="absolute flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-medium rounded transition-colors hover:opacity-90"
              style="
                right: 0;
                top: 100%;
                margin-top: 2px;
                background-color: var(--nord14);
                color: var(--nord0);
                box-shadow: 0 1px 3px rgba(0,0,0,0.2);
              "
              onmousedown={(e) => handleDoneClick(e, op)}
            >
              <Check size={10} />
              Done
            </button>
          </div>
        {:else if showVisuals}
          {@const scaledFontSize = calculatedFontSize * pdfToPixelScale}
          {@const rotationDeg = textOp.style.rotation || 0}
          <div
            class="w-full cursor-text whitespace-pre-wrap"
            style="
              font-family: {textOp.style.fontFamily};
              font-size: {scaledFontSize}px;
              color: {textOp.style.color};
              font-weight: {textOp.style.bold ? 'bold' : 'normal'};
              font-style: {textOp.style.italic ? 'italic' : 'normal'};
              text-align: {textOp.style.align || 'left'};
              text-decoration: none;
              background-color: rgba(255, 255, 255, 0.9);
              border: {textOp.text ? '1px solid rgba(136, 192, 208, 0.2)' : '1px dashed rgba(136, 192, 208, 0.4)'};
              line-height: {lineHeightRatio};
              padding: 0 1px;
              min-height: {px.height}px;
              transform: rotate({rotationDeg}deg);
              transform-origin: top left;
            "
            ondblclick={() => startEditingText(op)}
          >
            {textOp.text || 'Double-click to edit...'}
          </div>
        {/if}
      {:else if op.type === 'insert_image' && showVisuals}
        {@const imgOp = op as InsertImageOp}
        <!-- Image placeholder -->
        <div
          class="w-full h-full flex items-center justify-center"
          style="
            background-color: rgba(136, 192, 208, 0.1);
            border: 2px dashed var(--nord8);
          "
        >
          {#if imgOp.imageData}
            <img
              src={imgOp.imageData}
              alt="Inserted image"
              class="max-w-full max-h-full object-contain"
            />
          {:else}
            <span class="text-xs opacity-50">Click to select image</span>
          {/if}
        </div>
      {:else if op.type === 'draw_shape' && showVisuals}
        {@const shapeOp = op as DrawShapeOp}
        <!-- Shape -->
        <svg class="w-full h-full" viewBox="0 0 {px.width} {px.height}">
          {#if shapeOp.shape === 'rect'}
            <rect
              x={shapeOp.strokeWidth / 2}
              y={shapeOp.strokeWidth / 2}
              width={px.width - shapeOp.strokeWidth}
              height={px.height - shapeOp.strokeWidth}
              stroke={shapeOp.strokeColor}
              stroke-width={shapeOp.strokeWidth}
              fill={shapeOp.fillColor || 'none'}
            />
          {:else if shapeOp.shape === 'ellipse'}
            <ellipse
              cx={px.width / 2}
              cy={px.height / 2}
              rx={(px.width - shapeOp.strokeWidth) / 2}
              ry={(px.height - shapeOp.strokeWidth) / 2}
              stroke={shapeOp.strokeColor}
              stroke-width={shapeOp.strokeWidth}
              fill={shapeOp.fillColor || 'none'}
            />
          {:else if shapeOp.shape === 'line'}
            <line
              x1={0}
              y1={px.height}
              x2={px.width}
              y2={0}
              stroke={shapeOp.strokeColor}
              stroke-width={shapeOp.strokeWidth}
            />
          {/if}
        </svg>
      {/if}

      <!-- Selection handles -->
      {#if isSelected && interactive}
        <!-- Remove button -->
        <button
          onclick={() => store.removeOp(op.id)}
          class="absolute -top-2 -right-2 w-5 h-5 rounded-full flex items-center justify-center transition-colors hover:scale-110"
          style="background-color: var(--nord11); color: var(--nord6);"
          title="Remove"
        >
          <X size={12} />
        </button>

        <!-- Move indicator -->
        <div
          class="absolute -top-2 -left-2 w-5 h-5 rounded-full flex items-center justify-center"
          style="background-color: var(--nord10); color: var(--nord6);"
        >
          <Move size={12} />
        </div>

        <!-- Resize handles -->
        <div class="absolute -bottom-1 -right-1 w-3 h-3 cursor-se-resize" style="background-color: var(--nord8);"></div>
      {/if}
    </div>
  {/each}

  <!-- Drawing preview -->
  {#if isDrawing && previewRect}
    <div
      class="absolute pointer-events-none"
      style="
        left: {previewRect.x}px;
        top: {previewRect.y}px;
        width: {previewRect.width}px;
        height: {previewRect.height}px;
      "
    >
      {#if store.activeTool === 'text'}
        <div
          class="w-full h-full"
          style="background-color: rgba(136, 192, 208, 0.2); border: 2px dashed var(--nord8);"
        ></div>
      {:else if store.activeTool === 'image'}
        <div
          class="w-full h-full"
          style="background-color: rgba(163, 190, 140, 0.2); border: 2px dashed var(--nord14);"
        ></div>
      {:else if store.activeTool === 'shape-rect'}
        <svg class="w-full h-full">
          <rect
            x={store.activeStrokeWidth / 2}
            y={store.activeStrokeWidth / 2}
            width={previewRect.width - store.activeStrokeWidth}
            height={previewRect.height - store.activeStrokeWidth}
            stroke={store.activeStrokeColor}
            stroke-width={store.activeStrokeWidth}
            fill={store.activeFillEnabled ? store.activeFillColor : 'none'}
            opacity="0.5"
          />
        </svg>
      {:else if store.activeTool === 'shape-ellipse'}
        <svg class="w-full h-full">
          <ellipse
            cx={previewRect.width / 2}
            cy={previewRect.height / 2}
            rx={(previewRect.width - store.activeStrokeWidth) / 2}
            ry={(previewRect.height - store.activeStrokeWidth) / 2}
            stroke={store.activeStrokeColor}
            stroke-width={store.activeStrokeWidth}
            fill={store.activeFillEnabled ? store.activeFillColor : 'none'}
            opacity="0.5"
          />
        </svg>
      {:else if store.activeTool === 'line'}
        <svg class="w-full h-full">
          <line
            x1={0}
            y1={previewRect.height}
            x2={previewRect.width}
            y2={0}
            stroke={store.activeStrokeColor}
            stroke-width={store.activeStrokeWidth}
            opacity="0.5"
          />
        </svg>
      {/if}
    </div>
  {/if}
</div>
