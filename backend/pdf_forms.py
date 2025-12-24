#!/usr/bin/env python3
"""
PDF Form Fields (AcroForms) handling using PyMuPDF.
Supports reading, filling, and saving form fields.
"""

import sys
import json
import fitz  # PyMuPDF

# Field type constants from PyMuPDF
FIELD_TYPES = {
    0: "unknown",
    1: "button",      # Includes checkboxes and radio buttons
    2: "checkbox",
    3: "radiobutton",
    4: "text",
    5: "listbox",
    6: "combobox",
    7: "signature",
}


def get_field_type_name(field_type: int) -> str:
    """Convert field type integer to readable name."""
    return FIELD_TYPES.get(field_type, "unknown")


def list_form_fields(pdf_path: str) -> dict:
    """
    List all form fields in a PDF.
    Returns a dict with fields grouped by page.
    """
    doc = fitz.open(pdf_path)

    if not doc.is_form_pdf:
        doc.close()
        return {"is_form": False, "fields": [], "field_count": 0}

    fields = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        widget = page.first_widget

        while widget:
            field_info = {
                "name": widget.field_name or f"unnamed_{page_num}_{len(fields)}",
                "type": get_field_type_name(widget.field_type),
                "type_id": widget.field_type,
                "value": widget.field_value,
                "page": page_num,
                "rect": list(widget.rect),
                "flags": widget.field_flags,
                "read_only": bool(widget.field_flags & 1),  # Bit 1 = ReadOnly
            }

            # Add choices for dropdown/listbox
            if widget.field_type in (5, 6):  # listbox or combobox
                field_info["choices"] = widget.choice_values or []

            # Add button states for checkboxes/radio buttons
            if widget.field_type in (1, 2, 3):  # button types
                states = widget.button_states()
                field_info["on_state"] = widget.on_state()
                field_info["button_states"] = states
                # For checkboxes, value is True/False
                if widget.field_type == 2:
                    field_info["checked"] = widget.field_value == widget.on_state()

            # Add text field properties
            if widget.field_type == 4:  # text
                field_info["max_length"] = widget.text_maxlen
                field_info["multiline"] = bool(widget.field_flags & (1 << 12))

            fields.append(field_info)
            widget = widget.next

    doc.close()

    return {
        "is_form": True,
        "fields": fields,
        "field_count": len(fields),
    }


def fill_form_fields(pdf_path: str, output_path: str, field_values: dict) -> dict:
    """
    Fill form fields and save to a new file.

    Args:
        pdf_path: Path to source PDF
        output_path: Path to save filled PDF
        field_values: Dict mapping field names to values

    Returns:
        Dict with success status and filled field count
    """
    doc = fitz.open(pdf_path)

    if not doc.is_form_pdf:
        doc.close()
        return {"success": False, "error": "PDF does not contain form fields"}

    filled_count = 0
    errors = []

    for page in doc:
        widget = page.first_widget

        while widget:
            field_name = widget.field_name

            if field_name in field_values:
                try:
                    value = field_values[field_name]

                    # Handle different field types
                    if widget.field_type == 2:  # checkbox
                        if value is True or value == widget.on_state():
                            widget.field_value = widget.on_state()
                        else:
                            widget.field_value = False

                    elif widget.field_type == 3:  # radio button
                        if value == widget.on_state():
                            widget.field_value = widget.on_state()

                    elif widget.field_type in (5, 6):  # listbox/combobox
                        if value in (widget.choice_values or []):
                            widget.field_value = value
                        else:
                            errors.append(f"Invalid choice for {field_name}: {value}")

                    else:  # text and other fields
                        widget.field_value = str(value) if value is not None else ""

                    widget.update()
                    filled_count += 1

                except Exception as e:
                    errors.append(f"Error filling {field_name}: {str(e)}")

            widget = widget.next

    # Save the filled form
    doc.save(output_path)
    doc.close()

    return {
        "success": True,
        "filled_count": filled_count,
        "errors": errors if errors else None,
        "output_path": output_path,
    }


def main():
    """CLI interface for form operations."""
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: pdf_forms.py <operation> <pdf_path> [args...]"}))
        sys.exit(1)

    operation = sys.argv[1]
    pdf_path = sys.argv[2]

    try:
        if operation == "list":
            result = list_form_fields(pdf_path)

        elif operation == "fill":
            if len(sys.argv) < 5:
                print(json.dumps({"error": "Usage: pdf_forms.py fill <pdf_path> <output_path> <json_values>"}))
                sys.exit(1)
            output_path = sys.argv[3]
            field_values = json.loads(sys.argv[4])
            result = fill_form_fields(pdf_path, output_path, field_values)

        else:
            result = {"error": f"Unknown operation: {operation}"}

        print(json.dumps(result))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
