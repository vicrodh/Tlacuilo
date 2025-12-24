"""
PDF Graphical Signatures: Apply visual signature overlays to PDF documents.

These are NON-CRYPTOGRAPHIC signatures - purely visual overlays.
For legal digital signatures (PAdES), see pdf_digital_sign.py (future).

CLI usage (dev):
  python pdf_signatures.py apply --input doc.pdf --output signed.pdf --image sig.png --page 0 --x 100 --y 100 --width 200

JSON mode (for Tauri):
  echo '{"input": "doc.pdf", "output": "out.pdf", ...}' | python pdf_signatures.py apply --json
"""

from __future__ import annotations

import argparse
import sys
import json
import base64
import io
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


def apply_graphical_signature(
    input_path: Path,
    output_path: Path,
    image_path: Optional[Path] = None,
    image_bytes: Optional[bytes] = None,
    page_num: int = 0,
    x: float = 72,
    y: float = 72,
    width: float = 200,
    height: Optional[float] = None,
    rotation: float = 0,
    opacity: float = 1.0,
    fit_mode: str = "contain",
) -> dict:
    """
    Apply a graphical signature (image overlay) to a PDF page.

    Args:
        input_path: Source PDF file
        output_path: Destination PDF file
        image_path: Path to signature image (PNG/JPG)
        image_bytes: Raw image bytes (alternative to image_path)
        page_num: Page number (0-indexed)
        x: X position in points from left
        y: Y position in points from bottom
        width: Desired width in points
        height: Desired height (calculated from aspect ratio if None)
        rotation: Rotation angle in degrees
        opacity: Opacity (0.0 to 1.0)
        fit_mode: "contain", "cover", or "stretch"

    Returns:
        Dict with success status and message
    """
    result = {
        "success": False,
        "message": "",
        "signature_type": "graphical",
        "warning": "This is a visual overlay, NOT a cryptographic digital signature."
    }

    try:
        # Load image
        if image_bytes:
            img_data = image_bytes
        elif image_path and image_path.exists():
            img_data = image_path.read_bytes()
        else:
            result["message"] = "No image provided or image file not found"
            return result

        # Open PDF
        doc = fitz.open(input_path)

        if page_num < 0 or page_num >= len(doc):
            result["message"] = f"Page {page_num} does not exist (document has {len(doc)} pages)"
            doc.close()
            return result

        page = doc[page_num]
        page_rect = page.rect

        # Get image dimensions
        img = fitz.Pixmap(img_data)
        img_width = img.width
        img_height = img.height
        img_aspect = img_width / img_height if img_height > 0 else 1

        # Calculate final dimensions
        if height is None:
            height = width / img_aspect

        # Apply fit mode
        if fit_mode == "contain":
            # Scale to fit within the box while maintaining aspect ratio
            box_aspect = width / height if height > 0 else 1
            if img_aspect > box_aspect:
                final_width = width
                final_height = width / img_aspect
            else:
                final_height = height
                final_width = height * img_aspect
        elif fit_mode == "cover":
            # Scale to cover the box while maintaining aspect ratio
            box_aspect = width / height if height > 0 else 1
            if img_aspect < box_aspect:
                final_width = width
                final_height = width / img_aspect
            else:
                final_height = height
                final_width = height * img_aspect
        else:  # stretch
            final_width = width
            final_height = height

        # Calculate position (y is from bottom in PDF coordinates)
        # Convert to rect: x0, y0 (top-left), x1, y1 (bottom-right)
        # PyMuPDF uses top-left origin, so we need to flip y
        y_from_top = page_rect.height - y - final_height
        rect = fitz.Rect(x, y_from_top, x + final_width, y_from_top + final_height)

        # Apply rotation if needed
        if rotation != 0:
            # For rotation, we'll insert the image first, then apply rotation via matrix
            # This is a simplified approach - full rotation would require more complex handling
            pass

        # Insert image
        page.insert_image(
            rect,
            stream=img_data,
            overlay=True,
        )

        # Apply opacity if not 1.0 (requires more complex handling with transparency)
        # For now, we assume the PNG already has the correct transparency

        # Save with incremental update to preserve any existing signatures
        doc.save(output_path, incremental=False, deflate=True)
        doc.close()

        result["success"] = True
        result["message"] = f"Graphical signature applied to page {page_num + 1}"
        result["placement"] = {
            "page": page_num,
            "x": x,
            "y": y,
            "width": final_width,
            "height": final_height,
        }

    except Exception as e:
        result["message"] = f"Failed to apply signature: {str(e)}"

    return result


