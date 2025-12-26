"""
PDF Edit operations - Extract and modify PDF content.

Provides text block detection and content editing capabilities.
Uses PyMuPDF for extraction and manipulation.

CLI usage (dev):
  python pdf_edit.py text-blocks --input doc.pdf --page 0
  python pdf_edit.py insert-text --input doc.pdf --output out.pdf --page 0 --x 100 --y 100 --text "Hello"
  python pdf_edit.py preview --input doc.pdf --page 0 --edits '{"ops": [...]}'
"""

from __future__ import annotations

import argparse
import sys
import json
import base64
import io
import math
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


def get_text_blocks(
    input_path: Path,
    page_num: int,
) -> dict:
    """
    Extract text blocks from a PDF page with their positions.

    Returns blocks with coordinates in PDF points (origin bottom-left).
    Each block contains lines, and each line contains spans with font info.
    """
    result = {
        "success": False,
        "page": page_num,
        "blocks": [],
        "error": None,
    }

    try:
        doc = fitz.open(input_path)

        if page_num < 0 or page_num >= len(doc):
            result["error"] = f"Invalid page number: {page_num}"
            doc.close()
            return result

        page = doc[page_num]
        page_height = page.rect.height

        # Get text as dictionary with full details
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        blocks = []
        for block in text_dict.get("blocks", []):
            # Skip image blocks
            if block.get("type") != 0:
                continue

            block_data = {
                "id": f"block_{page_num}_{len(blocks)}",
                "bbox": {
                    "x0": block["bbox"][0],
                    "y0": block["bbox"][1],
                    "x1": block["bbox"][2],
                    "y1": block["bbox"][3],
                },
                # Normalized coordinates (0-1) for frontend
                "rect": {
                    "x": block["bbox"][0] / page.rect.width,
                    "y": block["bbox"][1] / page_height,
                    "width": (block["bbox"][2] - block["bbox"][0]) / page.rect.width,
                    "height": (block["bbox"][3] - block["bbox"][1]) / page_height,
                },
                "lines": [],
            }

            for line in block.get("lines", []):
                line_data = {
                    "bbox": {
                        "x0": line["bbox"][0],
                        "y0": line["bbox"][1],
                        "x1": line["bbox"][2],
                        "y1": line["bbox"][3],
                    },
                    "spans": [],
                }

                for span in line.get("spans", []):
                    span_data = {
                        "text": span.get("text", ""),
                        "font": span.get("font", ""),
                        "size": span.get("size", 12),
                        "color": span.get("color", 0),  # Integer color
                        "flags": span.get("flags", 0),  # Bold, italic, etc.
                        "bbox": {
                            "x0": span["bbox"][0],
                            "y0": span["bbox"][1],
                            "x1": span["bbox"][2],
                            "y1": span["bbox"][3],
                        },
                    }
                    line_data["spans"].append(span_data)

                block_data["lines"].append(line_data)

            # Get full text of block
            block_text = ""
            for line in block_data["lines"]:
                for span in line["spans"]:
                    block_text += span["text"]
                block_text += "\n"
            block_data["text"] = block_text.strip()

            blocks.append(block_data)

        result["success"] = True
        result["blocks"] = blocks
        result["page_width"] = page.rect.width
        result["page_height"] = page_height
        doc.close()

    except Exception as e:
        result["error"] = str(e)

    return result


def get_all_text_blocks(input_path: Path) -> dict:
    """
    Extract text blocks from all pages.
    """
    result = {
        "success": False,
        "pages": [],
        "error": None,
    }

    try:
        doc = fitz.open(input_path)

        for page_num in range(len(doc)):
            page_result = get_text_blocks(input_path, page_num)
            if page_result["success"]:
                result["pages"].append({
                    "page": page_num,
                    "blocks": page_result["blocks"],
                    "width": page_result["page_width"],
                    "height": page_result["page_height"],
                })

        result["success"] = True
        doc.close()

    except Exception as e:
        result["error"] = str(e)

    return result


def insert_text(
    input_path: Path,
    output_path: Path,
    page_num: int,
    x: float,
    y: float,
    text: str,
    font_name: str = "helv",
    font_size: float = 12,
    color: tuple = (0, 0, 0),
) -> dict:
    """
    Insert text at a specific position on a page.

    Coordinates are in PDF points, origin at bottom-left.
    """
    result = {
        "success": False,
        "message": "",
    }

    try:
        doc = fitz.open(input_path)

        if page_num < 0 or page_num >= len(doc):
            result["message"] = f"Invalid page number: {page_num}"
            doc.close()
            return result

        page = doc[page_num]

        # Insert text
        point = fitz.Point(x, y)
        rc = page.insert_text(
            point,
            text,
            fontname=font_name,
            fontsize=font_size,
            color=color,
        )

        if rc < 0:
            result["message"] = "Failed to insert text"
            doc.close()
            return result

        doc.save(output_path)
        doc.close()

        result["success"] = True
        result["message"] = f"Text inserted at ({x}, {y})"

    except Exception as e:
        result["message"] = str(e)

    return result


