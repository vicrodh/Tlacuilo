#!/usr/bin/env python3
"""
PDF OCR module using OCRmyPDF and Tesseract.

Provides OCR functionality for scanned PDFs:
- Text recognition using Tesseract
- Multiple language support
- Two modes:
  - Searchable: Invisible text layer (OCRmyPDF)
  - Editable: Real text objects with visual metrics
- Embedded metrics for consistent editing across sessions
"""

import argparse
import json
import sys
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from xml.etree import ElementTree

try:
    import ocrmypdf
    from ocrmypdf import ExitCode
    HAS_OCRMYPDF = True
except ImportError:
    HAS_OCRMYPDF = False

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


def check_dependencies() -> dict:
    """Check if OCRmyPDF and Tesseract are available."""
    result = {
        "ocrmypdf_installed": HAS_OCRMYPDF,
        "ocrmypdf_version": None,
        "tesseract_installed": False,
        "tesseract_version": None,
        "available_languages": [],
    }

    if HAS_OCRMYPDF:
        try:
            from ocrmypdf._exec import tesseract
            result["tesseract_installed"] = True

            # Get available languages
            try:
                import subprocess
                lang_output = subprocess.run(
                    ["tesseract", "--list-langs"],
                    capture_output=True,
                    text=True
                )
                if lang_output.returncode == 0:
                    # Skip first line (header) and get language codes
                    langs = lang_output.stdout.strip().split('\n')[1:]
                    result["available_languages"] = [l.strip() for l in langs if l.strip()]
            except Exception:
                pass

            # Get tesseract version
            try:
                ver_output = subprocess.run(
                    ["tesseract", "--version"],
                    capture_output=True,
                    text=True
                )
                if ver_output.returncode == 0:
                    # First line contains version
                    first_line = ver_output.stdout.split('\n')[0]
                    result["tesseract_version"] = first_line.replace("tesseract ", "")
            except Exception:
                pass

        except Exception:
            pass

    return result


def run_ocr(
    input_path: str,
    output_path: str,
    language: str = "eng",
    deskew: bool = False,
    rotate_pages: bool = False,
    remove_background: bool = False,
    clean: bool = False,
    skip_text: bool = False,
    force_ocr: bool = False,
    redo_ocr: bool = False,
    pdf_renderer: str = "auto",
    optimize: int = 1,
    pdfa_image_compression: str = "auto",
) -> dict:
    """
    Run OCR on a PDF file.

    Args:
        input_path: Path to input PDF
        output_path: Path to output PDF
        language: OCR language(s), e.g., "eng", "eng+spa"
        deskew: Deskew pages before OCR
        rotate_pages: Rotate pages to correct orientation
        remove_background: Remove background from pages
        clean: Clean pages to improve OCR accuracy
        skip_text: Skip pages that already have text
        force_ocr: Force OCR even if text is present
        redo_ocr: Redo OCR on pages that have text (removes existing text layer)
        pdf_renderer: PDF renderer (auto, hocr, sandwich, hocr-docker)
        optimize: Optimization level (0-3)
        pdfa_image_compression: Image compression for PDF/A (auto, jpeg, lossless)

    Returns:
        dict with success status and details
    """
    if not HAS_OCRMYPDF:
        return {
            "success": False,
            "error": "OCRmyPDF is not installed",
            "exit_code": -1,
        }

    input_file = Path(input_path)
    if not input_file.exists():
        return {
            "success": False,
            "error": f"Input file not found: {input_path}",
            "exit_code": -1,
        }

    try:
        # Build OCR options
        kwargs = {
            "language": language.split("+"),
            "deskew": deskew,
            "rotate_pages": rotate_pages,
            "remove_background": remove_background,
            "clean": clean,
            "skip_text": skip_text,
            "force_ocr": force_ocr,
            "redo_ocr": redo_ocr,
            "optimize": optimize,
            "progress_bar": False,
        }

        # Run OCR
        exit_code = ocrmypdf.ocr(input_path, output_path, **kwargs)

        if exit_code == ExitCode.ok:
            return {
                "success": True,
                "output_path": output_path,
                "exit_code": exit_code.value,
            }
        elif exit_code == ExitCode.already_done_ocr:
            return {
                "success": True,
                "output_path": output_path,
                "exit_code": exit_code.value,
                "message": "File already contains text layer",
            }
        else:
            return {
                "success": False,
                "exit_code": exit_code.value,
                "error": f"OCR failed with exit code: {exit_code.name}",
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "exit_code": -1,
        }


