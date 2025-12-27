#!/usr/bin/env python3
import argparse
import base64
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path
try:
    import cv2
    import numpy as np
    from fontTools.ttLib import TTFont
    from PIL import Image, ImageDraw, ImageFont
except Exception as exc:  # pragma: no cover - critical import
    sys.stderr.write(
        json.dumps(
            {"ok": False, "error": f"Required dependency missing: {exc}", "code": "DEPENDENCY_MISSING"},
            ensure_ascii=True,
        )
    )
    sys.exit(1)

SAMPLES = {
    "primary": "Hamburgefonstiv 0123456789",
    "alpha": "The quick brown fox jumps",
    "caps": "TYPOGRAPHY",
}
DEFAULT_SIZE = (256, 64)
DEBUG_DIR_NAME = "debug"
CATALOG_FILENAME = "font_catalog.json"
CATALOG_ARCHIVE = "font_catalog.json.gz"


def json_print(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True))
    sys.stdout.flush()


def error_exit(message: str, code: str = "FONT_DETECT_ERROR") -> None:
    sys.stderr.write(json.dumps({"ok": False, "error": message, "code": code}, ensure_ascii=True))
    sys.stderr.flush()
    sys.exit(1)


def get_cache_dir() -> Path:
    base = os.environ.get("TLACUILO_CACHE_DIR")
    if base:
        root = Path(base)
    else:
        root = Path.home() / ".cache" / "tlacuilo"
    cache_dir = root / "font-detect"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_script_dir() -> Path:
    return Path(__file__).resolve().parent


def exclusions_path() -> Path:
    return get_script_dir() / "font_detect_exclusions.json"


def catalog_path() -> Path:
    return get_script_dir() / CATALOG_FILENAME


def catalog_archive_path() -> Path:
    return get_script_dir() / CATALOG_ARCHIVE


def load_exclusions() -> dict:
    path = exclusions_path()
    if not path.exists():
        return {"names": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"names": []}


