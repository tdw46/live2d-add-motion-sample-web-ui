#!/usr/bin/env python3
"""Serve the WebUI and its local-only avatar generation API."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
import uuid
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error as urllib_error
from urllib import parse as urllib_parse

try:
    from PIL import Image as PILImage
except ImportError:  # The base static viewer can still run without the avatar-pipeline environment.
    PILImage = None
from urllib import request as urllib_request


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 17342
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from tools.layer_regeneration import geometric_counterpart_ids, matching_layer_group  # noqa: E402
HALLWAY_ENV = Path(
    os.environ.get(
        "LIVE2D_HALLWAY_ENV",
        "/Users/tylerwalker/dev/Hallway/hallway-anime-facial-landmark-classifier/.env",
    )
)
REGISTRY_PATH = PROJECT_ROOT / "local-assets" / "avatar-registry.json"
VIEWER_METADATA_PATH = PROJECT_ROOT / "local-assets" / "avatar-viewer-metadata.json"
GENERATED_ROOT = PROJECT_ROOT / "local-assets" / "generated-avatars"
PIPELINE_PYTHON = PROJECT_ROOT / ".venv-avatar" / "bin" / "python"
SEE_THROUGH = PROJECT_ROOT / "vendor" / "see-through"
IMAGE2LIVE2D = PROJECT_ROOT / "vendor" / "image2live2d"
MAX_BODY_BYTES = 32_768
MAX_LAYER_INSTRUCTION = 1200
MAX_LAYER_OFFSET = 512

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
REGISTRY_LOCK = threading.Lock()
VIEWER_METADATA_LOCK = threading.Lock()
EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="avatar-generation")
PNG_ALPHA_CACHE: dict[tuple[str, int, int], tuple[int, int, bytes] | None] = {}


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def hallway_settings() -> dict[str, str]:
    values = load_dotenv(HALLWAY_ENV)
    for key in ("GEMINI_API_KEY", "GEMINI_IMAGE_MODEL", "GEMINI_IMAGE_FALLBACK_MODEL"):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def default_avatar() -> dict:
    config_path = PROJECT_ROOT / "model.config.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        model3 = config["model3"]
    else:
        model3 = "models/hiyori_pro_t11/hiyori_pro_t11.model3.json"
    return {
        "id": "hiyori",
        "name": "Hiyori",
        "model3": model3,
        "default": True,
        "generated": False,
    }


def read_generated_avatars() -> list[dict]:
    if not REGISTRY_PATH.is_file():
        return []
    try:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    avatars = payload.get("avatars", []) if isinstance(payload, dict) else []
    clean = []
    for avatar in avatars:
        if not isinstance(avatar, dict):
            continue
        model3 = str(avatar.get("model3", ""))
        if model3 and (PROJECT_ROOT / model3).is_file():
            clean.append(avatar)
    clean.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return clean


def read_viewer_metadata() -> dict[str, dict]:
    if not VIEWER_METADATA_PATH.is_file():
        return {}
    try:
        payload = json.loads(VIEWER_METADATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    avatars = payload.get("avatars", {}) if isinstance(payload, dict) else {}
    return avatars if isinstance(avatars, dict) else {}


def avatar_catalog() -> list[dict]:
    viewer_metadata = read_viewer_metadata()
    avatars = [default_avatar(), *read_generated_avatars()]
    return [
        {
            **avatar,
            "viewer": viewer_metadata.get(str(avatar.get("id")), {}),
            "can_regenerate_layers": can_regenerate_avatar_layers(str(avatar.get("id", ""))),
        }
        for avatar in avatars
    ]


def validate_layer_order(value) -> list[str]:
    if not isinstance(value, list) or len(value) > 512:
        raise ValueError("layer_order must be an array with at most 512 drawable IDs.")
    result = []
    seen = set()
    for item in value:
        if not isinstance(item, str) or not 1 <= len(item) <= 128:
            raise ValueError("Each drawable ID must be a non-empty string up to 128 characters.")
        if any(ord(character) < 32 for character in item):
            raise ValueError("Drawable IDs cannot contain control characters.")
        if item in seen:
            raise ValueError(f"Duplicate drawable ID: {item}")
        seen.add(item)
        result.append(item)
    return result


def save_viewer_layer_order(avatar_id: str, layer_order: list[str]) -> dict:
    with VIEWER_METADATA_LOCK:
        metadata = read_viewer_metadata()
        viewer = dict(metadata.get(avatar_id, {}))
        viewer["layer_order"] = layer_order
        viewer["updated_at"] = datetime.now(timezone.utc).isoformat()
        metadata[avatar_id] = viewer
        payload = {"version": 1, "avatars": metadata}
        VIEWER_METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_path = VIEWER_METADATA_PATH.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temp_path.replace(VIEWER_METADATA_PATH)
        return viewer


def register_avatar(avatar: dict) -> None:
    with REGISTRY_LOCK:
        existing = [item for item in read_generated_avatars() if item.get("id") != avatar.get("id")]
        payload = {"version": 1, "avatars": [avatar, *existing]}
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_path = REGISTRY_PATH.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(REGISTRY_PATH)


def pipeline_status() -> dict:
    settings = hallway_settings()
    return {
        "gemini_configured": bool(settings.get("GEMINI_API_KEY")),
        "environment_ready": PIPELINE_PYTHON.is_file(),
        "see_through_ready": (SEE_THROUGH / "inference" / "scripts" / "inference_psd.py").is_file(),
        "rig_bridge_ready": (IMAGE2LIVE2D / "src" / "image2live2d").is_dir(),
        "profile": os.environ.get("SEE_THROUGH_PROFILE", "mps-smoke"),
    }


def update_job(job_id: str, **changes) -> None:
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(changes)
            JOBS[job_id]["updated_at"] = datetime.now(timezone.utc).isoformat()


def public_job(job: dict) -> dict:
    return {
        key: value for key, value in job.items()
        if key not in {"description", "instruction", "work_dir"}
    }


def _json_result(output: str) -> dict:
    line = next((line for line in reversed(output.splitlines()) if line.startswith("{")), "{}")
    return json.loads(line)


def _mime_for_path(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "image/png"


def _gemini_models(settings: dict[str, str]) -> list[str]:
    candidates = [
        settings.get("GEMINI_IMAGE_MODEL", ""),
        settings.get("GEMINI_IMAGE_FALLBACK_MODEL", ""),
        "gemini-3.1-flash-image-preview",
        "gemini-3-pro-image-preview",
        "gemini-2.5-flash-image",
    ]
    result = []
    for model in candidates:
        model = model.strip()
        if model and model not in result:
            result.append(model)
    return result


def _extract_gemini_image(response: dict) -> tuple[bytes, str] | None:
    for candidate in response.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if not isinstance(inline, dict) or not inline.get("data"):
                continue
            return base64.b64decode(inline["data"]), str(
                inline.get("mimeType") or inline.get("mime_type") or "image/png"
            )
    return None


def _gemini_inline_image(path: Path) -> dict:
    return {
        "inlineData": {
            "mimeType": _mime_for_path(path),
            "data": base64.b64encode(path.read_bytes()).decode("ascii"),
        }
    }


def build_layer_edit_prompt(
    layer_name: str,
    instruction: str,
    chroma: str,
    related_names: list[str],
    change_amount: str,
    preserve_colors: bool,
    attachment_lock: str,
    preserve_silhouette: bool = False,
) -> str:
    safe_instruction = re.sub(
        r"\btransparen(?:t|cy)\b",
        "isolated",
        instruction.strip(),
        flags=re.IGNORECASE,
    )
    amount = {
        "subtle": "Make a restrained refinement and retain nearly all existing design details.",
        "balanced": "Make a clear but controlled redesign while retaining the character identity.",
        "strong": "Make a substantial redesign while obeying every placement and connection constraint.",
    }[change_amount]
    color_rule = (
        "Keep the existing color palette and material values closely matched."
        if preserve_colors
        else "You may change the layer colors when the edit instruction calls for it."
    )
    lock_rule = (
        "Keep the proximal attachment edge pixel-accurate and leave extra continuity around that seam."
        if attachment_lock == "strict"
        else "Keep the proximal attachment edge and connection point in the same location."
    )
    silhouette_rule = (
        "Repaint strictly inside the target layer's existing boundary. Every contour, gap, strand, "
        "protrusion, and covered area must remain pixel-aligned to the target image."
        if preserve_silhouette
        else "Create the requested new silhouette when useful. Its boundary against the solid keyed "
        "background will become the new layer mask, so keep edges clean and preserve intentional holes."
    )
    alignment_rule = (
        "Keep the canvas dimensions, aspect ratio, framing, pixel coordinates, scale, rotation, "
        "orientation, silhouette footprint, occlusion boundaries, and contact points exactly aligned "
        "with the first image."
        if preserve_silhouette
        else "Keep the canvas dimensions and the proximal attachment point in the same pixel location. "
        "Do not zoom or recenter the part; the new outline may extend or contract only as requested."
    )
    related = (
        " Additional images show matching layers that must remain stylistically and structurally consistent: "
        + ", ".join(related_names)
        + "."
        if related_names
        else ""
    )
    prompt = (
        f"Edit the isolated anime rig layer named {layer_name}. The image labeled TARGET LAYER is the only "
        "image to repaint. The image labeled LOCAL CHARACTER CONTEXT is a cropped style and attachment "
        "reference only; never reproduce the character or context crop in the result."
        f"{related} Repaint only the target layer according to this instruction: {safe_instruction}\n"
        f"{amount} {color_rule} {silhouette_rule} {alignment_rule} {lock_rule} "
        "Do not crop, mirror, or rotate the layer. "
        f"Fill every pixel outside the isolated layer with one perfectly uniform solid {chroma} color. "
        f"The exact {chroma} color is reserved only for the outside background and intentional holes; never "
        "use that exact color to paint the foreground layer. The "
        "result must contain only this single detached body part, never a face, torso, legs, complete character, "
        "or reference-image crop. Do not add scenery, floor, text, labels, guides, cast shadows, extra objects, "
        "or any second character. Return "
        "exactly one image and no explanation."
    )
    if "transparent" in prompt.casefold():
        raise RuntimeError("Gemini layer-edit prompt contains a prohibited term.")
    return prompt


def generate_layer_image(
    *,
    prompt: str,
    target_path: Path,
    reference_path: Path,
    related_paths: list[Path],
    settings: dict[str, str],
) -> tuple[bytes, str, str]:
    api_key = settings.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in the Hallway .env file.")
    parts = [
        {"text": "TARGET LAYER — edit only the following isolated keyed image:"},
        _gemini_inline_image(target_path),
        {"text": "LOCAL CHARACTER CONTEXT — reference only; do not output this image:"},
        _gemini_inline_image(reference_path),
    ]
    for index, path in enumerate(related_paths, start=1):
        parts.extend((
            {"text": f"MATCHING LAYER REFERENCE {index} — style and symmetry reference only:"},
            _gemini_inline_image(path),
        ))
    parts.append({"text": prompt})
    attempts = [
        {
            "contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        },
        {
            "contents": [{"parts": [*parts, {"text": "Output only the isolated edited target layer."}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        },
    ]
    errors = []
    for model in _gemini_models(settings):
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{urllib_parse.quote(model, safe='')}:generateContent?key={urllib_parse.quote(api_key)}"
        )
        for payload in attempts:
            try:
                response = _gemini_request(url, payload)
                image = _extract_gemini_image(response)
                if image:
                    return image[0], image[1], model
                errors.append(f"{model}: no image returned")
            except RuntimeError as exc:
                errors.append(f"{model}: {exc}")
    raise RuntimeError(errors[-1] if errors else "Gemini did not return an edited layer.")


def _gemini_request(url: str, payload: dict) -> dict:
    request = urllib_request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=240) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        detail = ""
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            detail = str(body.get("error", {}).get("message", ""))
        except Exception:
            pass
        raise RuntimeError(f"Gemini request failed with HTTP {exc.code}: {detail or exc.reason}") from None
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Gemini connection failed: {exc.reason}") from None


def generate_character_image(description: str, settings: dict[str, str]) -> tuple[bytes, str, str]:
    api_key = settings.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in the Hallway .env file.")
    prompt = (
        "Create one polished anime character concept intended for automatic Live2D rigging. "
        "Show the complete body from the top of the hair to the soles of both shoes, centered with generous "
        "empty margin on a plain flat light-gray background. Use a straight-on orthographic view, neutral "
        "upright standing pose, arms relaxed slightly away from the torso, hands visible, legs separated, both "
        "eyes open, and a closed neutral mouth. Keep the silhouette, facial features, hair sections, clothing, "
        "hands, and feet clean and unobstructed. Use crisp professional anime key art, flat even lighting, clean "
        "edges, and no cast shadows, props, text, scenery, extra people, cropped limbs, foreshortening, side view, "
        "or dramatic pose. Character description: " + description.strip()
    )
    attempts = [
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": "3:4", "imageSize": "1K"},
            },
        },
        {
            "contents": [{"parts": [{"text": prompt + " Return only one image."}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        },
    ]
    errors = []
    for model in _gemini_models(settings):
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{urllib_parse.quote(model, safe='')}:generateContent?key={urllib_parse.quote(api_key)}"
        )
        for payload in attempts:
            try:
                result = _gemini_request(url, payload)
                image = _extract_gemini_image(result)
                if image:
                    return image[0], image[1], model
                errors.append(f"{model}: no image returned")
            except RuntimeError as exc:
                errors.append(f"{model}: {exc}")
    raise RuntimeError(errors[-1] if errors else "Gemini did not return an image.")


def _friendly_name(description: str, fallback: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", description)
    if words:
        return " ".join(words[:4]).title()
    return " ".join(description.split())[:28] or fallback


def _run_checked(command: list[str], *, cwd: Path) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        tail = "\n".join(result.stdout.splitlines()[-30:])
        raise RuntimeError(tail or f"Command exited with status {result.returncode}")
    return result.stdout


def select_semantic_psd(output_root: Path, source_stem: str) -> Path:
    """Return See-through's color-layer PSD, never its depth/debug PSDs."""
    psd_files = sorted(output_root.rglob("*.psd"))
    semantic_psds = [
        path
        for path in psd_files
        if not path.stem.casefold().endswith(("_depth", "_wdepth"))
    ]
    exact_matches = [path for path in semantic_psds if path.stem == source_stem]
    if len(exact_matches) == 1:
        return exact_matches[0]

    metadata_matches = [
        path for path in semantic_psds if Path(f"{path}.json").is_file()
    ]
    if len(metadata_matches) == 1:
        return metadata_matches[0]

    if not semantic_psds:
        raise RuntimeError(
            "See-through completed without producing a semantic color-layer PSD."
        )
    choices = ", ".join(path.relative_to(output_root).as_posix() for path in semantic_psds)
    raise RuntimeError(f"See-through produced ambiguous semantic PSD outputs: {choices}")


