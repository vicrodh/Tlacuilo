# Tlacuilo

Tlacuilo is an offline PDF toolkit for Linux built with Tauri (Rust) + Svelte/TypeScript and a Python 3.12 backend (PyMuPDF, pikepdf). Includes functional Merge, Split y Rotate flows with inline previews and per-page controls.

## Stack
- Frontend: Svelte + Vite + Tailwind CSS + DaisyUI
- Desktop shell: Tauri 2.x
- Backend: Python 3.12 (PyMuPDF, pikepdf, pypdf, reportlab, Pillow)

## Prerequisites
- Node.js 18+ and npm
- Rust toolchain (for Tauri)
- Python 3.12.x
- System libs used later: poppler-utils, ghostscript, tesseract-ocr (not required to run Sprint 0)

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
├── src/            # Svelte frontend
├── src-tauri/      # Tauri Rust project
├── backend/        # Python backend (venv + libs)
└── tlacuilo-docs/  # Untracked docs (states/handoffs) – kept outside repo root
```

## Conventions
- Code and comments: English. No emojis. Comments explain intent, not the obvious.
- Functions: small, reusable, defensive defaults.
- Keep files focused; avoid monolith components/stores.
- No co-authoring metadata in commits.

## Current Features
- Merge PDFs with drag-and-drop page ordering and inline preview.
- Split PDFs (all, selected pages, or groups) with thumbnail selector.
- Rotate PDFs with per-page or per-group angles, visual preview, and a result viewer (single / two-up / grid, fit width/height, thumbnails).

## Next Steps
- Add edit/annotate tooling UI from the figma baseline.
- Implement mirroring in rotate (backend support needed) and batch conversions.
- Harden packaging (Flatpak/AppImage) and add automated tests.
