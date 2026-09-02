import tempfile
import unittest
import json
import shutil
from pathlib import Path
from unittest.mock import patch

from tools.layer_regeneration import (
    apply_overrides,
    choose_chroma_key,
    geometric_counterpart_ids,
    matching_layer_group,
    mirror_result,
    prepare_request,
    recover_result,
)
from tools.serve import (
    JOBS,
    _png_alpha_digest,
    _png_alpha_is_covered,
    build_layer_edit_prompt,
    generation_redo_snapshots,
    generation_undo_snapshots,
    layer_generation_variants,
    run_layer_offset_job,
    run_layer_redo_generation_job,
    run_layer_revert_job,
    run_layer_select_variant_job,
    run_layer_undo_generation_job,
    run_specific_layer_job,
)

try:
    from PIL import Image, ImageDraw
except ImportError:  # pnpm's stdlib-only server Python does not need image dependencies.
    Image = None


class LayerPairingTests(unittest.TestCase):
    def test_finds_full_mirrored_connected_leg_group(self):
        ids = ["05_leg_r_up", "05_leg_r_lo", "06_leg_l_up", "06_leg_l_lo", "08_neck"]
        self.assertEqual(
            set(matching_layer_group("05_leg_r_up", ids)),
            {"05_leg_r_lo", "06_leg_l_up", "06_leg_l_lo"},
        )

    def test_finds_front_back_counterpart_across_draw_order_prefixes(self):
        ids = ["01_hair_back", "22_hair_front", "12_face_base"]
        self.assertEqual(matching_layer_group("22_hair_front", ids), ["01_hair_back"])

    def test_finds_generic_accessory_arms_by_mirrored_geometry(self):
        parts = {
            "02_accessory": {"semantic_role": "accessory", "bbox": [416, 189, 574, 418]},
            "03_accessory": {"semantic_role": "accessory", "bbox": [262, 190, 351, 412]},
            "23_accessory": {"semantic_role": "accessory", "bbox": [323, 52, 440, 106]},
        }
        self.assertEqual(
            geometric_counterpart_ids("03_accessory", parts, [768, 768]),
            ["02_accessory"],
        )
        self.assertEqual(geometric_counterpart_ids("23_accessory", parts, [768, 768]), [])

    def test_keeps_relaxed_narrow_arms_paired_near_the_body_midline(self):
        parts = {
            "02_accessory": {"semantic_role": "accessory", "bbox": [410, 189, 457, 418]},
            "03_accessory": {"semantic_role": "accessory", "bbox": [316, 189, 363, 418]},
            "23_accessory": {"semantic_role": "accessory", "bbox": [323, 52, 440, 106]},
        }
        self.assertEqual(
            geometric_counterpart_ids("03_accessory", parts, [768, 768]),
            ["02_accessory"],
        )


class LayerGenerationHistoryTests(unittest.TestCase):
    def test_finds_latest_generation_until_an_undo_consumes_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            override_dir = Path(temp_dir) / "overrides"
            history = override_dir.parent / "history"
            override_dir.mkdir()
            first = history / "20260901T000000Z"
            first.mkdir(parents=True)
            (first / "edit.json").write_text(json.dumps({
                "operation": "generation", "layers": ["hair_front"]
            }), encoding="utf-8")
            self.assertEqual(
                generation_undo_snapshots(override_dir, ["hair_front"])["hair_front"],
                first,
            )
            undo = history / "20260901T000001Z"
            undo.mkdir()
            (undo / "edit.json").write_text(json.dumps({
                "operation": "undo-generation",
                "source_history": {"hair_front": first.name},
            }), encoding="utf-8")
            self.assertEqual(generation_undo_snapshots(override_dir, ["hair_front"]), {})
            self.assertEqual(
                generation_redo_snapshots(override_dir, ["hair_front"])["hair_front"],
                undo,
            )
            redo = history / "20260901T000002Z"
            redo.mkdir()
            (redo / "edit.json").write_text(json.dumps({
                "operation": "redo-generation",
                "source_history": {"hair_front": undo.name},
                "generation_history": {"hair_front": first.name},
            }), encoding="utf-8")
            self.assertEqual(
                generation_undo_snapshots(override_dir, ["hair_front"])["hair_front"],
                first,
            )
            self.assertEqual(generation_redo_snapshots(override_dir, ["hair_front"]), {})

    def test_lists_original_and_every_accepted_generation_with_the_active_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            override_dir = root / "layer-regeneration" / "overrides"
            history = override_dir.parent / "history"
            baseline = override_dir.parent / "baseline" / "hair_front.png"
            fallback = root / "rig-drawable-layers" / "hair_front.png"
            for directory in (override_dir, history, baseline.parent, fallback.parent):
                directory.mkdir(parents=True, exist_ok=True)
            baseline.write_bytes(b"original")
            fallback.write_bytes(b"current-drawable")
            first = history / "20260901T000000Z"
            second = history / "20260901T000001Z"
            first.mkdir()
            second.mkdir()
            (first / "edit.json").write_text(json.dumps({
                "operation": "generation",
                "layers": ["hair_front"],
                "instruction": "Make it red.",
            }), encoding="utf-8")
            (second / "hair_front.png").write_bytes(b"red-result")
            (second / "edit.json").write_text(json.dumps({
                "operation": "generation",
                "layers": ["hair_front"],
                "instruction": "Make it blue.",
            }), encoding="utf-8")
            (override_dir / "hair_front.png").write_bytes(b"blue-result")

            variants = layer_generation_variants(
                override_dir, baseline, fallback, "hair_front"
            )
            self.assertEqual(
                [variant["id"] for variant in variants],
                ["baseline", first.name, second.name],
            )
            self.assertEqual(variants[1]["path"].read_bytes(), b"red-result")
            self.assertEqual(variants[2]["path"].read_bytes(), b"blue-result")
            self.assertEqual(
                [variant["id"] for variant in variants if variant["active"]],
                [second.name],
            )

    def test_direct_variant_selection_resets_history_to_the_selected_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            override_dir = Path(temp_dir) / "overrides"
            history = override_dir.parent / "history"
            override_dir.mkdir()
            first = history / "20260901T000000Z"
            second = history / "20260901T000001Z"
            selected = history / "20260901T000002Z"
            for directory in (first, second, selected):
                directory.mkdir(parents=True)
            for directory in (first, second):
                (directory / "edit.json").write_text(json.dumps({
                    "operation": "generation", "layers": ["hair_front"]
                }), encoding="utf-8")
            (selected / "edit.json").write_text(json.dumps({
                "operation": "select-variant",
                "variant_history": {"hair_front": first.name},
            }), encoding="utf-8")
            self.assertEqual(
                generation_undo_snapshots(override_dir, ["hair_front"])["hair_front"],
                first,
            )
            self.assertEqual(generation_redo_snapshots(override_dir, ["hair_front"]), {})