def generated_avatar_by_id(avatar_id: str) -> dict | None:
    return next(
        (avatar for avatar in read_generated_avatars() if str(avatar.get("id")) == avatar_id),
        None,
    )


def avatar_layer_regeneration_paths(avatar: dict) -> tuple[Path, Path, str]:
    """Resolve the existing semantic PSD, Live2D output, and model name for a generated avatar."""
    avatar_id = str(avatar.get("id", ""))
    if not re.fullmatch(r"gen-[A-Za-z0-9_-]+", avatar_id):
        raise RuntimeError("Only generated avatars can regenerate their layers.")
    avatar_root = (GENERATED_ROOT / avatar_id).resolve()
    if avatar_root.parent != GENERATED_ROOT.resolve():
        raise RuntimeError("Avatar path is outside the generated-avatar directory.")
    psd_path = select_semantic_psd(avatar_root / "see-through", "source")
    model3_path = (PROJECT_ROOT / str(avatar.get("model3", ""))).resolve()
    if not model3_path.is_file() or model3_path.suffix != ".json":
        raise RuntimeError("The generated avatar does not have a loadable model3 bundle.")
    if avatar_root not in model3_path.parents:
        raise RuntimeError("The generated avatar model is outside its working directory.")
    suffix = ".model3.json"
    model_name = model3_path.name[:-len(suffix)] if model3_path.name.endswith(suffix) else model3_path.stem
    return psd_path, model3_path.parent, model_name


def can_regenerate_avatar_layers(avatar_id: str) -> bool:
    avatar = generated_avatar_by_id(avatar_id)
    if avatar is None:
        return False
    try:
        avatar_layer_regeneration_paths(avatar)
    except (OSError, RuntimeError):
        return False
    return True


def avatar_layer_paths(avatar: dict) -> tuple[Path, Path, Path, Path]:
    psd_path, _, _ = avatar_layer_regeneration_paths(avatar)
    avatar_root = psd_path.parent.parent
    layer_dir = avatar_root / "rig-layers"
    override_dir = avatar_root / "layer-regeneration" / "overrides"
    baseline_dir = avatar_root / "layer-regeneration" / "baseline"
    if not layer_dir.is_dir():
        raise RuntimeError("The avatar has no finalized rig layers to edit.")
    sources = [
        path for path in avatar_root.iterdir()
        if path.is_file() and path.suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp"}
        and path.stem == "source"
    ]
    if not sources:
        raise RuntimeError("The avatar has no full-character reference image.")
    return layer_dir, override_dir, baseline_dir, sources[0]


def layer_edit_metadata_path(avatar: dict) -> Path:
    psd_path, _, _ = avatar_layer_regeneration_paths(avatar)
    return psd_path.parent.parent / "layer-regeneration" / "metadata.json"


def read_layer_edit_metadata(avatar: dict) -> dict:
    path = layer_edit_metadata_path(avatar)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    offsets = payload.get("offsets", {}) if isinstance(payload, dict) else {}
    return {"version": 1, "offsets": offsets if isinstance(offsets, dict) else {}}