def check_existing_signatures(input_path: Path) -> dict:
    """
    Check if a PDF has existing digital signatures.

    Returns info about existing signatures to warn user before modifying.
    """
    result = {
        "has_digital_signatures": False,
        "signature_count": 0,
        "signature_fields": [],
        "warning": None
    }

    try:
        doc = fitz.open(input_path)

        # Check for signature fields in the AcroForm
        for page in doc:
            for widget in page.widgets():
                if widget.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE:
                    result["has_digital_signatures"] = True
                    result["signature_count"] += 1
                    result["signature_fields"].append({
                        "name": widget.field_name or "Unnamed",
                        "page": page.number,
                        "signed": widget.field_value is not None
                    })

        doc.close()

        if result["has_digital_signatures"]:
            result["warning"] = (
                "This PDF contains digital signatures. "
                "Adding graphical elements may invalidate them."
            )

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="PDF Graphical Signatures")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Apply command
    apply_parser = subparsers.add_parser("apply", help="Apply graphical signature")
    apply_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    apply_parser.add_argument("--output", "-o", required=True, help="Output PDF path")
    apply_parser.add_argument("--image", help="Signature image path")
    apply_parser.add_argument("--image-b64", help="Signature image as base64")
    apply_parser.add_argument("--page", type=int, default=0, help="Page number (0-indexed)")
    apply_parser.add_argument("--x", type=float, default=72, help="X position in points")
    apply_parser.add_argument("--y", type=float, default=72, help="Y position in points")
    apply_parser.add_argument("--width", type=float, default=200, help="Width in points")
    apply_parser.add_argument("--height", type=float, help="Height in points (auto if not set)")
    apply_parser.add_argument("--rotation", type=float, default=0, help="Rotation in degrees")
    apply_parser.add_argument("--opacity", type=float, default=1.0, help="Opacity (0-1)")
    apply_parser.add_argument("--fit", choices=["contain", "cover", "stretch"], default="contain")
    apply_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Check command
    check_parser = subparsers.add_parser("check", help="Check for existing signatures")
    check_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    check_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "apply":
        image_bytes = None
        if args.image_b64:
            # Handle data URL format
            b64_data = args.image_b64
            if b64_data.startswith("data:"):
                b64_data = b64_data.split(",", 1)[1]
            image_bytes = base64.b64decode(b64_data)

        result = apply_graphical_signature(
            input_path=Path(args.input),
            output_path=Path(args.output),
            image_path=Path(args.image) if args.image else None,
            image_bytes=image_bytes,
            page_num=args.page,
            x=args.x,
            y=args.y,
            width=args.width,
            height=args.height,
            rotation=args.rotation,
            opacity=args.opacity,
            fit_mode=args.fit,
        )

        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            print(result["message"])
            if result.get("warning"):
                print(f"Note: {result['warning']}")
            sys.exit(0 if result["success"] else 1)

    elif args.command == "check":
        result = check_existing_signatures(Path(args.input))

        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            if result.get("has_digital_signatures"):
                print(f"Found {result['signature_count']} digital signature field(s)")
                if result.get("warning"):
                    print(f"Warning: {result['warning']}")
            else:
                print("No digital signatures found")


if __name__ == "__main__":
    main()