def replace_text_area(
    input_path: Path,
    output_path: Path,
    page_num: int,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    new_text: str,
    font_name: str = "helv",
    font_size: float = 12,
    color: tuple = (0, 0, 0),
) -> dict:
    """
    Replace text in a rectangular area.

    1. Adds a redaction annotation to remove existing content
    2. Applies the redaction
    3. Inserts new text at the position
    """
    result = {
        "success": False,
        "message": "",
    }

    try:
        doc = fitz.open(input_path)

        if page_num < 0 or page_num >= len(doc):
            result["message"] = f"Invalid page number: {page_num}"
            doc.close()
            return result

        page = doc[page_num]
        rect = fitz.Rect(x0, y0, x1, y1)

        # Step 1: Add redaction to remove existing content
        page.add_redact_annot(rect, fill=(1, 1, 1))  # White fill

        # Step 2: Apply redaction
        page.apply_redactions()

        # Step 3: Insert new text
        # Position at top-left of the rect, adjusted for text baseline
        text_point = fitz.Point(x0, y0 + font_size)
        page.insert_text(
            text_point,
            new_text,
            fontname=font_name,
            fontsize=font_size,
            color=color,
        )

        doc.save(output_path, garbage=4, deflate=True)
        doc.close()

        result["success"] = True
        result["message"] = f"Text replaced in area"

    except Exception as e:
        result["message"] = str(e)

    return result


def insert_image(
    input_path: Path,
    output_path: Path,
    image_path: Path,
    page_num: int,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    keep_aspect: bool = True,
) -> dict:
    """
    Insert an image at a specific position on a page.
    """
    result = {
        "success": False,
        "message": "",
    }

    try:
        doc = fitz.open(input_path)

        if page_num < 0 or page_num >= len(doc):
            result["message"] = f"Invalid page number: {page_num}"
            doc.close()
            return result

        page = doc[page_num]
        rect = fitz.Rect(x0, y0, x1, y1)

        # Insert image
        page.insert_image(rect, filename=str(image_path), keep_proportion=keep_aspect)

        doc.save(output_path)
        doc.close()

        result["success"] = True
        result["message"] = f"Image inserted"

    except Exception as e:
        result["message"] = str(e)

    return result


def apply_edits(
    input_path: Path,
    output_path: Path,
    edits_json: str,
) -> dict:
    """
    Apply multiple edit operations to a PDF.

    edits_json format:
    {
        "ops": [
            {
                "type": "insert_text" | "replace_text" | "draw_shape",
                "page": 0,  # 0-indexed
                "rect": { "x": 0.1, "y": 0.1, "width": 0.3, "height": 0.05 },  # normalized
                "text": "Hello",  # for text ops
                "style": { "fontFamily": "Helvetica", "fontSize": 12, "color": "#000000" },
                "shape": "rect" | "ellipse" | "line",  # for draw_shape
                "strokeColor": "#000000",
                "strokeWidth": 1,
                "fillColor": "#FFFFFF"  # optional
            }
        ],
        "pageWidths": { "0": 612, "1": 612 },   # page width in points
        "pageHeights": { "0": 792, "1": 792 }   # page height in points
    }
    """
    result = {
        "success": False,
        "message": "",
        "applied": 0,
    }

    try:
        edits = json.loads(edits_json)
        ops = edits.get("ops", [])
        page_widths = edits.get("pageWidths", {})
        page_heights = edits.get("pageHeights", {})

        if not ops:
            result["success"] = True
            result["message"] = "No operations to apply"
            return result

        doc = fitz.open(input_path)
        applied_count = 0

        for op in ops:
            op_type = op.get("type")
            page_num = op.get("page", 0)

            if page_num < 0 or page_num >= len(doc):
                continue

            page = doc[page_num]
            page_width = float(page_widths.get(str(page_num), page.rect.width))
            page_height = float(page_heights.get(str(page_num), page.rect.height))

            # Convert normalized rect to PDF points
            rect = op.get("rect", {})
            x0 = rect.get("x", 0) * page_width
            y0 = rect.get("y", 0) * page_height
            w = rect.get("width", 0) * page_width
            h = rect.get("height", 0) * page_height
            x1 = x0 + w
            y1 = y0 + h

            if op_type == "insert_text":
                text = op.get("text", "")
                style = op.get("style", {})
                css_font = style.get("fontFamily", "helv")
                font_size = style.get("fontSize", 12)
                color_str = style.get("color", "#000000")
                rotation = style.get("rotation", 0)  # Text rotation in degrees

                # Parse hex color to RGB tuple
                color = parse_hex_color(color_str)

                # Parse CSS font-family to PyMuPDF font name
                font_name = parse_css_font_family(css_font)

                # Insert at top-left of rect, adjusted for baseline
                point = fitz.Point(x0, y0 + font_size)
                page.insert_text(
                    point,
                    text,
                    fontname=font_name,
                    fontsize=font_size,
                    color=color,
                    rotate=int(rotation) if rotation else 0,
                )
                applied_count += 1

            elif op_type == "replace_text":
                text = op.get("text", "")
                style = op.get("style", {})
                css_font = style.get("fontFamily", "helv")
                font_size = style.get("fontSize", 12)
                color_str = style.get("color", "#000000")
                rotation = style.get("rotation", 0)  # Text rotation in degrees
                color = parse_hex_color(color_str)
                is_bold = style.get("bold", False)
                is_italic = style.get("italic", False)

                # Parse CSS font-family to PyMuPDF font name
                font_name = parse_css_font_family(css_font)

                # Scale font size to compensate for PyMuPDF built-in font metrics
                # being slightly smaller than typical document fonts
                font_size = font_size * 1.08

                # Extend redaction rect downward to cover descenders (letters like p, g, j, q)
                # Descenders typically extend ~25% of font size below baseline
                descender_extension = font_size * 0.3
                redact_rect = fitz.Rect(x0, y0, x1, y1 + descender_extension)
                page.add_redact_annot(redact_rect, fill=(1, 1, 1))  # White fill
                page.apply_redactions()

                # Use insert_textbox for multi-line text to properly fit within the area
                # This handles line wrapping and vertical alignment
                text_rect = fitz.Rect(x0, y0, x1, y1)
                page.insert_textbox(
                    text_rect,
                    text,
                    fontname=font_name,
                    fontsize=font_size,
                    color=color,
                    rotate=int(rotation) if rotation else 0,
                    align=0,  # 0 = left, 1 = center, 2 = right
                )
                applied_count += 1

            elif op_type == "draw_shape":
                shape_type = op.get("shape", "rect")
                stroke_color_str = op.get("strokeColor", "#000000")
                stroke_width = op.get("strokeWidth", 1)
                fill_color_str = op.get("fillColor")

                stroke_color = parse_hex_color(stroke_color_str)
                fill_color = parse_hex_color(fill_color_str) if fill_color_str else None

                shape = page.new_shape()
                draw_rect = fitz.Rect(x0, y0, x1, y1)

                if shape_type == "rect":
                    shape.draw_rect(draw_rect)
                elif shape_type == "ellipse":
                    shape.draw_oval(draw_rect)
                elif shape_type == "line":
                    shape.draw_line(fitz.Point(x0, y1), fitz.Point(x1, y0))

                shape.finish(
                    color=stroke_color,
                    fill=fill_color,
                    width=stroke_width,
                )
                shape.commit()
                applied_count += 1

        doc.save(output_path, garbage=4, deflate=True)
        doc.close()

        result["success"] = True
        result["message"] = f"Applied {applied_count} edit(s)"
        result["applied"] = applied_count

    except Exception as e:
        result["message"] = str(e)

    return result


