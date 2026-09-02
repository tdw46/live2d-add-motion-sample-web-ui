#!/usr/bin/env python3
"""Image preparation helpers for Gemini-backed edits of finalized rig layers.

The local HTTP server intentionally stays stdlib-only.  This module is executed with
``.venv-avatar`` for Pillow/NumPy work, and is also imported by ``rig_avatar.py`` when
persisted layer overrides are applied after See-through extraction.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SIDE_PAIRS = (("l", "r"), ("left", "right"), ("front", "back"), ("up", "lo"))


def semantic_stem(layer_id: str) -> str:
    """Drop See-through's numeric draw-order prefix while keeping its semantic name."""
    return re.sub(r"^\d+_", "", layer_id.casefold())


def matching_layer_ids(layer_id: str, available_ids: list[str]) -> list[str]:
    """Find left/right, front/back, and connected upper/lower counterparts."""
    source = semantic_stem(layer_id)
    variants: set[str] = set()
    for left, right in SIDE_PAIRS:
        for old, new in ((left, right), (right, left)):
            replaced = re.sub(rf"(^|_){re.escape(old)}(?=_|$)", rf"\1{new}", source)
            if replaced != source:
                variants.add(replaced)
    return [
        candidate
        for candidate in available_ids
        if candidate != layer_id and semantic_stem(candidate) in variants
    ]


def matching_layer_group(layer_id: str, available_ids: list[str]) -> list[str]:
    """Return the transitive structural group, e.g. both upper/lower segments on both legs."""
    found: list[str] = []
    queue = [layer_id]
    while queue:
        current = queue.pop(0)
        for candidate in matching_layer_ids(current, available_ids):
            if candidate != layer_id and candidate not in found:
                found.append(candidate)
                queue.append(candidate)
    return found


def geometric_counterpart_ids(
    layer_id: str,
    parts: dict[str, dict],
    canvas: list[int] | tuple[int, int] | None,
) -> list[str]:
    """Find an unnamed mirrored counterpart from emitted drawable geometry.

    See-through occasionally labels both arms as generic ``accessory`` layers. In that case there is
    no semantic L/R token to match, but the two drawables still have opposite, nearly mirrored canvas
    placement and similar vertical footprints. Return only the strongest credible counterpart so a
    centered crown, cape, or other accessory is not pulled into an arm edit.
    """
    if layer_id not in parts or not canvas or len(canvas) != 2:
        return []
    width, height = (float(canvas[0]), float(canvas[1]))
    if width <= 0 or height <= 0:
        return []
    source = parts[layer_id]
    source_bbox = source.get("bbox") if isinstance(source, dict) else None
    if not isinstance(source_bbox, list) or len(source_bbox) != 4:
        return []
    sx0, sy0, sx1, sy1 = map(float, source_bbox)
    scx, scy = (sx0 + sx1) / 2.0, (sy0 + sy1) / 2.0
    sw, sh = max(1.0, sx1 - sx0), max(1.0, sy1 - sy0)
    # A centered drawable has no unambiguous opposite side.
    if abs(scx - width / 2.0) < width * 0.03:
        return []

    source_role = str(source.get("semantic_role", ""))
    candidates: list[tuple[float, str]] = []
    for candidate_id, candidate in parts.items():
        if candidate_id == layer_id or not isinstance(candidate, dict):
            continue
        if str(candidate.get("semantic_role", "")) != source_role:
            continue
        bbox = candidate.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        x0, y0, x1, y1 = map(float, bbox)
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        cw, ch = max(1.0, x1 - x0), max(1.0, y1 - y0)
        if (scx - width / 2.0) * (cx - width / 2.0) >= 0:
            continue
        mirror_error = abs((scx + cx) - width) / width
        vertical_error = abs(scy - cy) / height
        height_error = abs(sh - ch) / max(sh, ch)
        width_error = abs(sw - cw) / max(sw, cw)
        if mirror_error > 0.16 or vertical_error > 0.14 or height_error > 0.42:
            continue
        score = mirror_error * 3.0 + vertical_error * 3.0 + height_error + width_error * 0.35
        candidates.append((score, candidate_id))
    if not candidates:
        return []
    candidates.sort()
    return [candidates[0][1]]