def load_catalog_from_path(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_catalog_from_gzip(path: Path, dest: Path | None) -> dict | None:
    try:
        with gzip.open(path, "rb") as handle:
            raw = handle.read()
        if dest:
            dest.write_bytes(raw)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def load_catalog(cache_dir: Path | None = None) -> dict | None:
    if cache_dir:
        cached = cache_dir / CATALOG_FILENAME
        if cached.exists():
            return load_catalog_from_path(cached)

    path = catalog_path()
    if path.exists():
        return load_catalog_from_path(path)

    archive = catalog_archive_path()
    if archive.exists():
        dest = None
        if cache_dir:
            dest = cache_dir / CATALOG_FILENAME
        return load_catalog_from_gzip(archive, dest)

    return None


def compute_font_list_hash(fonts: list[dict]) -> str:
    entries = []
    for font in fonts:
        path = font.get("path")
        if not path:
            continue
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0
        entries.append(f"{path}|{mtime}")
    entries.sort()
    digest = hashlib.sha1("\n".join(entries).encode("utf-8")).hexdigest()
    return digest


def is_excluded(entry: dict, exclusions: dict) -> bool:
    family = (entry.get("family") or "").lower()
    style = (entry.get("style") or "").lower()
    name = f"{family} {style}"
    path = entry.get("path") or ""

    if "glyphlessfont" in name:
        return True
    if "glyph" in name:
        return True

    try:
        if os.path.getsize(path) < 10 * 1024:
            return True
    except OSError:
        return True

    for token in ["dingbats", "wingdings", "symbol", "emoji"]:
        if token in name:
            return True

    for banned in exclusions.get("names", []):
        if banned.lower() in name:
            return True

    return False


def classify_font(font_path: str, family: str, style: str) -> tuple[str, int, bool]:
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

    try:
        font = TTFont(font_path, lazy=True)
        os2 = font["OS/2"] if "OS/2" in font else None
        if os2:
            weight = int(getattr(os2, "usWeightClass", weight))
            italic = bool(os2.fsSelection & 0x01) or italic
            panose = getattr(os2, "panose", None)
            if panose:
                if getattr(panose, "bProportion", 0) == 9:
                    category = "monospace"
                serif_style = getattr(panose, "bSerifStyle", 0)
                if 2 <= serif_style <= 7:
                    category = "serif"
        font.close()
    except Exception:
        pass

    return category, weight, italic


def encode_template_preview(path: Path) -> str | None:
    if not path or not path.exists():
        return None
    try:
        data = path.read_bytes()
    except Exception:
        return None
    return base64.b64encode(data).decode("ascii")


def manifest_path(cache_dir: Path) -> Path:
    return cache_dir / "manifest.json"


def templates_dir(cache_dir: Path) -> Path:
    path = cache_dir / "templates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_manifest(cache_dir: Path) -> dict | None:
    path = manifest_path(cache_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def run_fc_list() -> list[dict]:
    try:
        result = subprocess.run(
            ["fc-list", "--format", "%{file}\t%{family}\t%{style}\n"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("fontconfig not installed (fc-list missing)") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        raise RuntimeError(f"fc-list failed: {stderr}") from exc

    fonts = []
    seen = set()
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        path = parts[0].strip()
        if not path or path in seen:
            continue
        seen.add(path)
        family_raw = parts[1].strip()
        style_raw = parts[2].strip()
        family = family_raw.split(",")[0].strip() if family_raw else Path(path).stem
        style = style_raw.split(",")[0].strip() if style_raw else "Regular"
        fonts.append({"path": path, "family": family, "style": style})
    return fonts


def preprocess_image(img: Image.Image, target_height: int, debug_path: Path | None = None) -> Image.Image:
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
        error_exit("Input image is empty after preprocessing", code="INVALID_IMAGE")
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

    if debug_path:
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_path), canvas)

    return Image.fromarray(canvas)


def render_sample(font_path: str, text: str, size: tuple[int, int]) -> Image.Image | None:
    img = Image.new("L", size, color=255)
    draw = ImageDraw.Draw(img)
    font_size = 42
    font = None
    bbox = None

    for _ in range(8):
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            font = None
            break

        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if text_w <= size[0] - 8 and text_h <= size[1] - 8:
            break
        font_size -= 4
        if font_size < 10:
            break

    if not font or not bbox:
        return None

    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size[0] - text_w) / 2 - bbox[0]
    y = (size[1] - text_h) / 2 - bbox[1]

    draw.text((x, y), text, font=font, fill=0)
    return preprocess_image(img.convert("RGB"), size[1])


def compute_ssim(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        return 0.0
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    c1 = 6.5025
    c2 = 58.5225
    mu_a = a.mean()
    mu_b = b.mean()
    sigma_a = ((a - mu_a) ** 2).mean()
    sigma_b = ((b - mu_b) ** 2).mean()
    sigma_ab = ((a - mu_a) * (b - mu_b)).mean()
    numerator = (2 * mu_a * mu_b + c1) * (2 * sigma_ab + c2)
    denominator = (mu_a ** 2 + mu_b ** 2 + c1) * (sigma_a + sigma_b + c2)
    if denominator == 0:
        return 0.0
    score = numerator / denominator
    return max(0.0, min(1.0, float(score)))


def histogram_score(a: np.ndarray, b: np.ndarray) -> float:
    hist_a = cv2.calcHist([a], [0], None, [64], [0, 256])
    hist_b = cv2.calcHist([b], [0], None, [64], [0, 256])
    corr = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)
    score = (corr + 1.0) / 2.0
    return max(0.0, min(1.0, float(score)))


def template_score(a: np.ndarray, b: np.ndarray) -> float:
    res = cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)
    score = float(res.max())
    return max(0.0, min(1.0, score))


def combined_score(a: np.ndarray, b: np.ndarray) -> tuple[float, dict]:
    ssim = compute_ssim(a, b)
    hist = histogram_score(a, b)
    templ = template_score(a, b)
    score = ssim * 0.4 + hist * 0.3 + templ * 0.3
    return score, {"ssim": ssim, "histogram": hist, "template": templ}


def decode_template_image(data: str) -> np.ndarray | None:
    try:
        raw = base64.b64decode(data)
    except Exception:
        return None
    img = Image.open(io.BytesIO(raw))
    return np.array(img)