def parse_hex_color(hex_str: str) -> tuple:
    """Parse hex color string to RGB tuple (0-1 range)."""
    if not hex_str:
        return (0, 0, 0)
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 6:
        r = int(hex_str[0:2], 16) / 255
        g = int(hex_str[2:4], 16) / 255
        b = int(hex_str[4:6], 16) / 255
        return (r, g, b)
    return (0, 0, 0)


def parse_css_font_family(css_font: str) -> str:
    """
    Parse CSS font-family string and return PyMuPDF font name.

    CSS font families look like: '"Times New Roman", Times, Georgia, serif'
    We extract the first font name and map it to PyMuPDF's built-in fonts.

    PRIORITY: Font name detection > serif category > monospace category
    (Reduces false monospace detection from OCR documents)
    """
    if not css_font:
        return "tiro"  # Default to serif for documents

    # Split by comma and get individual font names
    fonts = [f.strip().strip('"').strip("'") for f in css_font.split(",")]

    # Check the last token for font category (serif, sans-serif, monospace)
    category = fonts[-1].lower() if fonts else ""

    # Map specific fonts to PyMuPDF names
    font_map = {
        # Serif fonts
        "times new roman": "tiro",
        "times": "tiro",
        "georgia": "tiro",
        "palatino": "tiro",
        "palatino linotype": "tiro",
        "book antiqua": "tiro",
        "garamond": "tiro",
        "cambria": "tiro",
        "dejavu serif": "tiro",
        "liberation serif": "tiro",
        "noto serif": "tiro",
        "freeserif": "tiro",

        # Sans-serif fonts
        "arial": "helv",
        "helvetica": "helv",
        "verdana": "helv",
        "tahoma": "helv",
        "trebuchet ms": "helv",
        "calibri": "helv",
        "dejavu sans": "helv",
        "liberation sans": "helv",
        "noto sans": "helv",
        "freesans": "helv",

        # Monospace fonts (only match if explicitly named)
        "courier": "cour",
        "courier new": "cour",
        "consolas": "cour",
        "monaco": "cour",
        "dejavu sans mono": "cour",
        "liberation mono": "cour",
        "noto mono": "cour",
        "freemono": "cour",
    }

    # Try to match specific fonts first
    for font in fonts:
        font_lower = font.lower()
        if font_lower in font_map:
            return font_map[font_lower]

    # Fall back to category - prioritize serif over monospace
    if category == "serif":
        return "tiro"  # Times Roman
    elif category == "sans-serif":
        return "helv"  # Helvetica
    elif category == "monospace":
        return "cour"  # Courier
    else:
        # Default to serif for documents (most common in formal documents)
        return "tiro"


