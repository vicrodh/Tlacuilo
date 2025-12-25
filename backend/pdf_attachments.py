"""
PDF attachments: list, extract, and get info about embedded files.

CLI usage (dev):
  python pdf_attachments.py list --input document.pdf
  python pdf_attachments.py extract --input document.pdf --name "file.txt" --output /tmp/file.txt
  python pdf_attachments.py extract-all --input document.pdf --output-dir /tmp/attachments
  python pdf_attachments.py preview --input document.pdf --name "file.txt"
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


def list_attachments(input_path: Path) -> list[dict[str, Any]]:
    """List all embedded files in a PDF with their metadata."""
    doc = fitz.open(str(input_path))

    attachments = []
    count = doc.embfile_count()

    for i in range(count):
        info = doc.embfile_info(i)
        attachments.append({
            "index": i,
            "name": info.get("name", f"attachment_{i}"),
            "filename": info.get("filename", ""),
            "size": info.get("size", 0),
            "length": info.get("length", 0),  # Compressed size
            "created": info.get("creationDate", ""),
            "modified": info.get("modDate", ""),
            "description": info.get("desc", ""),
            "checksum": info.get("checksum", ""),
        })

    doc.close()
    return attachments


def get_attachment_preview(input_path: Path, name_or_index: str | int, max_text_size: int = 50000) -> dict[str, Any]:
    """
    Get attachment content for preview.

    Returns:
        - For images (jpg, png, gif, webp, svg, bmp): base64 encoded data
        - For text files (txt, md, json, xml, csv, log, html, css, js): text content
        - For other files: first 1KB as hex dump
    """
    doc = fitz.open(str(input_path))

    try:
        # Get content
        if isinstance(name_or_index, int) or (isinstance(name_or_index, str) and name_or_index.isdigit()):
            idx = int(name_or_index)
            content = doc.embfile_get(idx)
            info = doc.embfile_info(idx)
        else:
            content = doc.embfile_get(name_or_index)
            names = doc.embfile_names()
            idx = names.index(name_or_index) if name_or_index in names else 0
            info = doc.embfile_info(idx)

        name = info.get("name", "")
        ext = name.split(".")[-1].lower() if "." in name else ""

        # Image extensions
        image_exts = {"jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "tiff", "ico"}

        # Text extensions
        text_exts = {"txt", "md", "json", "xml", "csv", "log", "html", "css", "js", "ts", "py", "rs", "go", "c", "cpp", "h", "hpp", "java", "kt", "swift", "rb", "php", "sh", "bash", "zsh", "yml", "yaml", "toml", "ini", "cfg", "conf"}

        result = {
            "name": name,
            "size": len(content),
            "type": "unknown",
            "content": None,
            "mime_type": None,
        }

        if ext in image_exts:
            # Return as base64 for images
            result["type"] = "image"
            result["content"] = base64.b64encode(content).decode("ascii")
            mime_map = {
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "gif": "image/gif",
                "webp": "image/webp",
                "svg": "image/svg+xml",
                "bmp": "image/bmp",
                "tiff": "image/tiff",
                "ico": "image/x-icon",
            }
            result["mime_type"] = mime_map.get(ext, "image/png")

        elif ext in text_exts:
            # Try to decode as text
            try:
                text = content.decode("utf-8")
                if len(text) > max_text_size:
                    text = text[:max_text_size] + "\n\n... (truncated)"
                result["type"] = "text"
                result["content"] = text
                result["mime_type"] = "text/plain"
            except UnicodeDecodeError:
                # Fall back to hex dump
                result["type"] = "binary"
                result["content"] = content[:1024].hex()
                result["mime_type"] = "application/octet-stream"

        else:
            # Unknown type - try text first, then hex
            try:
                text = content.decode("utf-8")
                if len(text) > max_text_size:
                    text = text[:max_text_size] + "\n\n... (truncated)"
                result["type"] = "text"
                result["content"] = text
                result["mime_type"] = "text/plain"
            except UnicodeDecodeError:
                result["type"] = "binary"
                result["content"] = content[:1024].hex()
                result["mime_type"] = "application/octet-stream"

        doc.close()
        return result

    except Exception as e:
        doc.close()
        return {
            "name": str(name_or_index),
            "size": 0,
            "type": "error",
            "content": str(e),
            "mime_type": None,
        }


def extract_attachment(input_path: Path, name_or_index: str | int, output_path: Path) -> dict[str, Any]:
    """Extract a single embedded file by name or index."""
    doc = fitz.open(str(input_path))

    try:
        # Try as index first if it's a number
        if isinstance(name_or_index, int) or name_or_index.isdigit():
            idx = int(name_or_index)
            content = doc.embfile_get(idx)
            info = doc.embfile_info(idx)
        else:
            # Try by name
            content = doc.embfile_get(name_or_index)
            # Find index for info
            names = doc.embfile_names()
            idx = names.index(name_or_index) if name_or_index in names else 0
            info = doc.embfile_info(idx)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content
        with output_path.open("wb") as f:
            f.write(content)

        doc.close()
        return {
            "success": True,
            "path": str(output_path),
            "name": info.get("name", ""),
            "size": len(content),
        }
    except Exception as e:
        doc.close()
        raise ValueError(f"Failed to extract attachment: {e}")


def extract_all_attachments(input_path: Path, output_dir: Path) -> list[dict[str, Any]]:
    """Extract all embedded files to a directory."""
    doc = fitz.open(str(input_path))

    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    count = doc.embfile_count()

    for i in range(count):
        info = doc.embfile_info(i)
        name = info.get("name", f"attachment_{i}")

        # Sanitize filename
        safe_name = "".join(c for c in name if c.isalnum() or c in "._-")
        if not safe_name:
            safe_name = f"attachment_{i}"

        output_path = output_dir / safe_name

        # Handle duplicates
        counter = 1
        original_path = output_path
        while output_path.exists():
            stem = original_path.stem
            suffix = original_path.suffix
            output_path = output_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        try:
            content = doc.embfile_get(i)
            with output_path.open("wb") as f:
                f.write(content)

            results.append({
                "success": True,
                "index": i,
                "name": name,
                "path": str(output_path),
                "size": len(content),
            })
        except Exception as e:
            results.append({
                "success": False,
                "index": i,
                "name": name,
                "error": str(e),
            })

    doc.close()
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF attachment operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # List command
    list_parser = subparsers.add_parser("list", help="List embedded files")
    list_parser.add_argument("--input", required=True, help="Input PDF path")

    # Extract single command
    extract_parser = subparsers.add_parser("extract", help="Extract a single file")
    extract_parser.add_argument("--input", required=True, help="Input PDF path")
    extract_parser.add_argument("--name", required=True, help="File name or index")
    extract_parser.add_argument("--output", required=True, help="Output file path")

    # Extract all command
    extract_all_parser = subparsers.add_parser("extract-all", help="Extract all files")
    extract_all_parser.add_argument("--input", required=True, help="Input PDF path")
    extract_all_parser.add_argument("--output-dir", required=True, help="Output directory")

    # Preview command
    preview_parser = subparsers.add_parser("preview", help="Get attachment content for preview")
    preview_parser.add_argument("--input", required=True, help="Input PDF path")
    preview_parser.add_argument("--name", required=True, help="File name or index")

    args = parser.parse_args()

    try:
        if args.command == "list":
            result = list_attachments(Path(args.input))
            print(json.dumps(result))

        elif args.command == "extract":
            result = extract_attachment(
                Path(args.input),
                args.name,
                Path(args.output)
            )
            print(json.dumps(result))

        elif args.command == "extract-all":
            result = extract_all_attachments(
                Path(args.input),
                Path(args.output_dir)
            )
            print(json.dumps(result))

        elif args.command == "preview":
            result = get_attachment_preview(
                Path(args.input),
                args.name
            )
            print(json.dumps(result))

        return 0

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
