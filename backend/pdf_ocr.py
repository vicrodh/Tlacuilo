#!/usr/bin/env python3
"""
PDF OCR module using OCRmyPDF.

Provides OCR functionality for scanned PDFs:
- Text recognition using Tesseract
- Multiple language support
- PDF/A output option
- Skip text detection (for already OCR'd PDFs)
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import ocrmypdf
    from ocrmypdf import ExitCode
    HAS_OCRMYPDF = True
except ImportError:
    HAS_OCRMYPDF = False


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
                if "/XObject" in page.get("/Resources", {}):
                    xobjects = page["/Resources"].get("/XObject", {})
                    for obj in xobjects.values():
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


def main():
    parser = argparse.ArgumentParser(description="PDF OCR operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Check command
    check_parser = subparsers.add_parser("check", help="Check dependencies")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze PDF for OCR needs")
    analyze_parser.add_argument("--input", required=True, help="Input PDF path")

    # OCR command
    ocr_parser = subparsers.add_parser("ocr", help="Run OCR on PDF")
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
    else:
        result = {"error": f"Unknown command: {args.command}"}

    print(json.dumps(result))


if __name__ == "__main__":
    main()