def baseline_available() -> tuple[bool, str | None]:
    try:
        subprocess.run(["fc-list", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        return False, "fontconfig not installed (fc-list missing)"
    except subprocess.CalledProcessError as exc:
        return False, f"fc-list failed: {exc.stderr.strip()}"
    return True, None


def ml_available(cache_dir: Path) -> tuple[bool, str | None]:
    try:
        import onnxruntime  # noqa: F401
        import numpy  # noqa: F401
    except Exception:
        return False, "onnxruntime not installed"

    config_path = cache_dir / "ml" / "model.json"
    if not config_path.exists():
        return False, "ml model config missing"

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return False, "ml model config unreadable"

    model_path = Path(config.get("model_path", ""))
    if not model_path.is_absolute():
        model_path = config_path.parent / model_path
    if not model_path.exists():
        return False, "ml model file missing"

    return True, None


def ml_ready_for_match(cache_dir: Path) -> tuple[bool, str | None]:
    ok, reason = ml_available(cache_dir)
    if not ok:
        return False, reason
    embeddings_path = cache_dir / "ml" / "embeddings.json"
    if not embeddings_path.exists():
        return False, "ml embeddings index missing"
    if not load_manifest(cache_dir):
        return False, "font index missing"
    return True, None


def load_ml_config(cache_dir: Path) -> dict:
    config_path = cache_dir / "ml" / "model.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    model_path = Path(config.get("model_path", ""))
    if not model_path.is_absolute():
        model_path = config_path.parent / model_path
    config["model_path"] = str(model_path)
    return config


def embed_image(img: Image.Image, config: dict):
    import numpy as np
    import onnxruntime as ort

    size = config.get("image_size") or list(DEFAULT_SIZE)
    if isinstance(size, list):
        size = (int(size[0]), int(size[1]))
    img = preprocess_image(img, size[1])
    layout = config.get("layout", "chw")
    normalize = config.get("normalize", "0-1")

    data = [p / 255.0 for p in img.getdata()]
    if normalize == "minus1-1":
        data = [p * 2.0 - 1.0 for p in data]

    arr = np.array(data, dtype=np.float32)
    if layout == "hwc":
        arr = arr.reshape((1, size[1], size[0], 1))
    else:
        arr = arr.reshape((1, 1, size[1], size[0]))

    session = ort.InferenceSession(str(config["model_path"]), providers=["CPUExecutionProvider"])
    input_name = config.get("input_name") or session.get_inputs()[0].name
    output_name = config.get("output_name") or session.get_outputs()[0].name
    output = session.run([output_name], {input_name: arr})[0]
    return output.squeeze().astype(np.float32)


def cosine_similarity(a, b) -> float:
    import numpy as np

    if a.shape != b.shape or a.size == 0:
        return 0.0
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def build_index(cache_dir: Path, force: bool) -> dict:
    start = time.time()
    fonts = run_fc_list()
    if not fonts:
        error_exit("No fonts found via fontconfig", code="FONT_NOT_FOUND")

    exclusions = load_exclusions()
    existing = load_manifest(cache_dir) or {}
    existing_fonts = {f["path"]: f for f in existing.get("fonts", [])}

    font_list_hash = compute_font_list_hash(fonts)
    if not force and existing.get("font_list_hash") == font_list_hash:
        return {
            "ok": True,
            "cache_dir": str(cache_dir),
            "indexed_fonts": len(existing.get("fonts", [])),
            "duration_ms": int((time.time() - start) * 1000),
            "ml_indexed": bool((cache_dir / "ml" / "embeddings.json").exists()),
            "cached": True,
        }

    templates = templates_dir(cache_dir)

    manifest = {
        "samples": SAMPLES,
        "template_size": list(DEFAULT_SIZE),
        "font_list_hash": font_list_hash,
        "fonts": [],
    }

    for entry in fonts:
        font_path = entry["path"]
        try:
            mtime = os.path.getmtime(font_path)
        except OSError:
            continue
        if is_excluded(entry, exclusions):
            continue

        font_hash = hashlib.sha1(font_path.encode("utf-8")).hexdigest()
        existing_entry = existing_fonts.get(font_path)
        templates_map = {}

        if existing_entry and not force and existing_entry.get("file_mtime") == mtime:
            templates_map = existing_entry.get("templates", {})
            if templates_map and all((templates / name).exists() for name in templates_map.values()):
                manifest["fonts"].append(existing_entry)
                continue

        for key, sample in SAMPLES.items():
            template_name = f"{font_hash}_{key}.png"
            template_path = templates / template_name
            rendered = render_sample(font_path, sample, DEFAULT_SIZE)
            if rendered is None:
                templates_map = {}
                break
            rendered.save(template_path)
            templates_map[key] = template_name

        if not templates_map:
            continue

        category, weight, italic = classify_font(font_path, entry["family"], entry["style"])

        manifest["fonts"].append({
            "id": font_hash,
            "path": font_path,
            "family": entry["family"],
            "style": entry["style"],
            "category": category,
            "weight": weight,
            "italic": italic,
            "file_mtime": mtime,
            "templates": templates_map,
        })

    manifest_path(cache_dir).write_text(json.dumps(manifest, ensure_ascii=True), encoding="utf-8")

    duration_ms = int((time.time() - start) * 1000)

    ml_ok, _ = ml_available(cache_dir)
    ml_indexed = False
    ml_reason = None
    if ml_ok:
        try:
            ml_indexed = build_ml_index(cache_dir, manifest)
        except Exception as exc:
            ml_reason = f"ML index build failed: {exc}"

    result = {
        "ok": True,
        "cache_dir": str(cache_dir),
        "indexed_fonts": len(manifest["fonts"]),
        "duration_ms": duration_ms,
        "ml_indexed": ml_indexed,
        "cached": False,
    }
    if ml_reason:
        result["ml_reason"] = ml_reason
    return result


def build_ml_index(cache_dir: Path, manifest: dict) -> bool:
    config = load_ml_config(cache_dir)
    ml_dir = cache_dir / "ml"
    ml_dir.mkdir(parents=True, exist_ok=True)
    embeddings = []
    for font in manifest["fonts"]:
        template_name = font["templates"].get("primary")
        if not template_name:
            continue
        template_path = templates_dir(cache_dir) / template_name
        if not template_path.exists():
            continue
        img = Image.open(template_path).convert("RGB")
        embedding = embed_image(img, config)
        embeddings.append({
            "id": font["id"],
            "vector": embedding.tolist(),
        })

    (ml_dir / "embeddings.json").write_text(
        json.dumps({"embeddings": embeddings, "dim": len(embeddings[0]["vector"]) if embeddings else 0}, ensure_ascii=True),
        encoding="utf-8",
    )
    return True


def baseline_match(cache_dir: Path, input_path: str, topk: int) -> list[dict]:
    manifest = load_manifest(cache_dir)
    if not manifest:
        error_exit("Font index not found. Run the index command first.", code="INDEX_MISSING")

    try:
        input_img = Image.open(input_path).convert("RGB")
    except Exception as exc:
        error_exit(f"Failed to open input image: {exc}", code="INVALID_IMAGE")

    debug_path = cache_dir / DEBUG_DIR_NAME / f"pre_{int(time.time() * 1000)}.png"
    input_processed = preprocess_image(input_img, DEFAULT_SIZE[1], debug_path=debug_path)
    input_arr = np.array(input_processed)

    results = []
    templates = templates_dir(cache_dir)
    for font in manifest.get("fonts", []):
        templates_map = font.get("templates", {})
        best = None
        best_breakdown = None
        for template_name in templates_map.values():
            template_path = templates / template_name
            if not template_path.exists():
                continue
            try:
                template_img = Image.open(template_path)
            except Exception:
                continue
            template_arr = np.array(template_img)
            score, breakdown = combined_score(input_arr, template_arr)
            if best is None or score > best:
                best = score
                best_breakdown = breakdown
        if best is None:
            continue
        results.append({
            "family": font["family"],
            "style": font["style"],
            "category": font.get("category", "sans-serif"),
            "weight": font.get("weight", 400),
            "italic": font.get("italic", False),
            "path": font["path"],
            "score": float(best),
            "score_breakdown": best_breakdown,
            "preview_sample": encode_template_preview(templates / templates_map.get("primary", "")),
        })

    results.sort(key=lambda item: item["score"], reverse=True)
    catalog = load_catalog(cache_dir)
    if catalog:
        for font in catalog.get("fonts", []):
            templates_map = font.get("templates", {})
            best = None
            best_breakdown = None
            for template_b64 in templates_map.values():
                template_arr = decode_template_image(template_b64)
                if template_arr is None:
                    continue
                score, breakdown = combined_score(input_arr, template_arr)
                if best is None or score > best:
                    best = score
                    best_breakdown = breakdown
            if best is None:
                continue
            results.append({
                "family": font.get("family", "Unknown"),
                "style": font.get("style", "Regular"),
                "category": font.get("category", "sans-serif"),
                "weight": font.get("weight", 400),
                "italic": font.get("italic", False),
                "path": f"catalog://{font.get('id', '')}",
                "score": float(best),
                "score_breakdown": best_breakdown,
                "preview_sample": templates_map.get("primary"),
            })

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:topk]


def ml_match(cache_dir: Path, input_path: str, topk: int, strict: bool = True) -> list[dict]:
    def fail(message: str, code: str) -> None:
        if strict:
            error_exit(message, code=code)
        raise RuntimeError(message)

    manifest = load_manifest(cache_dir)
    if not manifest:
        fail("Font index not found. Run the index command first.", "INDEX_MISSING")

    config = load_ml_config(cache_dir)
    embeddings_path = cache_dir / "ml" / "embeddings.json"
    if not embeddings_path.exists():
        fail("ML embeddings index missing. Run the index command first.", "INDEX_MISSING")

    embeddings = json.loads(embeddings_path.read_text(encoding="utf-8"))
    vectors = embeddings.get("embeddings", [])

    if not vectors:
        fail("ML embeddings index is empty.", "INDEX_CORRUPT")

    try:
        input_img = Image.open(input_path).convert("RGB")
    except Exception as exc:
        fail(f"Failed to open input image: {exc}", "INVALID_IMAGE")

    input_vec = embed_image(input_img, config)

    results = []
    vector_map = {entry["id"]: entry["vector"] for entry in vectors}

    import numpy as np

    for font in manifest.get("fonts", []):
        vec = vector_map.get(font["id"])
        if not vec:
            continue
        score = cosine_similarity(input_vec, np.array(vec, dtype=np.float32))
        results.append({
            "family": font["family"],
            "style": font["style"],
            "category": font.get("category", "sans-serif"),
            "weight": font.get("weight", 400),
            "italic": font.get("italic", False),
            "path": font["path"],
            "score": score,
            "score_breakdown": None,
            "preview_sample": encode_template_preview(
                templates_dir(cache_dir) / font.get("templates", {}).get("primary", "")
            ),
        })

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:topk]