def int_color_to_hex(color_int: int) -> str:
    """Convert PyMuPDF integer color to hex string."""
    # PyMuPDF stores color as integer: 0xRRGGBB
    r = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    b = color_int & 0xFF
    return f"#{r:02x}{g:02x}{b:02x}"


def render_page_preview(
    input_path: Path,
    page_num: int,
    edits_json: str,
    dpi: int = 150,
) -> dict:
    """
    Render a page with edits applied as a PNG image (base64).

    This provides live preview without saving the file.
    Returns base64-encoded PNG data.
    """
    result = {
        "success": False,
        "image": "",  # base64 PNG
        "width": 0,
        "height": 0,
        "error": None,
    }

    try:
        edits = json.loads(edits_json) if edits_json else {"ops": []}
        ops = edits.get("ops", [])

        doc = fitz.open(input_path)

        if page_num < 0 or page_num >= len(doc):
            result["error"] = f"Invalid page number: {page_num}"
            doc.close()
            return result

        page = doc[page_num]
        page_width = page.rect.width
        page_height = page.rect.height

        # Apply edits to this page
        for op in ops:
            op_page = op.get("page", 0)
            if op_page != page_num:
                continue

            op_type = op.get("type")
            rect = op.get("rect", {})

            # Convert normalized rect to PDF points
            x0 = rect.get("x", 0) * page_width
            y0 = rect.get("y", 0) * page_height
            w = rect.get("width", 0) * page_width
            h = rect.get("height", 0) * page_height
            x1 = x0 + w
            y1 = y0 + h

            if op_type == "insert_text":
                text = op.get("text", "")
                if not text:
                    continue
                style = op.get("style", {})
                css_font = style.get("fontFamily", "helv")
                font_size = style.get("fontSize", 12)
                color_str = style.get("color", "#000000")
                rotation = style.get("rotation", 0)
                color = parse_hex_color(color_str)

                # Parse CSS font-family to PyMuPDF font name
                font_name = parse_css_font_family(css_font)

                point = fitz.Point(x0, y0 + font_size)
                page.insert_text(
                    point,
                    text,
                    fontname=font_name,
                    fontsize=font_size,
                    color=color,
                    rotate=int(rotation) if rotation else 0,
                )

            elif op_type == "replace_text":
                text = op.get("text", "")
                style = op.get("style", {})
                css_font = style.get("fontFamily", "helv")
                font_size = style.get("fontSize", 12)
                color_str = style.get("color", "#000000")
                rotation = style.get("rotation", 0)
                color = parse_hex_color(color_str)

                # Parse CSS font-family to PyMuPDF font name
                font_name = parse_css_font_family(css_font)

                # Scale font size to compensate for PyMuPDF built-in font metrics
                font_size = font_size * 1.08

                # Extend redaction rect for descenders (letters like p, g, j, q)
                descender_extension = font_size * 0.3
                redact_rect = fitz.Rect(x0, y0, x1, y1 + descender_extension)
                page.add_redact_annot(redact_rect, fill=(1, 1, 1))
                page.apply_redactions()

                # Use insert_textbox for multi-line text
                if text:
                    text_rect = fitz.Rect(x0, y0, x1, y1)
                    page.insert_textbox(
                        text_rect,
                        text,
                        fontname=font_name,
                        fontsize=font_size,
                        color=color,
                        rotate=int(rotation) if rotation else 0,
                        align=0,
                    )

            elif op_type == "draw_shape":
                shape_type = op.get("shape", "rect")
                stroke_color_str = op.get("strokeColor", "#000000")
                stroke_width = op.get("strokeWidth", 1)
                fill_color_str = op.get("fillColor")

                stroke_color = parse_hex_color(stroke_color_str)
                fill_color = parse_hex_color(fill_color_str) if fill_color_str else None

                shape = page.new_shape()
                draw_rect = fitz.Rect(x0, y0, x1, y1)

                if shape_type == "rect":
                    shape.draw_rect(draw_rect)
                elif shape_type == "ellipse":
                    shape.draw_oval(draw_rect)
                elif shape_type == "line":
                    shape.draw_line(fitz.Point(x0, y1), fitz.Point(x1, y0))

                shape.finish(
                    color=stroke_color,
                    fill=fill_color,
                    width=stroke_width,
                )
                shape.commit()

        # Render page to pixmap
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # Convert to PNG bytes
        png_bytes = pix.tobytes("png")

        # Encode as base64
        b64_data = base64.b64encode(png_bytes).decode("utf-8")

        result["success"] = True
        result["image"] = b64_data
        result["width"] = pix.width
        result["height"] = pix.height

        doc.close()

    except Exception as e:
        result["error"] = str(e)

    return result


