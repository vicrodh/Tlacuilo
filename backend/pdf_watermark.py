#!/usr/bin/env python3
"""
PDF Watermark operations using PyMuPDF.
Supports text and image watermarks with configurable position, opacity, and rotation.
"""

import sys
import json
import fitz  # PyMuPDF


def add_text_watermark(
    input_path: str,
    output_path: str,
    text: str,
    font_size: float = 48,
    font_color: tuple = (0.5, 0.5, 0.5),
    opacity: float = 0.3,
    rotation: float = -45,
    position: str = "center",  # center, top-left, top-right, bottom-left, bottom-right, tile
    pages: str = "all",  # "all" or "1,3,5" or "1-5"
    layer: str = "under"  # under or over
) -> dict:
    """
    Add text watermark to PDF pages.

    Args:
        input_path: Source PDF path
        output_path: Destination PDF path
        text: Watermark text
        font_size: Font size in points
        font_color: RGB tuple (0-1 range)
        opacity: Transparency (0-1)
        rotation: Rotation angle in degrees
        position: Placement strategy
        pages: Page selection
        layer: "under" content or "over" content

    Returns:
        dict with success status and message
    """
    try:
        doc = fitz.open(input_path)
        page_indices = _parse_pages(pages, len(doc))

        for page_idx in page_indices:
            page = doc[page_idx]
            rect = page.rect

            # Calculate positions based on strategy
            positions = _get_text_positions(rect, text, font_size, position, rotation)

            for pos in positions:
                # Create text writer for watermark
                if layer == "under":
                    # Insert under existing content
                    shape = page.new_shape()
                    shape.insert_text(
                        pos,
                        text,
                        fontsize=font_size,
                        color=font_color,
                        rotate=rotation,
                    )
                    shape.finish(opacity=opacity)
                    shape.commit(overlay=False)
                else:
                    # Insert over existing content
                    shape = page.new_shape()
                    shape.insert_text(
                        pos,
                        text,
                        fontsize=font_size,
                        color=font_color,
                        rotate=rotation,
                    )
                    shape.finish(opacity=opacity)
                    shape.commit(overlay=True)

        doc.save(output_path)
        doc.close()

        return {
            "success": True,
            "message": f"Watermark added to {len(page_indices)} pages",
            "pages_processed": len(page_indices)
        }

    except Exception as e:
        return {"success": False, "message": str(e)}


def add_image_watermark(
    input_path: str,
    output_path: str,
    image_path: str,
    opacity: float = 0.3,
    scale: float = 0.5,  # Scale relative to page
    rotation: float = 0,
    position: str = "center",
    pages: str = "all",
    layer: str = "under"
) -> dict:
    """
    Add image watermark to PDF pages.

    Args:
        input_path: Source PDF path
        output_path: Destination PDF path
        image_path: Path to watermark image (PNG, JPG, etc.)
        opacity: Transparency (0-1)
        scale: Image scale relative to page width
        rotation: Rotation angle in degrees
        position: Placement strategy
        pages: Page selection
        layer: "under" content or "over" content

    Returns:
        dict with success status and message
    """
    try:
        doc = fitz.open(input_path)
        page_indices = _parse_pages(pages, len(doc))

        # Load image once
        img = fitz.Pixmap(image_path)

        for page_idx in page_indices:
            page = doc[page_idx]
            rect = page.rect

            # Calculate image dimensions
            img_width = rect.width * scale
            img_height = img_width * (img.height / img.width)

            # Get positions
            positions = _get_image_positions(rect, img_width, img_height, position)

            for img_rect in positions:
                # Insert image with transparency
                page.insert_image(
                    img_rect,
                    filename=image_path,
                    rotate=rotation,
                    overlay=(layer == "over"),
                    alpha=int(opacity * 255) if opacity < 1 else -1
                )

        doc.save(output_path)
        doc.close()

        return {
            "success": True,
            "message": f"Image watermark added to {len(page_indices)} pages",
            "pages_processed": len(page_indices)
        }

    except Exception as e:
        return {"success": False, "message": str(e)}


def _parse_pages(pages: str, total: int) -> list:
    """Parse page selection string into list of 0-based indices."""
    if pages == "all":
        return list(range(total))

    indices = set()
    parts = pages.split(",")

    for part in parts:
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            start = max(1, int(start))
            end = min(total, int(end))
            indices.update(range(start - 1, end))
        else:
            page_num = int(part)
            if 1 <= page_num <= total:
                indices.add(page_num - 1)

    return sorted(indices)


