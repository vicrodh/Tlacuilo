"""
PDF Annotation operations: embed, read, XFDF export/import.

Uses PyMuPDF for native PDF annotation handling.

CLI usage (dev):
  python pdf_annotations.py embed --input doc.pdf --annotations annot.json --output out.pdf
  python pdf_annotations.py read --input doc.pdf
  python pdf_annotations.py export-xfdf --input doc.pdf --output annot.xfdf
  python pdf_annotations.py import-xfdf --input doc.pdf --xfdf annot.xfdf --output out.pdf
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import fitz  # PyMuPDF


# Map our annotation types to PyMuPDF types
ANNOT_TYPE_MAP = {
    "highlight": fitz.PDF_ANNOT_HIGHLIGHT,
    "underline": fitz.PDF_ANNOT_UNDERLINE,
    "strikethrough": fitz.PDF_ANNOT_STRIKE_OUT,
    "comment": fitz.PDF_ANNOT_TEXT,
    "freetext": fitz.PDF_ANNOT_FREE_TEXT,
    "ink": fitz.PDF_ANNOT_INK,
    "rectangle": fitz.PDF_ANNOT_SQUARE,
    "ellipse": fitz.PDF_ANNOT_CIRCLE,
    "line": fitz.PDF_ANNOT_LINE,
    "arrow": fitz.PDF_ANNOT_LINE,  # Same as line but with arrow heads
    # sequenceNumber uses circle + freetext combination
}

# Reverse map for reading
ANNOT_TYPE_REVERSE = {
    fitz.PDF_ANNOT_HIGHLIGHT: "highlight",
    fitz.PDF_ANNOT_UNDERLINE: "underline",
    fitz.PDF_ANNOT_STRIKE_OUT: "strikethrough",
    fitz.PDF_ANNOT_TEXT: "comment",
    fitz.PDF_ANNOT_FREE_TEXT: "freetext",
    fitz.PDF_ANNOT_INK: "ink",
    fitz.PDF_ANNOT_SQUARE: "rectangle",
    fitz.PDF_ANNOT_CIRCLE: "ellipse",
    fitz.PDF_ANNOT_LINE: "line",  # Could be line or arrow, check line ends
}

# Arrow head styles for line annotations
ARROW_STYLE_MAP = {
    "none": fitz.PDF_ANNOT_LE_NONE,
    "open": fitz.PDF_ANNOT_LE_OPEN_ARROW,
    "closed": fitz.PDF_ANNOT_LE_CLOSED_ARROW,
}


def hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """Convert hex color (#RRGGBB) to RGB floats (0-1)."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return (r, g, b)


def rgb_to_hex(rgb: tuple[float, ...]) -> str:
    """Convert RGB floats (0-1) to hex color (#RRGGBB)."""
    if not rgb or len(rgb) < 3:
        return "#FFFF00"  # Default yellow
    r = int(rgb[0] * 255)
    g = int(rgb[1] * 255)
    b = int(rgb[2] * 255)
    return f"#{r:02x}{g:02x}{b:02x}"


def parse_da_string(doc: fitz.Document, annot: fitz.Annot) -> dict:
    """
    Parse the DA (Default Appearance) string from a FreeText annotation
    to extract text color and font size.

    DA format example: "/Helv 12 Tf 0 0 0 rg"
    - /Helv = font name
    - 12 = font size (in points)
    - Tf = text font operator
    - 0 0 0 rg = RGB color (black)

    Returns dict with 'color' (tuple) and 'fontsize' (float) keys.
    """
    result = {"color": None, "fontsize": None}

    try:
        xref = annot.xref
        annot_obj = doc.xref_object(xref)

        # Look for /DA in the annotation object
        # Format: /DA (/Helv 12 Tf 0 0 0 rg)
        da_match = re.search(r'/DA\s*\(([^)]+)\)', annot_obj)
        if not da_match:
            da_match = re.search(r'/DA\s*<([^>]+)>', annot_obj)

        if da_match:
            da_content = da_match.group(1)

            # Parse font size: /FontName SIZE Tf
            # Examples: /Helv 12 Tf, /TiRo 10.5 Tf
            fontsize_match = re.search(r'/\w+\s+([\d.]+)\s+Tf', da_content)
            if fontsize_match:
                result["fontsize"] = float(fontsize_match.group(1))

            # Parse RGB color (r g b rg)
            rgb_match = re.search(r'([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+rg', da_content)
            if rgb_match:
                r = float(rgb_match.group(1))
                g = float(rgb_match.group(2))
                b = float(rgb_match.group(3))
                result["color"] = (r, g, b)
            else:
                # Parse grayscale (value g)
                gray_match = re.search(r'([\d.]+)\s+g\b', da_content)
                if gray_match:
                    gray = float(gray_match.group(1))
                    result["color"] = (gray, gray, gray)

    except Exception:
        pass

    return result


def normalized_to_pdf_rect(
    norm_rect: dict[str, float],
    page_width: float,
    page_height: float,
) -> fitz.Rect:
    """
    Convert normalized rectangle (0-1) to PDF rect in points.
    Note: PDF origin is bottom-left, but PyMuPDF uses top-left.
    Our coordinates: x,y is top-left corner, y increases downward.
    """
    x = norm_rect["x"] * page_width
    y = norm_rect["y"] * page_height
    w = norm_rect["width"] * page_width
    h = norm_rect["height"] * page_height
    return fitz.Rect(x, y, x + w, y + h)


def pdf_rect_to_normalized(
    rect: fitz.Rect,
    page_width: float,
    page_height: float,
) -> dict[str, float]:
    """Convert PDF rect to normalized rectangle (0-1)."""
    return {
        "x": rect.x0 / page_width,
        "y": rect.y0 / page_height,
        "width": (rect.x1 - rect.x0) / page_width,
        "height": (rect.y1 - rect.y0) / page_height,
    }


def rect_to_quad(rect: fitz.Rect) -> fitz.Quad:
    """Convert rectangle to quad (for text markup annotations)."""
    return rect.quad


def embed_annotations(
    input_path: Path,
    annotations_json: str,
    output_path: Path,
) -> dict[str, Any]:
    """
    Embed annotations from JSON into a PDF.

    annotations_json format:
    {
      "1": [
        {
          "id": "...",
          "type": "highlight|underline|strikethrough|comment",
          "page": 1,
          "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.05},
          "color": "#FFFF00",
          "opacity": 0.5,
          "text": "optional comment text",
          "createdAt": "...",
          "modifiedAt": "..."
        }
      ]
    }

    Returns stats about embedded annotations.
    """
    doc = fitz.open(str(input_path))
    annotations = json.loads(annotations_json)

    stats = {"total": 0, "by_type": {}, "errors": [], "removed": 0}

    # First, remove all existing annotations of supported types to avoid duplicates
    supported_types = set(ANNOT_TYPE_MAP.values())
    for page in doc:
        annots_to_delete = []
        for annot in page.annots():
            if annot.type[0] in supported_types:
                annots_to_delete.append(annot)
        for annot in annots_to_delete:
            page.delete_annot(annot)
            stats["removed"] += 1

    for page_num_str, page_annots in annotations.items():
        page_num = int(page_num_str)
        page_idx = page_num - 1  # Convert to 0-indexed

        if page_idx < 0 or page_idx >= len(doc):
            stats["errors"].append(f"Page {page_num} out of bounds")
            continue

        page = doc[page_idx]
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height

        for annot_data in page_annots:
            try:
                annot_type = annot_data.get("type", "highlight")
                annot_id = annot_data.get("id", str(uuid4()))
                rect_data = annot_data.get("rect", {})
                color_hex = annot_data.get("color", "#FFFF00")
                opacity = annot_data.get("opacity", 0.5)
                text = annot_data.get("text", "")
                author = annot_data.get("author", "")

                # Convert normalized rect to PDF rect
                pdf_rect = normalized_to_pdf_rect(rect_data, page_width, page_height)
                color_rgb = hex_to_rgb(color_hex)

                annot = None

                if annot_type == "comment":
                    # Text annotation (sticky note icon)
                    point = fitz.Point(pdf_rect.x0, pdf_rect.y0)
                    annot = page.add_text_annot(point, text or "")
                    annot.set_colors(stroke=color_rgb)
                elif annot_type == "freetext":
                    # FreeText annotation (typewriter - text directly on page)
                    # fill_color=None for transparent background (no yellow box)
                    annot = page.add_freetext_annot(
                        pdf_rect,
                        text or "",
                        fontsize=12,
                        fontname="helv",
                        text_color=color_rgb,
                        fill_color=None,  # Transparent background
                    )
                elif annot_type in ("highlight", "underline", "strikethrough"):
                    # For underline/strikethrough, normalize height for consistent line thickness
                    if annot_type in ("underline", "strikethrough"):
                        # Standard text line height (12pt) for consistent rendering
                        standard_height = 12.0
                        if pdf_rect.height > standard_height * 1.5:
                            # Normalize oversized rects to standard height
                            if annot_type == "underline":
                                # Keep bottom edge, adjust top
                                normalized_rect = fitz.Rect(
                                    pdf_rect.x0,
                                    pdf_rect.y1 - standard_height,
                                    pdf_rect.x1,
                                    pdf_rect.y1,
                                )
                            else:  # strikethrough
                                # Center the standard height vertically
                                center_y = (pdf_rect.y0 + pdf_rect.y1) / 2
                                normalized_rect = fitz.Rect(
                                    pdf_rect.x0,
                                    center_y - standard_height / 2,
                                    pdf_rect.x1,
                                    center_y + standard_height / 2,
                                )
                            quad = rect_to_quad(normalized_rect)
                        else:
                            quad = rect_to_quad(pdf_rect)
                    else:
                        quad = rect_to_quad(pdf_rect)

                    if annot_type == "highlight":
                        annot = page.add_highlight_annot(quad)
                    elif annot_type == "underline":
                        annot = page.add_underline_annot(quad)
                    elif annot_type == "strikethrough":
                        annot = page.add_strikeout_annot(quad)

                    if annot:
                        annot.set_colors(stroke=color_rgb)
                        if text:
                            annot.set_info(content=text)

                elif annot_type == "ink":
                    # Ink/freehand annotation
                    paths = annot_data.get("paths", [])
                    if paths:
                        ink_list = []
                        for path in paths:
                            points = path.get("points", [])
                            # Use tuples (x, y) instead of fitz.Point objects
                            # PyMuPDF's add_ink_annot expects seq of seq of float pairs
                            pdf_points = []
                            for pt in points:
                                pdf_points.append((
                                    pt["x"] * page_width,
                                    pt["y"] * page_height,
                                ))
                            if pdf_points:
                                ink_list.append(pdf_points)
                        if ink_list:
                            annot = page.add_ink_annot(ink_list)
                            if annot:
                                annot.set_colors(stroke=color_rgb)
                                # Use strokeWidth from path if available, fallback to annotation level
                                sw = paths[0].get("strokeWidth", annot_data.get("strokeWidth", 0.003))
                                annot.set_border(width=sw * page_width)

                elif annot_type == "rectangle":
                    # Rectangle/square annotation
                    annot = page.add_rect_annot(pdf_rect)
                    if annot:
                        fill_data = annot_data.get("fill", {})
                        fill_color = None
                        if fill_data.get("enabled"):
                            fill_color = hex_to_rgb(fill_data.get("color", color_hex))
                        annot.set_colors(stroke=color_rgb, fill=fill_color)
                        sw = annot_data.get("strokeWidth", 0.002) * page_width
                        line_style = annot_data.get("lineStyle", "solid")
                        dashes = [3, 3] if line_style == "dashed" else ([1, 1] if line_style == "dotted" else None)
                        annot.set_border(width=sw, dashes=dashes)

                elif annot_type == "ellipse":
                    # Circle/ellipse annotation
                    annot = page.add_circle_annot(pdf_rect)
                    if annot:
                        fill_data = annot_data.get("fill", {})
                        fill_color = None
                        if fill_data.get("enabled"):
                            fill_color = hex_to_rgb(fill_data.get("color", color_hex))
                        annot.set_colors(stroke=color_rgb, fill=fill_color)
                        sw = annot_data.get("strokeWidth", 0.002) * page_width
                        line_style = annot_data.get("lineStyle", "solid")
                        dashes = [3, 3] if line_style == "dashed" else ([1, 1] if line_style == "dotted" else None)
                        annot.set_border(width=sw, dashes=dashes)

                elif annot_type in ("line", "arrow"):
                    # Line annotation (with optional arrow heads)
                    # Use startPoint/endPoint if available, otherwise fall back to rect corners
                    start_pt = annot_data.get("startPoint")
                    end_pt = annot_data.get("endPoint")
                    if start_pt and end_pt:
                        p1 = fitz.Point(start_pt["x"] * page_width, start_pt["y"] * page_height)
                        p2 = fitz.Point(end_pt["x"] * page_width, end_pt["y"] * page_height)
                    else:
                        # Fall back to rect corners
                        p1 = fitz.Point(pdf_rect.x0, pdf_rect.y0)
                        p2 = fitz.Point(pdf_rect.x1, pdf_rect.y1)
                    annot = page.add_line_annot(p1, p2)
                    if annot:
                        annot.set_colors(stroke=color_rgb)
                        sw = annot_data.get("strokeWidth", 0.002) * page_width
                        line_style = annot_data.get("lineStyle", "solid")
                        dashes = [3, 3] if line_style == "dashed" else ([1, 1] if line_style == "dotted" else None)
                        annot.set_border(width=sw, dashes=dashes)
                        # Set arrow heads
                        if annot_type == "arrow":
                            start_arrow = annot_data.get("startArrow", "none")
                            end_arrow = annot_data.get("endArrow", "closed")
                            start_style = ARROW_STYLE_MAP.get(start_arrow, fitz.PDF_ANNOT_LE_NONE)
                            end_style = ARROW_STYLE_MAP.get(end_arrow, fitz.PDF_ANNOT_LE_CLOSED_ARROW)
                            annot.set_line_ends(start_style, end_style)

                elif annot_type == "sequenceNumber":
                    # Sequence number: filled circle with number stored in content
                    # The number is rendered by the frontend; PDF stores it as metadata
                    seq_num = annot_data.get("sequenceNumber", 1)
                    annot = page.add_circle_annot(pdf_rect)
                    if annot:
                        annot.set_colors(stroke=color_rgb, fill=color_rgb)
                        annot.set_border(width=1)
                        # Store the sequence number in content field for round-trip
                        # Format: "SEQ:N" to identify this as a sequence number
                        annot.set_info(content=f"SEQ:{seq_num}")

                if annot:
                    annot.set_opacity(opacity)
                    # Store our ID in the subject field for round-trip
                    # Author goes in the title field (PyMuPDF convention)
                    info_dict = {"subject": annot_id}
                    if author:
                        info_dict["title"] = author
                    annot.set_info(**info_dict)
                    annot.update()

                    stats["total"] += 1
                    stats["by_type"][annot_type] = stats["by_type"].get(annot_type, 0) + 1

            except Exception as e:
                stats["errors"].append(f"Failed to add annotation: {e}")

    # Save: use incremental save when saving to same file
    input_resolved = Path(input_path).resolve()
    output_resolved = Path(output_path).resolve()

    if input_resolved == output_resolved:
        # Same file: must use incremental save
        doc.save(str(output_path), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    else:
        # Different file: can optimize
        doc.save(str(output_path), garbage=4, deflate=True)
    doc.close()

    return stats


def read_annotations(input_path: Path) -> dict[str, list[dict[str, Any]]]:
    """
    Read all annotations from a PDF and return in our JSON format.

    Returns:
    {
      "1": [annotations for page 1],
      "2": [annotations for page 2],
      ...
    }
    """
    doc = fitz.open(str(input_path))
    result: dict[str, list[dict[str, Any]]] = {}

    # Reverse map for arrow styles
    arrow_style_reverse = {v: k for k, v in ARROW_STYLE_MAP.items()}

    for page_idx, page in enumerate(doc):
        page_num = page_idx + 1
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height

        page_annots = []

        for annot in page.annots():
            annot_type_code = annot.type[0]

            # Skip unsupported annotation types
            if annot_type_code not in ANNOT_TYPE_REVERSE:
                continue

            our_type = ANNOT_TYPE_REVERSE[annot_type_code]

            # For text markup annotations, use vertices to get the actual rect
            # because annot.rect includes visual padding that grows on each save
            if our_type in ("highlight", "underline", "strikethrough") and annot.vertices:
                vertices = annot.vertices
                # Handle both tuple format [(x,y), ...] and flat format [x,y,x,y,...]
                if vertices and isinstance(vertices[0], tuple):
                    xs = [p[0] for p in vertices]
                    ys = [p[1] for p in vertices]
                else:
                    xs = [vertices[i] for i in range(0, len(vertices), 2)]
                    ys = [vertices[i] for i in range(1, len(vertices), 2)]
                rect = fitz.Rect(min(xs), min(ys), max(xs), max(ys))
            else:
                rect = annot.rect

            # Get annotation info
            info = annot.info
            # Our ID is stored in 'subject' field (see embed_annotations)
            annot_id = info.get("subject") or str(uuid4())
            text = info.get("content", "")
            # Author is stored in 'title' field
            author = info.get("title", "")

            # Get colors and fontsize - FreeText needs special handling
            fontsize = None
            fill_data = None
            stroke_width = None
            line_style = None
            start_arrow = None
            end_arrow = None
            paths = None
            start_point = None
            end_point = None
            seq_num = None

            if our_type == "freetext":
                # Parse DA string to get text color and fontsize
                da_info = parse_da_string(doc, annot)
                if da_info["color"]:
                    color_hex = rgb_to_hex(da_info["color"])
                else:
                    color_hex = "#000000"  # Default black for freetext
                fontsize = da_info["fontsize"] or 12  # Default 12pt if not found
                # For freetext, get text content from the annotation itself
                text = annot.get_text() or info.get("content", "") or ""
            elif our_type == "ink":
                # Get ink paths from vertices (list of lists of (x,y) tuples)
                colors = annot.colors
                stroke_color = colors.get("stroke") or (0, 0, 0)
                color_hex = rgb_to_hex(stroke_color)
                # Ink paths are stored in vertices as list of point lists
                ink_paths = annot.vertices if annot.vertices else []
                if ink_paths:
                    paths = []
                    border = annot.border or {}
                    sw = border.get("width", 1.0) if isinstance(border, dict) else 1.0
                    stroke_width = sw / page_width  # Normalize
                    for point_list in ink_paths:
                        points = []
                        for pt in point_list:
                            # Points are (x, y) tuples, normalize to 0-1
                            points.append({
                                "x": pt[0] / page_width,
                                "y": pt[1] / page_height,
                            })
                        if points:
                            paths.append({
                                "points": points,
                                "strokeWidth": stroke_width,
                                "color": color_hex,
                            })
            elif our_type in ("rectangle", "ellipse"):
                # Shape annotations - check for sequence number pattern
                # Detect filled circles with "SEQ:N" content as sequence numbers
                seq_num = None
                if our_type == "ellipse" and text.startswith("SEQ:"):
                    try:
                        seq_num = int(text.split(":")[1])
                        our_type = "sequenceNumber"
                    except (ValueError, IndexError):
                        pass

                colors = annot.colors
                stroke_color = colors.get("stroke") or (0, 0, 0)
                fill_color = colors.get("fill")
                color_hex = rgb_to_hex(stroke_color)
                # Get border info
                border = annot.border or {}
                sw = border.get("width", 1.0) if isinstance(border, dict) else 1.0
                stroke_width = sw / page_width  # Normalize
                # Get line style (dashes)
                dashes = border.get("dashes", []) if isinstance(border, dict) else []
                if dashes:
                    line_style = "dashed"
                else:
                    line_style = "solid"
                # Fill info
                if fill_color:
                    fill_data = {
                        "enabled": True,
                        "color": rgb_to_hex(fill_color),
                        "opacity": annot.opacity if annot.opacity >= 0 else 0.3,
                    }
            elif our_type == "line":
                # Line annotation (could be arrow)
                colors = annot.colors
                stroke_color = colors.get("stroke") or (0, 0, 0)
                color_hex = rgb_to_hex(stroke_color)
                # Get border info
                border = annot.border or {}
                sw = border.get("width", 1.0) if isinstance(border, dict) else 1.0
                stroke_width = sw / page_width
                # Get line style
                dashes = border.get("dashes", []) if isinstance(border, dict) else []
                line_style = "dashed" if dashes else "solid"
                # Get arrow heads (line ends)
                try:
                    line_ends = annot.line_ends
                    if line_ends:
                        start_arrow = arrow_style_reverse.get(line_ends[0], "none")
                        end_arrow = arrow_style_reverse.get(line_ends[1], "none")
                        # If has arrows, mark as arrow type
                        if end_arrow != "none" or start_arrow != "none":
                            our_type = "arrow"
                except Exception:
                    pass
                # Get actual line endpoints from vertices and store as startPoint/endPoint
                vertices = annot.vertices
                start_point = None
                end_point = None
                if vertices and len(vertices) >= 2:
                    p1 = vertices[0]
                    p2 = vertices[1]
                    # Store actual start/end points (normalized)
                    start_point = {"x": p1[0] / page_width, "y": p1[1] / page_height}
                    end_point = {"x": p2[0] / page_width, "y": p2[1] / page_height}
                    # Also compute bounding rect
                    rect = fitz.Rect(
                        min(p1[0], p2[0]),
                        min(p1[1], p2[1]),
                        max(p1[0], p2[0]),
                        max(p1[1], p2[1]),
                    )
            else:
                colors = annot.colors
                stroke_color = colors.get("stroke") or colors.get("fill") or (1, 1, 0)
                color_hex = rgb_to_hex(stroke_color)

            # Get opacity
            opacity = annot.opacity
            if opacity < 0:
                opacity = 0.5  # Default if not set

            # Get dates
            created = info.get("creationDate", "")
            modified = info.get("modDate", "")

            # Convert to ISO format if PDF date format
            now = datetime.now().isoformat()
            if not created:
                created = now
            if not modified:
                modified = now

            annot_data = {
                "id": annot_id,
                "type": our_type,
                "page": page_num,
                "rect": pdf_rect_to_normalized(rect, page_width, page_height),
                "color": color_hex,
                "opacity": opacity,
                "text": text,
                "author": author,
                "createdAt": created,
                "modifiedAt": modified,
            }
            # Add optional fields
            if fontsize is not None:
                annot_data["fontsize"] = fontsize
            if paths is not None:
                annot_data["paths"] = paths
            if fill_data is not None:
                annot_data["fill"] = fill_data
            if stroke_width is not None:
                annot_data["strokeWidth"] = stroke_width
            if line_style is not None:
                annot_data["lineStyle"] = line_style
            if start_arrow is not None:
                annot_data["startArrow"] = start_arrow
            if end_arrow is not None:
                annot_data["endArrow"] = end_arrow
            if start_point is not None:
                annot_data["startPoint"] = start_point
            if end_point is not None:
                annot_data["endPoint"] = end_point
            if seq_num is not None:
                annot_data["sequenceNumber"] = seq_num
                # Clear the "SEQ:" text since it's just metadata
                annot_data["text"] = ""
            page_annots.append(annot_data)

        if page_annots:
            result[str(page_num)] = page_annots

    doc.close()
    return result


def export_xfdf(input_path: Path, output_path: Path) -> int:
    """
    Export annotations from a PDF to XFDF format.
    Returns count of exported annotations.
    """
    doc = fitz.open(str(input_path))

    # Create XFDF root
    xfdf = ET.Element("xfdf")
    xfdf.set("xmlns", "http://ns.adobe.com/xfdf/")
    xfdf.set("xml:space", "preserve")

    # Add file reference
    f_elem = ET.SubElement(xfdf, "f")
    f_elem.set("href", input_path.name)

    # Add annots container
    annots_elem = ET.SubElement(xfdf, "annots")

    count = 0

    for page_idx, page in enumerate(doc):
        page_num = page_idx + 1  # XFDF uses 1-indexed pages (actually 0-indexed in spec)

        for annot in page.annots():
            annot_type_code = annot.type[0]

            # Map to XFDF element names
            xfdf_type = None
            if annot_type_code == fitz.PDF_ANNOT_HIGHLIGHT:
                xfdf_type = "highlight"
            elif annot_type_code == fitz.PDF_ANNOT_UNDERLINE:
                xfdf_type = "underline"
            elif annot_type_code == fitz.PDF_ANNOT_STRIKE_OUT:
                xfdf_type = "strikeout"
            elif annot_type_code == fitz.PDF_ANNOT_TEXT:
                xfdf_type = "text"
            elif annot_type_code == fitz.PDF_ANNOT_FREE_TEXT:
                xfdf_type = "freetext"

            if not xfdf_type:
                continue

            annot_elem = ET.SubElement(annots_elem, xfdf_type)

            # Set page (0-indexed in XFDF)
            annot_elem.set("page", str(page_idx))

            # Set rect
            rect = annot.rect
            annot_elem.set("rect", f"{rect.x0},{rect.y0},{rect.x1},{rect.y1}")

            # Set color
            colors = annot.colors
            stroke = colors.get("stroke") or colors.get("fill")
            if stroke and len(stroke) >= 3:
                color_str = f"#{int(stroke[0]*255):02x}{int(stroke[1]*255):02x}{int(stroke[2]*255):02x}"
                annot_elem.set("color", color_str)

            # Set opacity
            opacity = annot.opacity
            if opacity >= 0:
                annot_elem.set("opacity", str(opacity))

            # Set name/id
            info = annot.info
            name = info.get("name")
            if name:
                annot_elem.set("name", name)

            # Set content
            content = info.get("content")
            if content:
                contents_elem = ET.SubElement(annot_elem, "contents")
                contents_elem.text = content

            # Set dates
            if info.get("creationDate"):
                annot_elem.set("creationdate", info["creationDate"])
            if info.get("modDate"):
                annot_elem.set("date", info["modDate"])

            count += 1

    doc.close()

    # Write XFDF file
    tree = ET.ElementTree(xfdf)
    ET.indent(tree, space="  ")
    tree.write(str(output_path), encoding="utf-8", xml_declaration=True)

    return count


def import_xfdf(
    input_path: Path,
    xfdf_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """
    Import annotations from XFDF into a PDF.
    Returns stats about imported annotations.
    """
    doc = fitz.open(str(input_path))
    tree = ET.parse(str(xfdf_path))
    root = tree.getroot()

    # Handle namespace
    ns = {"xfdf": "http://ns.adobe.com/xfdf/"}

    stats = {"total": 0, "by_type": {}, "errors": []}

    # Find annots element (with or without namespace)
    annots_elem = root.find("annots") or root.find("xfdf:annots", ns)
    if annots_elem is None:
        return stats

    for annot_elem in annots_elem:
        try:
            # Get tag name without namespace
            tag = annot_elem.tag.split("}")[-1] if "}" in annot_elem.tag else annot_elem.tag

            # Get page number (0-indexed in XFDF)
            page_str = annot_elem.get("page", "0")
            page_idx = int(page_str)

            if page_idx < 0 or page_idx >= len(doc):
                stats["errors"].append(f"Page {page_idx} out of bounds")
                continue

            page = doc[page_idx]

            # Get rect
            rect_str = annot_elem.get("rect", "0,0,100,100")
            rect_parts = [float(x) for x in rect_str.split(",")]
            pdf_rect = fitz.Rect(rect_parts[0], rect_parts[1], rect_parts[2], rect_parts[3])

            # Get color
            color_str = annot_elem.get("color", "#FFFF00")
            color_rgb = hex_to_rgb(color_str)

            # Get opacity
            opacity_str = annot_elem.get("opacity", "0.5")
            opacity = float(opacity_str)

            # Get content
            contents_elem = annot_elem.find("contents") or annot_elem.find("xfdf:contents", ns)
            content = contents_elem.text if contents_elem is not None else ""

            # Get name/id
            name = annot_elem.get("name", str(uuid4()))

            annot = None

            if tag == "highlight":
                annot = page.add_highlight_annot(rect_to_quad(pdf_rect))
            elif tag == "underline":
                annot = page.add_underline_annot(rect_to_quad(pdf_rect))
            elif tag in ("strikeout", "strikethrough"):
                annot = page.add_strikeout_annot(rect_to_quad(pdf_rect))
            elif tag == "text":
                point = fitz.Point(pdf_rect.x0, pdf_rect.y0)
                annot = page.add_text_annot(point, content or "")
            elif tag == "freetext":
                annot = page.add_freetext_annot(pdf_rect, content or "")

            if annot:
                annot.set_colors(stroke=color_rgb)
                annot.set_opacity(opacity)
                # Store ID in subject field (consistent with embed_annotations)
                annot.set_info(subject=name)
                if content and tag not in ("text", "freetext"):
                    annot.set_info(content=content)
                annot.update()

                stats["total"] += 1
                stats["by_type"][tag] = stats["by_type"].get(tag, 0) + 1

        except Exception as e:
            stats["errors"].append(f"Failed to import annotation: {e}")

    # Save: use incremental save when saving to same file
    input_resolved = Path(input_path).resolve()
    output_resolved = Path(output_path).resolve()

    if input_resolved == output_resolved:
        # Same file: must use incremental save
        doc.save(str(output_path), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    else:
        # Different file: can optimize
        doc.save(str(output_path), garbage=4, deflate=True)
    doc.close()

    return stats


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PDF annotation operations")
    sub = parser.add_subparsers(dest="command", required=True)

    embed_p = sub.add_parser("embed", help="Embed annotations into PDF")
    embed_p.add_argument("--input", required=True, help="Input PDF path")
    embed_p.add_argument("--annotations", required=True, help="Annotations JSON file or string")
    embed_p.add_argument("--output", required=True, help="Output PDF path")

    read_p = sub.add_parser("read", help="Read annotations from PDF")
    read_p.add_argument("--input", required=True, help="Input PDF path")

    export_p = sub.add_parser("export-xfdf", help="Export annotations to XFDF")
    export_p.add_argument("--input", required=True, help="Input PDF path")
    export_p.add_argument("--output", required=True, help="Output XFDF path")

    import_p = sub.add_parser("import-xfdf", help="Import annotations from XFDF")
    import_p.add_argument("--input", required=True, help="Input PDF path")
    import_p.add_argument("--xfdf", required=True, help="XFDF file path")
    import_p.add_argument("--output", required=True, help="Output PDF path")

    return parser


def _main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "embed":
            # Load annotations from file or use as JSON string
            annot_input = args.annotations
            # Only try to read as file if it looks like a path (not JSON)
            if not annot_input.strip().startswith("{"):
                annot_path = Path(annot_input)
                if annot_path.is_file():
                    annot_input = annot_path.read_text()

            stats = embed_annotations(
                Path(args.input),
                annot_input,
                Path(args.output),
            )
            print(json.dumps(stats))

        elif args.command == "read":
            annotations = read_annotations(Path(args.input))
            print(json.dumps(annotations))

        elif args.command == "export-xfdf":
            count = export_xfdf(Path(args.input), Path(args.output))
            print(json.dumps({"exported": count}))

        elif args.command == "import-xfdf":
            stats = import_xfdf(
                Path(args.input),
                Path(args.xfdf),
                Path(args.output),
            )
            print(json.dumps(stats))

        else:
            parser.error("Unknown command")

    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