def get_text_blocks_with_fonts(
    input_path: Path,
    page_num: int,
) -> dict:
    """
    Extract text blocks with detailed font information.

    Returns blocks with font name, size, color for each span.
    This uses PyMuPDF's dict extraction which has full font details.
    """
    result = {
        "success": False,
        "page": page_num,
        "blocks": [],
        "error": None,
    }

    try:
        doc = fitz.open(input_path)

        if page_num < 0 or page_num >= len(doc):
            result["error"] = f"Invalid page number: {page_num}"
            doc.close()
            return result

        page = doc[page_num]
        page_width = page.rect.width
        page_height = page.rect.height

        # Get text with full details
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        blocks = []
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # Skip image blocks
                continue

            block_data = {
                "rect": {
                    "x": block["bbox"][0] / page_width,
                    "y": block["bbox"][1] / page_height,
                    "width": (block["bbox"][2] - block["bbox"][0]) / page_width,
                    "height": (block["bbox"][3] - block["bbox"][1]) / page_height,
                },
                "lines": [],
                "dominantFont": None,
                "dominantSize": None,
                "dominantColor": None,
            }

            # Track font usage to find dominant style
            font_counts = {}
            size_counts = {}
            color_counts = {}

            # Track serif/monospace flags
            serif_count = 0
            mono_count = 0
            total_char_count = 0

            for line in block.get("lines", []):
                # Get line direction/rotation (dir is a tuple [cos, sin] of the angle)
                line_dir = line.get("dir", (1.0, 0.0))  # Default horizontal
                # Calculate rotation angle in degrees from direction vector
                rotation_rad = math.atan2(line_dir[1], line_dir[0])
                rotation_deg = math.degrees(rotation_rad)

                line_data = {
                    "rect": {
                        "x": line["bbox"][0] / page_width,
                        "y": line["bbox"][1] / page_height,
                        "width": (line["bbox"][2] - line["bbox"][0]) / page_width,
                        "height": (line["bbox"][3] - line["bbox"][1]) / page_height,
                    },
                    "rotation": round(rotation_deg, 2),  # Text rotation angle
                    "spans": [],
                }

                for span in line.get("spans", []):
                    font = span.get("font", "")
                    size = span.get("size", 12)
                    color_int = span.get("color", 0)
                    flags = span.get("flags", 0)
                    text = span.get("text", "")

                    # Count for dominant detection
                    text_len = len(text)
                    font_counts[font] = font_counts.get(font, 0) + text_len
                    size_counts[size] = size_counts.get(size, 0) + text_len
                    color_counts[color_int] = color_counts.get(color_int, 0) + text_len

                    # Font type flags from PyMuPDF:
                    # bit 0 = superscript, bit 1 = italic, bit 2 = serifed,
                    # bit 3 = monospaced, bit 4 = bold
                    is_serif = bool(flags & (1 << 2))  # bit 2
                    is_mono = bool(flags & (1 << 3))   # bit 3

                    if text.strip():
                        total_char_count += text_len
                        if is_serif:
                            serif_count += text_len
                        if is_mono:
                            mono_count += text_len

                    span_data = {
                        "text": text,
                        "font": font,
                        "size": round(size, 1),
                        "color": int_color_to_hex(color_int),
                        "bold": bool(flags & (1 << 4)),  # bit 4 = bold
                        "italic": bool(flags & (1 << 1)),  # bit 1 = italic
                        "serif": is_serif,  # bit 2 = serifed
                        "mono": is_mono,    # bit 3 = monospaced
                        "rect": {
                            "x": span["bbox"][0] / page_width,
                            "y": span["bbox"][1] / page_height,
                            "width": (span["bbox"][2] - span["bbox"][0]) / page_width,
                            "height": (span["bbox"][3] - span["bbox"][1]) / page_height,
                        },
                    }
                    line_data["spans"].append(span_data)

                block_data["lines"].append(line_data)

            # Determine dominant font type (serif/mono/sans)
            if total_char_count > 0:
                block_data["isSerif"] = serif_count > total_char_count * 0.5
                block_data["isMono"] = mono_count > total_char_count * 0.5
            else:
                block_data["isSerif"] = False
                block_data["isMono"] = False

            # Calculate average rotation for the block
            rotations = [line["rotation"] for line in block_data["lines"] if line.get("rotation") is not None]
            if rotations:
                block_data["rotation"] = round(sum(rotations) / len(rotations), 2)
            else:
                block_data["rotation"] = 0.0

            # Set dominant font info
            if font_counts:
                block_data["dominantFont"] = max(font_counts, key=font_counts.get)
            if size_counts:
                block_data["dominantSize"] = max(size_counts, key=size_counts.get)
            if color_counts:
                dominant_color = max(color_counts, key=color_counts.get)
                block_data["dominantColor"] = int_color_to_hex(dominant_color)

            # Get full text
            text_parts = []
            for line in block_data["lines"]:
                line_text = "".join(s["text"] for s in line["spans"])
                text_parts.append(line_text)
            block_data["text"] = "\n".join(text_parts)

            blocks.append(block_data)

        result["success"] = True
        result["blocks"] = blocks
        result["pageWidth"] = page_width
        result["pageHeight"] = page_height
        doc.close()

    except Exception as e:
        result["error"] = str(e)

    return result


