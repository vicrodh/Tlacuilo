"""
Image conversion module for Tlacuilo.

Handles bidirectional conversion between images and PDF:
- Multiple images → single PDF
- PDF pages → individual images

Uses PyMuPDF (fitz) for all operations.

CLI usage:
  python pdf_convert.py images-to-pdf --inputs img1.jpg img2.png --output out.pdf
  python pdf_convert.py pdf-to-images --input doc.pdf --output-dir ./images --format png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import fitz  # PyMuPDF

try:
    from exceptions import ConversionError, InvalidFileTypeError
    from utils import (
        validate_file_exists,
        validate_files_exist,
        ensure_output_dir,
        get_extension,
    )
except ImportError:
    from .exceptions import ConversionError, InvalidFileTypeError
    from .utils import (
        validate_file_exists,
        validate_files_exist,
        ensure_output_dir,
        get_extension,
    )


# Supported formats
INPUT_IMAGE_FORMATS = ["jpg", "jpeg", "png", "webp", "tiff", "tif", "bmp", "gif"]
OUTPUT_IMAGE_FORMATS = ["png", "jpg", "jpeg", "webp", "tiff"]

# Page sizes in points (72 points = 1 inch)
PAGE_SIZES = {
    "a4": fitz.paper_size("a4"),           # 595 x 842
    "letter": fitz.paper_size("letter"),   # 612 x 792
    "legal": fitz.paper_size("legal"),     # 612 x 1008
    "a3": fitz.paper_size("a3"),           # 842 x 1191
    "a5": fitz.paper_size("a5"),           # 420 x 595
    "fit": None,                            # Special: fit to image size
}


def get_supported_formats() -> dict[str, list[str]]:
    """
    Get supported image formats for input and output.

    Returns:
        Dict with 'input' and 'output' format lists.
    """
    return {
        "input": INPUT_IMAGE_FORMATS.copy(),
        "output": OUTPUT_IMAGE_FORMATS.copy(),
    }


def images_to_pdf(
    image_paths: Sequence[Path | str],
    output: Path | str,
    *,
    page_size: str = "a4",
    orientation: str = "auto",
    margin_mm: float = 0,
    quality: int = 95,
) -> Path:
    """
    Convert multiple images to a single PDF.

    Args:
        image_paths: List of image file paths (in order)
        output: Output PDF path
        page_size: Page size ("a4", "letter", "legal", "a3", "a5", "fit")
        orientation: "auto", "portrait", or "landscape"
        margin_mm: Margin in millimeters
        quality: JPEG quality for compression (1-100)

    Returns:
        Path to created PDF.

    Raises:
        InvalidFileTypeError: If image format is not supported.
        ConversionError: If conversion fails.
    """
    if not image_paths:
        raise ConversionError("images", "pdf", "No images provided")

    # Validate inputs
    validated_paths = validate_files_exist(image_paths, INPUT_IMAGE_FORMATS)
    output_path = Path(output).resolve()
    ensure_output_dir(output_path.parent)

    # Convert margin from mm to points (1 mm = 2.834645669 points)
    margin_pt = margin_mm * 2.834645669

    # Get base page size
    size_key = page_size.lower()
    if size_key not in PAGE_SIZES:
        raise ConversionError("images", "pdf", f"Unknown page size: {page_size}")

    base_size = PAGE_SIZES[size_key]

    try:
        doc = fitz.open()

        for img_path in validated_paths:
            # Open image to get dimensions
            img_doc = fitz.open(str(img_path))
            img_page = img_doc[0]
            img_rect = img_page.rect
            img_width = img_rect.width
            img_height = img_rect.height

            # Determine page dimensions
            if base_size is None:  # "fit" mode
                page_width = img_width + 2 * margin_pt
                page_height = img_height + 2 * margin_pt
            else:
                # Determine orientation
                if orientation == "auto":
                    # Match image orientation
                    is_landscape = img_width > img_height
                elif orientation == "landscape":
                    is_landscape = True
                else:  # portrait
                    is_landscape = False

                if is_landscape:
                    page_width = max(base_size[0], base_size[1])
                    page_height = min(base_size[0], base_size[1])
                else:
                    page_width = min(base_size[0], base_size[1])
                    page_height = max(base_size[0], base_size[1])

            # Create new page
            page = doc.new_page(width=page_width, height=page_height)

            # Calculate image placement (centered with margin)
            available_width = page_width - 2 * margin_pt
            available_height = page_height - 2 * margin_pt

            # Scale image to fit available area while maintaining aspect ratio
            scale_x = available_width / img_width
            scale_y = available_height / img_height
            scale = min(scale_x, scale_y, 1.0)  # Don't upscale

            final_width = img_width * scale
            final_height = img_height * scale

            # Center the image
            x_offset = margin_pt + (available_width - final_width) / 2
            y_offset = margin_pt + (available_height - final_height) / 2

            img_rect = fitz.Rect(
                x_offset,
                y_offset,
                x_offset + final_width,
                y_offset + final_height,
            )

            # Insert image
            page.insert_image(img_rect, filename=str(img_path))
            img_doc.close()

        # Save with compression
        doc.save(
            str(output_path),
            garbage=4,  # Maximum garbage collection
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
        )
        doc.close()

        return output_path

    except fitz.FitzError as e:
        raise ConversionError("images", "pdf", str(e)) from e


def pdf_to_images(
    pdf_path: Path | str,
    output_dir: Path | str,
    *,
    format: str = "png",
    dpi: int = 150,
    pages: str | None = None,
    prefix: str = "page",
) -> list[Path]:
    """
    Convert PDF pages to individual images.

    Args:
        pdf_path: Input PDF path
        output_dir: Directory for output images
        format: Output format ("png", "jpg", "webp", "tiff")
        dpi: Resolution in dots per inch
        pages: Page range string (e.g., "1-3,5,7") or None for all
        prefix: Output filename prefix

    Returns:
        List of created image paths.

    Raises:
        InvalidFileTypeError: If format is not supported.
        ConversionError: If conversion fails.
    """
    # Validate format
    fmt = format.lower()
    if fmt == "jpeg":
        fmt = "jpg"
    if fmt not in OUTPUT_IMAGE_FORMATS:
        raise InvalidFileTypeError(format, OUTPUT_IMAGE_FORMATS)

    # Validate input
    input_path = validate_file_exists(pdf_path, ["pdf"])
    out_dir = ensure_output_dir(output_dir)

    try:
        doc = fitz.open(str(input_path))
        total_pages = len(doc)

        # Parse page range
        page_indices = _parse_page_range(pages, total_pages) if pages else list(range(total_pages))

        # Calculate zoom factor from DPI (72 DPI is base)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        output_paths: list[Path] = []

        for idx in page_indices:
            if idx < 0 or idx >= total_pages:
                continue

            page = doc[idx]
            pix = page.get_pixmap(matrix=matrix)

            # Determine output path
            page_num = idx + 1  # 1-indexed for filename
            filename = f"{prefix}_{page_num:04d}.{fmt}"
            out_path = out_dir / filename

            # Save based on format
            if fmt == "png":
                pix.save(str(out_path))
            elif fmt in ("jpg", "jpeg"):
                pix.save(str(out_path), jpg_quality=95)
            elif fmt == "webp":
                # PyMuPDF doesn't support webp directly, use PIL
                from PIL import Image
                import io
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                img.save(str(out_path), "WEBP", quality=95)
            elif fmt == "tiff":
                from PIL import Image
                import io
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                img.save(str(out_path), "TIFF")

            output_paths.append(out_path)

        doc.close()
        return output_paths

    except fitz.FitzError as e:
        raise ConversionError("pdf", format, str(e)) from e


def _parse_page_range(range_str: str, total_pages: int) -> list[int]:
    """
    Parse a page range string into a list of 0-indexed page numbers.

    Args:
        range_str: Range string like "1-3,5,7-9"
        total_pages: Total number of pages in document

    Returns:
        List of 0-indexed page numbers.
    """
    result: list[int] = []
    parts = [p.strip() for p in range_str.split(",") if p.strip()]

    for part in parts:
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start = int(start_str) - 1  # Convert to 0-indexed
            end = int(end_str) - 1
            if start < 0:
                start = 0
            if end >= total_pages:
                end = total_pages - 1
            result.extend(range(start, end + 1))
        else:
            idx = int(part) - 1  # Convert to 0-indexed
            if 0 <= idx < total_pages:
                result.append(idx)

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for idx in result:
        if idx not in seen:
            seen.add(idx)
            unique.append(idx)

    return unique


def get_image_info(image_path: Path | str) -> dict:
    """
    Get information about an image file.

    Args:
        image_path: Path to image

    Returns:
        Dict with width, height, format, and size_bytes.
    """
    path = validate_file_exists(image_path, INPUT_IMAGE_FORMATS)

    doc = fitz.open(str(path))
    page = doc[0]
    rect = page.rect
    doc.close()

    return {
        "width": int(rect.width),
        "height": int(rect.height),
        "format": get_extension(path),
        "size_bytes": path.stat().st_size,
    }


# === CLI ===

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Image-PDF conversion")
    sub = parser.add_subparsers(dest="command", required=True)

    # images-to-pdf
    img2pdf = sub.add_parser("images-to-pdf", help="Convert images to PDF")
    img2pdf.add_argument("--inputs", nargs="+", required=True, help="Image paths")
    img2pdf.add_argument("--output", required=True, help="Output PDF path")
    img2pdf.add_argument("--page-size", default="a4", help="Page size (a4, letter, fit, etc.)")
    img2pdf.add_argument("--orientation", default="auto", help="portrait, landscape, or auto")
    img2pdf.add_argument("--margin", type=float, default=0, help="Margin in mm")
    img2pdf.add_argument("--quality", type=int, default=95, help="Image quality (1-100)")

    # pdf-to-images
    pdf2img = sub.add_parser("pdf-to-images", help="Convert PDF to images")
    pdf2img.add_argument("--input", required=True, help="Input PDF path")
    pdf2img.add_argument("--output-dir", required=True, help="Output directory")
    pdf2img.add_argument("--format", default="png", help="Output format (png, jpg, webp, tiff)")
    pdf2img.add_argument("--dpi", type=int, default=150, help="Resolution in DPI")
    pdf2img.add_argument("--pages", help="Page range (e.g., '1-3,5,7')")
    pdf2img.add_argument("--prefix", default="page", help="Filename prefix")

    return parser


def _main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "images-to-pdf":
            result = images_to_pdf(
                [Path(p) for p in args.inputs],
                Path(args.output),
                page_size=args.page_size,
                orientation=args.orientation,
                margin_mm=args.margin,
                quality=args.quality,
            )
            print(f"Created: {result}")

        elif args.command == "pdf-to-images":
            results = pdf_to_images(
                Path(args.input),
                Path(args.output_dir),
                format=args.format,
                dpi=args.dpi,
                pages=args.pages,
                prefix=args.prefix,
            )
            print(f"Created {len(results)} images:")
            for p in results:
                print(f"  {p}")

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
