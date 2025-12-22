# Tlacuilo Development Roadmap

## Current Status
- **Viewer**: Complete (MuPDF-based)
- **Merge**: Complete
- **Split**: Complete
- **Rotate**: Complete

---

## Phase A: Core Manipulation (Rust/MuPDF)

| Tool | Status | Technology | Notes |
|------|--------|------------|-------|
| Viewer | ✅ Done | MuPDF/Rust | Continuous scroll, fit modes |
| Merge | ✅ Done | MuPDF/Rust | |
| Split | ✅ Done | MuPDF/Rust | |
| Rotate | ✅ Done | MuPDF/Rust | |
| Compress | ⬜ Pending | MuPDF/Rust | Next to implement |

---

## Phase B: Python Integration

### Prerequisites
- [x] Build `python_bridge.rs` module for subprocess management
- [x] Implement dependency checking and virtual environment support

| Tool | Status | Technology | Notes |
|------|--------|------------|-------|
| OCR | ⬜ Pending | OCRmyPDF (Python) | High value feature |
| Images → PDF | ⬜ Pending | MuPDF or Python | |
| PDF → Images | ⬜ Pending | MuPDF | |

---

## Phase C: Protection & Annotation

| Tool | Status | Technology | Notes |
|------|--------|------------|-------|
| Encrypt | ⬜ Pending | MuPDF/Rust | |
| Decrypt | ⬜ Pending | MuPDF/Rust | |
| Watermark | ⬜ Pending | MuPDF/Rust | |
| Page Numbers | ⬜ Pending | MuPDF/Rust | |
| Redact | ⬜ Pending | MuPDF/Rust | |

---

## Phase D: Viewer Annotations (Bridge to Editor)

| Feature | Status | Notes |
|---------|--------|-------|
| Text Highlights | ⬜ Pending | |
| Comments/Notes | ⬜ Pending | |
| Freehand Drawing | ⬜ Pending | |
| Stamps | ⬜ Pending | |

---

## Phase E: Editor MVP

> **Inflection Point**: Start Editor when Phase A + B are stable and viewer has basic annotations.

| Feature | Status | Notes |
|---------|--------|-------|
| Text Editing | ⬜ Pending | Consider Skia integration |
| Image Insertion | ⬜ Pending | |
| Form Fields | ⬜ Pending | |
| Digital Signatures | ⬜ Pending | |

---

## Phase F: Code Consolidation & Refactoring

> **Goal**: Eliminate duplicated code patterns and consolidate similar implementations.

| Task | Status | Description |
|------|--------|-------------|
| Migrate PDF ops to python_bridge | ⬜ Pending | Refactor merge_pdfs, split_pdf, rotate_pdf to use PythonBridge |
| Unify error handling | ⬜ Pending | Standardize error types across all Tauri commands |
| Extract common UI patterns | ⬜ Pending | Create reusable Svelte components for file selection, progress, etc. |
| Consolidate i18n | ⬜ Pending | Ensure all user-facing strings use translation system |

---

## External Dependencies

### Python Tools (via python_bridge.rs)
- **OCRmyPDF**: Tesseract wrapper for OCR (MPL-2.0)
- **KittenTTS**: Text-to-speech for accessibility (Apache 2.0)

### Future Considerations
- **Skia**: 2D graphics library for Editor (use `skia-safe` Rust crate)

---

## Commit Strategy
- Minimum one commit per feature
- Multiple commits for complex tasks
- Checkpoint commits before major refactors