def draw_shape(
    input_path: Path,
    output_path: Path,
    page_num: int,
    shape_type: str,  # 'rect', 'ellipse', 'line'
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    stroke_color: tuple = (0, 0, 0),
    stroke_width: float = 1,
    fill_color: Optional[tuple] = None,
) -> dict:
    """
    Draw a shape on a page.
    """
    result = {
        "success": False,
        "message": "",
    }

    try:
        doc = fitz.open(input_path)

        if page_num < 0 or page_num >= len(doc):
            result["message"] = f"Invalid page number: {page_num}"
            doc.close()
            return result

        page = doc[page_num]
        shape = page.new_shape()

        rect = fitz.Rect(x0, y0, x1, y1)

        if shape_type == "rect":
            shape.draw_rect(rect)
        elif shape_type == "ellipse":
            shape.draw_oval(rect)
        elif shape_type == "line":
            shape.draw_line(fitz.Point(x0, y1), fitz.Point(x1, y0))
        else:
            result["message"] = f"Unknown shape type: {shape_type}"
            doc.close()
            return result

        shape.finish(
            color=stroke_color,
            fill=fill_color,
            width=stroke_width,
        )
        shape.commit()

        doc.save(output_path)
        doc.close()

        result["success"] = True
        result["message"] = f"Shape drawn"

    except Exception as e:
        result["message"] = str(e)

    return result


