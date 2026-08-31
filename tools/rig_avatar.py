#!/usr/bin/env python3
"""Convert a See-through PSD into a complete browser-loadable Live2D bundle."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
IMAGE2LIVE2D_SRC = ROOT / "vendor" / "image2live2d" / "src"
sys.path.insert(0, str(IMAGE2LIVE2D_SRC))

from image2live2d.backends.live2d import Live2DEmitter  # noqa: E402
from image2live2d.backends.live2d.moc3_emit import native_moc_writer  # noqa: E402
from image2live2d.core.decompose import from_psd  # noqa: E402
from image2live2d.core.qa import evaluate  # noqa: E402
from image2live2d.pipeline import rig_from_stack  # noqa: E402


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Rig a See-through PSD as Live2D")
    parser.add_argument("psd")
    parser.add_argument("--output", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    psd_path = Path(args.psd).resolve()
    output_dir = Path(args.output).resolve()
    layer_dir = output_dir.parent / "rig-layers"
    if not psd_path.is_file():
        parser.error(f"PSD does not exist: {psd_path}")
    output_dir.mkdir(parents=True, exist_ok=True)

    stack = from_psd(psd_path, layer_dir)
    face_repaired = repair_incomplete_face(layer_dir)
    rig = rig_from_stack(stack, name=args.name, source=str(psd_path))
    bundle = Live2DEmitter(
        asset_root=layer_dir,
        moc_writer=native_moc_writer,
    ).build(rig, output_dir)
    if not bundle.moc_written:
        raise RuntimeError("Native Live2D writer did not emit a .moc3 file.")

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
    }
    (output_dir / "rig-report.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
