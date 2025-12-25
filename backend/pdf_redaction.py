"""
PDF Redaction operations.

IMPORTANT: Redaction permanently removes content from the PDF. It does not just
cover content with a black box - it actually deletes the underlying text and images.

CLI usage (dev):
  python pdf_redaction.py mark --input doc.pdf --output out.pdf --page 0 --x0 100 --y0 100 --x1 300 --y1 150
  python pdf_redaction.py apply --input doc.pdf --output out.pdf
  python pdf_redaction.py verify --input doc.pdf
"""

from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


def add_redaction_mark(
    input_path: Path,
    output_path: Path,
    page_num: int,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    fill_color: tuple[float, float, float] = (0, 0, 0),  # Black
    text: Optional[str] = None,  # Optional replacement text
) -> dict:
    """
    Add a redaction annotation to mark an area for redaction.

    The redaction is NOT applied yet - this just marks the area.
    Call apply_redactions() to permanently remove the content.

    Coordinates are in PDF points (1/72 inch), origin at bottom-left.
    """
    result = {
        "success": False,
        "message": "",
        "page": page_num,
        "rect": [x0, y0, x1, y1],
    }

    try:
        doc = fitz.open(input_path)

        if page_num < 0 or page_num >= len(doc):
            result["message"] = f"Invalid page number: {page_num}"
            doc.close()
            return result

        page = doc[page_num]
        rect = fitz.Rect(x0, y0, x1, y1)

        # Add redaction annotation
        annot = page.add_redact_annot(
            rect,
            text=text,  # Replacement text (if any)
            fill=fill_color,
        )

        # Save with redaction marks (not applied yet)
        doc.save(output_path)
        doc.close()

        result["success"] = True
        result["message"] = f"Redaction mark added to page {page_num + 1}"

    except Exception as e:
        result["message"] = f"Failed to add redaction: {str(e)}"

    return result


def apply_redactions(
    input_path: Path,
    output_path: Path,
    images: bool = True,  # Whether to redact images
    graphics: bool = True,  # Whether to redact graphics/drawings
) -> dict:
    """
    Apply all pending redactions in the document.

    WARNING: This PERMANENTLY removes the marked content. It cannot be undone.
    The content is completely removed from the PDF, not just covered.
    """
    result = {
        "success": False,
        "message": "",
        "pages_affected": 0,
        "redactions_applied": 0,
    }

    try:
        doc = fitz.open(input_path)

        total_redactions = 0
        pages_affected = set()

        for page_num, page in enumerate(doc):
            # Find all redaction annotations
            redact_annots = [
                annot for annot in page.annots()
                if annot and annot.type[0] == fitz.PDF_ANNOT_REDACT
            ]

            if redact_annots:
                pages_affected.add(page_num)
                total_redactions += len(redact_annots)

                # Apply redactions for this page
                page.apply_redactions(
                    images=fitz.PDF_REDACT_IMAGE_REMOVE if images else fitz.PDF_REDACT_IMAGE_NONE,
                    graphics=fitz.PDF_REDACT_LINE_ART_IF_TOUCHED if graphics else fitz.PDF_REDACT_LINE_ART_NONE,
                )

        if total_redactions == 0:
            result["message"] = "No redaction marks found in document"
            doc.close()
            return result

        # Save with garbage collection to remove the redacted content
        doc.save(output_path, garbage=4, deflate=True)
        doc.close()

        result["success"] = True
        result["pages_affected"] = len(pages_affected)
        result["redactions_applied"] = total_redactions
        result["message"] = f"Applied {total_redactions} redaction(s) on {len(pages_affected)} page(s)"

    except Exception as e:
        result["message"] = f"Failed to apply redactions: {str(e)}"

    return result


def get_pending_redactions(input_path: Path) -> dict:
    """
    Get all pending redaction marks in the document.

    Returns info about redaction annotations that haven't been applied yet.
    """
    result = {
        "has_redactions": False,
        "count": 0,
        "redactions": [],
        "error": None,
    }

    try:
        doc = fitz.open(input_path)

        for page_num, page in enumerate(doc):
            for annot in page.annots():
                if annot and annot.type[0] == fitz.PDF_ANNOT_REDACT:
                    rect = annot.rect
                    result["redactions"].append({
                        "page": page_num,
                        "x0": rect.x0,
                        "y0": rect.y0,
                        "x1": rect.x1,
                        "y1": rect.y1,
                    })

        result["count"] = len(result["redactions"])
        result["has_redactions"] = result["count"] > 0
        doc.close()

    except Exception as e:
        result["error"] = str(e)

    return result