def choose_chroma_key(images) -> tuple[int, int, int]:
    """Return the RGB-grid color with the largest minimum distance from all visible input colors."""
    import numpy as np

    colors = []
    for image in images:
        rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
        visible = rgba[..., :3][rgba[..., 3] >= 16]
        if visible.size:
            # Quantization keeps the maximin search bounded while retaining the input's gamut.
            colors.append(np.unique((visible // 8) * 8, axis=0))
    if not colors:
        raise ValueError("The selected layer has no visible pixels.")
    palette = np.unique(np.concatenate(colors, axis=0), axis=0).astype(np.int32)
    levels = np.array((0, 32, 64, 96, 128, 160, 192, 224, 255), dtype=np.int32)
    candidates = np.stack(np.meshgrid(levels, levels, levels, indexing="ij"), axis=-1).reshape(-1, 3)
    best_color = None
    best_distance = -1
    for start in range(0, len(candidates), 64):
        batch = candidates[start:start + 64]
        distances = ((batch[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)
        nearest = distances.min(axis=1)
        index = int(nearest.argmax())
        if int(nearest[index]) > best_distance:
            best_distance = int(nearest[index])
            best_color = batch[index]
    return tuple(int(channel) for channel in best_color)


def flatten_on_key(image, key: tuple[int, int, int]):
    from PIL import Image

    rgba = image.convert("RGBA")
    backdrop = Image.new("RGBA", rgba.size, (*key, 255))
    backdrop.alpha_composite(rgba)
    return backdrop.convert("RGB")


def prepare_request(
    layer_paths: list[Path],
    output_dir: Path,
    reference_path: Path | None = None,
) -> dict:
    from PIL import Image, ImageOps

    if not layer_paths:
        raise ValueError("At least one layer is required.")
    images = [Image.open(path).convert("RGBA") for path in layer_paths]
    if len({image.size for image in images}) != 1:
        raise ValueError("Related layers do not share one canvas size.")
    key = choose_chroma_key(images)
    output_dir.mkdir(parents=True, exist_ok=True)
    prepared = []
    for index, image in enumerate(images):
        path = output_dir / f"input-{index}.png"
        flatten_on_key(image, key).save(path)
        prepared.append(str(path.resolve()))
    bbox = images[0].getchannel("A").getbbox()
    if not bbox:
        raise ValueError("The selected layer has no visible pixels.")
    result = {
        "chroma": "#" + "".join(f"{channel:02X}" for channel in key),
        "canvas": list(images[0].size),
        "original_bbox": list(bbox),
        "prepared": prepared,
    }
    if reference_path:
        reference = Image.open(reference_path).convert("RGB")
        if reference.size != images[0].size:
            reference = ImageOps.fit(reference, images[0].size, method=Image.Resampling.LANCZOS)
        width, height = reference.size
        part_width, part_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        margin_x = max(48, round(part_width * 0.9))
        margin_y = max(48, round(part_height * 0.55))
        context_box = (
            max(0, bbox[0] - margin_x),
            max(0, bbox[1] - margin_y),
            min(width, bbox[2] + margin_x),
            min(height, bbox[3] + margin_y),
        )
        context_path = output_dir / "reference-context.jpg"
        reference.crop(context_box).save(context_path, quality=94)
        result["reference"] = str(context_path.resolve())
        result["reference_bbox"] = list(context_box)
    return result


def _key_to_rgb(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError("Chroma color must be #RRGGBB.")
    return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))


def recover_result(
    generated_path: Path,
    original_path: Path,
    output_path: Path,
    chroma: str,
    attachment_lock: str,
    preserve_silhouette: bool = False,
) -> dict:
    """Recover an RGBA layer, restore its bbox transform, and retain its proximal attachment band."""
    import numpy as np
    from collections import deque

    from PIL import Image, ImageFilter, ImageOps

    original = Image.open(original_path).convert("RGBA")
    generated = Image.open(generated_path).convert("RGB")
    if generated.size != original.size:
        generated = ImageOps.fit(generated, original.size, method=Image.Resampling.LANCZOS)

    requested_key = np.array(_key_to_rgb(chroma), dtype=np.float32)
    rgb = np.asarray(generated, dtype=np.float32)
    key_norm = max(float(np.linalg.norm(requested_key)), 1.0)
    pixel_norm = np.maximum(np.linalg.norm(rgb, axis=2), 1.0)
    # Gemini often keeps the requested hue but adds lighting gradients, JPEG noise, or a vignette.
    # Classify by hue direction and flood the looser match from both the canvas border and exact-key
    # islands. The latter are intentional holes in hair/clothing that may enclose the keyed background
    # completely; growing from their strict seed removes the surrounding noisy key shades as well.
    cosine = np.sum(rgb * requested_key[None, None, :], axis=2) / (pixel_norm * key_norm)
    candidate = cosine >= 0.76
    # A 0.90 seed also catches small JPEG-blended key islands along enclosed edges. Those islands may
    # not contain a pristine key pixel or touch the larger hole even though they are visibly chroma.
    key_seed = cosine >= 0.90
    background = np.zeros(candidate.shape, dtype=bool)
    queue = deque()
    for x in range(generated.width):
        if candidate[0, x]:
            background[0, x] = True
            queue.append((0, x))
        if candidate[-1, x] and not background[-1, x]:
            background[-1, x] = True
            queue.append((generated.height - 1, x))
    for y in range(generated.height):
        if candidate[y, 0] and not background[y, 0]:
            background[y, 0] = True
            queue.append((y, 0))
        if candidate[y, -1] and not background[y, -1]:
            background[y, -1] = True
            queue.append((y, generated.width - 1))
    for y, x in np.argwhere(key_seed):
        if not background[y, x]:
            background[y, x] = True
            queue.append((int(y), int(x)))
    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if (
                0 <= ny < generated.height and 0 <= nx < generated.width
                and candidate[ny, nx] and not background[ny, nx]
            ):
                background[ny, nx] = True
                queue.append((ny, nx))
    # Background pixels must be fully clear. Encoding hue confidence as partial alpha leaves thousands
    # of faint keyed pixels across otherwise empty space and magnifies JPEG noise during de-spilling.
    # Blur only the binary boundary so genuine artwork edges retain antialiasing.
    alpha = np.where(background, 0.0, 1.0)
    alpha = np.asarray(
        Image.fromarray((alpha * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(0.7)),
        dtype=np.uint8,
    ).copy()
    alpha[alpha < 8] = 0
    # Remove key-color spill from partially covered edge pixels. JPEG output and Gemini's soft backdrop
    # otherwise leave a bright chroma outline even after the background alpha is correctly recovered.
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]), axis=0)
    border_key = np.median(border, axis=0)
    alpha_float = alpha.astype(np.float32) / 255.0
    safe_alpha = np.maximum(alpha_float[..., None], 0.06)
    foreground_rgb = np.clip(
        (rgb - (1.0 - alpha_float[..., None]) * border_key[None, None, :]) / safe_alpha,
        0,
        255,
    )
    # Transparent RGB is invisible in a correct straight-alpha compositor, but nonzero JPEG residue
    # can still bleed through texture filtering at hole boundaries. Keep fully clear texels colorless.
    foreground_rgb[alpha == 0] = 0
    recovered = Image.fromarray(
        np.dstack((foreground_rgb.astype(np.uint8), alpha)),
        "RGBA",
    )

    original_bbox = original.getchannel("A").getbbox()
    generated_bbox = recovered.getchannel("A").point(lambda value: 255 if value >= 24 else 0).getbbox()
    if not original_bbox or not generated_bbox:
        raise ValueError("Gemini returned an empty layer after chroma removal.")
    generated_width_ratio = (generated_bbox[2] - generated_bbox[0]) / original.width
    generated_height_ratio = (generated_bbox[3] - generated_bbox[1]) / original.height
    original_area_ratio = (
        (original_bbox[2] - original_bbox[0]) * (original_bbox[3] - original_bbox[1])
        / (original.width * original.height)
    )
    if (
        original_area_ratio < 0.45
        and generated_width_ratio > 0.82
        and generated_height_ratio > 0.82
    ):
        raise ValueError(
            "Gemini returned a full-canvas character or scene instead of the isolated target layer."
        )

    # The normal path keeps the chroma-derived alpha in Gemini's original canvas coordinates. This
    # allows a generated part to acquire a genuinely new outline (longer hair, a narrower sleeve,
    # etc.) without being squeezed back into the finalized layer's old bounding box. Exact-mask mode
    # remains available for edits that intentionally must not change any occupied pixel.
    original_height = original_bbox[3] - original_bbox[1]
    original_width = original_bbox[2] - original_bbox[0]
    generated_width = generated_bbox[2] - generated_bbox[0]
    generated_height = generated_bbox[3] - generated_bbox[1]
    registered = Image.new("RGBA", original.size, (0, 0, 0, 0))
    if preserve_silhouette:
        target_width = original_width
        crop = recovered.crop(generated_bbox).resize(
            (original_width, original_height), Image.Resampling.LANCZOS
        )
        registered_x = original_bbox[0]
        registered.alpha_composite(crop, (registered_x, original_bbox[1]))
        generated_alpha = registered.getchannel("A")
        generated_rgb = registered.convert("RGB")
        fallback_rgb = original.convert("RGB")
        filled_rgb = Image.composite(generated_rgb, fallback_rgb, generated_alpha)
        registered = filled_rgb.convert("RGBA")
        registered.putalpha(original.getchannel("A"))
    else:
        target_width = generated_width
        registered_x = generated_bbox[0]
        registered = recovered.copy()

    band_fraction = {"strict": 0.06, "balanced": 0.03}.get(attachment_lock)
    if band_fraction is None:
        raise ValueError("attachment_lock must be strict or balanced.")
    band_height = min(16, max(2, round(original_height * band_fraction)))
    # Full original pixels at the proximal edge, then a short feather into regenerated content. Limbs,
    # neck, cape, front/back hair, and clothing all attach from this top-side edge in the finalized PNGs.
    mask = Image.new("L", original.size, 0)
    mask_array = np.zeros((original.height, original.width), dtype=np.uint8)
    y0 = original_bbox[1]
    y1 = min(original_bbox[3], y0 + band_height)
    if y1 > y0:
        ramp = np.linspace(255, 0, y1 - y0, endpoint=True, dtype=np.uint8)
        mask_array[y0:y1, original_bbox[0]:original_bbox[2]] = ramp[:, None]
    mask = Image.fromarray(mask_array, "L")
    registered = Image.composite(original, registered, mask)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    registered.save(output_path)
    return {
        "output": str(output_path.resolve()),
        "original_bbox": list(original_bbox),
        "generated_bbox": list(generated_bbox),
        "attachment_lock": attachment_lock,
        "preserve_silhouette": preserve_silhouette,
        "attachment_band_px": band_height,
        "registration": {
            "anchor": "exact-original-mask" if preserve_silhouette else "chroma-mask-canvas",
            "x": registered_x,
            "y": original_bbox[1] if preserve_silhouette else generated_bbox[1],
            "width": target_width,
            "height": original_height if preserve_silhouette else generated_height,
        },
    }


def mirror_result(
    source_path: Path,
    original_path: Path,
    output_path: Path,
    attachment_lock: str,
) -> dict:
    """Mirror a valid counterpart and retain the target side's original proximal seam."""
    import numpy as np
    from PIL import Image, ImageOps

    source = Image.open(source_path).convert("RGBA")
    original = Image.open(original_path).convert("RGBA")
    if source.size != original.size:
        raise ValueError("Mirrored counterpart does not share the target canvas size.")
    mirrored = ImageOps.mirror(source)
    original_bbox = original.getchannel("A").getbbox()
    if not original_bbox:
        raise ValueError("The target layer has no visible attachment seam.")
    band_fraction = {"strict": 0.06, "balanced": 0.03}.get(attachment_lock)
    if band_fraction is None:
        raise ValueError("attachment_lock must be strict or balanced.")
    height = original_bbox[3] - original_bbox[1]
    band_height = min(16, max(2, round(height * band_fraction)))
    mask_array = np.zeros((original.height, original.width), dtype=np.uint8)
    y0 = original_bbox[1]
    y1 = min(original_bbox[3], y0 + band_height)
    ramp = np.linspace(255, 0, max(1, y1 - y0), endpoint=True, dtype=np.uint8)
    mask_array[y0:y1, original_bbox[0]:original_bbox[2]] = ramp[:, None]
    result = Image.composite(original, mirrored, Image.fromarray(mask_array, "L"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)
    return {
        "output": str(output_path.resolve()),
        "fallback": "mirrored-related-layer",
        "attachment_lock": attachment_lock,
        "attachment_band_px": band_height,
    }


def apply_overrides(
    layer_dir: Path,
    override_dir: Path,
    *,
    manifest_path: Path | None = None,
    drawable_dir: Path | None = None,
    baseline_dir: Path | None = None,
    offsets: dict[str, dict[str, int]] | None = None,
) -> list[str]:
    """Merge per-drawable overrides into freshly extracted finalized source layers.

    A fallback one-file-per-layer mode is retained for old bundles without a drawable manifest.
    """
    from PIL import Image, ImageChops

    applied = []
    if not override_dir.is_dir():
        return applied
    offsets = offsets or {}
    parts = {}
    if manifest_path and manifest_path.is_file():
        try:
            parts = json.loads(manifest_path.read_text(encoding="utf-8")).get("parts", {})
        except (OSError, json.JSONDecodeError):
            parts = {}
    source_owner_counts: dict[str, int] = {}
    if isinstance(parts, dict):
        for part_info in parts.values():
            if isinstance(part_info, dict):
                source = str(part_info.get("source_file", ""))
                if source:
                    source_owner_counts[source] = source_owner_counts.get(source, 0) + 1
    for override in sorted(override_dir.glob("*.png")):
        info = parts.get(override.stem, {}) if isinstance(parts, dict) else {}
        source_file = str(info.get("source_file", override.name))
        if Path(source_file).name != source_file:
            raise ValueError(f"Unsafe override source for {override.name}")
        target = layer_dir / source_file
        if not target.is_file():
            raise ValueError(f"Override has no finalized layer target: {override.name}")
        with Image.open(target).convert("RGBA") as expected, Image.open(override).convert("RGBA") as replacement:
            if replacement.size != expected.size:
                raise ValueError(f"Override canvas does not match {override.name}")
            offset = offsets.get(override.stem, {})
            offset_x = int(offset.get("x", 0)) if isinstance(offset, dict) else 0
            offset_y = int(offset.get("y", 0)) if isinstance(offset, dict) else 0
            if offset_x or offset_y:
                shifted = Image.new("RGBA", replacement.size, (0, 0, 0, 0))
                shifted.alpha_composite(replacement, (offset_x, offset_y))
                replacement = shifted
            if info and source_owner_counts.get(source_file, 0) == 1:
                # This drawable owns the whole source PNG. Replacing it outright prevents the freshly
                # extracted original art from surviving underneath a regenerated silhouette.
                replacement.save(target)
            elif info and drawable_dir and (drawable_dir / override.name).is_file():
                baseline = baseline_dir / override.name if baseline_dir else None
                mask_source = (
                    baseline if baseline and baseline.is_file()
                    else drawable_dir / override.name
                )
                prior = Image.open(mask_source).convert("RGBA")
                clear_mask = ImageChops.lighter(prior.getchannel("A"), replacement.getchannel("A"))
                cleared = expected.copy()
                cleared.paste((0, 0, 0, 0), (0, 0), clear_mask)
                cleared.alpha_composite(replacement)
                cleared.save(target)
            else:
                replacement.save(target)
        applied.append(override.stem)
    return applied


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and recover finalized layer image edits")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--layer", action="append", required=True)
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--reference")
    recover = subparsers.add_parser("recover")
    recover.add_argument("--generated", required=True)
    recover.add_argument("--original", required=True)
    recover.add_argument("--output", required=True)
    recover.add_argument("--chroma", required=True)
    recover.add_argument("--attachment-lock", choices=("strict", "balanced"), default="strict")
    recover.add_argument("--preserve-silhouette", action="store_true")
    mirror = subparsers.add_parser("mirror")
    mirror.add_argument("--source", required=True)
    mirror.add_argument("--original", required=True)
    mirror.add_argument("--output", required=True)
    mirror.add_argument("--attachment-lock", choices=("strict", "balanced"), default="strict")
    args = parser.parse_args()

    if args.command == "prepare":
        result = prepare_request(
            [Path(value) for value in args.layer],
            Path(args.output),
            Path(args.reference) if args.reference else None,
        )
    elif args.command == "recover":
        result = recover_result(
            Path(args.generated),
            Path(args.original),
            Path(args.output),
            args.chroma,
            args.attachment_lock,
            args.preserve_silhouette,
        )
    else:
        result = mirror_result(
            Path(args.source),
            Path(args.original),
            Path(args.output),
            args.attachment_lock,
        )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
