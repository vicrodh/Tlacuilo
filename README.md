# Tlacuilo

A full-featured offline PDF toolkit for Linux. Built with privacy in mind - all processing happens locally on your machine.

## Features

### PDF Viewer & Annotations
- High-quality PDF rendering powered by MuPDF
- Multi-tab document viewer
- Full annotation support: highlights, underlines, strikethrough, comments, freetext, shapes, arrows, sequence numbers
- Text selection with context menu (copy, search, annotate)
- Search with highlight and navigation
- Save annotations embedded in PDF or as XFDF
- Print support with annotation options

### PDF Operations
- **Merge**: Combine multiple PDFs with drag-and-drop page reordering
- **Split**: Extract pages, ranges, or create multiple documents
- **Rotate**: Per-page or batch rotation with visual preview
- **Compress**: Reduce file size with configurable quality levels

### Conversion
- **Images to PDF**: JPG, PNG, WEBP, TIFF, BMP with per-image transforms
- **PDF to Images**: Export pages as PNG, JPG, WEBP, or TIFF at configurable DPI
- **Office to PDF**: DOCX, XLSX, PPTX, ODT via LibreOffice
- **Markdown to PDF**: With syntax highlighting and custom styles

### OCR
- Automatic OCR detection for scanned documents
- Multi-language support (Tesseract)
- Progress indication and batch processing

### UI/UX
- Clean Nord-themed interface
- Persistent settings and recent files
- Customizable favorites in sidebar
- Keyboard shortcuts

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | [Svelte 5](https://svelte.dev/) (runes) + [Vite](https://vitejs.dev/) + [Tailwind CSS](https://tailwindcss.com/) |
| Desktop | [Tauri 2.x](https://tauri.app/) (Rust) |
| PDF Rendering | [MuPDF](https://mupdf.com/) via Rust bindings |
| PDF Processing | [PyMuPDF](https://pymupdf.readthedocs.io/), [pikepdf](https://pikepdf.readthedocs.io/), [pypdf](https://pypdf.readthedocs.io/) |
| OCR | [OCRmyPDF](https://ocrmypdf.readthedocs.io/) + [Tesseract](https://tesseract-ocr.github.io/) |
| Icons | [Lucide](https://lucide.dev/) |
| Theme | [Nord](https://www.nordtheme.com/) |

## Prerequisites

- Node.js 18+ and npm
- Rust toolchain (for Tauri)
- Python 3.12.x

### System Dependencies

#### Build dependencies (Linux)

MuPDF links common dependencies from the system to avoid conflicts with GTK file dialogs.

**Arch Linux:**
```bash
sudo pacman -S --needed pkgconf libjpeg-turbo zlib freetype2 harfbuzz
```

**Debian/Ubuntu:**
```bash
sudo apt-get install -y pkg-config libjpeg62-turbo-dev zlib1g-dev libfreetype6-dev libharfbuzz-dev
```

**Fedora:**
```bash
sudo dnf install -y pkgconf-pkg-config libjpeg-turbo-devel zlib-devel freetype-devel harfbuzz-devel
```

#### Optional dependencies

| Feature | Package |
|---------|---------|
| Office conversion | `libreoffice-fresh` |
| PDF compression | `ghostscript` |
| OCR | `tesseract` + language packs (e.g., `tesseract-data-eng`, `tesseract-data-spa`) |

#### File dialogs (Linux)

For better Wayland + KDE/GNOME integration, install XDG Desktop Portal:

- **KDE Plasma**: `xdg-desktop-portal` + `xdg-desktop-portal-kde`
- **GNOME**: `xdg-desktop-portal` + `xdg-desktop-portal-gtk`

## Installation

```bash
# Clone the repository
git clone https://github.com/vicrodh/Tlacuilo.git
cd Tlacuilo

# Install frontend dependencies
npm install

# Setup Python backend
python3.12 -m venv backend/venv
backend/venv/bin/pip install --upgrade pip
backend/venv/bin/pip install -r backend/requirements.txt
```

## Development

```bash
# Frontend only (browser)
npm run dev

# Full desktop app
npm run tauri:dev
```

## Build

```bash
npm run tauri:build
```

## Attributions

### Core Technologies

- **[MuPDF](https://mupdf.com/)** - High-performance PDF rendering engine (AGPL-3.0)
- **[Tauri](https://tauri.app/)** - Desktop application framework
- **[Svelte](https://svelte.dev/)** - Frontend framework
- **[PyMuPDF](https://pymupdf.readthedocs.io/)** - Python bindings for MuPDF
- **[pikepdf](https://pikepdf.readthedocs.io/)** - PDF manipulation library
- **[OCRmyPDF](https://ocrmypdf.readthedocs.io/)** - OCR processing
- **[Tesseract OCR](https://tesseract-ocr.github.io/)** - OCR engine

### Design

- **[Nord Theme](https://www.nordtheme.com/)** - Color palette
- **[Lucide Icons](https://lucide.dev/)** - Icon set

### Inspiration

- **[Sumatra PDF](https://www.sumatrapdfreader.org/)** - MuPDF-based reader with excellent rendering quality
- **[Stirling PDF](https://github.com/Stirling-Tools/Stirling-PDF)** - Comprehensive open-source PDF toolkit

## Roadmap

### Nice to Have (Needs Research)

- **Cloud Storage Integration**: OneDrive, Google Drive, Dropbox, iCloud - import and save files directly to cloud services

## Contributing

We are not accepting pull requests at this time. Please open an issue if you have suggestions.

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

This license is required because Tlacuilo uses [MuPDF](https://mupdf.com/), which is licensed under AGPL-3.0. Under the terms of AGPL-3.0:

- You may use, modify, and distribute this software
- If you modify and distribute this software, you must release your modifications under AGPL-3.0
- If you run a modified version on a server and let others interact with it, you must make the source code available

See [LICENSE](LICENSE) for the full license text.