def verify_redaction(
    input_path: Path,
    page_num: int,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> dict:
    """
    Verify that content has been properly redacted in a given area.

    Checks if there's any remaining text or images in the specified rectangle.
    """
    result = {
        "area_clear": True,
        "text_found": "",
        "images_found": 0,
        "error": None,
    }

    try:
        doc = fitz.open(input_path)

        if page_num < 0 or page_num >= len(doc):
            result["error"] = f"Invalid page number: {page_num}"
            doc.close()
            return result

        page = doc[page_num]
        rect = fitz.Rect(x0, y0, x1, y1)

        # Check for remaining text
        text = page.get_text("text", clip=rect).strip()
        if text:
            result["area_clear"] = False
            result["text_found"] = text[:100]  # First 100 chars

        # Check for remaining images
        images = page.get_images(clip=rect)
        if images:
            result["area_clear"] = False
            result["images_found"] = len(images)

        doc.close()

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="PDF Redaction operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Mark command - add redaction annotation
    mark_parser = subparsers.add_parser("mark", help="Add redaction mark")
    mark_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    mark_parser.add_argument("--output", "-o", required=True, help="Output PDF path")
    mark_parser.add_argument("--page", "-p", type=int, required=True, help="Page number (0-indexed)")
    mark_parser.add_argument("--x0", type=float, required=True, help="Left X coordinate")
    mark_parser.add_argument("--y0", type=float, required=True, help="Bottom Y coordinate")
    mark_parser.add_argument("--x1", type=float, required=True, help="Right X coordinate")
    mark_parser.add_argument("--y1", type=float, required=True, help="Top Y coordinate")
    mark_parser.add_argument("--text", help="Replacement text (optional)")
    mark_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Apply command - apply all redactions
    apply_parser = subparsers.add_parser("apply", help="Apply all pending redactions")
    apply_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    apply_parser.add_argument("--output", "-o", required=True, help="Output PDF path")
    apply_parser.add_argument("--no-images", action="store_true", help="Don't redact images")
    apply_parser.add_argument("--no-graphics", action="store_true", help="Don't redact graphics")
    apply_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Pending command - list pending redactions
    pending_parser = subparsers.add_parser("pending", help="List pending redaction marks")
    pending_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    pending_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Verify command - verify redaction
    verify_parser = subparsers.add_parser("verify", help="Verify redaction was successful")
    verify_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    verify_parser.add_argument("--page", "-p", type=int, required=True, help="Page number (0-indexed)")
    verify_parser.add_argument("--x0", type=float, required=True, help="Left X coordinate")
    verify_parser.add_argument("--y0", type=float, required=True, help="Bottom Y coordinate")
    verify_parser.add_argument("--x1", type=float, required=True, help="Right X coordinate")
    verify_parser.add_argument("--y1", type=float, required=True, help="Top Y coordinate")
    verify_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "mark":
        result = add_redaction_mark(
            Path(args.input),
            Path(args.output),
            args.page,
            args.x0,
            args.y0,
            args.x1,
            args.y1,
            text=args.text,
        )

        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            print(result["message"])
            sys.exit(0 if result["success"] else 1)

    elif args.command == "apply":
        result = apply_redactions(
            Path(args.input),
            Path(args.output),
            images=not args.no_images,
            graphics=not args.no_graphics,
        )

        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            print(result["message"])
            sys.exit(0 if result["success"] else 1)

    elif args.command == "pending":
        result = get_pending_redactions(Path(args.input))

        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            if result.get("error"):
                print(f"Error: {result['error']}")
                sys.exit(1)
            if not result["has_redactions"]:
                print("No pending redaction marks")
            else:
                print(f"Found {result['count']} pending redaction(s):")
                for r in result["redactions"]:
                    print(f"  Page {r['page'] + 1}: ({r['x0']:.1f}, {r['y0']:.1f}) - ({r['x1']:.1f}, {r['y1']:.1f})")

    elif args.command == "verify":
        result = verify_redaction(
            Path(args.input),
            args.page,
            args.x0,
            args.y0,
            args.x1,
            args.y1,
        )

        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            if result.get("error"):
                print(f"Error: {result['error']}")
                sys.exit(1)
            if result["area_clear"]:
                print("Verification PASSED: Area is clear of content")
            else:
                print("Verification FAILED: Content remains in area")
                if result["text_found"]:
                    print(f"  Text found: {result['text_found'][:50]}...")
                if result["images_found"]:
                    print(f"  Images found: {result['images_found']}")
                sys.exit(1)


if __name__ == "__main__":
    main()
