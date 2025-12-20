# Tlacuilo

Tlacuilo is a full-featured offline PDF toolkit for Linux built with Tauri (Rust) + Svelte 5/TypeScript and a Python 3.12 backend (PyMuPDF, pikepdf, Pillow). Features a modular architecture with a unified PDF viewer component, persistent user settings, and a clean Nord-themed UI.

## Stack
- Frontend: Svelte 5 (runes) + Vite + Tailwind CSS
- Desktop shell: Tauri 2.x with tauri-plugin-store for persistence
- Backend: Python 3.12 (PyMuPDF, pikepdf, pypdf, reportlab, Pillow)
- Theme: Nord color palette

## Prerequisites
- Node.js 18+ and npm
- Rust toolchain (for Tauri)
- Python 3.12.x
- System libs (optional): libreoffice-fresh (Office conversions), ghostscript (compression), tesseract-ocr (OCR)

## Install
```bash
npm install
```

### Python backend
```bash
python3.12 -m venv backend/venv
backend/venv/bin/pip install --upgrade pip
backend/venv/bin/pip install -r backend/requirements.txt
```

## Run
- Frontend only: `npm run dev`
- Tauri desktop (bundles frontend + Rust shell): `npm run tauri:dev`
- Python CLI (dev, pages): `python backend/pdf_pages.py merge --inputs a.pdf b.pdf --output out.pdf`

## Build
- Production bundle: `npm run tauri:build`

## Project Structure
```
.
├── src/
│   ├── lib/
│   │   ├── components/     # Reusable UI components
│   │   │   ├── PDFViewer/  # Unified PDF viewer module
│   │   │   └── Sidebar.svelte
│   │   ├── stores/         # Svelte stores (settings, status)
│   │   ├── views/          # Feature views (Merge, Split, etc.)
│   │   └── utils/          # Helpers (pdfjs wrapper, etc.)
│   └── routes/             # SvelteKit routes
├── src-tauri/              # Tauri Rust project
├── backend/                # Python backend (venv + libs)
└── static/                 # Static assets
```

## Conventions
- Code and comments: English. No emojis. Comments explain intent, not the obvious.
- Functions: small, reusable, defensive defaults.
- Keep files focused; avoid monolith components/stores.

## Current Features

### PDF Operations
- **Merge PDFs**: Drag-and-drop file/page ordering with unified viewer preview
- **Split PDFs**: All pages, selected pages, or custom groups with thumbnail selector
- **Rotate PDFs**: Per-page or per-group angles with visual preview

### Conversion
- **Images to PDF**: Convert JPG, PNG, WEBP, TIFF, BMP with per-image transforms (rotate, flip)
- **PDF to Images**: Export pages as PNG, JPG, WEBP, or TIFF at configurable DPI

### UI/UX
- **Unified PDF Viewer**: Full-featured viewer with toolbar, sidebar thumbnails, zoom controls, and annotation tools (pen, highlight, text, redact, stamp)
- **Persistent Settings**: User favorites and recent files stored via tauri-plugin-store
- **Dynamic Dashboard**: Expandable tool groups with macOS-style dropdowns
- **Customizable Favorites**: User-configurable quick access in sidebar

## Planned Features
- Document to PDF conversion (DOCX, XLSX, PPTX, ODT via LibreOffice)
- Markdown to PDF conversion
- PDF compression (Ghostscript)
- OCR text extraction (Tesseract)
- Digital signatures
- Detachable viewer windows
- Form field editing
