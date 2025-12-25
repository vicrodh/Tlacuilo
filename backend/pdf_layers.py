"""
PDF Layers (Optional Content Groups) operations.

CLI usage (dev):
  python pdf_layers.py list --input doc.pdf
  python pdf_layers.py toggle --input doc.pdf --output out.pdf --layer "Layer1" --visible true
"""

from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


def get_layers(input_path: Path) -> dict:
    """
    Get all layers (OCGs) from a PDF.

    Returns dict with layer info.
    """
    result = {
        "has_layers": False,
        "layers": [],
        "error": None
    }

    try:
        doc = fitz.open(input_path)

        # Get OCG configuration
        ocgs = doc.get_ocgs()

        if ocgs:
            result["has_layers"] = True
            for xref, ocg_info in ocgs.items():
                layer = {
                    "xref": xref,
                    "name": ocg_info.get("name", f"Layer {xref}"),
                    "on": ocg_info.get("on", True),
                    "intent": ocg_info.get("intent", []),
                    "usage": ocg_info.get("usage", "")
                }
                result["layers"].append(layer)

        doc.close()

    except Exception as e:
        result["error"] = str(e)

    return result


def set_layer_visibility(
    input_path: Path,
    output_path: Path,
    layer_name: Optional[str] = None,
    layer_xref: Optional[int] = None,
    visible: bool = True
) -> dict:
    """
    Toggle visibility of a specific layer.

    Can identify layer by name or xref.
    """
    result = {
        "success": False,
        "message": "",
        "layer_name": layer_name or f"xref:{layer_xref}"
    }

    try:
        doc = fitz.open(input_path)
        ocgs = doc.get_ocgs()

        if not ocgs:
            result["message"] = "No layers found in document"
            doc.close()
            return result

        # Find the target layer
        target_xref = None
        if layer_xref is not None:
            target_xref = layer_xref
        elif layer_name:
            for xref, info in ocgs.items():
                if info.get("name") == layer_name:
                    target_xref = xref
                    break

        if target_xref is None:
            result["message"] = f"Layer not found: {layer_name or layer_xref}"
            doc.close()
            return result

        # Set layer visibility
        doc.set_layer(target_xref, on=visible)

        # Save
        doc.save(output_path)
        doc.close()

        result["success"] = True
        result["message"] = f"Layer '{layer_name or target_xref}' set to {'visible' if visible else 'hidden'}"

    except Exception as e:
        result["message"] = f"Failed to set layer visibility: {str(e)}"

    return result


def set_all_layers(
    input_path: Path,
    output_path: Path,
    visible: bool = True
) -> dict:
    """
    Set visibility of all layers at once.
    """
    result = {
        "success": False,
        "message": "",
        "layers_affected": 0
    }

    try:
        doc = fitz.open(input_path)
        ocgs = doc.get_ocgs()

        if not ocgs:
            result["message"] = "No layers found in document"
            doc.close()
            return result

        count = 0
        for xref in ocgs.keys():
            doc.set_layer(xref, on=visible)
            count += 1

        doc.save(output_path)
        doc.close()

        result["success"] = True
        result["layers_affected"] = count
        result["message"] = f"Set {count} layers to {'visible' if visible else 'hidden'}"

    except Exception as e:
        result["message"] = f"Failed to set layers: {str(e)}"

    return result


def main():
    parser = argparse.ArgumentParser(description="PDF Layers operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # List command
    list_parser = subparsers.add_parser("list", help="List all layers")
    list_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Toggle command
    toggle_parser = subparsers.add_parser("toggle", help="Toggle layer visibility")
    toggle_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    toggle_parser.add_argument("--output", "-o", required=True, help="Output PDF path")
    toggle_parser.add_argument("--layer", "-l", help="Layer name")
    toggle_parser.add_argument("--xref", type=int, help="Layer xref")
    toggle_parser.add_argument("--visible", type=lambda x: x.lower() == 'true', default=True,
                               help="Set visibility (true/false)")
    toggle_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Show all / Hide all
    all_parser = subparsers.add_parser("all", help="Set all layers visibility")
    all_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    all_parser.add_argument("--output", "-o", required=True, help="Output PDF path")
    all_parser.add_argument("--visible", type=lambda x: x.lower() == 'true', required=True,
                            help="Set all to visible (true/false)")
    all_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "list":
        result = get_layers(Path(args.input))

        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            if result.get("error"):
                print(f"Error: {result['error']}")
                sys.exit(1)
            if not result["has_layers"]:
                print("No layers found")
            else:
                print(f"Found {len(result['layers'])} layer(s):")
                for layer in result["layers"]:
                    status = "ON" if layer["on"] else "OFF"
                    print(f"  [{status}] {layer['name']} (xref: {layer['xref']})")

    elif args.command == "toggle":
        if not args.layer and not args.xref:
            print("Error: --layer or --xref required")
            sys.exit(1)

        result = set_layer_visibility(
            Path(args.input),
            Path(args.output),
            layer_name=args.layer,
            layer_xref=args.xref,
            visible=args.visible
        )

        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            print(result["message"])
            sys.exit(0 if result["success"] else 1)

    elif args.command == "all":
        result = set_all_layers(
            Path(args.input),
            Path(args.output),
            visible=args.visible
        )

        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            print(result["message"])
            sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
