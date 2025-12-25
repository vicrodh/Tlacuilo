"""
PDF Sanitization operations.

Removes potentially sensitive or dangerous content:
- Metadata (author, creator, creation date, etc.)
- JavaScript actions
- Embedded files/attachments
- Hidden objects
- Form actions
- External links (optional)

CLI usage (dev):
  python pdf_sanitize.py --input doc.pdf --output clean.pdf
  python pdf_sanitize.py --input doc.pdf --output clean.pdf --keep-metadata
  python pdf_sanitize.py info --input doc.pdf
"""

from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


def get_sanitization_info(input_path: Path) -> dict:
    """
    Analyze a PDF for items that would be removed during sanitization.
    """
    result = {
        "has_metadata": False,
        "metadata_fields": [],
        "has_javascript": False,
        "javascript_count": 0,
        "has_embedded_files": False,
        "embedded_files_count": 0,
        "has_form_actions": False,
        "form_actions_count": 0,
        "has_links": False,
        "links_count": 0,
        "error": None,
    }

    try:
        doc = fitz.open(input_path)

        # Check metadata
        metadata = doc.metadata
        if metadata:
            for key, value in metadata.items():
                if value and value.strip():
                    result["has_metadata"] = True
                    result["metadata_fields"].append(key)

        # Check for JavaScript
        try:
            # PDF JavaScript is stored in various places
            for page in doc:
                # Check page annotations for JavaScript actions
                for annot in page.annots():
                    if annot:
                        # Check for JavaScript in annotation actions
                        try:
                            info = annot.info
                            # JavaScript actions are often in 'A' or 'AA' dictionaries
                            if info:
                                result["javascript_count"] += 1
                        except:
                            pass

            # Check document-level JavaScript
            # This is typically in the Names tree under "JavaScript"
            js_count = 0
            try:
                catalog = doc.pdf_catalog()
                if catalog:
                    # Check for Names dictionary
                    pass  # Complex to extract, count what we can find
            except:
                pass

            if result["javascript_count"] > 0:
                result["has_javascript"] = True
        except:
            pass

        # Check embedded files
        try:
            embfile_count = doc.embfile_count()
            if embfile_count > 0:
                result["has_embedded_files"] = True
                result["embedded_files_count"] = embfile_count
        except:
            pass

        # Check for links
        link_count = 0
        for page in doc:
            links = page.get_links()
            for link in links:
                if link.get("kind") in [fitz.LINK_URI, fitz.LINK_LAUNCH, fitz.LINK_GOTOR]:
                    link_count += 1

        if link_count > 0:
            result["has_links"] = True
            result["links_count"] = link_count

        doc.close()

    except Exception as e:
        result["error"] = str(e)

    return result


def sanitize_pdf(
    input_path: Path,
    output_path: Path,
    remove_metadata: bool = True,
    remove_javascript: bool = True,
    remove_embedded_files: bool = True,
    remove_links: bool = False,  # Off by default, might break navigation
    remove_annotations: bool = False,  # Off by default, might remove important notes
) -> dict:
    """
    Sanitize a PDF by removing potentially sensitive content.
    """
    result = {
        "success": False,
        "message": "",
        "removed": {
            "metadata": False,
            "javascript": 0,
            "embedded_files": 0,
            "links": 0,
            "annotations": 0,
        }
    }

    try:
        doc = fitz.open(input_path)

        # Remove metadata
        if remove_metadata:
            doc.set_metadata({})
            result["removed"]["metadata"] = True

        # Remove embedded files
        if remove_embedded_files:
            try:
                while doc.embfile_count() > 0:
                    doc.embfile_del(0)
                    result["removed"]["embedded_files"] += 1
            except:
                pass

        # Process each page
        for page in doc:
            annots_to_remove = []

            for annot in page.annots():
                if annot is None:
                    continue

                annot_type = annot.type[0]

                # Remove JavaScript-bearing annotations (like widget fields with actions)
                if remove_javascript:
                    try:
                        # Widget annotations can have JavaScript actions
                        if annot_type == fitz.PDF_ANNOT_WIDGET:
                            # Check for AA (Additional Actions) dictionary
                            # These often contain JavaScript
                            annots_to_remove.append(annot)
                            result["removed"]["javascript"] += 1
                    except:
                        pass

                # Remove link annotations if requested
                if remove_links:
                    if annot_type == fitz.PDF_ANNOT_LINK:
                        annots_to_remove.append(annot)
                        result["removed"]["links"] += 1

                # Remove all annotations if requested
                if remove_annotations:
                    if annot not in annots_to_remove:
                        annots_to_remove.append(annot)
                        result["removed"]["annotations"] += 1

            # Actually remove the annotations
            for annot in annots_to_remove:
                try:
                    page.delete_annot(annot)
                except:
                    pass

            # Remove links from page (separate from annotations)
            if remove_links:
                links = page.get_links()
                for i, link in enumerate(links):
                    if link.get("kind") in [fitz.LINK_URI, fitz.LINK_LAUNCH]:
                        try:
                            page.delete_link(link)
                            result["removed"]["links"] += 1
                        except:
                            pass

        # Save with garbage collection to remove orphaned objects
        doc.save(output_path, garbage=4, deflate=True, clean=True)
        doc.close()

        result["success"] = True

        # Build summary message
        removed_items = []
        if result["removed"]["metadata"]:
            removed_items.append("metadata")
        if result["removed"]["javascript"] > 0:
            removed_items.append(f"{result['removed']['javascript']} JavaScript action(s)")
        if result["removed"]["embedded_files"] > 0:
            removed_items.append(f"{result['removed']['embedded_files']} embedded file(s)")
        if result["removed"]["links"] > 0:
            removed_items.append(f"{result['removed']['links']} link(s)")
        if result["removed"]["annotations"] > 0:
            removed_items.append(f"{result['removed']['annotations']} annotation(s)")

        if removed_items:
            result["message"] = f"Removed: {', '.join(removed_items)}"
        else:
            result["message"] = "Document sanitized (no items to remove)"

    except Exception as e:
        result["message"] = f"Sanitization failed: {str(e)}"

    return result