def _get_text_positions(rect: fitz.Rect, text: str, font_size: float, position: str, rotation: float) -> list:
    """Calculate text insertion points based on position strategy."""
    positions = []

    # Approximate text width (rough estimate)
    text_width = len(text) * font_size * 0.5
    text_height = font_size

    if position == "center":
        x = rect.width / 2 - text_width / 2
        y = rect.height / 2
        positions.append(fitz.Point(x, y))

    elif position == "top-left":
        positions.append(fitz.Point(50, 50 + font_size))

    elif position == "top-right":
        positions.append(fitz.Point(rect.width - text_width - 50, 50 + font_size))

    elif position == "bottom-left":
        positions.append(fitz.Point(50, rect.height - 50))

    elif position == "bottom-right":
        positions.append(fitz.Point(rect.width - text_width - 50, rect.height - 50))

    elif position == "tile":
        # Create a grid of watermarks
        spacing_x = max(text_width * 1.5, 200)
        spacing_y = max(text_height * 3, 150)

        y = spacing_y
        while y < rect.height:
            x = spacing_x / 2
            while x < rect.width:
                positions.append(fitz.Point(x, y))
                x += spacing_x
            y += spacing_y

    return positions


def _get_image_positions(rect: fitz.Rect, img_width: float, img_height: float, position: str) -> list:
    """Calculate image rects based on position strategy."""
    positions = []
    margin = 30

    if position == "center":
        x = (rect.width - img_width) / 2
        y = (rect.height - img_height) / 2
        positions.append(fitz.Rect(x, y, x + img_width, y + img_height))

    elif position == "top-left":
        positions.append(fitz.Rect(margin, margin, margin + img_width, margin + img_height))

    elif position == "top-right":
        x = rect.width - img_width - margin
        positions.append(fitz.Rect(x, margin, x + img_width, margin + img_height))

    elif position == "bottom-left":
        y = rect.height - img_height - margin
        positions.append(fitz.Rect(margin, y, margin + img_width, y + img_height))

    elif position == "bottom-right":
        x = rect.width - img_width - margin
        y = rect.height - img_height - margin
        positions.append(fitz.Rect(x, y, x + img_width, y + img_height))

    elif position == "tile":
        spacing_x = img_width * 1.5
        spacing_y = img_height * 1.5

        y = spacing_y / 2
        while y + img_height < rect.height:
            x = spacing_x / 2
            while x + img_width < rect.width:
                positions.append(fitz.Rect(x, y, x + img_width, y + img_height))
                x += spacing_x
            y += spacing_y

    return positions


def get_preview_info(input_path: str) -> dict:
    """Get PDF info for watermark preview."""
    try:
        doc = fitz.open(input_path)
        info = {
            "success": True,
            "page_count": len(doc),
            "pages": []
        }

        for i, page in enumerate(doc):
            info["pages"].append({
                "index": i,
                "width": page.rect.width,
                "height": page.rect.height
            })

        doc.close()
        return info

    except Exception as e:
        return {"success": False, "message": str(e)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "message": "No command specified"}))
        sys.exit(1)

    command = sys.argv[1]

    if command == "text":
        if len(sys.argv) < 5:
            print(json.dumps({"success": False, "message": "Usage: text <input> <output> <text> [options_json]"}))
            sys.exit(1)

        input_path = sys.argv[2]
        output_path = sys.argv[3]
        text = sys.argv[4]

        # Parse optional JSON options
        options = {}
        if len(sys.argv) > 5:
            try:
                options = json.loads(sys.argv[5])
            except json.JSONDecodeError:
                pass

        result = add_text_watermark(
            input_path,
            output_path,
            text,
            font_size=options.get("font_size", 48),
            font_color=tuple(options.get("font_color", [0.5, 0.5, 0.5])),
            opacity=options.get("opacity", 0.3),
            rotation=options.get("rotation", -45),
            position=options.get("position", "center"),
            pages=options.get("pages", "all"),
            layer=options.get("layer", "under")
        )
        print(json.dumps(result))
        sys.exit(0 if result["success"] else 1)

    elif command == "image":
        if len(sys.argv) < 5:
            print(json.dumps({"success": False, "message": "Usage: image <input> <output> <image_path> [options_json]"}))
            sys.exit(1)

        input_path = sys.argv[2]
        output_path = sys.argv[3]
        image_path = sys.argv[4]

        options = {}
        if len(sys.argv) > 5:
            try:
                options = json.loads(sys.argv[5])
            except json.JSONDecodeError:
                pass

        result = add_image_watermark(
            input_path,
            output_path,
            image_path,
            opacity=options.get("opacity", 0.3),
            scale=options.get("scale", 0.5),
            rotation=options.get("rotation", 0),
            position=options.get("position", "center"),
            pages=options.get("pages", "all"),
            layer=options.get("layer", "under")
        )
        print(json.dumps(result))
        sys.exit(0 if result["success"] else 1)

    elif command == "info":
        if len(sys.argv) < 3:
            print(json.dumps({"success": False, "message": "Usage: info <input>"}))
            sys.exit(1)

        result = get_preview_info(sys.argv[2])
        print(json.dumps(result))
        sys.exit(0 if result["success"] else 1)

    else:
        print(json.dumps({"success": False, "message": f"Unknown command: {command}"}))
        sys.exit(1)
