# Codex Prompt: PDF Editor Line Deletion Bug

## Project Context

Tlacuilo is a PDF editor built with:
- **Frontend**: SvelteKit + TypeScript (Tauri app)
- **Backend**: Python with PyMuPDF (fitz) for PDF manipulation

The "Editable OCR mode" allows users to click on text in OCR'd PDFs and edit it inline. The flow is:
1. User clicks a text line → editor overlay appears
2. User edits text → clicks "Done"
3. User clicks "Apply" → backend processes all edits and saves new PDF

## The Problem

Two persistent bugs:

### Bug 1: Font Size Mismatch
The edited text appears LARGER than the original text in the saved PDF.

- **Screenshot 72** (`/tmp/image-72.png`): Shows edited text with overlay
- **Screenshot 73** (`/tmp/image-73.png`): Shows original text (hiding edit) - the edited text is visibly larger

### Bug 2: Line Deletion (CRITICAL)
When editing a line, the LINE BELOW gets deleted in the saved PDF.

- **Screenshot 74** (`/tmp/image-74.png`): Shows saved PDF with missing line
- The line "Laboratory Information Management System (LIMS) in its drinking water bacteriology testing" is completely gone
- User annotation: "La linea desapareció de nuevo :(" (The line disappeared again)

## Relevant Files

### Frontend: `/home/blitzkriegfc/Personal/ihpdf/src/lib/components/PDFViewer/EditOverlay.svelte`

Key function `handleLineClick()` (around line 530-610):
- Creates a `ReplaceTextOp` when user clicks a line
- Stores `originalLines` with the line's rect for positioning during Apply
- Uses `line.spans[0].size` for font size (recently changed from `block.dominantSize`)

Key function `calculateDisplayFontSize()` (around line 89-103):
- Now returns `reportedFontSize` directly (simplified)

### Backend: `/home/blitzkriegfc/Personal/ihpdf/backend/pdf_edit.py`

Key function `apply_edits()` (around line 360-610):
- Two-pass approach for replace_text operations
- Pass 1: Collect all ops by page
- Pass 2: Draw white rects, add redact annotations, apply_redactions() ONCE, insert text

Current rect calculation (around line 449-474):
```python
# Shrink vertically from BOTH top and bottom
top_shrink = orig_h * 0.10
bottom_shrink = orig_h * 0.25
safe_y0 = orig_y0 + top_shrink
safe_y1 = orig_y0 + orig_h - bottom_shrink
cover_rect = fitz.Rect(orig_x0, safe_y0, orig_x0 + orig_w, safe_y1)
redact_rect = cover_rect
```

## What We've Tried

1. **Font size**: Changed from `block.dominantSize` to `line.spans[0].size`
2. **Rect shrinking**: Shrink from both top (10%) and bottom (25%) to avoid adjacent lines
3. **Batched redactions**: Call `apply_redactions()` only once per page
4. **Separate rects**: Tried different rects for white cover vs text redaction

## Root Cause Analysis

### Font Size Issue
The OCR's reported font size might not match the VISUAL size in scanned documents. For OCR'd PDFs:
- The scanned image shows text at visual size X
- The invisible text layer uses font size Y for searchability
- OCR reports Y, but user sees X

### Line Deletion Issue
PyMuPDF's `add_redact_annot()` + `apply_redactions()` removes ANY text whose bounding box OVERLAPS with the redaction rect. OCR bounding boxes often extend into adjacent lines, so even a "shrunk" rect may still overlap with the next line's characters.

## Questions for Codex

1. **Font Size**: How can we accurately determine the visual font size for text insertion that matches the original scanned appearance? Should we calculate from bbox height instead of using OCR-reported size?

2. **Line Deletion**: Is there a way to redact ONLY the specific text content without using rect-based redaction? Or should we avoid redaction entirely and just draw over the text?

3. **Alternative Approach**: Would it be better to:
   - Extract the entire page as an image
   - Draw the edits on the image
   - Replace the page content entirely?

## Environment

- PyMuPDF version: Latest (fitz)
- PDF type: OCR'd scanned documents (image layer + invisible text layer)
- Coordinate system: Normalized (0-1) in frontend, converted to PDF points in backend

## Expected Behavior

1. Edited text should match the visual size of surrounding text
2. Only the edited line should be modified; adjacent lines must remain intact
3. The result should look like a clean edit, not a visible patch
