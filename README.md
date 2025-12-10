# I H PDF

Desktop PDF toolkit for Linux built with Tauri (Rust) + Svelte/TypeScript and a Python 3.12 backend (PyMuPDF, pikepdf). This repo currently contains the Sprint 0 scaffold: frontend shell, Tauri skeleton, and Python environment setup.

## Stack
- Frontend: Svelte + Vite + Tailwind CSS + DaisyUI
- Desktop shell: Tauri 1.x
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

## Build
- Production bundle: `npm run tauri:build`

## Project Structure
```
.
├── src/            # Svelte frontend
├── src-tauri/      # Tauri Rust project
├── backend/        # Python backend (venv + libs)
└── ihpdf-docs/     # Untracked docs (states/handoffs) – kept outside repo root
```

## Conventions
- Code and comments: English. No emojis. Comments explain intent, not the obvious.
- Functions: small, reusable, defensive defaults.
- Keep files focused; avoid monolith components/stores.
- No co-authoring metadata in commits.

## Next Steps
- Wire the Python bridge (Tauri commands → Python subprocess/runner).
- Add core PDF operations module in Python (merge/split/reorder/rotate).
- Lay out annotation/text-edit limited UI skeleton.
