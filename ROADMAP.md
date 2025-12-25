# Tlacuilo - Roadmap

**Last updated:** 2024-12-24

---

## Current State: Functional PDF Viewer/Annotator

The viewer is usable for daily work. Manipulation tools (merge, split, rotate, compress, convert) are functional.

---

## Completed

### Core Viewer
- [x] High-quality PDF rendering with MuPDF (Rust bindings)
- [x] Multi-tab viewer
- [x] Zoom controls (fit-width, fit-page, custom)
- [x] View rotation
- [x] Page navigation
- [x] Text selection with context menu
- [x] Copy selected text
- [x] Search with highlight and navigation

### Annotations
- [x] Highlight
- [x] Underline
- [x] Strikethrough
- [x] Comments (sticky notes)
- [x] Freetext (typewriter)
- [x] Ink (freehand drawing)
- [x] Rectangle
- [x] Ellipse
- [x] Line
- [x] Arrow (configurable endpoints)
- [x] Sequence Numbers
- [x] Configurable colors and opacity
- [x] Line styles (solid, dashed, dotted)
- [x] Fill for shapes
- [x] Save annotations to PDF
- [x] Export as XFDF
- [x] Print with annotation options
- [x] Annotations panel with search
- [x] Change existing annotation color
- [x] Stamps (predefined, custom text, image, with rotation)

### Bookmarks
- [x] PDF Outlines (Table of Contents) reader
- [x] Navigation to section with precise scroll
- [x] Hierarchical expandable outlines
- [x] User bookmarks
- [x] Bookmark persistence per file
- [x] Add/edit/delete bookmarks
- [x] Search in bookmarks and outlines

### OCR
- [x] Automatic scanned document detection
- [x] OCR with Tesseract via ocrmypdf
- [x] Multi-language support
- [x] Progress indicator
- [x] OCR temporary file handling
- [x] Flow: original file -> OCR -> temp -> Save As

### PDF Operations
- [x] Merge PDFs
- [x] Split PDFs
- [x] Rotate pages
- [x] Compress PDFs (Ghostscript)

### Conversion
- [x] Images to PDF (JPG, PNG, WEBP, TIFF, BMP)
- [x] PDF to Images (PNG, JPG, WEBP, TIFF)
- [x] DPI configuration
- [x] Per-image transforms

### UI/UX
- [x] Nord theme
- [x] Sidebar with customizable favorites
- [x] Recent files
- [x] Persistent configuration (tauri-plugin-store)
- [x] Keyboard shortcuts
- [x] Tab system
- [x] Application menu (File, Edit, View, Help)
- [x] Confirmation dialog for unsaved changes

---

## In Progress

### Print Dialog (Before MVP)
- [ ] Custom print dialog (not depending on external viewers)
- [ ] Printer selection via CUPS
- [ ] Page range, copies, orientation options
- [ ] Print preview (nice to have)

### Signatures Module
- [x] Placeholder UI
- [x] Graphic signature (draw/load image)
- [x] Saved signatures library
- [x] Position signature in document (via stamps tool)
- [ ] PAdES digital signatures (P12/PFX)
- [ ] Signature verification

### Metadata Viewer
- [x] Show document info (title, author, dates)
- [x] PDF properties (version, encryption)
- [x] Statistics (pages, size)
- [x] Copy fields to clipboard

### Attachments Viewer
- [x] List embedded files with metadata
- [x] Extract individual attachment (Save As dialog)
- [x] Extract all attachments
- [ ] Attachment preview (images, text)

---

## Next (Quick Wins)

### Stamps
- [x] Predefined stamps (Approved, Draft, Confidential, etc.)
- [x] Custom text stamps
- [x] Image stamps (PNG/JPG)
- [x] Configurable rotation (-90, -45, 0, 45, 90)
- [x] Position as annotation

---

## Mid-term

### AcroForms
- [x] Detect form fields
- [x] Fill fields (text, checkbox, radio, dropdown)
- [x] Save filled form
- [x] Form mode toggle with field counter
- [x] Light-themed styled controls

### Callouts
- [ ] Freetext with connector line
- [ ] Automatic positioning

### Layers
- [x] Detect PDF layers
- [x] Toggle visibility

---

## Mid-term

### Protection / Security
- [x] Unlock PDF (remove restrictions)
- [x] Encrypt PDF (add password)
- [x] Remove password protection

### Redaction
- [ ] Mark areas for redaction
- [ ] Remove actual content (not just visually cover)
- [ ] Redaction verification

### Sanitization
- [ ] Clean metadata
- [ ] Remove scripts
- [ ] Remove hidden objects

## Long-term

### Office Conversion
- [ ] DOCX to PDF (LibreOffice)
- [ ] XLSX to PDF
- [ ] PPTX to PDF

---

## Nice to Have (Needs Research)

- [ ] Cloud Storage Integration (OneDrive, Google Drive, Dropbox, iCloud)
- [ ] Scan to PDF (SANE)
- [ ] Compare PDFs
- [ ] Repair damaged PDFs
- [ ] PKCS#11 (hardware tokens)

---

## Current Architecture

```
ihpdf/
├── src-tauri/           # Rust (Tauri + MuPDF bindings)
│   ├── src/
│   │   ├── lib.rs       # Commands and menu
│   │   ├── pdf_viewer.rs # MuPDF operations
│   │   ├── pdf_ocr.rs   # OCR wrapper
│   │   └── ...
│
├── src/                 # Frontend (Svelte 5 + TypeScript)
│   ├── lib/
│   │   ├── components/
│   │   │   ├── PDFViewer/    # Viewer components
│   │   │   ├── Sidebar/      # Navigation
│   │   │   └── ...
│   │   ├── stores/           # Svelte stores
│   │   └── views/            # Page views
│
├── backend/             # Python scripts
│   ├── pdf_ops.py       # Merge, split, rotate
│   ├── pdf_compress.py  # Compression
│   ├── pdf_convert.py   # Image conversion
│   └── ...
```

---

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | Svelte 5 (runes) + Vite |
| Desktop | Tauri 2.x (Rust) |
| PDF Rendering | MuPDF via Rust bindings |
| PDF Processing | PyMuPDF, pikepdf, pypdf |
| OCR | ocrmypdf + Tesseract |
| Styling | Tailwind CSS + Nord theme |
| Icons | Lucide |
