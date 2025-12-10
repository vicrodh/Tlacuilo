"""
Page operations: merge, split, reorder, rotate.

CLI usage (dev):
  python pdf_pages.py merge --inputs in1.pdf in2.pdf --output merged.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Sequence

from pypdf import PdfReader, PdfWriter


def merge_pdfs(inputs: Sequence[Path], output: Path) -> None:
    if len(inputs) < 2:
        raise ValueError("At least two input PDFs are required.")
    writer = PdfWriter()
    for path in inputs:
        reader = PdfReader(str(path))
        for page in reader.pages:
            writer.add_page(page)
    with output.open("wb") as fh:
        writer.write(fh)


def reorder_pages(input_path: Path, order: Sequence[int], output: Path) -> None:
    reader = PdfReader(str(input_path))
    writer = PdfWriter()
    total = len(reader.pages)
    for idx in order:
        if idx < 0 or idx >= total:
            raise ValueError(f"Page index {idx} out of bounds for document with {total} pages.")
        writer.add_page(reader.pages[idx])
    with output.open("wb") as fh:
        writer.write(fh)


def split_pdf(input_path: Path, ranges: Iterable[str], output_dir: Path) -> list[Path]:
    reader = PdfReader(str(input_path))
    output_dir.mkdir(parents=True, exist_ok=True)
    total = len(reader.pages)

    # If no ranges provided, split page by page.
    ranges_list = list(ranges)
    if not ranges_list:
        ranges_list = [str(i) for i in range(1, total + 1)]

    outputs: list[Path] = []
    for i, range_expr in enumerate(ranges_list, start=1):
        writer = PdfWriter()
        for page_index in parse_ranges(range_expr, total):
            writer.add_page(reader.pages[page_index])
        out_path = output_dir / f"split_{i}.pdf"
        with out_path.open("wb") as fh:
            writer.write(fh)
        outputs.append(out_path)
    return outputs


def rotate_pages(input_path: Path, rotations: dict[int, int], output: Path) -> None:
    reader = PdfReader(str(input_path))
    writer = PdfWriter()
    total = len(reader.pages)
    for idx, page in enumerate(reader.pages):
        rotation = rotations.get(idx, 0) % 360
        rotated = page.rotate(rotation)
        writer.add_page(rotated)
    with output.open("wb") as fh:
        writer.write(fh)


def parse_ranges(expr: str, total_pages: int) -> list[int]:
    result: list[int] = []
    parts = [p.strip() for p in expr.split(",") if p.strip()]
    for part in parts:
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start = int(start_str) - 1
            end = int(end_str) - 1
            if start < 0 or end < start or end >= total_pages:
                raise ValueError(f"Invalid range '{part}' for {total_pages} pages.")
            result.extend(range(start, end + 1))
        else:
            idx = int(part) - 1
            if idx < 0 or idx >= total_pages:
                raise ValueError(f"Page {part} out of bounds for {total_pages} pages.")
            result.append(idx)
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PDF page operations")
    sub = parser.add_subparsers(dest="command", required=True)

    merge_p = sub.add_parser("merge", help="Merge multiple PDFs")
    merge_p.add_argument("--inputs", nargs="+", required=True, help="Input PDF paths")
    merge_p.add_argument("--output", required=True, help="Output PDF path")

    reorder_p = sub.add_parser("reorder", help="Reorder pages of a PDF")
    reorder_p.add_argument("--input", required=True, help="Input PDF path")
    reorder_p.add_argument("--order", nargs="+", type=int, required=True, help="Zero-based page order")
    reorder_p.add_argument("--output", required=True, help="Output PDF path")

    split_p = sub.add_parser("split", help="Split PDF by ranges")
    split_p.add_argument("--input", required=True, help="Input PDF path")
    split_p.add_argument("--ranges", nargs="*", help="Ranges like 1-3,5; empty = split every page")
    split_p.add_argument("--output-dir", required=True, help="Directory for split PDFs")

    rotate_p = sub.add_parser("rotate", help="Rotate pages")
    rotate_p.add_argument("--input", required=True, help="Input PDF path")
    rotate_p.add_argument(
        "--rotation",
        nargs="*",
        help="page=degrees, e.g., 0=90 2=180; empty = apply --degrees to all pages",
    )
    rotate_p.add_argument("--degrees", type=int, default=90, help="Degrees when rotation list is empty (default 90)")
    rotate_p.add_argument("--output", required=True, help="Output PDF path")

    return parser


def _main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "merge":
            merge_pdfs([Path(p) for p in args.inputs], Path(args.output))
        elif args.command == "reorder":
            reorder_pages(Path(args.input), args.order, Path(args.output))
        elif args.command == "split":
            ranges = args.ranges or []
            split_pdf(Path(args.input), ranges, Path(args.output_dir))
        elif args.command == "rotate":
            rotations: dict[int, int] = {}
            if args.rotation:
                for pair in args.rotation:
                    page_str, deg_str = pair.split("=", 1)
                    rotations[int(page_str)] = int(deg_str)
            else:
                # Apply degrees to all pages
                reader = PdfReader(str(args.input))
                for idx in range(len(reader.pages)):
                    rotations[idx] = args.degrees
            rotate_pages(Path(args.input), rotations, Path(args.output))
        else:
            parser.error("Unknown command")
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