def handle_check(args: argparse.Namespace) -> None:
    cache_dir = get_cache_dir()
    baseline_ok, baseline_reason = baseline_available()
    ml_ok, ml_reason = ml_available(cache_dir)
    manifest = load_manifest(cache_dir)

    payload = {
        "ok": True,
        "cache_dir": str(cache_dir),
        "engines": {
            "baseline_render_compare": {
                "available": baseline_ok,
                "reason": baseline_reason,
            },
            "ml_embeddings": {
                "available": ml_ok,
                "reason": ml_reason,
            },
        },
        "indexed_fonts": len(manifest.get("fonts", [])) if manifest else 0,
    }
    json_print(payload)


def handle_index(args: argparse.Namespace) -> None:
    cache_dir = get_cache_dir()
    payload = build_index(cache_dir, args.force)
    json_print(payload)


def handle_match(args: argparse.Namespace) -> None:
    cache_dir = get_cache_dir()
    requested_engine = args.engine
    topk = max(1, int(args.topk))
    start = time.time()

    fallback_used = False
    fallback_reason = None
    engine_used = None
    candidates = []

    if requested_engine == "auto":
        ml_ok, ml_reason = ml_ready_for_match(cache_dir)
        if ml_ok:
            try:
                candidates = ml_match(cache_dir, args.input, topk, strict=False)
                engine_used = "ml_embeddings"
            except Exception as exc:
                fallback_used = True
                fallback_reason = f"ml failed: {exc}"
        else:
            fallback_used = True
            fallback_reason = ml_reason or "ml unavailable"

    if requested_engine == "baseline" or (requested_engine == "auto" and engine_used is None):
        candidates = baseline_match(cache_dir, args.input, topk)
        engine_used = "baseline_render_compare"

    if requested_engine == "ml":
        ml_ok, ml_reason = ml_ready_for_match(cache_dir)
        if not ml_ok:
            error_exit(ml_reason or "ml unavailable", code="ENGINE_UNAVAILABLE")
        candidates = ml_match(cache_dir, args.input, topk, strict=True)
        engine_used = "ml_embeddings"

    duration_ms = int((time.time() - start) * 1000)
    manifest = load_manifest(cache_dir)
    indexed_fonts = len(manifest.get("fonts", [])) if manifest else 0

    payload = {
        "ok": True,
        "requested_engine": requested_engine,
        "engine_used": engine_used,
        "fallback": {
            "used": bool(fallback_used),
            "reason": fallback_reason,
        },
        "candidates": candidates,
        "meta": {
            "indexed_fonts": indexed_fonts,
            "duration_ms": duration_ms,
        },
    }
    json_print(payload)