def write_layer_edit_metadata(path: Path, metadata: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def available_avatar_layers(avatar: dict, include_variants: bool = True) -> list[dict]:
    layer_dir, override_dir, baseline_dir, _ = avatar_layer_paths(avatar)
    drawable_dir = layer_dir.parent / "rig-drawable-layers"
    manifest_path = layer_dir.parent / "rig-layers-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        parts = manifest.get("parts", {})
        canvas = manifest.get("canvas")
    except (OSError, json.JSONDecodeError):
        parts = {}
        canvas = None
    if not isinstance(parts, dict) or not parts:
        parts = {
            path.stem: {"source_file": path.name, "semantic_role": "other"}
            for path in sorted(layer_dir.glob("*.png"))
        }
    source_by_id = {
        str(layer_id): str(info.get("source_file", ""))
        for layer_id, info in parts.items()
        if isinstance(info, dict)
    }
    editable_by_id = {
        str(layer_id): str(info.get("editable_file", info.get("source_file", "")))
        for layer_id, info in parts.items()
        if isinstance(info, dict)
    }
    ids = list(source_by_id)
    edit_metadata = read_layer_edit_metadata(avatar)
    offsets = edit_metadata["offsets"]
    geometry_related = {
        layer_id: geometric_counterpart_ids(layer_id, parts, canvas)
        for layer_id in ids
    }
    undo_snapshots = generation_undo_snapshots(override_dir, ids)
    redo_snapshots = generation_redo_snapshots(override_dir, ids)

    def display_name(layer_id: str) -> str | None:
        info = parts.get(layer_id, {})
        explicit = info.get("display_name") if isinstance(info, dict) else None
        if explicit:
            return str(explicit)
        bbox = info.get("bbox") if isinstance(info, dict) else None
        if (
            str(info.get("semantic_role", "")) == "accessory"
            and geometry_related[layer_id]
            and isinstance(bbox, list) and len(bbox) == 4
            and isinstance(canvas, list) and len(canvas) == 2
        ):
            # See-through uses character-relative sides: screen-left is the character's right arm.
            center_x = (float(bbox[0]) + float(bbox[2])) / 2.0
            return "Arm Right" if center_x < float(canvas[0]) / 2.0 else "Arm Left"
        return None

    def public_variants(layer_id: str) -> list[dict]:
        if not include_variants:
            return []
        records = layer_generation_variants(
            override_dir,
            baseline_dir / editable_by_id[layer_id],
            drawable_dir / editable_by_id[layer_id],
            layer_id,
        )
        return [
            {
                key: value
                for key, value in {
                    **record,
                    "texture_only": bool(
                        texture_replacement_destinations(
                            avatar,
                            {layer_id: record["path"]},
                            offsets,
                        )
                    ),
                    "thumbnail_url": (
                        f"/api/avatars/{urllib_parse.quote(str(avatar['id']))}/layers/"
                        f"{urllib_parse.quote(layer_id)}/variants/"
                        f"{urllib_parse.quote(str(record['id']))}.png"
                    ),
                }.items()
                if key != "path"
            }
            for record in records
        ]

    return [
        {
            "id": layer_id,
            "source_file": source_by_id[layer_id],
            "editable_file": editable_by_id[layer_id],
            "semantic_role": str(parts[layer_id].get("semantic_role", "other")),
            "display_name": display_name(layer_id),
            "related": list(dict.fromkeys([
                *matching_layer_group(layer_id, ids),
                *geometry_related[layer_id],
                *(
                    candidate for candidate in ids
                    if candidate != layer_id and source_by_id[candidate] == source_by_id[layer_id]
                ),
            ])),
            "overridden": (override_dir / f"{layer_id}.png").is_file(),
            "can_revert": (
                (override_dir / f"{layer_id}.png").is_file()
                or bool(offsets.get(layer_id))
            ),
            "can_undo_generation": layer_id in undo_snapshots,
            "can_redo_generation": layer_id in redo_snapshots,
            "variants": public_variants(layer_id),
            "offset": offsets.get(layer_id, {"x": 0, "y": 0}),
            "canvas": canvas if isinstance(canvas, list) and len(canvas) == 2 else None,
        }
        for layer_id in ids
        if source_by_id[layer_id]
        and (layer_dir / source_by_id[layer_id]).is_file()
        and editable_by_id.get(layer_id)
        and (drawable_dir / editable_by_id[layer_id]).is_file()
    ]


def _layer_path(directory: Path, source_file: str) -> Path:
    if Path(source_file).name != source_file or not source_file.casefold().endswith(".png"):
        raise ValueError("Invalid finalized layer source.")
    path = directory / source_file
    if not path.is_file() or path.parent.resolve() != directory.resolve():
        raise ValueError(f"Finalized layer not found: {source_file}")
    return path


def selected_layer_group(catalog: dict[str, dict], primary_id: str, include_related: bool) -> list[str]:
    selected = [primary_id]
    if include_related:
        queue = [primary_id]
        while queue:
            current = queue.pop(0)
            for related_id in catalog[current].get("related", []):
                if related_id in catalog and related_id not in selected:
                    selected.append(related_id)
                    queue.append(related_id)
    return selected


def snapshot_layer_edit_state(
    override_dir: Path,
    metadata_path: Path,
    layer_ids: list[str],
    operation: dict,
) -> Path:
    history_dir = override_dir.parent / "history" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    )
    history_dir.mkdir(parents=True, exist_ok=False)
    for layer_id in layer_ids:
        current = override_dir / f"{layer_id}.png"
        if current.is_file():
            shutil.copy2(current, history_dir / current.name)
    if metadata_path.is_file():
        shutil.copy2(metadata_path, history_dir / "metadata.json")
    (history_dir / "edit.json").write_text(
        json.dumps(operation, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return history_dir


def generation_history_state(
    override_dir: Path,
    layer_ids: list[str],
) -> tuple[dict[str, Path], dict[str, Path]]:
    """Replay generation history into per-layer undo and redo stacks."""
    history_root = override_dir.parent / "history"
    wanted = set(layer_ids)
    stacks = {layer_id: {"undo": [], "redo": []} for layer_id in wanted}
    generation_catalog = {layer_id: [] for layer_id in wanted}

    def remove_named(stack: list[Path], name: str) -> None:
        for index in range(len(stack) - 1, -1, -1):
            if stack[index].name == name:
                stack.pop(index)
                return

    for history_dir in sorted(history_root.glob("*")):
        try:
            operation = json.loads((history_dir / "edit.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        operation_name = operation.get("operation")
        is_generation = operation_name == "generation" or (
            operation_name is None and isinstance(operation.get("instruction"), str)
        )
        if is_generation:
            for layer_id in operation.get("layers", []):
                layer_id = str(layer_id)
                if layer_id not in stacks:
                    continue
                generation_catalog[layer_id].append(history_dir)
                stacks[layer_id]["undo"].append(history_dir)
                stacks[layer_id]["redo"].clear()
            continue
        if operation_name == "select-variant":
            selections = operation.get("variant_history", {})
            if not isinstance(selections, dict):
                continue
            for layer_id, variant_id in selections.items():
                layer_id = str(layer_id)
                if layer_id not in stacks:
                    continue
                stacks[layer_id]["redo"].clear()
                if not variant_id or str(variant_id) == "baseline":
                    stacks[layer_id]["undo"].clear()
                    continue
                selected_index = next(
                    (
                        index for index, generation_dir in enumerate(generation_catalog[layer_id])
                        if generation_dir.name == str(variant_id)
                    ),
                    None,
                )
                if selected_index is not None:
                    stacks[layer_id]["undo"] = generation_catalog[layer_id][:selected_index + 1]
            continue
        if operation_name == "undo-generation":
            sources = operation.get("source_history", {})
            if isinstance(sources, dict):
                for layer_id, source in sources.items():
                    layer_id = str(layer_id)
                    if layer_id not in stacks:
                        continue
                    remove_named(stacks[layer_id]["undo"], str(source))
                    stacks[layer_id]["redo"].append(history_dir)
            continue
        if operation_name != "redo-generation":
            continue
        sources = operation.get("source_history", {})
        generation_sources = operation.get("generation_history", {})
        if not isinstance(sources, dict):
            continue
        for layer_id, source in sources.items():
            layer_id = str(layer_id)
            if layer_id not in stacks:
                continue
            remove_named(stacks[layer_id]["redo"], str(source))
            generation_name = (
                str(generation_sources.get(layer_id, ""))
                if isinstance(generation_sources, dict)
                else ""
            )
            if not generation_name:
                try:
                    undo_operation = json.loads(
                        (history_root / str(source) / "edit.json").read_text(encoding="utf-8")
                    )
                    generation_name = str(
                        undo_operation.get("source_history", {}).get(layer_id, "")
                    )
                except (OSError, json.JSONDecodeError, AttributeError):
                    generation_name = ""
            generation_dir = history_root / generation_name
            if generation_name and generation_dir.is_dir():
                stacks[layer_id]["undo"].append(generation_dir)

    undo = {
        layer_id: values["undo"][-1]
        for layer_id, values in stacks.items()
        if values["undo"]
    }
    redo = {
        layer_id: values["redo"][-1]
        for layer_id, values in stacks.items()
        if values["redo"]
    }
    return undo, redo


def generation_undo_snapshots(override_dir: Path, layer_ids: list[str]) -> dict[str, Path]:
    return generation_history_state(override_dir, layer_ids)[0]


def generation_redo_snapshots(override_dir: Path, layer_ids: list[str]) -> dict[str, Path]:
    return generation_history_state(override_dir, layer_ids)[1]


def _file_digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _png_alpha_plane(path: Path) -> tuple[int, int, bytes] | None:
    """Decode an 8-bit, non-interlaced PNG alpha plane using only the server stdlib."""
    if not path.is_file():
        return None
    stat = path.stat()
    cache_key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    if cache_key in PNG_ALPHA_CACHE:
        return PNG_ALPHA_CACHE[cache_key]
    if PILImage is not None:
        try:
            with PILImage.open(path) as image:
                rgba = image.convert("RGBA")
                result = (rgba.width, rgba.height, rgba.getchannel("A").tobytes())
        except (OSError, ValueError):
            result = None
        if len(PNG_ALPHA_CACHE) > 1024:
            PNG_ALPHA_CACHE.clear()
        PNG_ALPHA_CACHE[cache_key] = result
        return result
    try:
        payload = path.read_bytes()
        if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            return None
        cursor = 8
        width = height = bit_depth = color_type = interlace = None
        compressed = bytearray()
        transparency = b""
        while cursor + 12 <= len(payload):
            length = struct.unpack(">I", payload[cursor:cursor + 4])[0]
            chunk_type = payload[cursor + 4:cursor + 8]
            chunk = payload[cursor + 8:cursor + 8 + length]
            cursor += 12 + length
            if chunk_type == b"IHDR":
                width, height, bit_depth, color_type, _, _, interlace = struct.unpack(
                    ">IIBBBBB", chunk
                )
            elif chunk_type == b"IDAT":
                compressed.extend(chunk)
            elif chunk_type == b"tRNS":
                transparency = bytes(chunk)
            elif chunk_type == b"IEND":
                break
        channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
        if not width or not height or bit_depth != 8 or interlace != 0 or channels is None:
            return None
        stride = width * channels
        decoded = zlib.decompress(bytes(compressed))
        rows: list[bytearray] = []
        source_offset = 0

        def paeth(left: int, above: int, upper_left: int) -> int:
            estimate = left + above - upper_left
            distances = (
                abs(estimate - left), abs(estimate - above), abs(estimate - upper_left)
            )
            return (left, above, upper_left)[distances.index(min(distances))]

        for row_index in range(height):
            filter_type = decoded[source_offset]
            source_offset += 1
            source_row = decoded[source_offset:source_offset + stride]
            source_offset += stride
            prior = rows[row_index - 1] if row_index else bytearray(stride)
            row = bytearray(stride)
            for index, raw in enumerate(source_row):
                left = row[index - channels] if index >= channels else 0
                above = prior[index]
                upper_left = prior[index - channels] if index >= channels else 0
                if filter_type == 0:
                    value = raw
                elif filter_type == 1:
                    value = raw + left
                elif filter_type == 2:
                    value = raw + above
                elif filter_type == 3:
                    value = raw + ((left + above) // 2)
                elif filter_type == 4:
                    value = raw + paeth(left, above, upper_left)
                else:
                    return None
                row[index] = value & 0xFF
            rows.append(row)

        if color_type == 6:
            alpha = b"".join(row[3::4] for row in rows)
        elif color_type == 4:
            alpha = b"".join(row[1::2] for row in rows)
        elif color_type == 3:
            alpha = b"".join(
                bytes(
                    transparency[index] if index < len(transparency) else 255
                    for index in row
                )
                for row in rows
            )
        else:
            alpha = bytes([255]) * (width * height)
        result = (width, height, alpha)
    except (OSError, ValueError, IndexError, struct.error, zlib.error):
        result = None
    if len(PNG_ALPHA_CACHE) > 1024:
        PNG_ALPHA_CACHE.clear()
    PNG_ALPHA_CACHE[cache_key] = result
    return result


def _png_alpha_digest(path: Path) -> str | None:
    plane = _png_alpha_plane(path)
    if plane is None:
        return None
    width, height, alpha = plane
    return hashlib.sha256(struct.pack(">II", width, height) + alpha).hexdigest()


def _png_alpha_is_covered(
    replacement_path: Path,
    coverage_path: Path,
    *,
    threshold: int = 8,
) -> bool:
    """Whether every visible replacement pixel lies inside the emitted ArtMesh triangles."""
    replacement = _png_alpha_plane(replacement_path)
    coverage = _png_alpha_plane(coverage_path)
    if replacement is None or coverage is None or replacement[:2] != coverage[:2]:
        return False
    visible_mask = replacement[2].translate(bytes(value > threshold for value in range(256)))
    uncovered_mask = coverage[2].translate(bytes(value == 0 for value in range(256)))
    visible_bits = int.from_bytes(visible_mask)
    uncovered = (visible_bits & int.from_bytes(uncovered_mask)).bit_count()
    visible = visible_bits.bit_count()
    # Rasterized grid edges can miss a handful of antialiased fringe pixels even for the texture the
    # rig was authored from. Keep the tolerance tiny so a materially new silhouette still rebuilds.
    return uncovered <= max(32, int(visible * 0.002))


def layer_generation_variants(
    override_dir: Path,
    baseline_path: Path,
    fallback_original_path: Path,
    layer_id: str,
) -> list[dict]:
    """Return the finalized original and every accepted Gemini result for one layer."""
    history_root = override_dir.parent / "history"
    history: list[tuple[Path, dict]] = []
    for history_dir in sorted(history_root.glob("*")):
        try:
            operation = json.loads((history_dir / "edit.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(operation, dict):
            history.append((history_dir, operation))

    generations: list[tuple[int, Path, dict]] = []
    for history_index, (history_dir, operation) in enumerate(history):
        operation_name = operation.get("operation")
        is_generation = operation_name == "generation" or (
            operation_name is None and isinstance(operation.get("instruction"), str)
        )
        if is_generation and layer_id in {str(value) for value in operation.get("layers", [])}:
            generations.append((history_index, history_dir, operation))

    original_path = baseline_path if baseline_path.is_file() else fallback_original_path
    variants: list[dict] = []
    if original_path.is_file():
        variants.append({
            "id": "baseline",
            "kind": "baseline",
            "index": 0,
            "instruction": "",
            "created_at": "",
            "path": original_path,
        })

    current_override = override_dir / f"{layer_id}.png"
    for generation_index, (history_index, history_dir, operation) in enumerate(generations, 1):
        result_path = history_dir / "results" / f"{layer_id}.png"
        if not result_path.is_file():
            result_path = next(
                (
                    later_dir / f"{layer_id}.png"
                    for later_dir, _ in history[history_index + 1:]
                    if (later_dir / f"{layer_id}.png").is_file()
                ),
                current_override,
            )
        if not result_path.is_file():
            continue
        variants.append({
            "id": history_dir.name,
            "kind": "generation",
            "index": generation_index,
            "instruction": str(operation.get("instruction", "")).strip(),
            "created_at": str(operation.get("edited_at", "")),
            "path": result_path,
        })

    active_path = current_override if current_override.is_file() else original_path
    active_digest = _file_digest(active_path)
    active_alpha_digest = _png_alpha_digest(active_path)
    active_id = None
    for variant in variants:
        if active_digest and _file_digest(variant["path"]) == active_digest:
            active_id = variant["id"]
    if active_id is None and variants:
        active_id = "baseline" if not current_override.is_file() else variants[-1]["id"]
    for variant in variants:
        variant["active"] = variant["id"] == active_id
        variant["texture_only"] = bool(
            active_alpha_digest
            and _png_alpha_digest(variant["path"]) == active_alpha_digest
        )
    return variants


def layer_variant_path(avatar: dict, layer_id: str, variant_id: str) -> Path | None:
    layer_dir, override_dir, baseline_dir, _ = avatar_layer_paths(avatar)
    drawable_dir = layer_dir.parent / "rig-drawable-layers"
    catalog = {item["id"]: item for item in available_avatar_layers(avatar, include_variants=False)}
    layer = catalog.get(layer_id)
    if layer is None:
        return None
    variants = layer_generation_variants(
        override_dir,
        baseline_dir / layer["editable_file"],
        drawable_dir / layer["editable_file"],
        layer_id,
    )
    return next((item["path"] for item in variants if item["id"] == variant_id), None)


def avatar_texture_path(avatar: dict, layer_id: str) -> Path | None:
    model3_value = str(avatar.get("model3", ""))
    if not model3_value:
        return None
    model3_path = Path(model3_value)
    if not model3_path.is_absolute():
        model3_path = PROJECT_ROOT / model3_path
    model3_path = model3_path.resolve()
    try:
        definition = json.loads(model3_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    suffix = f"_tex_{layer_id}.png"
    for reference in definition.get("FileReferences", {}).get("Textures", []):
        relative = urllib_parse.urlsplit(str(reference)).path
        if not Path(relative).name.endswith(suffix):
            continue
        texture_path = (model3_path.parent / relative).resolve()
        try:
            texture_path.relative_to(model3_path.parent.resolve())
        except ValueError:
            return None
        return texture_path if texture_path.is_file() else None
    return None


def avatar_mesh_coverage_path(avatar: dict, layer_id: str) -> Path | None:
    layer_dir, _, _, _ = avatar_layer_paths(avatar)
    manifest_path = layer_dir.parent / "rig-layers-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        part = manifest.get("parts", {}).get(layer_id, {})
    except (OSError, json.JSONDecodeError):
        return None
    filename = str(part.get("mesh_coverage_file", ""))
    if not filename or Path(filename).name != filename:
        return None
    coverage_path = layer_dir.parent / "rig-mesh-coverage" / filename
    expected_digest = str(part.get("mesh_coverage_sha256", ""))
    if not coverage_path.is_file() or (
        expected_digest and _file_digest(coverage_path) != expected_digest
    ):
        return None
    return coverage_path


def texture_replacement_destinations(
    avatar: dict,
    layer_paths: dict[str, Path],
    offsets: dict[str, dict] | None = None,
) -> dict[str, Path] | None:
    """Return current texture slots when every replacement keeps the rig geometry valid."""
    destinations: dict[str, Path] = {}
    offsets = offsets or {}
    for layer_id, replacement_path in layer_paths.items():
        if offsets.get(layer_id):
            return None
        texture_path = avatar_texture_path(avatar, layer_id)
        if texture_path is None:
            return None
        active_alpha = _png_alpha_digest(texture_path)
        replacement_alpha = _png_alpha_digest(replacement_path)
        if not active_alpha or not replacement_alpha:
            return None
        if replacement_alpha != active_alpha:
            coverage_path = avatar_mesh_coverage_path(avatar, layer_id)
            if coverage_path is None or not _png_alpha_is_covered(
                replacement_path, coverage_path
            ):
                return None
        destinations[layer_id] = texture_path
    return destinations


def _rig_command(
    psd_path: Path,
    live2d_dir: Path,
    model_name: str,
    override_dir: Path,
    metadata_path: Path | None = None,
) -> list[str]:
    command = [
        str(PIPELINE_PYTHON),
        str(PROJECT_ROOT / "tools" / "rig_avatar.py"),
        str(psd_path),
        "--output",
        str(live2d_dir),
        "--name",
        model_name,
    ]
    if override_dir.is_dir() and any(override_dir.glob("*.png")):
        command.extend(("--layer-overrides", str(override_dir)))
        if metadata_path and metadata_path.is_file():
            command.extend(("--layer-edit-metadata", str(metadata_path)))
    return command


def run_specific_layer_job(job_id: str) -> None:
    """Regenerate one finalized layer and its opted-in structural counterparts, then rebuild the rig."""
    with JOBS_LOCK:
        job = JOBS[job_id].copy()
    avatar_id = str(job["avatar_id"])
    try:
        avatar = generated_avatar_by_id(avatar_id)
        if avatar is None:
            raise RuntimeError("Generated avatar not found.")
        settings = hallway_settings()
        if not settings.get("GEMINI_API_KEY"):
            raise RuntimeError("Gemini is not configured in the Hallway .env file.")
        psd_path, live2d_dir, model_name = avatar_layer_regeneration_paths(avatar)
        layer_dir, override_dir, baseline_dir, reference_path = avatar_layer_paths(avatar)
        edit_metadata_path = layer_edit_metadata_path(avatar)
        drawable_dir = layer_dir.parent / "rig-drawable-layers"
        catalog = {item["id"]: item for item in available_avatar_layers(avatar)}
        primary_id = str(job["layer_id"])
        requested_ids = selected_layer_group(
            catalog, primary_id, bool(job.get("include_related", True))
        )
        paths = {
            layer_id: _layer_path(drawable_dir, catalog[layer_id]["editable_file"])
            for layer_id in requested_ids
        }
        source_paths = list(dict.fromkeys(paths.values()))

        work_dir = Path(job["work_dir"])
        pending_dir = work_dir / "pending-overrides"
        work_dir.mkdir(parents=True, exist_ok=False)
        pending_dir.mkdir()
        baseline_dir.mkdir(parents=True, exist_ok=True)
        edited = []
        gemini_models = []
        pending_by_source: dict[Path, Path] = {}
        rejected_isolation: list[dict] = []
        for index, source_path in enumerate(source_paths):
            source_ids = [layer_id for layer_id in requested_ids if paths[layer_id] == source_path]
            update_job(
                job_id,
                phase="gemini",
                message=f"Regenerating {', '.join(source_ids)} with Gemini ({index + 1}/{len(source_paths)})…",
                layer_ids=requested_ids,
            )
            baseline_path = baseline_dir / source_path.name
            if not baseline_path.is_file():
                shutil.copy2(source_path, baseline_path)
            related_sources = [candidate for candidate in source_paths if candidate != source_path]
            related_ids = [
                layer_id for layer_id in requested_ids if paths[layer_id] in related_sources
            ]
            prepare_dir = work_dir / f"prepare-{index}"
            prepare_output = _run_checked(
                [
                    str(PIPELINE_PYTHON),
                    str(PROJECT_ROOT / "tools" / "layer_regeneration.py"),
                    "prepare",
                    "--layer",
                    str(source_path),
                    *(item for candidate in related_sources for item in ("--layer", str(candidate))),
                    "--output",
                    str(prepare_dir),
                    "--reference",
                    str(reference_path),
                ],
                cwd=PROJECT_ROOT,
            )
            prepared = _json_result(prepare_output)
            prepared_paths = [Path(value) for value in prepared["prepared"]]
            prompt = build_layer_edit_prompt(
                ", ".join(source_ids),
                str(job["instruction"]),
                str(prepared["chroma"]),
                related_ids,
                str(job["change_amount"]),
                bool(job["preserve_colors"]),
                str(job["attachment_lock"]),
                bool(job.get("preserve_silhouette", False)),
            )
            image_bytes, image_mime, gemini_model = generate_layer_image(
                prompt=prompt,
                target_path=prepared_paths[0],
                reference_path=Path(prepared["reference"]),
                related_paths=prepared_paths[1:],
                settings=settings,
            )
            gemini_models.append(gemini_model)
            extension = mimetypes.guess_extension(image_mime.split(";", 1)[0]) or ".png"
            generated_path = work_dir / f"gemini-{index}{extension}"
            generated_path.write_bytes(image_bytes)
            pending_path = pending_dir / source_path.name
            try:
                recovery_output = _run_checked(
                    [
                        str(PIPELINE_PYTHON),
                        str(PROJECT_ROOT / "tools" / "layer_regeneration.py"),
                        "recover",
                        "--generated",
                        str(generated_path),
                        "--original",
                        str(source_path),
                        "--output",
                        str(pending_path),
                        "--chroma",
                        str(prepared["chroma"]),
                        "--attachment-lock",
                        str(job["attachment_lock"]),
                        *(["--preserve-silhouette"] if job.get("preserve_silhouette", False) else []),
                    ],
                    cwd=PROJECT_ROOT,
                )
            except RuntimeError as exc:
                if "full-canvas character or scene" not in str(exc):
                    raise
                rejected_isolation.append({
                    "source": source_path,
                    "ids": source_ids,
                    "related_sources": related_sources,
                    "pending": pending_path,
                    "error": str(exc),
                })
                continue
            pending_by_source[source_path] = pending_path
            edited.append({"ids": source_ids, **_json_result(recovery_output)})

        for rejected in rejected_isolation:
            counterpart = next(
                (source for source in rejected["related_sources"] if source in pending_by_source),
                None,
            )
            if counterpart is None:
                raise RuntimeError(
                    "Gemini returned the complete character instead of an isolated layer, and no valid "
                    "matching layer was available for a mirrored fallback."
                )
            mirror_output = _run_checked(
                [
                    str(PIPELINE_PYTHON),
                    str(PROJECT_ROOT / "tools" / "layer_regeneration.py"),
                    "mirror",
                    "--source",
                    str(pending_by_source[counterpart]),
                    "--original",
                    str(rejected["source"]),
                    "--output",
                    str(rejected["pending"]),
                    "--attachment-lock",
                    str(job["attachment_lock"]),
                ],
                cwd=PROJECT_ROOT,
            )
            pending_by_source[rejected["source"]] = rejected["pending"]
            edited.append({
                "ids": rejected["ids"],
                "rejected_reason": "full-character-output",
                **_json_result(mirror_output),
            })

        candidate_dir = work_dir / "candidate-overrides"
        if override_dir.is_dir():
            shutil.copytree(override_dir, candidate_dir)
        else:
            candidate_dir.mkdir()
        for pending_path in pending_dir.glob("*.png"):
            shutil.copy2(pending_path, candidate_dir / pending_path.name)
        metadata = {
            "job_id": job_id,
            "operation": "generation",
            "avatar_id": avatar_id,
            "layers": requested_ids,
            "instruction": job["instruction"],
            "include_related": bool(job["include_related"]),
            "preserve_colors": bool(job["preserve_colors"]),
            "change_amount": job["change_amount"],
            "attachment_lock": job["attachment_lock"],
            "preserve_silhouette": bool(job.get("preserve_silhouette", False)),
            "use_generated_mask": not bool(job.get("preserve_silhouette", False)),
            "mask_source": (
                "original"
                if job.get("preserve_silhouette", False)
                else "chroma-keyed-generation"
            ),
            "gemini_models": gemini_models,
            "edited_at": datetime.now(timezone.utc).isoformat(),
            "results": edited,
        }
        replacement_paths = {
            layer_id: pending_by_source[paths[layer_id]]
            for layer_id in requested_ids
            if paths[layer_id] in pending_by_source
        }
        active_edit_metadata = read_layer_edit_metadata(avatar)
        texture_destinations = (
            texture_replacement_destinations(
                avatar, replacement_paths, active_edit_metadata["offsets"]
            )
            if len(replacement_paths) == len(requested_ids)
            else None
        )
        texture_only = texture_destinations is not None
        metadata["texture_only"] = texture_only
        if texture_only:
            update_job(
                job_id,
                phase="textures",
                message="Applying generated layer textures without rebuilding the rig…",
                texture_only=True,
            )
        else:
            update_job(
                job_id,
                phase="rigging",
                message="The generated silhouette changed; rebuilding meshes and the Live2D rig…",
                texture_only=False,
            )
            output = _run_checked(
                _rig_command(psd_path, live2d_dir, model_name, candidate_dir, edit_metadata_path),
                cwd=PROJECT_ROOT,
            )
            rig_result = _json_result(output)
            if not Path(rig_result.get("model3", "")).is_file():
                raise RuntimeError("Edited layer rebuild did not produce a loadable model3 bundle.")
        # Persist only after either a valid candidate rig or an exact active-alpha match has established
        # that the result is safe. Existing edits are archived before replacement, so another generation
        # never destroys the last accepted layer image.
        generation_history_dir = snapshot_layer_edit_state(
            override_dir,
            edit_metadata_path,
            requested_ids,
            metadata,
        )
        result_archive = generation_history_dir / "results"
        for layer_id in requested_ids:
            accepted = replacement_paths.get(layer_id, candidate_dir / f"{layer_id}.png")
            if accepted.is_file():
                result_archive.mkdir(exist_ok=True)
                shutil.copy2(accepted, result_archive / f"{layer_id}.png")
        override_dir.mkdir(parents=True, exist_ok=True)
        for pending_path in pending_dir.glob("*.png"):
            current_override = override_dir / pending_path.name
            shutil.copy2(pending_path, current_override)
        if texture_only:
            for layer_id, texture_destination in texture_destinations.items():
                temporary = texture_destination.with_suffix(".tmp")
                shutil.copy2(replacement_paths[layer_id], temporary)
                temporary.replace(texture_destination)
        updated_avatar = {
            **avatar,
            "qa_passed": (
                bool(avatar.get("qa_passed"))
                if texture_only
                else bool(rig_result.get("qa_passed"))
            ),
            "cape_inpaint": (
                avatar.get("cape_inpaint")
                if texture_only
                else rig_result.get("cape_inpaint")
            ),
            "layer_overrides": (
                sorted(path.stem for path in override_dir.glob("*.png"))
                if texture_only
                else rig_result.get("layer_overrides", requested_ids)
            ),
            "layer_offsets": active_edit_metadata["offsets"],
            "layer_edits_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        register_avatar(updated_avatar)
        update_job(
            job_id,
            phase="complete",
            message=(
                "Generated layer textures applied instantly; the Live2D rig was unchanged."
                if texture_only
                else "Selected layers regenerated and the Live2D avatar rebuilt."
            ),
            avatar=updated_avatar,
            layer_ids=requested_ids,
            texture_only=texture_only,
            variant_id=generation_history_dir.name,
        )
    except Exception as exc:
        update_job(job_id, phase="failed", message="Layer edit stopped.", error=str(exc))


def run_layer_offset_job(job_id: str) -> None:
    """Apply non-destructive whole-pixel placement to one override (and optional counterparts)."""
    with JOBS_LOCK:
        job = JOBS[job_id].copy()
    avatar_id = str(job["avatar_id"])
    try:
        avatar = generated_avatar_by_id(avatar_id)
        if avatar is None:
            raise RuntimeError("Generated avatar not found.")
        psd_path, live2d_dir, model_name = avatar_layer_regeneration_paths(avatar)
        layer_dir, override_dir, baseline_dir, _ = avatar_layer_paths(avatar)
        drawable_dir = layer_dir.parent / "rig-drawable-layers"
        metadata_path = layer_edit_metadata_path(avatar)
        catalog = {item["id"]: item for item in available_avatar_layers(avatar)}
        layer_ids = selected_layer_group(
            catalog, str(job["layer_id"]), bool(job.get("include_related", False))
        )
        offset = {"x": int(job["offset_x"]), "y": int(job["offset_y"])}
        work_dir = Path(job["work_dir"])
        work_dir.mkdir(parents=True, exist_ok=False)
        candidate_dir = work_dir / "candidate-overrides"
        if override_dir.is_dir():
            shutil.copytree(override_dir, candidate_dir)
        else:
            candidate_dir.mkdir()
        baseline_dir.mkdir(parents=True, exist_ok=True)
        for layer_id in layer_ids:
            candidate = candidate_dir / f"{layer_id}.png"
            if candidate.is_file():
                continue
            editable = _layer_path(drawable_dir, catalog[layer_id]["editable_file"])
            baseline = baseline_dir / editable.name
            if not baseline.is_file():
                shutil.copy2(editable, baseline)
            shutil.copy2(baseline, candidate)

        metadata = read_layer_edit_metadata(avatar)
        for layer_id in layer_ids:
            if offset["x"] or offset["y"]:
                metadata["offsets"][layer_id] = dict(offset)
            else:
                metadata["offsets"].pop(layer_id, None)
        candidate_metadata = work_dir / "metadata.json"
        write_layer_edit_metadata(candidate_metadata, metadata)
        update_job(job_id, phase="rigging", message="Applying layer placement and rebuilding the rig…")
        output = _run_checked(
            _rig_command(psd_path, live2d_dir, model_name, candidate_dir, candidate_metadata),
            cwd=PROJECT_ROOT,
        )
        rig_result = _json_result(output)
        if not Path(rig_result.get("model3", "")).is_file():
            raise RuntimeError("Layer placement did not produce a loadable model3 bundle.")

        operation = {
            "job_id": job_id,
            "operation": "offset",
            "avatar_id": avatar_id,
            "layers": layer_ids,
            "offset": offset,
            "edited_at": datetime.now(timezone.utc).isoformat(),
        }
        snapshot_layer_edit_state(override_dir, metadata_path, layer_ids, operation)
        override_dir.mkdir(parents=True, exist_ok=True)
        for layer_id in layer_ids:
            shutil.copy2(candidate_dir / f"{layer_id}.png", override_dir / f"{layer_id}.png")
        write_layer_edit_metadata(metadata_path, metadata)
        updated_avatar = {
            **avatar,
            "qa_passed": bool(rig_result.get("qa_passed")),
            "layer_overrides": rig_result.get("layer_overrides", []),
            "layer_offsets": metadata["offsets"],
            "layer_edits_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        register_avatar(updated_avatar)
        update_job(
            job_id,
            phase="complete",
            message="Layer placement saved and the Live2D avatar rebuilt.",
            avatar=updated_avatar,
            layer_ids=layer_ids,
        )
    except Exception as exc:
        update_job(job_id, phase="failed", message="Layer placement stopped.", error=str(exc))


def run_layer_revert_job(job_id: str) -> None:
    """Reset selected drawables to their finalized pre-edit art and clear saved placement."""
    with JOBS_LOCK:
        job = JOBS[job_id].copy()
    avatar_id = str(job["avatar_id"])
    try:
        avatar = generated_avatar_by_id(avatar_id)
        if avatar is None:
            raise RuntimeError("Generated avatar not found.")
        psd_path, live2d_dir, model_name = avatar_layer_regeneration_paths(avatar)
        _, override_dir, _, _ = avatar_layer_paths(avatar)
        metadata_path = layer_edit_metadata_path(avatar)
        catalog = {item["id"]: item for item in available_avatar_layers(avatar)}
        layer_ids = selected_layer_group(
            catalog, str(job["layer_id"]), bool(job.get("include_related", False))
        )
        work_dir = Path(job["work_dir"])
        work_dir.mkdir(parents=True, exist_ok=False)
        candidate_dir = work_dir / "candidate-overrides"
        if override_dir.is_dir():
            shutil.copytree(override_dir, candidate_dir)
        else:
            candidate_dir.mkdir()
        for layer_id in layer_ids:
            (candidate_dir / f"{layer_id}.png").unlink(missing_ok=True)
        metadata = read_layer_edit_metadata(avatar)
        for layer_id in layer_ids:
            metadata["offsets"].pop(layer_id, None)
        candidate_metadata = work_dir / "metadata.json"
        write_layer_edit_metadata(candidate_metadata, metadata)

        update_job(job_id, phase="rigging", message="Restoring finalized layer art and rebuilding the rig…")
        output = _run_checked(
            _rig_command(psd_path, live2d_dir, model_name, candidate_dir, candidate_metadata),
            cwd=PROJECT_ROOT,
        )
        rig_result = _json_result(output)
        if not Path(rig_result.get("model3", "")).is_file():
            raise RuntimeError("Layer reset did not produce a loadable model3 bundle.")

        operation = {
            "job_id": job_id,
            "operation": "revert",
            "avatar_id": avatar_id,
            "layers": layer_ids,
            "edited_at": datetime.now(timezone.utc).isoformat(),
        }
        snapshot_layer_edit_state(override_dir, metadata_path, layer_ids, operation)
        for layer_id in layer_ids:
            (override_dir / f"{layer_id}.png").unlink(missing_ok=True)
        write_layer_edit_metadata(metadata_path, metadata)
        updated_avatar = {
            **avatar,
            "qa_passed": bool(rig_result.get("qa_passed")),
            "layer_overrides": rig_result.get("layer_overrides", []),
            "layer_offsets": metadata["offsets"],
            "layer_edits_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        register_avatar(updated_avatar)
        update_job(
            job_id,
            phase="complete",
            message="Selected layer art restored to its finalized original.",
            avatar=updated_avatar,
            layer_ids=layer_ids,
        )
    except Exception as exc:
        update_job(job_id, phase="failed", message="Layer reset stopped.", error=str(exc))


def run_layer_select_variant_job(job_id: str) -> None:
    """Activate an accepted result for one layer and its opted-in grouped counterparts."""
    with JOBS_LOCK:
        job = JOBS[job_id].copy()
    avatar_id = str(job["avatar_id"])
    try:
        avatar = generated_avatar_by_id(avatar_id)
        if avatar is None:
            raise RuntimeError("Generated avatar not found.")
        psd_path, live2d_dir, model_name = avatar_layer_regeneration_paths(avatar)
        _, override_dir, _, _ = avatar_layer_paths(avatar)
        metadata_path = layer_edit_metadata_path(avatar)
        catalog = {item["id"]: item for item in available_avatar_layers(avatar)}
        primary_id = str(job["layer_id"])
        variant_id = str(job["variant_id"])
        requested_ids = selected_layer_group(
            catalog, primary_id, bool(job.get("include_related", True))
        )
        variant_records = {
            layer_id: next(
                (
                    item for item in catalog[layer_id].get("variants", [])
                    if item.get("id") == variant_id
                ),
                None,
            )
            for layer_id in requested_ids
        }
        variant_paths = {
            layer_id: layer_variant_path(avatar, layer_id, variant_id)
            for layer_id, record in variant_records.items()
            if record is not None
        }
        if variant_paths.get(primary_id) is None:
            raise RuntimeError("The selected generated layer variant is no longer available.")
        variant_paths = {
            layer_id: path for layer_id, path in variant_paths.items() if path is not None
        }
        layer_ids = list(variant_paths)
        metadata = read_layer_edit_metadata(avatar)
        replacement_destinations = texture_replacement_destinations(
            avatar, variant_paths, metadata["offsets"]
        )
        texture_only = replacement_destinations is not None

        work_dir = Path(job["work_dir"])
        work_dir.mkdir(parents=True, exist_ok=False)
        candidate_dir = work_dir / "candidate-overrides"
        if override_dir.is_dir():
            shutil.copytree(override_dir, candidate_dir)
        else:
            candidate_dir.mkdir()
        for layer_id, variant_path in variant_paths.items():
            destination = candidate_dir / f"{layer_id}.png"
            if variant_id == "baseline" and not metadata["offsets"].get(layer_id):
                destination.unlink(missing_ok=True)
            else:
                shutil.copy2(variant_path, destination)
        candidate_metadata = work_dir / "metadata.json"
        write_layer_edit_metadata(candidate_metadata, metadata)

        if texture_only:
            texture_stage = work_dir / "candidate-textures"
            texture_stage.mkdir()
            texture_destinations = {}
            for layer_id, variant_path in variant_paths.items():
                texture_destination = replacement_destinations[layer_id]
                staged_texture = texture_stage / texture_destination.name
                shutil.copy2(variant_path, staged_texture)
                texture_destinations[layer_id] = (staged_texture, texture_destination)
            update_job(
                job_id,
                phase="textures",
                message="Switching layer textures without rebuilding the rig…",
                texture_only=True,
            )
        else:
            update_job(
                job_id,
                phase="rigging",
                message="The silhouette changed; rebuilding the Live2D mesh and rig…",
                texture_only=False,
            )
            output = _run_checked(
                _rig_command(psd_path, live2d_dir, model_name, candidate_dir, candidate_metadata),
                cwd=PROJECT_ROOT,
            )
            rig_result = _json_result(output)
            if not Path(rig_result.get("model3", "")).is_file():
                raise RuntimeError("Layer variant selection did not produce a loadable model3 bundle.")

        operation = {
            "job_id": job_id,
            "operation": "select-variant",
            "avatar_id": avatar_id,
            "layers": layer_ids,
            "include_related": bool(job.get("include_related", True)),
            "texture_only": texture_only,
            "variant_history": {layer_id: variant_id for layer_id in layer_ids},
            "edited_at": datetime.now(timezone.utc).isoformat(),
        }
        snapshot_layer_edit_state(override_dir, metadata_path, layer_ids, operation)
        override_dir.mkdir(parents=True, exist_ok=True)
        for layer_id in layer_ids:
            destination = candidate_dir / f"{layer_id}.png"
            if destination.is_file():
                shutil.copy2(destination, override_dir / destination.name)
            else:
                (override_dir / f"{layer_id}.png").unlink(missing_ok=True)
        if texture_only:
            for staged_texture, texture_destination in texture_destinations.values():
                temporary = texture_destination.with_suffix(".tmp")
                shutil.copy2(staged_texture, temporary)
                temporary.replace(texture_destination)
        updated_avatar = {
            **avatar,
            "qa_passed": (
                bool(avatar.get("qa_passed"))
                if texture_only
                else bool(rig_result.get("qa_passed"))
            ),
            "layer_overrides": (
                sorted(path.stem for path in override_dir.glob("*.png"))
                if texture_only
                else rig_result.get("layer_overrides", [])
            ),
            "layer_offsets": metadata["offsets"],
            "layer_edits_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        register_avatar(updated_avatar)
        update_job(
            job_id,
            phase="complete",
            message=(
                "Layer texture switched instantly; the Live2D rig was unchanged."
                if texture_only
                else "Layer variant selected and the Live2D avatar rebuilt."
            ),
            avatar=updated_avatar,
            layer_ids=layer_ids,
            texture_only=texture_only,
        )
    except Exception as exc:
        update_job(job_id, phase="failed", message="Layer variant selection stopped.", error=str(exc))


def run_layer_undo_generation_job(job_id: str) -> None:
    """Restore the override state saved immediately before the latest layer generation."""
    with JOBS_LOCK:
        job = JOBS[job_id].copy()
    avatar_id = str(job["avatar_id"])
    try:
        avatar = generated_avatar_by_id(avatar_id)
        if avatar is None:
            raise RuntimeError("Generated avatar not found.")
        psd_path, live2d_dir, model_name = avatar_layer_regeneration_paths(avatar)
        _, override_dir, _, _ = avatar_layer_paths(avatar)
        metadata_path = layer_edit_metadata_path(avatar)
        catalog = {item["id"]: item for item in available_avatar_layers(avatar)}
        layer_ids = selected_layer_group(
            catalog, str(job["layer_id"]), bool(job.get("include_related", True))
        )
        snapshots = generation_undo_snapshots(override_dir, layer_ids)
        if not snapshots:
            raise RuntimeError("No prior generation is available to undo for this layer.")

        work_dir = Path(job["work_dir"])
        work_dir.mkdir(parents=True, exist_ok=False)
        candidate_dir = work_dir / "candidate-overrides"
        if override_dir.is_dir():
            shutil.copytree(override_dir, candidate_dir)
        else:
            candidate_dir.mkdir()
        restored_ids = []
        for layer_id, snapshot in snapshots.items():
            destination = candidate_dir / f"{layer_id}.png"
            prior = snapshot / f"{layer_id}.png"
            if prior.is_file():
                shutil.copy2(prior, destination)
            else:
                destination.unlink(missing_ok=True)
            restored_ids.append(layer_id)

        metadata = read_layer_edit_metadata(avatar)
        candidate_metadata = work_dir / "metadata.json"
        write_layer_edit_metadata(candidate_metadata, metadata)
        update_job(job_id, phase="rigging", message="Undoing the last layer generation and rebuilding the rig…")
        output = _run_checked(
            _rig_command(psd_path, live2d_dir, model_name, candidate_dir, candidate_metadata),
            cwd=PROJECT_ROOT,
        )
        rig_result = _json_result(output)
        if not Path(rig_result.get("model3", "")).is_file():
            raise RuntimeError("Generation undo did not produce a loadable model3 bundle.")

        operation = {
            "job_id": job_id,
            "operation": "undo-generation",
            "avatar_id": avatar_id,
            "layers": restored_ids,
            "source_history": {
                layer_id: snapshots[layer_id].name for layer_id in restored_ids
            },
            "edited_at": datetime.now(timezone.utc).isoformat(),
        }
        snapshot_layer_edit_state(override_dir, metadata_path, restored_ids, operation)
        override_dir.mkdir(parents=True, exist_ok=True)
        for layer_id in restored_ids:
            candidate = candidate_dir / f"{layer_id}.png"
            destination = override_dir / f"{layer_id}.png"
            if candidate.is_file():
                shutil.copy2(candidate, destination)
            else:
                destination.unlink(missing_ok=True)
        write_layer_edit_metadata(metadata_path, metadata)
        updated_avatar = {
            **avatar,
            "qa_passed": bool(rig_result.get("qa_passed")),
            "layer_overrides": rig_result.get("layer_overrides", []),
            "layer_offsets": metadata["offsets"],
            "layer_edits_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        register_avatar(updated_avatar)
        update_job(
            job_id,
            phase="complete",
            message="Last layer generation undone.",
            avatar=updated_avatar,
            layer_ids=restored_ids,
        )
    except Exception as exc:
        update_job(job_id, phase="failed", message="Generation undo stopped.", error=str(exc))


def run_layer_redo_generation_job(job_id: str) -> None:
    """Restore the generated override captured immediately before the latest undo."""
    with JOBS_LOCK:
        job = JOBS[job_id].copy()
    avatar_id = str(job["avatar_id"])
    try:
        avatar = generated_avatar_by_id(avatar_id)
        if avatar is None:
            raise RuntimeError("Generated avatar not found.")
        psd_path, live2d_dir, model_name = avatar_layer_regeneration_paths(avatar)
        _, override_dir, _, _ = avatar_layer_paths(avatar)
        metadata_path = layer_edit_metadata_path(avatar)
        catalog = {item["id"]: item for item in available_avatar_layers(avatar)}
        layer_ids = selected_layer_group(
            catalog, str(job["layer_id"]), bool(job.get("include_related", True))
        )
        snapshots = generation_redo_snapshots(override_dir, layer_ids)
        if not snapshots:
            raise RuntimeError("No undone generation is available to redo for this layer.")

        work_dir = Path(job["work_dir"])
        work_dir.mkdir(parents=True, exist_ok=False)
        candidate_dir = work_dir / "candidate-overrides"
        if override_dir.is_dir():
            shutil.copytree(override_dir, candidate_dir)
        else:
            candidate_dir.mkdir()
        restored_ids = []
        generation_sources = {}
        for layer_id, snapshot in snapshots.items():
            destination = candidate_dir / f"{layer_id}.png"
            generated = snapshot / f"{layer_id}.png"
            if generated.is_file():
                shutil.copy2(generated, destination)
            else:
                destination.unlink(missing_ok=True)
            try:
                undo_operation = json.loads(
                    (snapshot / "edit.json").read_text(encoding="utf-8")
                )
                generation_source = str(
                    undo_operation.get("source_history", {}).get(layer_id, "")
                )
            except (OSError, json.JSONDecodeError, AttributeError):
                generation_source = ""
            if generation_source:
                generation_sources[layer_id] = generation_source
            restored_ids.append(layer_id)

        metadata = read_layer_edit_metadata(avatar)
        candidate_metadata = work_dir / "metadata.json"
        write_layer_edit_metadata(candidate_metadata, metadata)
        update_job(
            job_id,
            phase="rigging",
            message="Redoing the layer generation and rebuilding the rig…",
        )
        output = _run_checked(
            _rig_command(psd_path, live2d_dir, model_name, candidate_dir, candidate_metadata),
            cwd=PROJECT_ROOT,
        )
        rig_result = _json_result(output)
        if not Path(rig_result.get("model3", "")).is_file():
            raise RuntimeError("Generation redo did not produce a loadable model3 bundle.")

        operation = {
            "job_id": job_id,
            "operation": "redo-generation",
            "avatar_id": avatar_id,
            "layers": restored_ids,
            "source_history": {
                layer_id: snapshots[layer_id].name for layer_id in restored_ids
            },
            "generation_history": generation_sources,
            "edited_at": datetime.now(timezone.utc).isoformat(),
        }
        snapshot_layer_edit_state(override_dir, metadata_path, restored_ids, operation)
        override_dir.mkdir(parents=True, exist_ok=True)
        for layer_id in restored_ids:
            candidate = candidate_dir / f"{layer_id}.png"
            destination = override_dir / f"{layer_id}.png"
            if candidate.is_file():
                shutil.copy2(candidate, destination)
            else:
                destination.unlink(missing_ok=True)
        write_layer_edit_metadata(metadata_path, metadata)
        updated_avatar = {
            **avatar,
            "qa_passed": bool(rig_result.get("qa_passed")),
            "layer_overrides": rig_result.get("layer_overrides", []),
            "layer_offsets": metadata["offsets"],
            "layer_edits_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        register_avatar(updated_avatar)
        update_job(
            job_id,
            phase="complete",
            message="Last undone layer generation restored.",
            avatar=updated_avatar,
            layer_ids=restored_ids,
        )
    except Exception as exc:
        update_job(job_id, phase="failed", message="Generation redo stopped.", error=str(exc))


def run_layer_regeneration_job(job_id: str) -> None:
    """Re-import an existing semantic PSD and rebuild its rig; never rerun Gemini/See-through."""
    with JOBS_LOCK:
        job = JOBS[job_id].copy()
    avatar_id = str(job["avatar_id"])
    try:
        avatar = generated_avatar_by_id(avatar_id)
        if avatar is None:
            raise RuntimeError("Generated avatar not found.")
        psd_path, live2d_dir, model_name = avatar_layer_regeneration_paths(avatar)
        _, override_dir, _, _ = avatar_layer_paths(avatar)
        edit_metadata_path = layer_edit_metadata_path(avatar)
        update_job(
            job_id,
            phase="rigging",
            message="Reapplying layer separation, inpainting, meshes, and the Live2D rig…",
        )
        output = _run_checked(
            _rig_command(psd_path, live2d_dir, model_name, override_dir, edit_metadata_path),
            cwd=PROJECT_ROOT,
        )
        rig_result = _json_result(output)
        model3_path = Path(rig_result.get("model3", ""))
        if not model3_path.is_file():
            raise RuntimeError("Layer regeneration did not produce a loadable model3 bundle.")
        updated_avatar = {
            **avatar,
            "qa_passed": bool(rig_result.get("qa_passed")),
            "cape_inpaint": rig_result.get("cape_inpaint"),
            "layer_overrides": rig_result.get("layer_overrides", []),
            "layer_offsets": read_layer_edit_metadata(avatar)["offsets"],
            "layers_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        register_avatar(updated_avatar)
        cape_method = (rig_result.get("cape_inpaint") or {}).get("method")
        update_job(
            job_id,
            phase="complete",
            message=(
                "Layers regenerated with See-through LaMa inpainting."
                if cape_method == "see-through-lama"
                else "Layers regenerated from the existing semantic PSD."
            ),
            avatar=updated_avatar,
        )
    except Exception as exc:
        update_job(
            job_id,
            phase="failed",
            message="Layer regeneration stopped.",
            error=str(exc),
        )


def run_avatar_job(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id].copy()
    description = job["description"]
    work_dir = Path(job["work_dir"])
    try:
        ready = pipeline_status()
        missing = [key for key, value in ready.items() if key.endswith("_ready") and not value]
        if missing:
            raise RuntimeError("Avatar environment is not ready. Run python3 tools/setup_avatar_pipeline.py first.")

        work_dir.mkdir(parents=True, exist_ok=False)
        settings = hallway_settings()
        update_job(job_id, phase="gemini", message="Creating a front-facing full-body concept with Gemini…")
        image_bytes, image_mime, gemini_model = generate_character_image(description, settings)
        extension = mimetypes.guess_extension(image_mime.split(";", 1)[0]) or ".png"
        if extension == ".jpe":
            extension = ".jpg"
        source_path = work_dir / f"source{extension}"
        source_path.write_bytes(image_bytes)
        source_url = f"/local-assets/generated-avatars/{job_id}/{source_path.name}"
        update_job(
            job_id,
            source_url=source_url,
            gemini_model=gemini_model,
            phase="seethrough",
            message="Separating the artwork into semantic layers with See-through on Metal…",
        )

        profile = os.environ.get("SEE_THROUGH_PROFILE", "mps-smoke")
        see_output = work_dir / "see-through"
        _run_checked(
            [
                str(PIPELINE_PYTHON),
                str(PROJECT_ROOT / "tools" / "run_seethrough.py"),
                str(source_path),
                "--profile",
                profile,
                "--output",
                str(see_output),
            ],
            cwd=PROJECT_ROOT,
        )
        psd_path = select_semantic_psd(see_output, source_path.stem)

        update_job(
            job_id,
            phase="rigging",
            message="Building meshes, deformations, physics, motions, and the Live2D bundle…",
        )
        model_name = f"avatar_{job_id.replace('-', '_')}"
        live2d_dir = work_dir / "live2d"
        output = _run_checked(
            [
                str(PIPELINE_PYTHON),
                str(PROJECT_ROOT / "tools" / "rig_avatar.py"),
                str(psd_path),
                "--output",
                str(live2d_dir),
                "--name",
                model_name,
            ],
            cwd=PROJECT_ROOT,
        )
        result_line = next((line for line in reversed(output.splitlines()) if line.startswith("{")), "{}")
        rig_result = json.loads(result_line)
        model3_path = Path(rig_result.get("model3", ""))
        if not model3_path.is_file():
            raise RuntimeError("The rigging bridge did not produce a loadable .model3.json bundle.")
        relative_model3 = model3_path.resolve().relative_to(PROJECT_ROOT).as_posix()
        avatar = {
            "id": job_id,
            "name": _friendly_name(description, f"Generated {job_id[-6:]}"),
            "model3": relative_model3,
            "preview": source_url,
            "default": False,
            "generated": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "gemini_model": gemini_model,
            "see_through_profile": profile,
            "qa_passed": bool(rig_result.get("qa_passed")),
            "cape_inpaint": rig_result.get("cape_inpaint"),
        }
        register_avatar(avatar)
        update_job(
            job_id,
            phase="complete",
            message="Avatar ready — loading the new Live2D model…",
            avatar=avatar,
        )
    except Exception as exc:
        update_job(job_id, phase="failed", message="Avatar generation stopped.", error=str(exc))


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "Live2DLocal/1.0"

    def end_headers(self) -> None:
        # Generated model3/moc3/textures are rebuilt in place. Browser freshness caching can keep an
        # earlier moc alive after the JSON and CDI have changed, making new layers look missing.
        # This is a local development server, so every asset should reflect disk state immediately.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urllib_parse.urlsplit(self.path).path
        if path == "/api/avatars":
            self.send_json({"avatars": avatar_catalog(), "pipeline": pipeline_status()})
            return
        variant_image_match = re.fullmatch(
            r"/api/avatars/([A-Za-z0-9_-]+)/layers/([A-Za-z0-9_-]+)/variants/([A-Za-z0-9._-]+)\.png",
            path,
        )
        if variant_image_match:
            avatar_id, layer_id, variant_id = variant_image_match.groups()
            avatar = generated_avatar_by_id(avatar_id)
            image_path = layer_variant_path(avatar, layer_id, variant_id) if avatar else None
            if image_path is None or not image_path.is_file():
                self.send_json({"error": "Layer variant image not found."}, status=404)
                return
            body = image_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        layers_match = re.fullmatch(r"/api/avatars/([A-Za-z0-9_-]+)/layers", path)
        if layers_match:
            avatar = generated_avatar_by_id(layers_match.group(1))
            if avatar is None:
                self.send_json({"error": "Generated avatar not found."}, status=404)
                return
            try:
                layers = available_avatar_layers(avatar)
            except (OSError, RuntimeError) as exc:
                self.send_json({"error": str(exc)}, status=409)
                return
            self.send_json({"avatar_id": avatar["id"], "layers": layers})
            return
        match = re.fullmatch(r"/api/avatar-jobs/([A-Za-z0-9_-]+)", path)
        if match:
            with JOBS_LOCK:
                job = JOBS.get(match.group(1))
                payload = public_job(job.copy()) if job else None
            if payload is None:
                self.send_json({"error": "Avatar job not found."}, status=404)
            else:
                self.send_json(payload)
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urllib_parse.urlsplit(self.path).path
        layer_action_match = re.fullmatch(
            r"/api/avatars/([A-Za-z0-9_-]+)/(offset-layer|revert-layer|undo-generation|redo-generation|select-variant)",
            path,
        )
        if layer_action_match:
            avatar_id, action = layer_action_match.groups()
            avatar = generated_avatar_by_id(avatar_id)
            if avatar is None:
                self.send_json({"error": "Generated avatar not found."}, status=404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_BODY_BYTES:
                self.send_json({"error": "Request body is empty or too large."}, status=400)
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_json({"error": "Request body must be valid JSON."}, status=400)
                return
            layer_id = str(payload.get("layer_id", ""))
            include_related = payload.get("include_related", False)
            if not isinstance(include_related, bool):
                self.send_json({"error": "Layer options must be true or false."}, status=400)
                return
            try:
                catalog = {item["id"]: item for item in available_avatar_layers(avatar)}
            except (OSError, RuntimeError) as exc:
                self.send_json({"error": str(exc)}, status=409)
                return
            if layer_id not in catalog:
                self.send_json({"error": "Finalized layer not found."}, status=404)
                return
            now = datetime.now(timezone.utc).isoformat()
            job_id = f"layer-{action}-{int(time.time())}-{uuid.uuid4().hex[:6]}"
            avatar_root = (GENERATED_ROOT / avatar_id).resolve()
            job = {
                "id": job_id,
                "avatar_id": avatar_id,
                "layer_id": layer_id,
                "include_related": include_related,
                "work_dir": str(avatar_root / "layer-regeneration" / "jobs" / job_id),
                "phase": "queued",
                "created_at": now,
                "updated_at": now,
            }
            if action == "offset-layer":
                offset_x = payload.get("offset_x", 0)
                offset_y = payload.get("offset_y", 0)
                if (
                    isinstance(offset_x, bool) or isinstance(offset_y, bool)
                    or not isinstance(offset_x, int) or not isinstance(offset_y, int)
                    or abs(offset_x) > MAX_LAYER_OFFSET or abs(offset_y) > MAX_LAYER_OFFSET
                ):
                    self.send_json(
                        {"error": f"Layer offsets must be whole pixels from -{MAX_LAYER_OFFSET} to {MAX_LAYER_OFFSET}."},
                        status=400,
                    )
                    return
                job.update(
                    offset_x=offset_x,
                    offset_y=offset_y,
                    message="Layer placement queued…",
                )
                runner = run_layer_offset_job
            elif action == "revert-layer":
                selected = selected_layer_group(catalog, layer_id, include_related)
                if not any(catalog[item].get("can_revert") for item in selected):
                    self.send_json({"error": "The selected layer has no saved edit to reset."}, status=409)
                    return
                job["message"] = "Layer reset queued…"
                runner = run_layer_revert_job
            elif action == "undo-generation":
                selected = selected_layer_group(catalog, layer_id, include_related)
                if not any(catalog[item].get("can_undo_generation") for item in selected):
                    self.send_json({"error": "The selected layer has no generation to undo."}, status=409)
                    return
                job["message"] = "Generation undo queued…"
                runner = run_layer_undo_generation_job
            elif action == "redo-generation":
                selected = selected_layer_group(catalog, layer_id, include_related)
                if not any(catalog[item].get("can_redo_generation") for item in selected):
                    self.send_json({"error": "The selected layer has no generation to redo."}, status=409)
                    return
                job["message"] = "Generation redo queued…"
                runner = run_layer_redo_generation_job
            else:
                variant_id = str(payload.get("variant_id", ""))
                selected = selected_layer_group(catalog, layer_id, include_related)
                targeted_variants = {
                    selected_id: next(
                        (
                            item for item in catalog[selected_id].get("variants", [])
                            if item.get("id") == variant_id
                        ),
                        None,
                    )
                    for selected_id in selected
                }
                if targeted_variants.get(layer_id) is None:
                    self.send_json({"error": "The selected layer variant was not found."}, status=404)
                    return
                available_targets = {
                    selected_id: variant
                    for selected_id, variant in targeted_variants.items()
                    if variant is not None
                }
                if all(variant.get("active") for variant in available_targets.values()):
                    self.send_json({"error": "That layer variant is already selected."}, status=409)
                    return
                job.update(
                    variant_id=variant_id,
                    include_related=include_related,
                    message="Layer variant selection queued…",
                )
                runner = run_layer_select_variant_job
            with JOBS_LOCK:
                JOBS[job_id] = job
            EXECUTOR.submit(runner, job_id)
            self.send_json({"job_id": job_id, "phase": "queued"}, status=202)
            return
        specific_match = re.fullmatch(
            r"/api/avatars/([A-Za-z0-9_-]+)/regenerate-layer",
            path,
        )
        if specific_match:
            avatar_id = specific_match.group(1)
            avatar = generated_avatar_by_id(avatar_id)
            if avatar is None:
                self.send_json({"error": "Generated avatar not found."}, status=404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_BODY_BYTES:
                self.send_json({"error": "Request body is empty or too large."}, status=400)
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_json({"error": "Request body must be valid JSON."}, status=400)
                return
            layer_id = str(payload.get("layer_id", ""))
            instruction = str(payload.get("instruction", "")).strip()
            include_related = payload.get("include_related", True)
            preserve_colors = payload.get("preserve_colors", True)
            if "use_generated_mask" in payload:
                use_generated_mask = payload.get("use_generated_mask")
                preserve_silhouette = (
                    not use_generated_mask if isinstance(use_generated_mask, bool) else False
                )
            else:
                preserve_silhouette = payload.get("preserve_silhouette", False)
                use_generated_mask = not preserve_silhouette if isinstance(preserve_silhouette, bool) else True
            change_amount = str(payload.get("change_amount", "balanced"))
            attachment_lock = str(payload.get("attachment_lock", "strict"))
            if not 3 <= len(instruction) <= MAX_LAYER_INSTRUCTION:
                self.send_json({"error": "Describe the requested layer change in 3–1200 characters."}, status=400)
                return
            if (
                not isinstance(include_related, bool)
                or not isinstance(preserve_colors, bool)
                or not isinstance(use_generated_mask, bool)
                or not isinstance(preserve_silhouette, bool)
            ):
                self.send_json({"error": "Layer options must be true or false."}, status=400)
                return
            if change_amount not in {"subtle", "balanced", "strong"}:
                self.send_json({"error": "Invalid change amount."}, status=400)
                return
            if attachment_lock not in {"strict", "balanced"}:
                self.send_json({"error": "Invalid attachment lock."}, status=400)
                return
            try:
                layer_ids = {item["id"] for item in available_avatar_layers(avatar)}
            except (OSError, RuntimeError) as exc:
                self.send_json({"error": str(exc)}, status=409)
                return
            if layer_id not in layer_ids:
                self.send_json({"error": "Finalized layer not found."}, status=404)
                return
            readiness = pipeline_status()
            if not readiness["gemini_configured"] or not readiness["environment_ready"]:
                self.send_json({"error": "Gemini or the avatar environment is not ready."}, status=503)
                return
            job_id = f"layer-edit-{int(time.time())}-{uuid.uuid4().hex[:6]}"
            now = datetime.now(timezone.utc).isoformat()
            avatar_root = (GENERATED_ROOT / avatar_id).resolve()
            with JOBS_LOCK:
                JOBS[job_id] = {
                    "id": job_id,
                    "avatar_id": avatar_id,
                    "layer_id": layer_id,
                    "instruction": instruction,
                    "include_related": include_related,
                    "preserve_colors": preserve_colors,
                    "preserve_silhouette": preserve_silhouette,
                    "use_generated_mask": use_generated_mask,
                    "change_amount": change_amount,
                    "attachment_lock": attachment_lock,
                    "work_dir": str(avatar_root / "layer-regeneration" / "jobs" / job_id),
                    "phase": "queued",
                    "message": "Targeted layer regeneration queued…",
                    "created_at": now,
                    "updated_at": now,
                }
            EXECUTOR.submit(run_specific_layer_job, job_id)
            self.send_json({"job_id": job_id, "phase": "queued"}, status=202)
            return
        regenerate_match = re.fullmatch(
            r"/api/avatars/([A-Za-z0-9_-]+)/regenerate-layers",
            path,
        )
        if regenerate_match:
            avatar_id = regenerate_match.group(1)
            if not can_regenerate_avatar_layers(avatar_id):
                self.send_json(
                    {"error": "This avatar has no reusable semantic PSD layers."},
                    status=409,
                )
                return
            job_id = f"layers-{int(time.time())}-{uuid.uuid4().hex[:6]}"
            now = datetime.now(timezone.utc).isoformat()
            with JOBS_LOCK:
                JOBS[job_id] = {
                    "id": job_id,
                    "avatar_id": avatar_id,
                    "phase": "queued",
                    "message": "Layer regeneration queued…",
                    "created_at": now,
                    "updated_at": now,
                }
            EXECUTOR.submit(run_layer_regeneration_job, job_id)
            self.send_json({"job_id": job_id, "phase": "queued"}, status=202)
            return
        if path != "/api/avatars/generate":
            self.send_json({"error": "Not found."}, status=404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            self.send_json({"error": "Request body is empty or too large."}, status=400)
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json({"error": "Request body must be valid JSON."}, status=400)
            return
        description = str(payload.get("description", "")).strip()
        if len(description) < 3:
            self.send_json({"error": "Please provide a fuller character description."}, status=400)
            return
        if len(description) > 1200:
            self.send_json({"error": "Character description is too long."}, status=400)
            return
        readiness = pipeline_status()
        if not readiness["gemini_configured"]:
            self.send_json({"error": "Gemini is not configured in the Hallway .env file."}, status=503)
            return
        if not all(readiness[key] for key in ("environment_ready", "see_through_ready", "rig_bridge_ready")):
            self.send_json(
                {"error": "Avatar environment is not ready. Run python3 tools/setup_avatar_pipeline.py."},
                status=503,
            )
            return

        job_id = f"gen-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc).isoformat()
        job = {
            "id": job_id,
            "phase": "queued",
            "message": "Avatar generation queued…",
            "description": description,
            "work_dir": str(GENERATED_ROOT / job_id),
            "created_at": now,
            "updated_at": now,
        }
        with JOBS_LOCK:
            JOBS[job_id] = job
        EXECUTOR.submit(run_avatar_job, job_id)
        self.send_json({"job_id": job_id, "phase": "queued"}, status=202)

    def do_PUT(self) -> None:
        path = urllib_parse.urlsplit(self.path).path
        match = re.fullmatch(
            r"/api/avatars/([A-Za-z0-9_-]+)/viewer-metadata",
            path,
        )
        if not match:
            self.send_json({"error": "Not found."}, status=404)
            return
        avatar_id = match.group(1)
        if avatar_id not in {str(avatar.get("id")) for avatar in avatar_catalog()}:
            self.send_json({"error": "Avatar not found."}, status=404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            self.send_json({"error": "Request body is empty or too large."}, status=400)
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json({"error": "Request body must be valid JSON."}, status=400)
            return
        try:
            layer_order = validate_layer_order(payload.get("layer_order"))
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)
            return
        viewer = save_viewer_layer_order(avatar_id, layer_order)
        self.send_json({"avatar_id": avatar_id, "viewer": viewer})


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Live2D motion WebUI")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    os.chdir(PROJECT_ROOT)
    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"Live2D WebUI: http://localhost:{args.port}", flush=True)
    print("Avatar pipeline: " + json.dumps(pipeline_status(), sort_keys=True), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        EXECUTOR.shutdown(wait=False, cancel_futures=True)
        server.server_close()


if __name__ == "__main__":
    main()
