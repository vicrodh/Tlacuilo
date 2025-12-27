#!/usr/bin/env python3
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

try:
    import cv2
    import numpy as np
    from fontTools.ttLib import TTCollection, TTFont
    from PIL import Image, ImageDraw, ImageFont
except Exception as exc:  # pragma: no cover
    sys.stderr.write(f"Missing dependency: {exc}\n")
    sys.exit(1)

SAMPLES = {
    "primary": "Hamburgefonstiv 0123456789",
    "alpha": "The quick brown fox jumps",
    "caps": "TYPOGRAPHY",
}
DEFAULT_SIZE = (256, 64)


def error_exit(message: str) -> None:
    sys.stderr.write(message + "\n")
    sys.exit(1)


def get_script_dir() -> Path:
    return Path(__file__).resolve().parent


def exclusions_path() -> Path:
    return get_script_dir() / "font_detect_exclusions.json"


def load_exclusions() -> dict:
    path = exclusions_path()
    if not path.exists():
        return {"names": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"names": []}


def is_excluded(name: str, path: str, exclusions: dict) -> bool:
    lowered = name.lower()
    if "glyphlessfont" in lowered or "glyph" in lowered:
        return True
    if any(token in lowered for token in ["dingbats", "wingdings", "symbol", "emoji"]):
        return True
    try:
        if os.path.getsize(path) < 10 * 1024:
            return True
    except OSError:
        return True
    for banned in exclusions.get("names", []):
        if banned.lower() in lowered:
            return True
    return False


def preprocess_image(img: Image.Image, target_height: int) -> Image.Image:
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    coords = cv2.findNonZero(255 - binary)
    if coords is None:
        processed = binary
    else:
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) > 1.0:
            (h, w) = binary.shape[:2]
            center = (w // 2, h // 2)
            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            binary = cv2.warpAffine(binary, matrix, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)

        coords = cv2.findNonZero(255 - binary)
        if coords is None:
            processed = binary
        else:
            x, y, w, h = cv2.boundingRect(coords)
            processed = binary[y:y + h, x:x + w]

    if processed.size == 0:
        processed = binary

    h, w = processed.shape[:2]
    if h == 0:
        return Image.fromarray(binary)

    scale = target_height / float(h)
    new_w = max(1, int(w * scale))
    resized = cv2.resize(processed, (new_w, target_height), interpolation=cv2.INTER_AREA)

    canvas = np.full((target_height, DEFAULT_SIZE[0]), 255, dtype=np.uint8)
    if new_w > DEFAULT_SIZE[0]:
        resized = cv2.resize(resized, DEFAULT_SIZE, interpolation=cv2.INTER_AREA)
        canvas = resized
    else:
        x_offset = (DEFAULT_SIZE[0] - new_w) // 2
        canvas[:, x_offset:x_offset + new_w] = resized

    return Image.fromarray(canvas)


def render_sample(font_path: str, text: str, font_index: int | None) -> Image.Image | None:
    img = Image.new("L", DEFAULT_SIZE, color=255)
    draw = ImageDraw.Draw(img)
    font_size = 42
    font = None
    bbox = None

    for _ in range(8):
        try:
            font = ImageFont.truetype(font_path, font_size, index=font_index or 0)
        except Exception:
            font = None
            break

        try:
            bbox = draw.textbbox((0, 0), text, font=font)
        except Exception:
            return None
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if text_w <= DEFAULT_SIZE[0] - 8 and text_h <= DEFAULT_SIZE[1] - 8:
            break
        font_size -= 4
        if font_size < 10:
            break

    if not font or not bbox:
        return None

    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (DEFAULT_SIZE[0] - text_w) / 2 - bbox[0]
    y = (DEFAULT_SIZE[1] - text_h) / 2 - bbox[1]

    try:
        draw.text((x, y), text, font=font, fill=0)
    except Exception:
        return None
    return preprocess_image(img.convert("RGB"), DEFAULT_SIZE[1])


def encode_png(img: Image.Image) -> str:
    buffer = BytesBuffer()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def classify_font(font: TTFont, family: str, style: str) -> tuple[str, int, bool]:
    name = f"{family} {style}".lower()
    category = "sans-serif"
    weight = 400
    italic = "italic" in name or "oblique" in name

    if any(token in name for token in ["mono", "code", "typewriter"]):
        category = "monospace"
    elif any(token in name for token in ["script", "cursive", "hand"]):
        category = "script"
    elif any(token in name for token in ["display", "blackletter", "decorative"]):
        category = "display"
    elif "serif" in name:
        category = "serif"

    if "OS/2" in font:
        os2 = font["OS/2"]
        weight = int(getattr(os2, "usWeightClass", weight))
        italic = bool(os2.fsSelection & 0x01) or italic
        panose = getattr(os2, "panose", None)
        if panose:
            if getattr(panose, "bProportion", 0) == 9:
                category = "monospace"
            serif_style = getattr(panose, "bSerifStyle", 0)
            if 2 <= serif_style <= 7:
                category = "serif"

    return category, weight, italic


def get_name(font: TTFont, name_id: int) -> str | None:
    if "name" not in font:
        return None
    for record in font["name"].names:
        if record.nameID == name_id:
            try:
                return record.toUnicode()
            except Exception:
                try:
                    return record.string.decode("utf-8", errors="ignore")
                except Exception:
                    continue
    return None


def iter_font_files(folders: list[str]) -> list[str]:
    exts = {".ttf", ".otf", ".ttc", ".otc", ".woff", ".woff2"}
    files: list[str] = []
    for folder in folders:
        path = Path(folder)
        if not path.exists():
            continue
        for file_path in path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in exts:
                files.append(str(file_path))
    return files


def build_catalog(folders: list[str], output: str) -> None:
    start = time.time()
    exclusions = load_exclusions()
    files = iter_font_files(folders)
    if not files:
        error_exit("No fonts found in provided folders")

    catalog = {
        "version": 1,
        "samples": SAMPLES,
        "template_size": list(DEFAULT_SIZE),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": folders,
        "fonts": [],
    }

    seen = {}

    for path in files:
        suffix = Path(path).suffix.lower()
        if suffix in {".ttc", ".otc"}:
            try:
                collection = TTCollection(path)
            except Exception:
                continue
            for idx, font in enumerate(collection.fonts):
                entry = build_entry(font, path, idx, exclusions)
                if entry:
                    merge_entry(entry, catalog, seen)
        else:
            try:
                font = TTFont(path, lazy=True)
            except Exception:
                continue
            entry = build_entry(font, path, None, exclusions)
            if entry:
                merge_entry(entry, catalog, seen)
            try:
                font.close()
            except Exception:
                pass

    catalog_path = Path(output)
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=True), encoding="utf-8")
    elapsed_ms = int((time.time() - start) * 1000)
    print(f"Catalog written: {catalog_path} ({len(catalog['fonts'])} fonts, {elapsed_ms} ms)")


