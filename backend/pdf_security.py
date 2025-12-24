"""
PDF Security operations: unlock, encrypt, decrypt.

CLI usage (dev):
  python pdf_security.py unlock --input locked.pdf --output unlocked.pdf
  python pdf_security.py unlock --input locked.pdf --output unlocked.pdf --password secret
  python pdf_security.py encrypt --input in.pdf --output encrypted.pdf --user-password view --owner-password admin
"""

from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path

import pikepdf


def unlock_pdf(
    input_path: Path,
    output_path: Path,
    password: str | None = None
) -> dict:
    """
    Remove all restrictions from a PDF.

    - If PDF has no encryption: copies as-is
    - If PDF has user password: requires password to open
    - If PDF has only owner password (restrictions): removes restrictions without password

    Returns a dict with status info.
    """
    result = {
        "success": False,
        "was_encrypted": False,
        "had_restrictions": False,
        "message": ""
    }

    try:
        # Try to open without password first
        try:
            pdf = pikepdf.open(input_path)
            result["was_encrypted"] = pdf.is_encrypted
        except pikepdf.PasswordError:
            # Needs password to open
            if not password:
                result["message"] = "PDF requires a password to open"
                result["needs_password"] = True
                return result
            pdf = pikepdf.open(input_path, password=password)
            result["was_encrypted"] = True

        # Check if there are restrictions
        if pdf.is_encrypted:
            result["had_restrictions"] = True

        # Save without encryption (removes all restrictions)
        pdf.save(output_path)
        pdf.close()

        result["success"] = True
        if result["was_encrypted"] or result["had_restrictions"]:
            result["message"] = "PDF unlocked successfully"
        else:
            result["message"] = "PDF was not encrypted, copied as-is"

    except pikepdf.PasswordError:
        result["message"] = "Incorrect password"
        result["needs_password"] = True
    except Exception as e:
        result["message"] = f"Failed to unlock PDF: {str(e)}"

    return result


def encrypt_pdf(
    input_path: Path,
    output_path: Path,
    user_password: str | None = None,
    owner_password: str | None = None,
    allow_printing: bool = True,
    allow_copying: bool = True,
    allow_modifying: bool = False,
    allow_annotating: bool = True
) -> dict:
    """
    Encrypt a PDF with optional user/owner passwords and permissions.

    - user_password: Required to open the PDF (can be empty for no open password)
    - owner_password: Required to change permissions/remove encryption
    """
    result = {
        "success": False,
        "message": ""
    }

    try:
        pdf = pikepdf.open(input_path)

        # Build permissions
        permissions = pikepdf.Permissions(
            print_lowres=allow_printing,
            print_highres=allow_printing,
            extract=allow_copying,
            modify_other=allow_modifying,
            modify_annotation=allow_annotating,
            modify_form=allow_annotating,
            modify_assembly=allow_modifying,
            accessibility=True  # Always allow accessibility
        )

        # At least one password must be set
        if not user_password and not owner_password:
            owner_password = ""  # pikepdf requires at least owner password

        pdf.save(
            output_path,
            encryption=pikepdf.Encryption(
                user=user_password or "",
                owner=owner_password or user_password or "",
                allow=permissions
            )
        )
        pdf.close()

        result["success"] = True
        result["message"] = "PDF encrypted successfully"

    except Exception as e:
        result["message"] = f"Failed to encrypt PDF: {str(e)}"

    return result


def check_pdf_security(input_path: Path) -> dict:
    """
    Check the security status of a PDF.
    """
    result = {
        "is_encrypted": False,
        "needs_password": False,
        "has_restrictions": False,
        "permissions": {}
    }

    try:
        try:
            pdf = pikepdf.open(input_path)
        except pikepdf.PasswordError:
            result["needs_password"] = True
            result["is_encrypted"] = True
            return result

        result["is_encrypted"] = pdf.is_encrypted

        if pdf.is_encrypted:
            result["has_restrictions"] = True
            # Try to get permissions info
            try:
                perms = pdf.allow
                result["permissions"] = {
                    "printing": perms.print_lowres or perms.print_highres,
                    "copying": perms.extract,
                    "modifying": perms.modify_other,
                    "annotating": perms.modify_annotation
                }
            except:
                pass

        pdf.close()

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="PDF Security operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Unlock command
    unlock_parser = subparsers.add_parser("unlock", help="Remove PDF restrictions")
    unlock_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    unlock_parser.add_argument("--output", "-o", required=True, help="Output PDF path")
    unlock_parser.add_argument("--password", "-p", help="Password if required")
    unlock_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Encrypt command
    encrypt_parser = subparsers.add_parser("encrypt", help="Encrypt PDF")
    encrypt_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    encrypt_parser.add_argument("--output", "-o", required=True, help="Output PDF path")
    encrypt_parser.add_argument("--user-password", help="Password to open PDF")
    encrypt_parser.add_argument("--owner-password", help="Password to modify permissions")
    encrypt_parser.add_argument("--no-print", action="store_true", help="Disable printing")
    encrypt_parser.add_argument("--no-copy", action="store_true", help="Disable copying")
    encrypt_parser.add_argument("--no-modify", action="store_true", help="Disable modifying")
    encrypt_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Check command
    check_parser = subparsers.add_parser("check", help="Check PDF security status")
    check_parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    check_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "unlock":
        result = unlock_pdf(
            Path(args.input),
            Path(args.output),
            args.password
        )
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            print(result["message"])
            sys.exit(0 if result["success"] else 1)

    elif args.command == "encrypt":
        result = encrypt_pdf(
            Path(args.input),
            Path(args.output),
            args.user_password,
            args.owner_password,
            allow_printing=not args.no_print,
            allow_copying=not args.no_copy,
            allow_modifying=not args.no_modify
        )
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            print(result["message"])
            sys.exit(0 if result["success"] else 1)

    elif args.command == "check":
        result = check_pdf_security(Path(args.input))
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result))
        else:
            if result.get("needs_password"):
                print("PDF requires password to open")
            elif result["is_encrypted"]:
                print("PDF has restrictions")
            else:
                print("PDF is not encrypted")


if __name__ == "__main__":
    main()
