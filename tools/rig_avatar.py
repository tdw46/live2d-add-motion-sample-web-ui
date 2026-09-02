#!/usr/bin/env python3
"""Convert a See-through PSD into a complete browser-loadable Live2D bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
IMAGE2LIVE2D_SRC = ROOT / "vendor" / "image2live2d" / "src"
SEE_THROUGH_ROOT = ROOT / "vendor" / "see-through"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(IMAGE2LIVE2D_SRC))

# LaMa is written for CUDA, but its small number of unsupported MPS operations can safely fall
# back to CPU while the convolution-heavy work remains on Apple Silicon's GPU.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

from image2live2d.backends.live2d import Live2DEmitter  # noqa: E402
from image2live2d.backends.live2d.moc3_emit import native_moc_writer  # noqa: E402
from image2live2d.core.decompose import from_psd  # noqa: E402
from image2live2d.core.qa import evaluate  # noqa: E402
from image2live2d.pipeline import rig_from_stack  # noqa: E402
from tools.layer_regeneration import apply_overrides  # noqa: E402


def restore_stack_display_names(stack, display_names: dict[str, str | None]) -> None:
    """Restore See-through provenance after reloading edited PNGs from their semantic filenames."""
    for layer in stack.layers:
        if layer.id in display_names:
            layer.display_name = display_names[layer.id]


def build_variant_mesh_guides(stack, regeneration_dir: Path) -> dict[str, Path]:
    """Union accepted variant alpha so known silhouettes share one reusable ArtMesh."""
    from PIL import Image, ImageChops

    baseline_dir = regeneration_dir / "baseline"
    history_dir = regeneration_dir / "history"
    guide_dir = regeneration_dir / "mesh-guides"
    guide_dir.mkdir(parents=True, exist_ok=True)
    guides: dict[str, Path] = {}
    expected = set()
    for layer in stack.layers:
        current_path = Path(layer.texture_path)
        if not current_path.is_file():
            continue
        current = Image.open(current_path).convert("RGBA")
        union_alpha = current.getchannel("A")
        candidates = [baseline_dir / f"{layer.id}.png"]
        candidates.extend(sorted(history_dir.glob(f"*/results/{layer.id}.png")))
        candidates.extend(sorted(history_dir.glob(f"*/{layer.id}.png")))
        for candidate in candidates:
            if not candidate.is_file():
                continue
            variant = Image.open(candidate).convert("RGBA")
            if variant.size == current.size:
                union_alpha = ImageChops.lighter(union_alpha, variant.getchannel("A"))
        guide = current.copy()
        guide.putalpha(union_alpha)
        guide_path = guide_dir / f"{layer.id}.png"
        guide.save(guide_path)
        guides[layer.id] = guide_path
        expected.add(guide_path.name)
    for stale in guide_dir.glob("*.png"):
        if stale.name not in expected:
            stale.unlink()
    return guides


def write_drawable_layers(
    rig,
    layer_dir: Path,
    drawable_dir: Path,
    coverage_dir: Path,
) -> dict:
    """Materialize one full-canvas RGBA image per emitted drawable for precise future edits."""
    from PIL import Image, ImageChops, ImageDraw

    textures = {texture.id: texture for texture in rig.textures}
    drawable_dir.mkdir(parents=True, exist_ok=True)
    coverage_dir.mkdir(parents=True, exist_ok=True)
    expected_names = set()
    parts = {}
    canvas = None
    for part in rig.parts:
        texture = textures[part.texture_id]
        source_path = layer_dir / texture.path
        mesh = rig.mesh_for(part.id)
        if mesh is None or not source_path.is_file():
            continue
        source = Image.open(source_path).convert("RGBA")
        width, height = source.size
        canvas = [width, height]
        mask = Image.new("L", source.size, 0)
        draw = ImageDraw.Draw(mask)
        for triangle in mesh.triangles:
            points = [
                (round(mesh.uvs[index][0] * (width - 1)), round(mesh.uvs[index][1] * (height - 1)))
                for index in triangle
            ]
            draw.polygon(points, fill=255)
            draw.line(points + [points[0]], fill=255, width=2)
        drawable = source.copy()
        drawable_alpha = ImageChops.multiply(source.getchannel("A"), mask)
        drawable.putalpha(drawable_alpha)
        filename = f"{part.id}.png"
        drawable.save(drawable_dir / filename)
        coverage = Image.new("RGBA", source.size, (255, 255, 255, 0))
        coverage.putalpha(mask)
        coverage_path = coverage_dir / filename
        coverage.save(coverage_path)
        expected_names.add(filename)
        parts[part.id] = {
            "source_file": texture.path,
            "editable_file": filename,
            "semantic_role": part.semantic_role.value,
            "display_name": part.display_name,
            "bbox": list(drawable_alpha.getbbox()) if drawable_alpha.getbbox() else None,
            "mesh_coverage_file": filename,
            "mesh_coverage_sha256": hashlib.sha256(coverage_path.read_bytes()).hexdigest(),
        }
    for directory in (drawable_dir, coverage_dir):
        for stale in directory.glob("*.png"):
            if stale.name not in expected_names:
                stale.unlink()
    return {"version": 4, "canvas": canvas, "parts": parts}


def build_cape_inpainter(psd_path: Path, mode: str):
    """Reuse See-through's anime LaMa completion model for cape-only masked inpainting."""
    state = {"requested": mode, "method": "smooth", "device": None, "error": None}
    if mode == "smooth":
        return None, state

    try:
        import numpy as np
        import torch
        from PIL import Image

        sys.path.insert(0, str(SEE_THROUGH_ROOT))
        from annotators.lama_inpainter import apply_inpaint

        if torch.cuda.is_available():
            device = "cuda"
        elif torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"

        source = None
        source_root = psd_path.parent.parent
        for extension in (".png", ".jpg", ".jpeg", ".webp"):
            candidate = source_root / f"{psd_path.stem}{extension}"
            if candidate.is_file():
                source = np.array(Image.open(candidate).convert("RGB"), dtype=np.uint8)
                break

        def inpaint(topwear_rgb, mask):
            canvas = source if source is not None and source.shape == topwear_rgb.shape else topwear_rgb
            try:
                result = apply_inpaint(canvas, mask, device=device)
            except Exception as exc:
                state["error"] = f"{type(exc).__name__}: {exc}"
                if mode == "lama":
                    raise
                return None
            state.update(method="see-through-lama", device=device, error=None)
            return result

        return inpaint, state
    except Exception as exc:
        state["error"] = f"{type(exc).__name__}: {exc}"
        if mode == "lama":
            raise
        return None, state