def handle_match_region(args: argparse.Namespace) -> None:
    try:
        import fitz
    except Exception as exc:
        error_exit(f"PyMuPDF not available: {exc}", code="DEPENDENCY_MISSING")

    rect_parts = [float(x.strip()) for x in args.rect.split(",")]
    if len(rect_parts) != 4:
        error_exit("rect must be x0,y0,x1,y1", code="INVALID_ARGUMENT")

    x0, y0, x1, y1 = rect_parts
    if x1 <= x0 or y1 <= y0:
        error_exit("rect coordinates invalid", code="INVALID_ARGUMENT")

    try:
        doc = fitz.open(args.pdf)
        page = doc.load_page(args.page)
        matrix = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        scale = 2.0
        crop = (x0 * scale, y0 * scale, x1 * scale, y1 * scale)
        img = img.crop(crop)
    except Exception as exc:
        error_exit(f"Failed to extract region: {exc}", code="PDF_REGION_ERROR")

    temp_dir = get_cache_dir() / DEBUG_DIR_NAME
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"region_{int(time.time() * 1000)}.png"
    img.save(temp_path)

    args.input = str(temp_path)
    handle_match(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Font detection tools")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="Check engine availability")

    index = sub.add_parser("index", help="Build or refresh font index")
    index.add_argument("--force", action="store_true", help="Force rebuild")

    match = sub.add_parser("match", help="Match font from image")
    match.add_argument("--input", required=True, help="Input image path")
    match.add_argument("--engine", default="auto", choices=["auto", "baseline", "ml"], help="Engine to use")
    match.add_argument("--topk", default=5, help="Top-K results")

    match_region = sub.add_parser("match-region", help="Match font from PDF region")
    match_region.add_argument("--pdf", required=True, help="PDF file path")
    match_region.add_argument("--page", type=int, required=True, help="0-based page index")
    match_region.add_argument("--rect", required=True, help="x0,y0,x1,y1")
    match_region.add_argument("--engine", default="auto", choices=["auto", "baseline", "ml"], help="Engine to use")
    match_region.add_argument("--topk", default=5, help="Top-K results")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "check":
            handle_check(args)
        elif args.command == "index":
            handle_index(args)
        elif args.command == "match":
            handle_match(args)
        elif args.command == "match-region":
            handle_match_region(args)
        else:
            error_exit("Unknown command", code="INVALID_ARGUMENT")
    except SystemExit:
        raise
    except Exception as exc:
        error_exit(f"font_detect failed: {exc}", code="FONT_DETECT_ERROR")


if __name__ == "__main__":
    main()