def analyze_pdf(input_path: str) -> dict:
    """
    Analyze a PDF to determine if it needs OCR.

    Returns information about:
    - Number of pages
    - Whether it contains text
    - Whether it appears to be scanned
    """
    if not HAS_OCRMYPDF:
        return {
            "success": False,
            "error": "OCRmyPDF is not installed",
        }

    try:
        from pdfminer.high_level import extract_text
        from pikepdf import Pdf

        with Pdf.open(input_path) as pdf:
            page_count = len(pdf.pages)

        # Try to extract text
        text = extract_text(input_path, maxpages=3)  # Sample first 3 pages
        has_text = len(text.strip()) > 50  # More than 50 chars suggests real text

        # Check if pages contain images (potential scanned document)
        with Pdf.open(input_path) as pdf:
            has_images = False
            for page in list(pdf.pages)[:3]:  # Sample first 3 pages
                resources = page.get("/Resources", {})
                if "/XObject" in resources:
                    xobjects = resources.get("/XObject", {})
                    # pikepdf dictionaries don't have .values(), iterate via keys
                    for key in xobjects.keys():
                        obj = xobjects[key]
                        if obj.get("/Subtype") == "/Image":
                            has_images = True
                            break
                if has_images:
                    break

        # Determine if OCR is needed
        needs_ocr = has_images and not has_text

        return {
            "success": True,
            "page_count": page_count,
            "has_text": has_text,
            "has_images": has_images,
            "needs_ocr": needs_ocr,
            "recommendation": "OCR recommended" if needs_ocr else "OCR not needed" if has_text else "Analyze more pages",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


# =============================================================================
# Editable OCR Mode - Creates real text objects with visual metrics
# =============================================================================

def parse_hocr_bbox(title: str) -> Optional[tuple]:
    """Extract bbox coordinates from hOCR title attribute."""
    match = re.search(r'bbox\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', title)
    if match:
        return tuple(map(int, match.groups()))
    return None


def parse_hocr_confidence(title: str) -> int:
    """Extract confidence (x_wconf) from hOCR title attribute."""
    match = re.search(r'x_wconf\s+(\d+)', title)
    if match:
        return int(match.group(1))
    return 0


def parse_hocr(hocr_content: str) -> List[Dict[str, Any]]:
    """
    Parse hOCR output from Tesseract.

    Returns list of text blocks with:
    - bbox: bounding box in pixels
    - text: recognized text
    - lines: list of lines with individual words
    - confidence: OCR confidence
    """
    blocks = []

    try:
        # Parse as HTML/XML
        root = ElementTree.fromstring(hocr_content)

        # Find all ocr_carea (content areas) or ocr_par (paragraphs)
        for area in root.iter():
            if area.get('class') in ('ocr_carea', 'ocr_par'):
                title = area.get('title', '')
                area_bbox = parse_hocr_bbox(title)

                if not area_bbox:
                    continue

                block = {
                    'bbox': area_bbox,
                    'lines': [],
                    'text': '',
                }

                # Find lines within this area
                for line_elem in area.iter():
                    if line_elem.get('class') == 'ocr_line':
                        line_title = line_elem.get('title', '')
                        line_bbox = parse_hocr_bbox(line_title)

                        if not line_bbox:
                            continue

                        line = {
                            'bbox': line_bbox,
                            'words': [],
                            'text': '',
                        }

                        # Find words within this line
                        for word_elem in line_elem.iter():
                            if word_elem.get('class') == 'ocrx_word':
                                word_title = word_elem.get('title', '')
                                word_bbox = parse_hocr_bbox(word_title)
                                word_conf = parse_hocr_confidence(word_title)
                                word_text = ''.join(word_elem.itertext()).strip()

                                if word_bbox and word_text:
                                    line['words'].append({
                                        'bbox': word_bbox,
                                        'text': word_text,
                                        'confidence': word_conf,
                                    })

                        if line['words']:
                            line['text'] = ' '.join(w['text'] for w in line['words'])
                            block['lines'].append(line)

                if block['lines']:
                    block['text'] = '\n'.join(l['text'] for l in block['lines'])
                    blocks.append(block)

    except ElementTree.ParseError as e:
        print(f"[WARN] hOCR parse error: {e}", file=sys.stderr)

    return blocks


def calculate_visual_font_size(bbox: tuple, dpi: int = 300) -> float:
    """
    Calculate visual font size from bounding box.

    Args:
        bbox: (x0, y0, x1, y1) in pixels
        dpi: image resolution (dots per inch)

    Returns:
        Font size in PDF points (1/72 inch)
    """
    # Height in pixels
    pixel_height = bbox[3] - bbox[1]

    # Convert to points: pixels / dpi * 72
    points = pixel_height / dpi * 72

    return round(points, 2)


def get_image_regions(page, zoom: float) -> list:
    """
    Detect ONLY actual image regions (logos, photos) in a PDF page.
    Returns list of rects in PDF coordinates that should NOT be touched.

    CONSERVATIVE: Only detect embedded images, not vector graphics
    (vector graphics detection was causing entire pages to be skipped)
    """
    image_rects = []
    page_rect = page.rect
    page_area = page_rect.width * page_rect.height

    # Get embedded images on the page (photos, logos, etc.)
    for img in page.get_images(full=True):
        try:
            xref = img[0]
            img_rects = page.get_image_rects(xref)
            for rect in img_rects:
                # Skip if the image covers most of the page (it's the background)
                img_area = rect.width * rect.height
                if img_area > page_area * 0.5:
                    print(f"[INFO]   Skipping full-page background image", file=sys.stderr)
                    continue

                # Only consider images that are logo-sized (not tiny icons or huge backgrounds)
                # Typical logo: 50-300pt wide, 30-200pt tall
                if rect.width > 30 and rect.height > 30 and rect.width < 400 and rect.height < 300:
                    padded = rect + (-3, -3, 3, 3)
                    image_rects.append(padded)
                    print(f"[INFO]   Detected image region: {rect.width:.0f}x{rect.height:.0f}pt", file=sys.stderr)
        except Exception:
            pass

    # NOTE: Removed get_drawings() - it was detecting ALL vector elements
    # including text paths, causing entire pages to be skipped

    return image_rects


def is_garbage_text(text: str) -> bool:
    """
    Check if OCR text is clearly garbage (very high ratio of special chars).
    CONSERVATIVE: Only skip obvious garbage, not edge cases.
    """
    if not text or len(text.strip()) == 0:
        return True

    text_clean = text.strip()

    # Only skip if it's a single weird character
    if len(text_clean) == 1 and not text_clean.isalnum():
        return True

    # Count truly garbage characters (not normal punctuation)
    garbage_chars = set('\\|}{[]@#$%^&*<>~`')
    garbage_count = sum(1 for c in text_clean if c in garbage_chars)

    # Only skip if MORE THAN 50% garbage (very lenient)
    if len(text_clean) > 0 and garbage_count / len(text_clean) > 0.5:
        return True

    return False


def rect_overlaps_any(rect, rect_list, threshold=0.7) -> bool:
    """
    Check if a rectangle SIGNIFICANTLY overlaps with any rect in the list.
    threshold=0.7 means 70% of the rect must be inside an image to be skipped.
    """
    for other in rect_list:
        intersection = rect & other
        if intersection.is_empty:
            continue

        rect_area = rect.width * rect.height
        if rect_area > 0:
            overlap_ratio = (intersection.width * intersection.height) / rect_area
            if overlap_ratio > threshold:
                return True

    return False


def is_all_caps(text: str) -> bool:
    """
    Check if text is ALL CAPS (used for headings/subtitles).
    ALL CAPS text has no descenders, so bounding boxes are shorter.
    """
    # Extract only letters
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 3:
        return False

    # Count uppercase letters
    upper_count = sum(1 for c in letters if c.isupper())

    # Consider ALL CAPS if 90%+ are uppercase
    return upper_count / len(letters) >= 0.9


def has_descenders(text: str) -> bool:
    """
    Check if text contains characters with descenders (g, j, p, q, y).
    Text without descenders has shorter bounding boxes.
    """
    descender_chars = set('gjpqy')
    return any(c.lower() in descender_chars for c in text)


def calculate_baseline_font_size(blocks: list, zoom: float) -> float:
    """
    Calculate a reference font size from all text blocks.
    Uses the median of line heights from multi-line blocks (body text).
    """
    line_heights = []

    for block in blocks:
        # Focus on blocks with multiple lines (more likely body text)
        if len(block.get('lines', [])) >= 2:
            for line in block['lines']:
                bbox = line.get('bbox')
                if bbox:
                    height_pt = (bbox[3] - bbox[1]) / zoom
                    if 8 < height_pt < 30:  # Reasonable text range
                        line_heights.append(height_pt)

    if not line_heights:
        # Fallback: use all lines
        for block in blocks:
            for line in block.get('lines', []):
                bbox = line.get('bbox')
                if bbox:
                    height_pt = (bbox[3] - bbox[1]) / zoom
                    if 8 < height_pt < 30:
                        line_heights.append(height_pt)

    if line_heights:
        sorted_heights = sorted(line_heights)
        median = sorted_heights[len(sorted_heights) // 2]
        return median * 0.85  # Convert to font size

    return 11.0  # Default fallback


def run_editable_ocr(
    input_path: str,
    output_path: str,
    language: str = "eng",
    dpi: int = 300,
    font_family: str = "auto",
    preserve_images: bool = True,
    embed_metrics: bool = True,
) -> dict:
    """
    Run OCR and create editable text objects.

    This mode creates a PDF with:
    - Original images/logos preserved (detected and skipped)
    - Text replaced with editable text objects
    - Accurate font sizes from OCR bounding boxes
    - Embedded metrics for future editing

    Args:
        input_path: Path to input PDF
        output_path: Path to output PDF
        language: OCR language (e.g., "eng", "eng+spa")
        dpi: Resolution for rendering pages (higher = more accurate)
        font_family: Font to use ("auto", "times", "helvetica", "courier")
        preserve_images: Keep images/logos (True) or convert everything (False)
        embed_metrics: Embed visual metrics in PDF metadata

    Returns:
        dict with success status, metrics, and output path
    """
    if not HAS_PYMUPDF:
        return {
            "success": False,
            "error": "PyMuPDF is required for editable OCR",
        }

    input_file = Path(input_path)
    if not input_file.exists():
        return {
            "success": False,
            "error": f"Input file not found: {input_path}",
        }

    try:
        # Open the input PDF
        doc = fitz.open(input_path)

        # Create a new PDF for output
        out_doc = fitz.open()

        # Metrics to embed in PDF
        all_metrics = {
            "version": 2,  # Version 2 with improved algorithm
            "dpi": dpi,
            "language": language,
            "font_family": font_family,
            "pages": [],
        }

        # Map font family selection to PyMuPDF font name
        font_map = {
            "auto": "tiro",
            "times": "tiro",
            "helvetica": "helv",
            "arial": "helv",
            "courier": "cour",
            "serif": "tiro",
            "sans-serif": "helv",
            "sans": "helv",
            "monospace": "cour",
        }
        pymupdf_font = font_map.get(font_family.lower(), "tiro")

        print(f"[INFO] Starting editable OCR v2: {len(doc)} pages, DPI={dpi}, lang={language}", file=sys.stderr)

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_rect = page.rect
            zoom = dpi / 72.0

            print(f"[INFO] Processing page {page_num + 1}/{len(doc)}...", file=sys.stderr)

            # Detect image/graphic regions to preserve
            image_regions = get_image_regions(page, zoom) if preserve_images else []
            print(f"[INFO]   Found {len(image_regions)} image/graphic regions to preserve", file=sys.stderr)

            # Render page to image for OCR (high DPI for accuracy)
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            # Create new page with same dimensions
            new_page = out_doc.new_page(width=page_rect.width, height=page_rect.height)

            # Insert the RENDERED IMAGE as background (not show_pdf_page!)
            # This ensures no text duplication from original PDF text layers
            # We use the same pixmap we'll send to Tesseract
            img_rect = fitz.Rect(0, 0, page_rect.width, page_rect.height)
            new_page.insert_image(img_rect, pixmap=pix)

            # Save to temp file for Tesseract
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                pix.save(tmp.name)
                tmp_path = tmp.name

            try:
                # Run Tesseract with hOCR output
                result = subprocess.run(
                    ['tesseract', tmp_path, 'stdout', '-l', language, 'hocr'],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if result.returncode != 0:
                    print(f"[WARN] Tesseract failed on page {page_num + 1}: {result.stderr}", file=sys.stderr)
                    continue

                hocr_content = result.stdout
                blocks = parse_hocr(hocr_content)

                print(f"[INFO]   Found {len(blocks)} text blocks from OCR", file=sys.stderr)

                # Calculate baseline font size for this page
                baseline_font_size = calculate_baseline_font_size(blocks, zoom)
                print(f"[INFO]   Baseline font size: {baseline_font_size:.1f}pt", file=sys.stderr)

                # Page metrics
                page_metrics = {
                    "page": page_num,
                    "width": page_rect.width,
                    "height": page_rect.height,
                    "blocks": [],
                    "skipped_blocks": 0,
                }

                blocks_processed = 0
                blocks_skipped = 0

                for block in blocks:
                    # Convert pixel bbox to PDF points
                    px_bbox = block['bbox']
                    pdf_bbox = fitz.Rect(
                        px_bbox[0] / zoom,
                        px_bbox[1] / zoom,
                        px_bbox[2] / zoom,
                        px_bbox[3] / zoom,
                    )

                    # Skip blocks that overlap with images
                    if preserve_images and rect_overlaps_any(pdf_bbox, image_regions):
                        print(f"[INFO]   Skipping block overlapping image: '{block['text'][:30]}...'", file=sys.stderr)
                        blocks_skipped += 1
                        continue

                    # Skip garbage text
                    if is_garbage_text(block['text']):
                        print(f"[INFO]   Skipping garbage text: '{block['text'][:30]}...'", file=sys.stderr)
                        blocks_skipped += 1
                        continue

                    # Skip very small blocks (likely noise)
                    if pdf_bbox.width < 10 or pdf_bbox.height < 5:
                        blocks_skipped += 1
                        continue

                    # Calculate appropriate whitening rect
                    white_rect = pdf_bbox + (-1, -1, 1, 1)

                    # White out the original text area
                    shape = new_page.new_shape()
                    shape.draw_rect(white_rect)
                    shape.finish(color=None, fill=(1, 1, 1))
                    shape.commit()

                    # Process each line with its own positioning
                    for line in block['lines']:
                        line_px_bbox = line['bbox']
                        line_pdf_bbox = fitz.Rect(
                            line_px_bbox[0] / zoom,
                            line_px_bbox[1] / zoom,
                            line_px_bbox[2] / zoom,
                            line_px_bbox[3] / zoom,
                        )

                        line_text = line['text']

                        # Calculate font size from line height
                        line_height_px = line_px_bbox[3] - line_px_bbox[1]
                        line_height_pt = line_height_px / zoom
                        font_size = line_height_pt * 0.85  # Base: 85% of line height

                        # ALL CAPS correction: text without descenders has shorter bbox
                        # Apply scaling factor to compensate (descenders add ~20% to line height)
                        if is_all_caps(line_text) or not has_descenders(line_text):
                            # Scale up by ~18% to match text with descenders
                            font_size = font_size * 1.18

                        # Ensure font size is at least the baseline (body text size)
                        # This prevents subtitles from being smaller than body text
                        if font_size < baseline_font_size * 0.95:
                            # If calculated size is smaller than baseline, use baseline
                            # (subtitles should never be smaller than body text)
                            font_size = max(font_size, baseline_font_size)

                        # Clamp font size to reasonable range
                        font_size = max(6, min(72, font_size))

                        # Position text at baseline
                        # For ALL CAPS (no descenders), baseline is higher (~85%)
                        # For normal text with descenders, baseline is lower (~80%)
                        if is_all_caps(line_text) or not has_descenders(line_text):
                            baseline_ratio = 0.85
                        else:
                            baseline_ratio = 0.80

                        text_x = line_pdf_bbox.x0
                        text_y = line_pdf_bbox.y0 + (line_pdf_bbox.height * baseline_ratio)

                        try:
                            new_page.insert_text(
                                fitz.Point(text_x, text_y),
                                line_text,
                                fontname=pymupdf_font,
                                fontsize=font_size,
                                color=(0, 0, 0),
                            )
                        except Exception as e:
                            print(f"[WARN] Failed to insert text '{line_text[:20]}...': {e}", file=sys.stderr)

                    blocks_processed += 1

                    # Store block metrics
                    page_metrics['blocks'].append({
                        'bbox_pdf': (pdf_bbox.x0, pdf_bbox.y0, pdf_bbox.x1, pdf_bbox.y1),
                        'text': block['text'],
                        'line_count': len(block['lines']),
                    })

                page_metrics['skipped_blocks'] = blocks_skipped
                all_metrics['pages'].append(page_metrics)

                print(f"[INFO]   Processed {blocks_processed} blocks, skipped {blocks_skipped}", file=sys.stderr)

            finally:
                Path(tmp_path).unlink(missing_ok=True)

        # Embed metrics in PDF metadata if requested
        if embed_metrics:
            metrics_json = json.dumps(all_metrics)
            out_doc.set_metadata({
                'keywords': f'tlacuilo_ocr_metrics:{metrics_json}'
            })

        # Save the output PDF
        out_doc.save(output_path, garbage=4, deflate=True)
        out_doc.close()
        doc.close()

        return {
            "success": True,
            "output_path": output_path,
            "mode": "editable",
            "pages_processed": len(all_metrics['pages']),
            "total_blocks": sum(len(p['blocks']) for p in all_metrics['pages']),
            "metrics_embedded": embed_metrics,
        }

    except Exception as e:
        import traceback
        print(f"[ERROR] Editable OCR failed: {traceback.format_exc()}", file=sys.stderr)
        return {
            "success": False,
            "error": str(e),
        }


def get_embedded_metrics(input_path: str) -> dict:
    """
    Extract embedded OCR metrics from a PDF.

    Returns the metrics if present, or indicates they're not available.
    """
    if not HAS_PYMUPDF:
        return {
            "success": False,
            "error": "PyMuPDF is required",
        }

    try:
        doc = fitz.open(input_path)
        metadata = doc.metadata
        doc.close()

        keywords = metadata.get('keywords', '')

        if keywords.startswith('tlacuilo_ocr_metrics:'):
            metrics_json = keywords[len('tlacuilo_ocr_metrics:'):]
            metrics = json.loads(metrics_json)
            return {
                "success": True,
                "has_metrics": True,
                "metrics": metrics,
            }

        return {
            "success": True,
            "has_metrics": False,
            "message": "No Tlacuilo OCR metrics found in this PDF",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="PDF OCR operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Check command
    check_parser = subparsers.add_parser("check", help="Check dependencies")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze PDF for OCR needs")
    analyze_parser.add_argument("--input", required=True, help="Input PDF path")

    # OCR command (searchable - invisible text layer)
    ocr_parser = subparsers.add_parser("ocr", help="Run OCR on PDF (searchable mode)")
    ocr_parser.add_argument("--input", required=True, help="Input PDF path")
    ocr_parser.add_argument("--output", required=True, help="Output PDF path")
    ocr_parser.add_argument("--language", default="eng", help="OCR language(s)")
    ocr_parser.add_argument("--deskew", action="store_true", help="Deskew pages")
    ocr_parser.add_argument("--rotate-pages", action="store_true", help="Auto-rotate pages")
    ocr_parser.add_argument("--remove-background", action="store_true", help="Remove background")
    ocr_parser.add_argument("--clean", action="store_true", help="Clean pages")
    ocr_parser.add_argument("--skip-text", action="store_true", help="Skip pages with text")
    ocr_parser.add_argument("--force-ocr", action="store_true", help="Force OCR")
    ocr_parser.add_argument("--redo-ocr", action="store_true", help="Redo existing OCR")
    ocr_parser.add_argument("--optimize", type=int, default=1, help="Optimization level 0-3")

    # OCR Editable command (editable - real text objects with visual metrics)
    editable_parser = subparsers.add_parser("ocr-editable", help="Run editable OCR on PDF")
    editable_parser.add_argument("--input", required=True, help="Input PDF path")
    editable_parser.add_argument("--output", required=True, help="Output PDF path")
    editable_parser.add_argument("--language", default="eng", help="OCR language(s)")
    editable_parser.add_argument("--dpi", type=int, default=300, help="DPI for rendering (default: 300)")
    editable_parser.add_argument("--font-family", default="auto", help="Font family (auto, serif, sans-serif)")
    editable_parser.add_argument("--preserve-images", action="store_true", default=True, help="Preserve original images")
    editable_parser.add_argument("--embed-metrics", action="store_true", default=True, help="Embed OCR metrics in PDF")

    # Get embedded metrics command
    metrics_parser = subparsers.add_parser("get-metrics", help="Get embedded OCR metrics from PDF")
    metrics_parser.add_argument("--input", required=True, help="Input PDF path")

    args = parser.parse_args()

    if args.command == "check":
        result = check_dependencies()
    elif args.command == "analyze":
        result = analyze_pdf(args.input)
    elif args.command == "ocr":
        result = run_ocr(
            input_path=args.input,
            output_path=args.output,
            language=args.language,
            deskew=args.deskew,
            rotate_pages=args.rotate_pages,
            remove_background=args.remove_background,
            clean=args.clean,
            skip_text=args.skip_text,
            force_ocr=args.force_ocr,
            redo_ocr=args.redo_ocr,
            optimize=args.optimize,
        )
    elif args.command == "ocr-editable":
        result = run_editable_ocr(
            input_path=args.input,
            output_path=args.output,
            language=args.language,
            dpi=args.dpi,
            font_family=args.font_family,
            preserve_images=args.preserve_images,
            embed_metrics=args.embed_metrics,
        )
    elif args.command == "get-metrics":
        result = get_embedded_metrics(args.input)
    else:
        result = {"error": f"Unknown command: {args.command}"}

    print(json.dumps(result))


if __name__ == "__main__":
    main()