def _alpha_bbox(path: Path):
    from PIL import Image

    return Image.open(path).convert("RGBA").getchannel("A").getbbox()


def _pixels(image):
    getter = getattr(image, "get_flattened_data", None)
    return getter() if getter else image.getdata()


def repair_incomplete_face(layer_dir: Path) -> bool:
    """Fill a missing See-through face plane while preserving its extracted jaw line.

    The experimental MPS depth path can occasionally return only the jaw contour for
    the ``face`` layer. Eyes, mouth, ears, neck, and hair remain usable, so a skin-toned
    oval behind those parts is a safer recovery than shipping a transparent face.
    """
    from PIL import Image, ImageDraw

    face_paths = list(layer_dir.glob("*_face_base.png"))
    eye_l_paths = list(layer_dir.glob("*_eye_l.png"))
    eye_r_paths = list(layer_dir.glob("*_eye_r.png"))
    mouth_paths = list(layer_dir.glob("*_mouth.png"))
    neck_paths = list(layer_dir.glob("*_neck.png"))
    if not all((face_paths, eye_l_paths, eye_r_paths, mouth_paths)):
        return False

    face_path = face_paths[0]
    original = Image.open(face_path).convert("RGBA")
    face_alpha = original.getchannel("A")
    face_bbox = face_alpha.getbbox()
    if not face_bbox:
        fill_ratio = 0.0
    else:
        nonempty = sum(1 for value in _pixels(face_alpha) if value > 16)
        bbox_area = max(1, (face_bbox[2] - face_bbox[0]) * (face_bbox[3] - face_bbox[1]))
        fill_ratio = nonempty / bbox_area
    if fill_ratio >= 0.35:
        return False

    left_bbox = _alpha_bbox(eye_l_paths[0])
    right_bbox = _alpha_bbox(eye_r_paths[0])
    mouth_bbox = _alpha_bbox(mouth_paths[0])
    if not left_bbox or not right_bbox or not mouth_bbox:
        return False
    eye_centers = sorted(
        [
            ((left_bbox[0] + left_bbox[2]) / 2, (left_bbox[1] + left_bbox[3]) / 2),
            ((right_bbox[0] + right_bbox[2]) / 2, (right_bbox[1] + right_bbox[3]) / 2),
        ]
    )
    eye_gap = max(8.0, eye_centers[1][0] - eye_centers[0][0])
    center_x = (eye_centers[0][0] + eye_centers[1][0]) / 2
    eye_y = (eye_centers[0][1] + eye_centers[1][1]) / 2
    top = eye_y - 1.45 * eye_gap
    bottom = mouth_bbox[3] + 0.78 * eye_gap
    radius_x = 1.18 * eye_gap

    skin_samples = []
    if neck_paths:
        neck = Image.open(neck_paths[0]).convert("RGBA")
        skin_samples = [
            (r, g, b)
            for r, g, b, alpha in _pixels(neck)
            if alpha > 128 and max(r, g, b) - min(r, g, b) < 110
        ]
    if skin_samples:
        skin = tuple(int(statistics.median(pixel[channel] for pixel in skin_samples)) for channel in range(3))
    else:
        skin = (231, 194, 178)

    repaired = Image.new("RGBA", original.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(repaired)
    draw.ellipse(
        (
            int(center_x - radius_x),
            int(top),
            int(center_x + radius_x),
            int(bottom),
        ),
        fill=(*skin, 255),
    )
    repaired.alpha_composite(original)
    repaired.save(face_path)
    return True


def version_model_resources(model3_path: Path, token: str | None = None) -> str:
    """Version emitted URLs so an in-place rebuild cannot reuse an older MOC or texture."""
    payload = json.loads(model3_path.read_text(encoding="utf-8"))
    version = token or str(time.time_ns())

    def add_version(value):
        if isinstance(value, dict):
            return {key: add_version(item) for key, item in value.items()}
        if isinstance(value, list):
            return [add_version(item) for item in value]
        if isinstance(value, str) and value.partition("?")[0].lower().endswith(
            (".moc3", ".png", ".json")
        ):
            return f"{value.split('?', 1)[0]}?v={version}"
        return value

    payload["FileReferences"] = add_version(payload.get("FileReferences", {}))
    model3_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return version


def main() -> None:
    parser = argparse.ArgumentParser(description="Rig a See-through PSD as Live2D")
    parser.add_argument("psd")
    parser.add_argument("--output", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--cape-inpaint",
        choices=("auto", "lama", "smooth"),
        default="auto",
        help="Cape completion method; auto reuses See-through LaMa and falls back to smoothing.",
    )
    parser.add_argument(
        "--layer-overrides",
        help="Directory of finalized full-canvas PNG layers to apply after PSD extraction/inpainting.",
    )
    parser.add_argument(
        "--layer-edit-metadata",
        help="JSON metadata containing non-destructive per-drawable pixel offsets.",
    )
    args = parser.parse_args()

    psd_path = Path(args.psd).resolve()
    output_dir = Path(args.output).resolve()
    layer_dir = output_dir.parent / "rig-layers"
    if not psd_path.is_file():
        parser.error(f"PSD does not exist: {psd_path}")
    if psd_path.stem.casefold().endswith(("_depth", "_wdepth")):
        parser.error(
            "Refusing to rig a See-through depth/debug PSD; pass the matching semantic color-layer PSD."
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    cape_inpainter, cape_inpaint = build_cape_inpainter(psd_path, args.cape_inpaint)
    stack = from_psd(psd_path, layer_dir, cape_inpainter=cape_inpainter)
    source_display_names = {layer.id: layer.display_name for layer in stack.layers}
    face_repaired = repair_incomplete_face(layer_dir)
    layer_manifest_path = layer_dir.parent / "rig-layers-manifest.json"
    drawable_layer_dir = layer_dir.parent / "rig-drawable-layers"
    baseline_layer_dir = layer_dir.parent / "layer-regeneration" / "baseline"
    layer_offsets = {}
    if args.layer_edit_metadata:
        metadata_path = Path(args.layer_edit_metadata).resolve()
        if metadata_path.is_file():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if isinstance(metadata, dict) and isinstance(metadata.get("offsets"), dict):
                layer_offsets = metadata["offsets"]
    layer_overrides = apply_overrides(
        layer_dir,
        Path(args.layer_overrides).resolve(),
        manifest_path=layer_manifest_path,
        drawable_dir=drawable_layer_dir,
        baseline_dir=baseline_layer_dir,
        offsets=layer_offsets,
    ) if args.layer_overrides else []
    # Re-read the finalized directory after applying replacements so meshes, textures, and semantic roles
    # are authored from the edited pixels rather than the pre-edit PSD extraction held in ``stack``.
    if layer_overrides:
        from image2live2d.core.decompose import from_layer_dir
        stack = from_layer_dir(layer_dir)
        restore_stack_display_names(stack, source_display_names)
    regeneration_dir = layer_dir.parent / "layer-regeneration"
    mesh_guides = build_variant_mesh_guides(stack, regeneration_dir)
    rig = rig_from_stack(
        stack,
        name=args.name,
        source=str(psd_path),
        mesh_alpha_paths=mesh_guides,
    )
    layer_manifest = write_drawable_layers(
        rig,
        layer_dir,
        drawable_layer_dir,
        layer_dir.parent / "rig-mesh-coverage",
    )
    layer_manifest_path.write_text(
        json.dumps(layer_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    bundle = Live2DEmitter(
        asset_root=layer_dir,
        moc_writer=native_moc_writer,
    ).build(rig, output_dir)
    if not bundle.moc_written:
        raise RuntimeError("Native Live2D writer did not emit a .moc3 file.")
    version_model_resources(bundle.model3_path)

    report = evaluate(rig, args.name)
    summary = {
        "model3": str(bundle.model3_path.resolve()),
        "moc3": str((output_dir / f"{args.name}.moc3").resolve()),
        "files": len(bundle.files),
        "parts": len(rig.parts),
        "parameters": len(rig.parameters),
        "physics": len(rig.physics),
        "qa_passed": report.passed,
        "face_repaired": face_repaired,
        "cape_inpaint": cape_inpaint,
        "layer_overrides": layer_overrides,
        "layer_offsets": layer_offsets,
    }
    (output_dir / "rig-report.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