class GeminiLayerPromptTests(unittest.TestCase):
    def test_prompt_requests_a_new_chroma_derived_mask_without_zooming(self):
        prompt = build_layer_edit_prompt(
            "Legwear Left Upper",
            "Add cleaner armor panel lines and make the surroundings transparent.",
            "#00FF00",
            ["Legwear Right Upper"],
            "balanced",
            True,
            "strict",
        )
        self.assertNotIn("transparent", prompt.casefold())
        self.assertIn("proximal attachment edge pixel-accurate", prompt)
        self.assertIn("will become the new layer mask", prompt)
        self.assertIn("Do not zoom or recenter", prompt)
        self.assertNotIn("silhouette footprint", prompt)
        self.assertIn("#00FF00", prompt)

    def test_exact_mask_prompt_remains_available_as_an_opt_in(self):
        prompt = build_layer_edit_prompt(
            "Hair Front",
            "Recolor the hair red.",
            "#00FF00",
            ["Hair Back"],
            "balanced",
            False,
            "strict",
            True,
        )
        self.assertIn("pixel coordinates", prompt)
        self.assertIn("Repaint strictly inside the target layer's existing boundary", prompt)
        self.assertIn("#00FF00", prompt)


@unittest.skipIf(Image is None, "Pillow is available in .venv-avatar only")
class LayerImageRoundTripTests(unittest.TestCase):
    def _layer(self):
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 8, 43, 54), fill=(210, 80, 120, 255))
        return image

    def test_chroma_is_far_from_the_visible_palette(self):
        key = choose_chroma_key([self._layer()])
        source = (210, 80, 120)
        self.assertGreater(sum((a - b) ** 2 for a, b in zip(key, source)), 30_000)

    def test_alpha_digest_allows_recolors_but_rejects_silhouette_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = self._layer()
            recolored = Image.new("RGBA", original.size, (30, 90, 220, 255))
            recolored.putalpha(original.getchannel("A"))
            changed = self._layer()
            ImageDraw.Draw(changed).ellipse((4, 4, 18, 18), fill=(20, 80, 220, 255))
            paths = [root / name for name in ("original.png", "recolored.png", "changed.png")]
            for image, path in zip((original, recolored, changed), paths):
                image.save(path)
            self.assertEqual(_png_alpha_digest(paths[0]), _png_alpha_digest(paths[1]))
            self.assertNotEqual(_png_alpha_digest(paths[0]), _png_alpha_digest(paths[2]))

    def test_mesh_coverage_accepts_known_silhouette_but_rejects_pixels_outside_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            coverage = Image.new("RGBA", (32, 32), (255, 255, 255, 0))
            ImageDraw.Draw(coverage).rectangle((4, 4, 20, 28), fill=(255, 255, 255, 255))
            covered = Image.new("RGBA", (32, 32), (220, 40, 60, 0))
            ImageDraw.Draw(covered).rectangle((10, 6, 18, 25), fill=(220, 40, 60, 255))
            escaped = covered.copy()
            ImageDraw.Draw(escaped).rectangle((23, 8, 29, 20), fill=(220, 40, 60, 255))
            coverage_path = root / "coverage.png"
            covered_path = root / "covered.png"
            escaped_path = root / "escaped.png"
            coverage.save(coverage_path)
            covered.save(covered_path)
            escaped.save(escaped_path)

            self.assertTrue(_png_alpha_is_covered(covered_path, coverage_path))
            self.assertFalse(_png_alpha_is_covered(escaped_path, coverage_path))

    def test_recovery_uses_the_chroma_derived_mask_without_old_bbox_resizing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = self._layer()
            original_path = root / "original.png"
            original.save(original_path)
            generated = Image.new("RGB", original.size, (0, 255, 0))
            ImageDraw.Draw(generated).ellipse((14, 5, 49, 58), fill=(20, 80, 220))
            generated_path = root / "generated.png"
            generated.save(generated_path)
            output_path = root / "output.png"
            result = recover_result(
                generated_path, original_path, output_path, "#00FF00", "strict"
            )
            output = Image.open(output_path).convert("RGBA")
            output_bbox = output.getchannel("A").getbbox()
            original_bbox = original.getchannel("A").getbbox()
            self.assertLess(output_bbox[0], original_bbox[0])
            self.assertGreater(output_bbox[2], original_bbox[2])
            self.assertGreater(output_bbox[3], original_bbox[3])
            self.assertEqual(output.getpixel((30, 8)), original.getpixel((30, 8)))
            self.assertGreaterEqual(result["attachment_band_px"], 2)
            self.assertEqual(result["registration"]["anchor"], "chroma-mask-canvas")

    def test_exact_silhouette_mode_restores_original_alpha_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = self._layer()
            original_path = root / "original.png"
            original.save(original_path)
            generated = Image.new("RGB", original.size, (0, 255, 0))
            ImageDraw.Draw(generated).ellipse((8, 4, 55, 60), fill=(190, 20, 40))
            generated_path = root / "generated.png"
            generated.save(generated_path)
            output_path = root / "output.png"
            result = recover_result(
                generated_path,
                original_path,
                output_path,
                "#00FF00",
                "strict",
                True,
            )
            output = Image.open(output_path).convert("RGBA")
            self.assertEqual(
                output.getchannel("A").tobytes(),
                original.getchannel("A").tobytes(),
            )
            self.assertEqual(result["registration"]["anchor"], "exact-original-mask")

    def test_chroma_gradient_is_removed_from_the_border_connected_background(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = self._layer()
            original_path = root / "original.png"
            original.save(original_path)
            generated = Image.new("RGB", (64, 64))
            pixels = generated.load()
            for y in range(64):
                for x in range(64):
                    pixels[x, y] = (10 + x // 4, 220 + y // 3, 8 + x // 6)
            ImageDraw.Draw(generated).rectangle((27, 3, 36, 61), fill=(80, 40, 170))
            generated_path = root / "generated.png"
            generated.save(generated_path)
            output_path = root / "output.png"
            recover_result(generated_path, original_path, output_path, "#00FF00", "strict")
            output = Image.open(output_path).convert("RGBA")
            self.assertEqual(output.getpixel((0, 0))[3], 0)
            self.assertGreater(output.getpixel((30, 30))[3], 200)

    def test_chroma_is_removed_from_an_enclosed_hole(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = self._layer()
            original_path = root / "original.png"
            original.save(original_path)
            generated = Image.new("RGB", original.size, (255, 255, 0))
            draw = ImageDraw.Draw(generated)
            draw.ellipse((8, 4, 55, 60), fill=(80, 30, 170))
            draw.ellipse((24, 20, 39, 43), fill=(255, 255, 0))
            generated_path = root / "generated.png"
            generated.save(generated_path)
            output_path = root / "output.png"

            recover_result(generated_path, original_path, output_path, "#FFFF00", "strict")
            output = Image.open(output_path).convert("RGBA")
            self.assertLess(output.getpixel((31, 31))[3], 8)
            self.assertGreater(output.getpixel((16, 31))[3], 200)

    def test_noisy_chroma_is_removed_cleanly_from_an_enclosed_hole(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = self._layer()
            original_path = root / "original.png"
            original.save(original_path)
            generated = Image.new("RGB", original.size, (255, 248, 8))
            draw = ImageDraw.Draw(generated)
            draw.ellipse((7, 3, 56, 61), fill=(70, 35, 165))
            draw.ellipse((21, 17, 42, 46), fill=(190, 190, 90))
            # Saving as JPEG reproduces the ringing and color variation returned by Gemini.
            generated_path = root / "generated.jpg"
            generated.save(generated_path, quality=82)
            output_path = root / "output.png"

            recover_result(generated_path, original_path, output_path, "#FFFF00", "strict")
            alpha = Image.open(output_path).convert("RGBA").getchannel("A")
            self.assertLess(alpha.crop((27, 24, 37, 39)).getextrema()[1], 8)
            self.assertLess(alpha.crop((0, 0, 5, 64)).getextrema()[1], 8)
            self.assertGreater(alpha.getpixel((13, 32)), 200)

    def test_prepare_uses_a_cropped_local_character_reference(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layer = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
            ImageDraw.Draw(layer).rectangle((104, 70, 128, 205), fill=(210, 80, 120, 255))
            layer_path = root / "layer.png"
            layer.save(layer_path)
            reference = Image.new("RGB", layer.size, (40, 50, 60))
            reference_path = root / "reference.jpg"
            reference.save(reference_path)
            result = prepare_request([layer_path], root / "prepared", reference_path)
            with Image.open(result["reference"]) as context:
                self.assertLess(context.width, reference.width)
                self.assertLessEqual(context.height, reference.height)
            self.assertEqual(len(result["reference_bbox"]), 4)

    def test_recovery_rejects_a_full_canvas_character_for_a_small_layer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = self._layer()
            original_path = root / "original.png"
            original.save(original_path)
            generated = Image.new("RGB", original.size, (0, 255, 0))
            ImageDraw.Draw(generated).rectangle((1, 1, 62, 62), fill=(60, 80, 180))
            generated_path = root / "generated.png"
            generated.save(generated_path)
            with self.assertRaisesRegex(ValueError, "full-canvas character or scene"):
                recover_result(
                    generated_path,
                    original_path,
                    root / "output.png",
                    "#00FF00",
                    "strict",
                )

    def test_mirror_fallback_uses_valid_counterpart_and_target_attachment_seam(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(source).rectangle((42, 8, 50, 54), fill=(40, 90, 220, 255))
            source_path = root / "source.png"
            source.save(source_path)
            original = Image.new("RGBA", source.size, (0, 0, 0, 0))
            ImageDraw.Draw(original).rectangle((13, 8, 21, 54), fill=(220, 80, 50, 255))
            original_path = root / "original.png"
            original.save(original_path)
            output_path = root / "mirrored.png"
            result = mirror_result(source_path, original_path, output_path, "strict")
            output = Image.open(output_path).convert("RGBA")
            self.assertEqual(result["fallback"], "mirrored-related-layer")
            self.assertEqual(output.getpixel((16, 8)), original.getpixel((16, 8)))
            self.assertGreater(output.getpixel((16, 30))[3], 200)

    def test_overrides_require_an_existing_same_canvas_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layer_dir = root / "layers"
            override_dir = root / "overrides"
            layer_dir.mkdir()
            override_dir.mkdir()
            self._layer().save(layer_dir / "arm_l.png")
            replacement = self._layer()
            replacement.putpixel((30, 30), (10, 20, 30, 255))
            replacement.save(override_dir / "arm_l.png")
            self.assertEqual(apply_overrides(layer_dir, override_dir), ["arm_l"])
            self.assertEqual(Image.open(layer_dir / "arm_l.png").getpixel((30, 30)), (10, 20, 30, 255))

    def test_unique_drawable_override_replaces_original_instead_of_compositing_both(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layer_dir = root / "layers"
            drawable_dir = root / "drawables"
            override_dir = root / "overrides"
            for directory in (layer_dir, drawable_dir, override_dir):
                directory.mkdir()
            original = Image.new("RGBA", (40, 24), (0, 0, 0, 0))
            ImageDraw.Draw(original).rectangle((2, 3, 12, 20), fill=(220, 40, 60, 255))
            original.save(layer_dir / "arm.png")
            original.save(drawable_dir / "arm.png")
            replacement = Image.new("RGBA", original.size, (0, 0, 0, 0))
            ImageDraw.Draw(replacement).rectangle((24, 3, 31, 20), fill=(40, 80, 220, 255))
            replacement.save(override_dir / "arm.png")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "parts": {"arm": {"source_file": "arm.png"}}
            }), encoding="utf-8")

            apply_overrides(
                layer_dir,
                override_dir,
                manifest_path=manifest,
                drawable_dir=drawable_dir,
            )
            result = Image.open(layer_dir / "arm.png").convert("RGBA")
            self.assertEqual(result.getpixel((6, 10))[3], 0)
            self.assertEqual(result.getpixel((27, 10)), (40, 80, 220, 255))

    def test_drawable_override_leaves_the_opted_out_half_of_a_shared_source_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layer_dir = root / "layers"
            drawable_dir = root / "drawables"
            override_dir = root / "overrides"
            for directory in (layer_dir, drawable_dir, override_dir):
                directory.mkdir()
            shared = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
            draw = ImageDraw.Draw(shared)
            draw.rectangle((2, 2, 17, 17), fill=(220, 30, 40, 255))
            draw.rectangle((22, 2, 37, 17), fill=(30, 80, 220, 255))
            shared.save(layer_dir / "footwear.png")
            left = Image.new("RGBA", shared.size, (0, 0, 0, 0))
            left.alpha_composite(shared.crop((0, 0, 20, 20)), (0, 0))
            left.save(drawable_dir / "footwear_l.png")
            replacement = Image.new("RGBA", shared.size, (0, 0, 0, 0))
            ImageDraw.Draw(replacement).rectangle((2, 2, 17, 17), fill=(20, 210, 90, 255))
            replacement.save(override_dir / "footwear_l.png")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "parts": {
                    "footwear_l": {"source_file": "footwear.png"},
                    "footwear_r": {"source_file": "footwear.png"},
                }
            }), encoding="utf-8")

            apply_overrides(
                layer_dir,
                override_dir,
                manifest_path=manifest,
                drawable_dir=drawable_dir,
            )
            result = Image.open(layer_dir / "footwear.png").convert("RGBA")
            self.assertEqual(result.getpixel((8, 8)), (20, 210, 90, 255))
            self.assertEqual(result.getpixel((30, 8)), (30, 80, 220, 255))

    def test_drawable_override_applies_saved_whole_pixel_offset_non_destructively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layer_dir = root / "layers"
            drawable_dir = root / "drawables"
            override_dir = root / "overrides"
            for directory in (layer_dir, drawable_dir, override_dir):
                directory.mkdir()
            original = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
            ImageDraw.Draw(original).rectangle((5, 5, 12, 20), fill=(220, 30, 40, 255))
            original.save(layer_dir / "arm.png")
            original.save(drawable_dir / "arm_l.png")
            original.save(override_dir / "arm_l.png")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "parts": {"arm_l": {"source_file": "arm.png"}}
            }), encoding="utf-8")

            apply_overrides(
                layer_dir,
                override_dir,
                manifest_path=manifest,
                drawable_dir=drawable_dir,
                offsets={"arm_l": {"x": 4, "y": 3}},
            )
            result = Image.open(layer_dir / "arm.png").convert("RGBA")
            self.assertEqual(result.getpixel((6, 6))[3], 0)
            self.assertEqual(result.getpixel((10, 10)), (220, 30, 40, 255))

    def test_targeted_job_stages_related_drawables_and_persists_only_after_rig_passes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layer_dir = root / "rig-layers"
            drawable_dir = root / "rig-drawable-layers"
            live2d_dir = root / "live2d"
            for directory in (layer_dir, drawable_dir, live2d_dir):
                directory.mkdir()
            source = self._layer()
            source.save(layer_dir / "footwear.png")
            source.save(drawable_dir / "footwear_l.png")
            source.save(drawable_dir / "footwear_r.png")
            reference = root / "source.jpg"
            source.convert("RGB").save(reference)
            psd = root / "source.psd"
            psd.touch()
            model3 = live2d_dir / "avatar.model3.json"
            model3.write_text("{}", encoding="utf-8")
            override_dir = root / "layer-regeneration" / "overrides"
            baseline_dir = root / "layer-regeneration" / "baseline"
            job_id = "layer-edit-test"
            JOBS[job_id] = {
                "id": job_id,
                "avatar_id": "gen-test",
                "layer_id": "footwear_l",
                "instruction": "Clean up the armor panels.",
                "include_related": True,
                "preserve_colors": True,
                "change_amount": "balanced",
                "attachment_lock": "strict",
                "work_dir": str(root / "job"),
                "phase": "queued",
            }
            catalog = [
                {"id": "footwear_l", "editable_file": "footwear_l.png", "related": ["footwear_r"]},
                {"id": "footwear_r", "editable_file": "footwear_r.png", "related": ["footwear_l"]},
            ]

            def fake_run(command, *, cwd):
                if "layer_regeneration.py" in " ".join(command) and "prepare" in command:
                    output = Path(command[command.index("--output") + 1])
                    output.mkdir(parents=True)
                    prepared = []
                    values = [command[index + 1] for index, value in enumerate(command) if value == "--layer"]
                    for index, value in enumerate(values):
                        path = output / f"input-{index}.png"
                        shutil.copy2(value, path)
                        prepared.append(str(path))
                    context = output / "reference-context.jpg"
                    shutil.copy2(reference, context)
                    return json.dumps({
                        "chroma": "#00FF00",
                        "prepared": prepared,
                        "reference": str(context),
                    })
                if "layer_regeneration.py" in " ".join(command) and "recover" in command:
                    original = Path(command[command.index("--original") + 1])
                    output = Path(command[command.index("--output") + 1])
                    shutil.copy2(original, output)
                    return json.dumps({"output": str(output), "attachment_band_px": 4})
                model3.write_text("{}", encoding="utf-8")
                return json.dumps({"model3": str(model3), "qa_passed": True, "layer_overrides": [
                    "footwear_l", "footwear_r"
                ]})

            with (
                patch("tools.serve.generated_avatar_by_id", return_value={"id": "gen-test", "model3": str(model3)}),
                patch("tools.serve.hallway_settings", return_value={"GEMINI_API_KEY": "configured"}),
                patch("tools.serve.avatar_layer_regeneration_paths", return_value=(psd, live2d_dir, "avatar")),
                patch("tools.serve.avatar_layer_paths", return_value=(layer_dir, override_dir, baseline_dir, reference)),
                patch("tools.serve.available_avatar_layers", return_value=catalog),
                patch("tools.serve.generate_layer_image", return_value=(b"image", "image/png", "gemini-test")),
                patch("tools.serve._run_checked", side_effect=fake_run),
                patch("tools.serve.register_avatar") as register,
            ):
                run_specific_layer_job(job_id)

            self.assertEqual(JOBS[job_id]["phase"], "complete")
            self.assertTrue((override_dir / "footwear_l.png").is_file())
            self.assertTrue((override_dir / "footwear_r.png").is_file())
            archived_results = list((override_dir.parent / "history").glob("*/results/*.png"))
            self.assertEqual(
                {path.name for path in archived_results},
                {"footwear_l.png", "footwear_r.png"},
            )
            register.assert_called_once()
            JOBS.pop(job_id, None)

    def test_targeted_same_alpha_generation_applies_texture_without_rig_rebuild(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layer_dir = root / "rig-layers"
            drawable_dir = root / "rig-drawable-layers"
            live2d_dir = root / "live2d"
            texture_dir = live2d_dir / "textures"
            override_dir = root / "layer-regeneration" / "overrides"
            baseline_dir = root / "layer-regeneration" / "baseline"
            metadata_path = root / "layer-regeneration" / "metadata.json"
            for directory in (layer_dir, drawable_dir, texture_dir):
                directory.mkdir(parents=True)
            source = self._layer()
            source.save(layer_dir / "hair_front.png")
            source.save(drawable_dir / "hair_front.png")
            texture_path = texture_dir / "000_tex_hair_front.png"
            source.save(texture_path)
            reference = root / "source.jpg"
            source.convert("RGB").save(reference)
            psd = root / "source.psd"
            psd.touch()
            model3 = live2d_dir / "avatar.model3.json"
            model3.write_text(json.dumps({
                "FileReferences": {"Textures": ["textures/000_tex_hair_front.png"]}
            }), encoding="utf-8")
            avatar = {
                "id": "gen-test",
                "model3": str(model3),
                "qa_passed": True,
            }
            job_id = "layer-edit-texture-only-test"
            JOBS[job_id] = {
                "id": job_id,
                "avatar_id": "gen-test",
                "layer_id": "hair_front",
                "instruction": "Make the hair bright red.",
                "include_related": False,
                "preserve_colors": False,
                "change_amount": "balanced",
                "attachment_lock": "strict",
                "work_dir": str(root / "job"),
                "phase": "queued",
            }
            catalog = [{
                "id": "hair_front",
                "editable_file": "hair_front.png",
                "related": [],
            }]
            commands = []

            def fake_run(command, *, cwd):
                commands.append(command)
                if "prepare" in command:
                    output = Path(command[command.index("--output") + 1])
                    output.mkdir(parents=True)
                    prepared = output / "input-0.png"
                    shutil.copy2(command[command.index("--layer") + 1], prepared)
                    context = output / "reference-context.jpg"
                    shutil.copy2(reference, context)
                    return json.dumps({
                        "chroma": "#00FF00",
                        "prepared": [str(prepared)],
                        "reference": str(context),
                    })
                if "recover" in command:
                    original = Image.open(command[command.index("--original") + 1]).convert("RGBA")
                    replacement = Image.new("RGBA", original.size, (220, 25, 45, 255))
                    replacement.putalpha(original.getchannel("A"))
                    output = Path(command[command.index("--output") + 1])
                    replacement.save(output)
                    return json.dumps({"output": str(output), "attachment_band_px": 4})
                raise AssertionError("The Live2D rig command must not run for a same-alpha generation.")

            with (
                patch("tools.serve.generated_avatar_by_id", return_value=avatar),
                patch("tools.serve.hallway_settings", return_value={"GEMINI_API_KEY": "configured"}),
                patch("tools.serve.avatar_layer_regeneration_paths", return_value=(psd, live2d_dir, "avatar")),
                patch("tools.serve.avatar_layer_paths", return_value=(layer_dir, override_dir, baseline_dir, reference)),
                patch("tools.serve.layer_edit_metadata_path", return_value=metadata_path),
                patch("tools.serve.available_avatar_layers", return_value=catalog),
                patch("tools.serve.generate_layer_image", return_value=(b"image", "image/png", "gemini-test")),
                patch("tools.serve._run_checked", side_effect=fake_run),
                patch("tools.serve.register_avatar") as register,
            ):
                run_specific_layer_job(job_id)

            self.assertEqual(JOBS[job_id]["phase"], "complete")
            self.assertTrue(JOBS[job_id]["texture_only"])
            self.assertTrue(JOBS[job_id]["variant_id"])
            self.assertFalse(any("rig_avatar.py" in " ".join(command) for command in commands))
            self.assertEqual(
                texture_path.read_bytes(),
                (override_dir / "hair_front.png").read_bytes(),
            )
            register.assert_called_once()
            JOBS.pop(job_id, None)

    def test_offset_is_saved_non_destructively_and_revert_removes_the_active_override(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layer_dir = root / "rig-layers"
            drawable_dir = root / "rig-drawable-layers"
            live2d_dir = root / "live2d"
            override_dir = root / "layer-regeneration" / "overrides"
            baseline_dir = root / "layer-regeneration" / "baseline"
            metadata_path = root / "layer-regeneration" / "metadata.json"
            for directory in (layer_dir, drawable_dir, live2d_dir, override_dir):
                directory.mkdir(parents=True)
            source = self._layer()
            source.save(layer_dir / "arm_l.png")
            source.save(drawable_dir / "arm_l.png")
            source.save(override_dir / "arm_l.png")
            reference = root / "source.jpg"
            source.convert("RGB").save(reference)
            psd = root / "source.psd"
            psd.touch()
            model3 = live2d_dir / "avatar.model3.json"
            model3.write_text("{}", encoding="utf-8")
            avatar = {"id": "gen-test", "model3": str(model3)}
            catalog = [{
                "id": "arm_l",
                "editable_file": "arm_l.png",
                "related": [],
                "can_revert": True,
            }]

            def fake_run(command, *, cwd):
                model3.write_text("{}", encoding="utf-8")
                overrides = [] if not any(Path(value).name == "arm_l.png" for value in command) else ["arm_l"]
                return json.dumps({"model3": str(model3), "qa_passed": True, "layer_overrides": overrides})

            common_patches = (
                patch("tools.serve.generated_avatar_by_id", return_value=avatar),
                patch("tools.serve.avatar_layer_regeneration_paths", return_value=(psd, live2d_dir, "avatar")),
                patch("tools.serve.avatar_layer_paths", return_value=(layer_dir, override_dir, baseline_dir, reference)),
                patch("tools.serve.layer_edit_metadata_path", return_value=metadata_path),
                patch("tools.serve.available_avatar_layers", return_value=catalog),
                patch("tools.serve._run_checked", side_effect=fake_run),
                patch("tools.serve.register_avatar"),
            )
            offset_job = "layer-offset-test"
            JOBS[offset_job] = {
                "id": offset_job,
                "avatar_id": "gen-test",
                "layer_id": "arm_l",
                "include_related": False,
                "offset_x": 7,
                "offset_y": -3,
                "work_dir": str(root / "offset-job"),
                "phase": "queued",
            }
            with common_patches[0], common_patches[1], common_patches[2], common_patches[3], common_patches[4], common_patches[5], common_patches[6]:
                run_layer_offset_job(offset_job)
            self.assertEqual(JOBS[offset_job]["phase"], "complete")
            self.assertEqual(
                json.loads(metadata_path.read_text(encoding="utf-8"))["offsets"]["arm_l"],
                {"x": 7, "y": -3},
            )

            revert_job = "layer-revert-test"
            JOBS[revert_job] = {
                "id": revert_job,
                "avatar_id": "gen-test",
                "layer_id": "arm_l",
                "include_related": False,
                "work_dir": str(root / "revert-job"),
                "phase": "queued",
            }
            with (
                patch("tools.serve.generated_avatar_by_id", return_value=avatar),
                patch("tools.serve.avatar_layer_regeneration_paths", return_value=(psd, live2d_dir, "avatar")),
                patch("tools.serve.avatar_layer_paths", return_value=(layer_dir, override_dir, baseline_dir, reference)),
                patch("tools.serve.layer_edit_metadata_path", return_value=metadata_path),
                patch("tools.serve.available_avatar_layers", return_value=catalog),
                patch("tools.serve._run_checked", side_effect=fake_run),
                patch("tools.serve.register_avatar"),
            ):
                run_layer_revert_job(revert_job)
            self.assertEqual(JOBS[revert_job]["phase"], "complete")
            self.assertFalse((override_dir / "arm_l.png").exists())
            self.assertNotIn(
                "arm_l", json.loads(metadata_path.read_text(encoding="utf-8"))["offsets"]
            )
            JOBS.pop(offset_job, None)
            JOBS.pop(revert_job, None)

    def test_generation_undo_restores_the_pre_generation_baseline_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layer_dir = root / "rig-layers"
            live2d_dir = root / "live2d"
            override_dir = root / "layer-regeneration" / "overrides"
            baseline_dir = root / "layer-regeneration" / "baseline"
            metadata_path = root / "layer-regeneration" / "metadata.json"
            history_dir = override_dir.parent / "history" / "20260902T000000Z"
            for directory in (layer_dir, live2d_dir, override_dir, baseline_dir, history_dir):
                directory.mkdir(parents=True)
            source = self._layer()
            source.save(layer_dir / "hair_front.png")
            source.save(override_dir / "hair_front.png")
            (history_dir / "edit.json").write_text(
                json.dumps({"operation": "generation", "layers": ["hair_front"]}),
                encoding="utf-8",
            )
            reference = root / "source.jpg"
            source.convert("RGB").save(reference)
            psd = root / "source.psd"
            psd.touch()
            model3 = live2d_dir / "avatar.model3.json"
            model3.write_text("{}", encoding="utf-8")
            avatar = {"id": "gen-test", "model3": str(model3)}
            catalog = [{"id": "hair_front", "related": [], "can_undo_generation": True}]
            job_id = "layer-undo-generation-test"
            JOBS[job_id] = {
                "id": job_id,
                "avatar_id": "gen-test",
                "layer_id": "hair_front",
                "include_related": True,
                "work_dir": str(root / "undo-job"),
                "phase": "queued",
            }

            with (
                patch("tools.serve.generated_avatar_by_id", return_value=avatar),
                patch("tools.serve.avatar_layer_regeneration_paths", return_value=(psd, live2d_dir, "avatar")),
                patch("tools.serve.avatar_layer_paths", return_value=(layer_dir, override_dir, baseline_dir, reference)),
                patch("tools.serve.layer_edit_metadata_path", return_value=metadata_path),
                patch("tools.serve.available_avatar_layers", return_value=catalog),
                patch("tools.serve._run_checked", return_value=json.dumps({
                    "model3": str(model3), "qa_passed": True, "layer_overrides": []
                })),
                patch("tools.serve.register_avatar"),
            ):
                run_layer_undo_generation_job(job_id)

            self.assertEqual(JOBS[job_id]["phase"], "complete")
            self.assertFalse((override_dir / "hair_front.png").exists())
            undo_edits = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in (override_dir.parent / "history").glob("*/edit.json")
            ]
            undo = next(edit for edit in undo_edits if edit.get("operation") == "undo-generation")
            self.assertEqual(undo["source_history"]["hair_front"], history_dir.name)
            self.assertEqual(generation_undo_snapshots(override_dir, ["hair_front"]), {})
            redo_snapshots = generation_redo_snapshots(override_dir, ["hair_front"])
            self.assertIn("hair_front", redo_snapshots)

            redo_job_id = "layer-redo-generation-test"
            JOBS[redo_job_id] = {
                "id": redo_job_id,
                "avatar_id": "gen-test",
                "layer_id": "hair_front",
                "include_related": True,
                "work_dir": str(root / "redo-job"),
                "phase": "queued",
            }
            with (
                patch("tools.serve.generated_avatar_by_id", return_value=avatar),
                patch("tools.serve.avatar_layer_regeneration_paths", return_value=(psd, live2d_dir, "avatar")),
                patch("tools.serve.avatar_layer_paths", return_value=(layer_dir, override_dir, baseline_dir, reference)),
                patch("tools.serve.layer_edit_metadata_path", return_value=metadata_path),
                patch("tools.serve.available_avatar_layers", return_value=catalog),
                patch("tools.serve._run_checked", return_value=json.dumps({
                    "model3": str(model3), "qa_passed": True, "layer_overrides": ["hair_front"]
                })),
                patch("tools.serve.register_avatar"),
            ):
                run_layer_redo_generation_job(redo_job_id)

            self.assertEqual(JOBS[redo_job_id]["phase"], "complete")
            self.assertTrue((override_dir / "hair_front.png").is_file())
            self.assertIn("hair_front", generation_undo_snapshots(override_dir, ["hair_front"]))
            self.assertEqual(generation_redo_snapshots(override_dir, ["hair_front"]), {})
            JOBS.pop(job_id, None)
            JOBS.pop(redo_job_id, None)

    def test_select_variant_updates_grouped_counterparts_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layer_dir = root / "rig-layers"
            live2d_dir = root / "live2d"
            override_dir = root / "layer-regeneration" / "overrides"
            baseline_dir = root / "layer-regeneration" / "baseline"
            metadata_path = root / "layer-regeneration" / "metadata.json"
            for directory in (layer_dir, live2d_dir, override_dir, baseline_dir):
                directory.mkdir(parents=True)
            (override_dir / "hair_front.png").write_bytes(b"current")
            (override_dir / "hair_back.png").write_bytes(b"current-back")
            selected_front = root / "selected-front.png"
            selected_back = root / "selected-back.png"
            selected_front.write_bytes(b"older-generated-result")
            selected_back.write_bytes(b"older-generated-back")
            psd = root / "source.psd"
            psd.touch()
            reference = root / "source.jpg"
            reference.touch()
            model3 = live2d_dir / "avatar.model3.json"
            model3.write_text("{}", encoding="utf-8")
            avatar = {"id": "gen-test", "model3": str(model3)}
            job_id = "layer-select-variant-test"
            JOBS[job_id] = {
                "id": job_id,
                "avatar_id": "gen-test",
                "layer_id": "hair_front",
                "variant_id": "20260901T000000Z",
                "include_related": True,
                "work_dir": str(root / "select-job"),
                "phase": "queued",
            }
            catalog = [
                {
                    "id": "hair_front",
                    "related": ["hair_back"],
                    "variants": [{"id": "20260901T000000Z", "active": False}],
                },
                {
                    "id": "hair_back",
                    "related": ["hair_front"],
                    "variants": [{"id": "20260901T000000Z", "active": False}],
                },
            ]

            with (
                patch("tools.serve.generated_avatar_by_id", return_value=avatar),
                patch("tools.serve.avatar_layer_regeneration_paths", return_value=(psd, live2d_dir, "avatar")),
                patch("tools.serve.avatar_layer_paths", return_value=(layer_dir, override_dir, baseline_dir, reference)),
                patch("tools.serve.layer_edit_metadata_path", return_value=metadata_path),
                patch("tools.serve.available_avatar_layers", return_value=catalog),
                patch(
                    "tools.serve.layer_variant_path",
                    side_effect=lambda _avatar, layer_id, _variant_id: (
                        selected_front if layer_id == "hair_front" else selected_back
                    ),
                ),
                patch("tools.serve._run_checked", return_value=json.dumps({
                    "model3": str(model3), "qa_passed": True, "layer_overrides": ["hair_front"]
                })),
                patch("tools.serve.register_avatar"),
            ):
                run_layer_select_variant_job(job_id)

            self.assertEqual(JOBS[job_id]["phase"], "complete")
            self.assertEqual(
                (override_dir / "hair_front.png").read_bytes(),
                b"older-generated-result",
            )
            self.assertEqual(
                (override_dir / "hair_back.png").read_bytes(),
                b"older-generated-back",
            )
            operations = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in (override_dir.parent / "history").glob("*/edit.json")
            ]
            selection = next(
                operation for operation in operations
                if operation.get("operation") == "select-variant"
            )
            self.assertEqual(
                selection["variant_history"],
                {
                    "hair_front": "20260901T000000Z",
                    "hair_back": "20260901T000000Z",
                },
            )
            JOBS.pop(job_id, None)

    def test_same_alpha_variant_swaps_texture_without_running_the_rig(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layer_dir = root / "rig-layers"
            live2d_dir = root / "live2d"
            texture_dir = live2d_dir / "textures"
            override_dir = root / "layer-regeneration" / "overrides"
            baseline_dir = root / "layer-regeneration" / "baseline"
            metadata_path = root / "layer-regeneration" / "metadata.json"
            for directory in (layer_dir, texture_dir, override_dir, baseline_dir):
                directory.mkdir(parents=True)
            current = self._layer()
            selected = Image.new("RGBA", current.size, (25, 80, 220, 255))
            selected.putalpha(current.getchannel("A"))
            current.save(override_dir / "hair_front.png")
            selected_path = root / "selected.png"
            selected.save(selected_path)
            texture_path = texture_dir / "000_tex_hair_front.png"
            current.save(texture_path)
            model3 = live2d_dir / "avatar.model3.json"
            model3.write_text(json.dumps({
                "FileReferences": {"Textures": ["textures/000_tex_hair_front.png?v=1"]}
            }), encoding="utf-8")
            psd = root / "source.psd"
            psd.touch()
            reference = root / "source.jpg"
            reference.touch()
            avatar = {"id": "gen-test", "model3": str(model3), "qa_passed": True}
            catalog = [{
                "id": "hair_front",
                "related": [],
                "variants": [{
                    "id": "20260901T000000Z", "active": False, "texture_only": True
                }],
            }]
            job_id = "layer-select-texture-only-test"
            JOBS[job_id] = {
                "id": job_id,
                "avatar_id": "gen-test",
                "layer_id": "hair_front",
                "variant_id": "20260901T000000Z",
                "include_related": False,
                "work_dir": str(root / "select-job"),
                "phase": "queued",
            }
            with (
                patch("tools.serve.generated_avatar_by_id", return_value=avatar),
                patch("tools.serve.avatar_layer_regeneration_paths", return_value=(psd, live2d_dir, "avatar")),
                patch("tools.serve.avatar_layer_paths", return_value=(layer_dir, override_dir, baseline_dir, reference)),
                patch("tools.serve.layer_edit_metadata_path", return_value=metadata_path),
                patch("tools.serve.available_avatar_layers", return_value=catalog),
                patch("tools.serve.layer_variant_path", return_value=selected_path),
                patch("tools.serve._run_checked") as run_checked,
                patch("tools.serve.register_avatar"),
            ):
                run_layer_select_variant_job(job_id)

            run_checked.assert_not_called()
            self.assertEqual(JOBS[job_id]["phase"], "complete")
            self.assertTrue(JOBS[job_id]["texture_only"])
            self.assertEqual(texture_path.read_bytes(), selected_path.read_bytes())
            self.assertEqual(
                (override_dir / "hair_front.png").read_bytes(), selected_path.read_bytes()
            )
            JOBS.pop(job_id, None)


if __name__ == "__main__":
    unittest.main()