def build_entry(font: TTFont, path: str, font_index: int | None, exclusions: dict) -> dict | None:
    family = get_name(font, 1) or Path(path).stem
    style = get_name(font, 2) or "Regular"
    full_name = f"{family} {style}".strip()
    if is_excluded(full_name, path, exclusions):
        return None

    category, weight, italic = classify_font(font, family, style)
    postscript = get_name(font, 6) or full_name

    templates = {}
    for key, sample in SAMPLES.items():
        img = render_sample(path, sample, font_index)
        if img is None:
            return None
        templates[key] = encode_png(img)

    font_id = f"{postscript}|{weight}|{int(italic)}|{font_index or 0}"
    font_id = str(abs(hash(font_id)))

    return {
        "id": font_id,
        "family": family,
        "style": style,
        "category": category,
        "weight": weight,
        "italic": italic,
        "postscript": postscript,
        "font_index": font_index,
        "sources": [path],
        "templates": templates,
    }


def merge_entry(entry: dict, catalog: dict, seen: dict) -> None:
    key = (entry["family"].lower(), entry["style"].lower(), entry["weight"], entry["italic"])
    existing = seen.get(key)
    if existing is None:
        catalog["fonts"].append(entry)
        seen[key] = entry
        return
    existing["sources"].extend(entry.get("sources", []))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build font catalog for offline identification")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build catalog")
    build.add_argument("--output", default=str(get_script_dir() / "font_catalog.json"))
    build.add_argument("--folders", nargs="+", required=True, help="Folders to scan")

    return parser


class BytesBuffer(bytearray):
    def write(self, b):
        self.extend(b)

    def getvalue(self):
        return bytes(self)


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "build":
        build_catalog(args.folders, args.output)