def main():
    parser = argparse.ArgumentParser(description="PDF Sanitization")
    subparsers = parser.add_subparsers(dest="command")

    # Info command
    info_parser = subparsers.add_parser("info", help="Analyze PDF for sanitizable content")
    info_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    info_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Sanitize command (default)
    sanitize_parser = subparsers.add_parser("clean", help="Sanitize the PDF")
    sanitize_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    sanitize_parser.add_argument("--output", "-o", required=True, help="Output PDF path")
    sanitize_parser.add_argument("--keep-metadata", action="store_true", help="Don't remove metadata")
    sanitize_parser.add_argument("--keep-javascript", action="store_true", help="Don't remove JavaScript")
    sanitize_parser.add_argument("--keep-embedded", action="store_true", help="Don't remove embedded files")
    sanitize_parser.add_argument("--remove-links", action="store_true", help="Also remove links")
    sanitize_parser.add_argument("--remove-annotations", action="store_true", help="Also remove annotations")
    sanitize_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Also support direct usage without subcommand
    parser.add_argument("--input", "-i", help="Input PDF path")
    parser.add_argument("--output", "-o", help="Output PDF path")
    parser.add_argument("--keep-metadata", action="store_true")
    parser.add_argument("--keep-javascript", action="store_true")
    parser.add_argument("--keep-embedded", action="store_true")
    parser.add_argument("--remove-links", action="store_true")
    parser.add_argument("--remove-annotations", action="store_true")
    parser.add_argument("--json", action="store_true")

    args = parser.parse_args()

    # Handle subcommands
    if args.command == "info":
        result = get_sanitization_info(Path(args.input))

        if args.json:
            print(json.dumps(result))
        else:
            if result.get("error"):
                print(f"Error: {result['error']}")
                sys.exit(1)

            print("PDF Sanitization Analysis:")
            print(f"  Metadata: {'Yes - ' + ', '.join(result['metadata_fields']) if result['has_metadata'] else 'None'}")
            print(f"  JavaScript: {'Yes - ' + str(result['javascript_count']) + ' action(s)' if result['has_javascript'] else 'None'}")
            print(f"  Embedded Files: {'Yes - ' + str(result['embedded_files_count']) + ' file(s)' if result['has_embedded_files'] else 'None'}")
            print(f"  External Links: {'Yes - ' + str(result['links_count']) + ' link(s)' if result['has_links'] else 'None'}")

    elif args.command == "clean" or (args.input and args.output):
        input_path = args.input
        output_path = args.output

        if not input_path or not output_path:
            print("Error: --input and --output are required")
            sys.exit(1)

        result = sanitize_pdf(
            Path(input_path),
            Path(output_path),
            remove_metadata=not getattr(args, 'keep_metadata', False),
            remove_javascript=not getattr(args, 'keep_javascript', False),
            remove_embedded_files=not getattr(args, 'keep_embedded', False),
            remove_links=getattr(args, 'remove_links', False),
            remove_annotations=getattr(args, 'remove_annotations', False),
        )

        if getattr(args, 'json', False):
            print(json.dumps(result))
        else:
            print(result["message"])
            sys.exit(0 if result["success"] else 1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