def analyze_fonts(input_path: Path) -> dict:
    """
    Analyze fonts used in a PDF document.

    Returns information about each font including:
    - Font name and properties
    - Whether it's embedded/subset
    - System font availability
    - Suggested alternatives with similarity scores
    """
    result = {
        "success": False,
        "fonts": [],
        "summary": {
            "total": 0,
            "embedded": 0,
            "missing": 0,
            "low_match": 0,
        },
        "error": None,
    }

    # Known system fonts and their properties for matching
    SYSTEM_FONTS = {
        # Serif fonts
        "times new roman": {"type": "serif", "weight": "normal", "style": "normal"},
        "times": {"type": "serif", "weight": "normal", "style": "normal"},
        "georgia": {"type": "serif", "weight": "normal", "style": "normal"},
        "palatino": {"type": "serif", "weight": "normal", "style": "normal"},
        "garamond": {"type": "serif", "weight": "normal", "style": "normal"},
        "cambria": {"type": "serif", "weight": "normal", "style": "normal"},
        "book antiqua": {"type": "serif", "weight": "normal", "style": "normal"},
        "liberation serif": {"type": "serif", "weight": "normal", "style": "normal"},
        "dejavu serif": {"type": "serif", "weight": "normal", "style": "normal"},
        "noto serif": {"type": "serif", "weight": "normal", "style": "normal"},
        "tiro": {"type": "serif", "weight": "normal", "style": "normal"},

        # Sans-serif fonts
        "arial": {"type": "sans", "weight": "normal", "style": "normal"},
        "helvetica": {"type": "sans", "weight": "normal", "style": "normal"},
        "verdana": {"type": "sans", "weight": "normal", "style": "normal"},
        "tahoma": {"type": "sans", "weight": "normal", "style": "normal"},
        "calibri": {"type": "sans", "weight": "normal", "style": "normal"},
        "trebuchet ms": {"type": "sans", "weight": "normal", "style": "normal"},
        "liberation sans": {"type": "sans", "weight": "normal", "style": "normal"},
        "dejavu sans": {"type": "sans", "weight": "normal", "style": "normal"},
        "noto sans": {"type": "sans", "weight": "normal", "style": "normal"},
        "helv": {"type": "sans", "weight": "normal", "style": "normal"},

        # Monospace fonts
        "courier": {"type": "mono", "weight": "normal", "style": "normal"},
        "courier new": {"type": "mono", "weight": "normal", "style": "normal"},
        "consolas": {"type": "mono", "weight": "normal", "style": "normal"},
        "monaco": {"type": "mono", "weight": "normal", "style": "normal"},
        "liberation mono": {"type": "mono", "weight": "normal", "style": "normal"},
        "dejavu sans mono": {"type": "mono", "weight": "normal", "style": "normal"},
        "noto mono": {"type": "mono", "weight": "normal", "style": "normal"},
        "cour": {"type": "mono", "weight": "normal", "style": "normal"},
    }

    def get_font_type(font_name: str, flags: int) -> str:
        """Determine font type from name and flags."""
        name_lower = font_name.lower()

        # Check name first
        if any(x in name_lower for x in ["courier", "mono", "consol", "fixed"]):
            return "mono"
        if any(x in name_lower for x in ["times", "roman", "serif", "georgia", "palatino", "garamond"]):
            if "sans" not in name_lower:
                return "serif"
        if any(x in name_lower for x in ["arial", "helv", "helvetica", "verdana", "calibri", "sans", "gothic"]):
            return "sans"

        # Fall back to flags
        # bit 2 = serif, bit 3 = monospace
        if flags & (1 << 3):  # monospace
            return "mono"
        if flags & (1 << 2):  # serif
            return "serif"

        return "sans"  # Default

    def calculate_similarity(pdf_font: dict, system_font: dict) -> float:
        """Calculate similarity score between PDF font and system font."""
        score = 0.0

        # Type match is most important (50%)
        if pdf_font["type"] == system_font["type"]:
            score += 0.5
        elif pdf_font["type"] == "serif" and system_font["type"] == "sans":
            score += 0.1  # Low match
        elif pdf_font["type"] == "sans" and system_font["type"] == "serif":
            score += 0.1

        # Weight match (25%)
        if pdf_font.get("bold") == (system_font.get("weight") == "bold"):
            score += 0.25
        else:
            score += 0.1

        # Style match (25%)
        if pdf_font.get("italic") == (system_font.get("style") == "italic"):
            score += 0.25
        else:
            score += 0.1

        return score

    def find_best_matches(font_info: dict) -> list:
        """Find best matching system fonts."""
        matches = []

        for sys_name, sys_props in SYSTEM_FONTS.items():
            similarity = calculate_similarity(font_info, sys_props)

            # Bonus for name similarity
            pdf_name = font_info["name"].lower()
            if sys_name in pdf_name or pdf_name in sys_name:
                similarity = min(1.0, similarity + 0.3)

            matches.append({
                "name": sys_name.title(),
                "similarity": round(similarity * 100),
            })

        # Sort by similarity and return top 3
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches[:3]

    try:
        doc = fitz.open(input_path)

        # Collect all fonts from all pages
        all_fonts = {}  # font_name -> font_info

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Get fonts used on this page
            font_list = page.get_fonts(full=True)

            for font in font_list:
                # font tuple: (xref, ext, type, basefont, name, encoding, ref_name)
                xref, ext, font_type, basefont, name, encoding, ref_name = font[:7] if len(font) >= 7 else (font + (None,) * (7 - len(font)))

                # Use basefont or name
                font_name = basefont or name or f"Unknown-{xref}"

                # Clean up font name (remove subset prefix like ABCDEF+)
                clean_name = font_name
                if "+" in font_name:
                    clean_name = font_name.split("+", 1)[1]

                if clean_name not in all_fonts:
                    all_fonts[clean_name] = {
                        "original_name": font_name,
                        "clean_name": clean_name,
                        "xref": xref,
                        "type": font_type,
                        "encoding": encoding,
                        "pages": [],
                        "is_subset": "+" in font_name,
                        "is_embedded": ext not in ["", None, "n/a"],
                    }

                if page_num + 1 not in all_fonts[clean_name]["pages"]:
                    all_fonts[clean_name]["pages"].append(page_num + 1)

        # Analyze each font
        fonts_list = []
        missing_count = 0
        low_match_count = 0
        embedded_count = 0

        for font_name, font_data in all_fonts.items():
            # Determine font properties
            name_lower = font_name.lower()

            # Detect bold/italic from name
            is_bold = any(x in name_lower for x in ["bold", "black", "heavy", "demi"])
            is_italic = any(x in name_lower for x in ["italic", "oblique", "slant"])

            # Detect font type
            font_type = get_font_type(font_name, 0)

            font_info = {
                "name": font_name,
                "originalName": font_data["original_name"],
                "type": font_type,
                "bold": is_bold,
                "italic": is_italic,
                "embedded": font_data["is_embedded"],
                "subset": font_data["is_subset"],
                "pages": font_data["pages"],
                "pageCount": len(font_data["pages"]),
            }

            # Find best matches
            matches = find_best_matches(font_info)
            font_info["matches"] = matches
            font_info["bestMatch"] = matches[0] if matches else None
            font_info["bestMatchScore"] = matches[0]["similarity"] if matches else 0

            # Check if we have a good match
            if font_info["bestMatchScore"] < 85:
                low_match_count += 1
                font_info["status"] = "low_match"
            elif not font_data["is_embedded"]:
                missing_count += 1
                font_info["status"] = "missing"
            else:
                font_info["status"] = "ok"

            if font_data["is_embedded"]:
                embedded_count += 1

            fonts_list.append(font_info)

        # Sort by page count (most used first)
        fonts_list.sort(key=lambda x: x["pageCount"], reverse=True)

        result["success"] = True
        result["fonts"] = fonts_list
        result["summary"] = {
            "total": len(fonts_list),
            "embedded": embedded_count,
            "missing": missing_count,
            "low_match": low_match_count,
        }

        doc.close()

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="PDF Edit operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Text blocks command
    blocks_parser = subparsers.add_parser("text-blocks", help="Get text blocks from page")
    blocks_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    blocks_parser.add_argument("--page", "-p", type=int, required=True, help="Page number (0-indexed)")
    blocks_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Insert text command
    insert_parser = subparsers.add_parser("insert-text", help="Insert text")
    insert_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    insert_parser.add_argument("--output", "-o", required=True, help="Output PDF path")
    insert_parser.add_argument("--page", "-p", type=int, required=True, help="Page number")
    insert_parser.add_argument("--x", type=float, required=True, help="X coordinate")
    insert_parser.add_argument("--y", type=float, required=True, help="Y coordinate")
    insert_parser.add_argument("--text", "-t", required=True, help="Text to insert")
    insert_parser.add_argument("--font", default="helv", help="Font name")
    insert_parser.add_argument("--size", type=float, default=12, help="Font size")
    insert_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Replace text command
    replace_parser = subparsers.add_parser("replace-text", help="Replace text in area")
    replace_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    replace_parser.add_argument("--output", "-o", required=True, help="Output PDF path")
    replace_parser.add_argument("--page", "-p", type=int, required=True, help="Page number")
    replace_parser.add_argument("--x0", type=float, required=True)
    replace_parser.add_argument("--y0", type=float, required=True)
    replace_parser.add_argument("--x1", type=float, required=True)
    replace_parser.add_argument("--y1", type=float, required=True)
    replace_parser.add_argument("--text", "-t", required=True, help="New text")
    replace_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Apply edits batch command
    apply_parser = subparsers.add_parser("apply-edits", help="Apply multiple edits from JSON")
    apply_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    apply_parser.add_argument("--output", "-o", required=True, help="Output PDF path")
    apply_parser.add_argument("--edits", "-e", required=True, help="JSON string with edit operations")
    apply_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Preview command - render page with edits as PNG
    preview_parser = subparsers.add_parser("preview", help="Render page preview with edits")
    preview_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    preview_parser.add_argument("--page", "-p", type=int, required=True, help="Page number (0-indexed)")
    preview_parser.add_argument("--edits", "-e", default="{}", help="JSON string with edit operations")
    preview_parser.add_argument("--dpi", type=int, default=150, help="Render DPI")
    preview_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Text blocks with fonts command
    fonts_parser = subparsers.add_parser("text-blocks-fonts", help="Get text blocks with font info")
    fonts_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    fonts_parser.add_argument("--page", "-p", type=int, required=True, help="Page number (0-indexed)")
    fonts_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Analyze fonts command
    analyze_parser = subparsers.add_parser("analyze-fonts", help="Analyze fonts in PDF")
    analyze_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    analyze_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "text-blocks":
        result = get_text_blocks(Path(args.input), args.page)
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            if result["success"]:
                print(f"Found {len(result['blocks'])} text blocks on page {args.page + 1}")
                for block in result["blocks"]:
                    print(f"  [{block['id']}] {block['text'][:50]}...")
            else:
                print(f"Error: {result['error']}")
                sys.exit(1)

    elif args.command == "insert-text":
        result = insert_text(
            Path(args.input),
            Path(args.output),
            args.page,
            args.x,
            args.y,
            args.text,
            args.font,
            args.size,
        )
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            print(result["message"])
            sys.exit(0 if result["success"] else 1)

    elif args.command == "replace-text":
        result = replace_text_area(
            Path(args.input),
            Path(args.output),
            args.page,
            args.x0,
            args.y0,
            args.x1,
            args.y1,
            args.text,
        )
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            print(result["message"])
            sys.exit(0 if result["success"] else 1)

    elif args.command == "apply-edits":
        result = apply_edits(
            Path(args.input),
            Path(args.output),
            args.edits,
        )
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            print(result["message"])
            sys.exit(0 if result["success"] else 1)

    elif args.command == "preview":
        result = render_page_preview(
            Path(args.input),
            args.page,
            args.edits,
            args.dpi,
        )
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            if result["success"]:
                print(f"Preview rendered: {result['width']}x{result['height']}")
                # For non-JSON, just show info (image is too big to print)
            else:
                print(f"Error: {result['error']}")
                sys.exit(1)

    elif args.command == "text-blocks-fonts":
        result = get_text_blocks_with_fonts(Path(args.input), args.page)
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            if result["success"]:
                print(f"Found {len(result['blocks'])} text blocks with font info")
                for i, block in enumerate(result["blocks"]):
                    print(f"  Block {i}: {block['dominantFont']} {block['dominantSize']}pt {block['dominantColor']}")
                    print(f"    Text: {block['text'][:60]}...")
            else:
                print(f"Error: {result['error']}")
                sys.exit(1)

    elif args.command == "analyze-fonts":
        result = analyze_fonts(Path(args.input))
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            if result["success"]:
                summary = result["summary"]
                print(f"\nFont Analysis for: {args.input}")
                print(f"{'=' * 50}")
                print(f"Total fonts: {summary['total']}")
                print(f"Embedded: {summary['embedded']}")
                print(f"Missing: {summary['missing']}")
                print(f"Low match (<85%): {summary['low_match']}")
                print(f"\n{'Font Name':<30} {'Type':<8} {'Match':<20} {'Score'}")
                print(f"{'-' * 70}")
                for font in result["fonts"]:
                    status_icon = "✓" if font["status"] == "ok" else "⚠" if font["status"] == "low_match" else "✗"
                    best = font.get("bestMatch", {})
                    match_name = best.get("name", "N/A") if best else "N/A"
                    match_score = f"{best.get('similarity', 0)}%" if best else "N/A"
                    print(f"{status_icon} {font['name']:<28} {font['type']:<8} {match_name:<20} {match_score}")
            else:
                print(f"Error: {result['error']}")
                sys.exit(1)


if __name__ == "__main__":
    main()
