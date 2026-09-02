import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.rig_avatar import (
    build_variant_mesh_guides,
    repair_incomplete_face,
    restore_stack_display_names,
    version_model_resources,
)
from tools.run_seethrough import DEFAULT_PROFILE, PROFILES
from tools.serve import (
    avatar_layer_regeneration_paths,
    require_rig_qa,
    select_semantic_psd,
    validate_layer_order,
)


class SelectSemanticPsdTests(unittest.TestCase):
    def test_prefers_exact_color_psd_over_depth_psd(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            color = root / "source.psd"
            depth = root / "source_depth.psd"
            color.touch()
            depth.touch()

            self.assertEqual(select_semantic_psd(root, "source"), color)

    def test_uses_single_metadata_backed_semantic_psd(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            color = root / "renamed.psd"
            color.touch()
            Path(f"{color}.json").touch()
            (root / "renamed_depth.psd").touch()

            self.assertEqual(select_semantic_psd(root, "source"), color)

    def test_rejects_depth_only_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "source_depth.psd").touch()

            with self.assertRaisesRegex(RuntimeError, "semantic color-layer PSD"):
                select_semantic_psd(root, "source")


class LayerOrderValidationTests(unittest.TestCase):
    def test_accepts_unique_drawable_ids(self):
        self.assertEqual(
            validate_layer_order(["hair_back", "face", "hair_front"]),
            ["hair_back", "face", "hair_front"],
        )

    def test_rejects_duplicate_drawable_ids(self):
        with self.assertRaisesRegex(ValueError, "Duplicate drawable ID"):
            validate_layer_order(["face", "face"])

    def test_rejects_non_array_layer_order(self):
        with self.assertRaisesRegex(ValueError, "must be an array"):
            validate_layer_order("face")


class ModelResourceVersionTests(unittest.TestCase):
    def test_versions_every_emitted_asset_reference(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            model3 = Path(temp_dir) / "avatar.model3.json"
            model3.write_text(
                json.dumps({
                    "FileReferences": {
                        "Moc": "avatar.moc3",
                        "Textures": ["textures/body.png"],
                        "Physics": "avatar.physics3.json?old=1",
                        "Motions": {"Idle": [{"File": "idle.motion3.json"}]},
                    }
                }),
                encoding="utf-8",
            )

            self.assertEqual(version_model_resources(model3, "build-2"), "build-2")
            refs = json.loads(model3.read_text(encoding="utf-8"))["FileReferences"]
            self.assertEqual(refs["Moc"], "avatar.moc3?v=build-2")
            self.assertEqual(refs["Textures"], ["textures/body.png?v=build-2"])
            self.assertEqual(refs["Physics"], "avatar.physics3.json?v=build-2")
            self.assertEqual(refs["Motions"]["Idle"][0]["File"], "idle.motion3.json?v=build-2")


class LayerDisplayNameTests(unittest.TestCase):
    def test_restores_see_through_names_after_override_reload(self):
        stack = SimpleNamespace(layers=[
            SimpleNamespace(id="00_clothing", display_name=None),
            SimpleNamespace(id="24_clothing", display_name=None),
        ])
        restore_stack_display_names(stack, {
            "00_clothing": "Topwear",
            "24_clothing": "Cape",
        })
        self.assertEqual(
            [layer.display_name for layer in stack.layers],
            ["Topwear", "Cape"],
        )


class VariantMeshGuideTests(unittest.TestCase):
    def test_unions_current_baseline_and_archived_variant_alpha(self):
        from PIL import Image, ImageDraw

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current_dir = root / "rig-layers"
            regeneration = root / "layer-regeneration"
            baseline_dir = regeneration / "baseline"
            history_results = regeneration / "history" / "generation-1" / "results"
            for directory in (current_dir, baseline_dir, history_results):
                directory.mkdir(parents=True)

            def layer(path, box):
                image = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
                ImageDraw.Draw(image).rectangle(box, fill=(220, 40, 60, 255))
                image.save(path)

            current = current_dir / "arm_l.png"
            layer(current, (13, 4, 18, 26))
            layer(baseline_dir / "arm_l.png", (4, 4, 13, 20))
            layer(history_results / "arm_l.png", (18, 4, 27, 20))
            stack = SimpleNamespace(layers=[SimpleNamespace(id="arm_l", texture_path=current)])

            guide_path = build_variant_mesh_guides(stack, regeneration)["arm_l"]
            alpha = Image.open(guide_path).convert("RGBA").getchannel("A")
            self.assertEqual(alpha.getpixel((5, 10)), 255)
            self.assertEqual(alpha.getpixel((15, 24)), 255)
            self.assertEqual(alpha.getpixel((26, 10)), 255)


class FaceRecoveryTests(unittest.TestCase):
    def test_recovers_missing_face_from_head_and_subtracts_separate_features(self):
        from PIL import Image, ImageDraw

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layer_dir = root / "rig-layers"
            source_dir = root / "source"
            layer_dir.mkdir()
            source_dir.mkdir()

            head = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(head).ellipse((14, 8, 50, 56), fill=(60, 180, 220, 255))
            head.save(source_dir / "head.png")

            hair = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(hair).rectangle((10, 4, 54, 18), fill=(180, 20, 40, 255))
            hair.save(layer_dir / "10_hair_front.png")
            eye = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(eye).ellipse((24, 25, 30, 31), fill=(255, 255, 255, 255))
            eye.save(layer_dir / "11_eye_l.png")

            self.assertEqual(repair_incomplete_face(layer_dir, source_dir), "head-output")
            recovered = Image.open(layer_dir / "10_face_base.png").convert("RGBA")
            self.assertEqual(recovered.getpixel((32, 40)), (60, 180, 220, 255))
            self.assertEqual(recovered.getpixel((26, 28))[3], 0)
            self.assertEqual(recovered.getpixel((32, 12))[3], 0)


class AvatarQualityGateTests(unittest.TestCase):
    def test_accepts_passing_rig(self):
        require_rig_qa({"qa_passed": True})

    def test_rejects_failed_rig_with_reasons(self):
        with self.assertRaisesRegex(RuntimeError, "missing_role"):
            require_rig_qa({"qa_passed": False, "qa_reasons": ["lint:missing_role"]})


class SeeThroughProfileTests(unittest.TestCase):
    def test_quality_profile_is_explicit_default(self):
        self.assertEqual(DEFAULT_PROFILE, "community-quality")
        args = PROFILES[DEFAULT_PROFILE]
        self.assertEqual(args[args.index("--resolution") + 1], "1280")
        self.assertEqual(args[args.index("--resolution_depth") + 1], "768")
        self.assertEqual(args[args.index("--inference_steps") + 1], "30")
        self.assertEqual(args[args.index("--inference_steps_depth") + 1], "10")


class LayerRegenerationPathTests(unittest.TestCase):
    def test_resolves_existing_psd_and_model_without_generation_inputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            generated = root / "local-assets" / "generated-avatars"
            avatar_root = generated / "gen-example"
            see_through = avatar_root / "see-through"
            live2d = avatar_root / "live2d"
            see_through.mkdir(parents=True)
            live2d.mkdir()
            psd = see_through / "source.psd"
            model3 = live2d / "avatar_gen_example.model3.json"
            psd.touch()
            model3.write_text("{}", encoding="utf-8")
            avatar = {
                "id": "gen-example",
                "model3": model3.relative_to(root).as_posix(),
                "generated": True,
            }

            with (
                patch("tools.serve.PROJECT_ROOT", root),
                patch("tools.serve.GENERATED_ROOT", generated),
            ):
                self.assertEqual(
                    avatar_layer_regeneration_paths(avatar),
                    (psd.resolve(), live2d.resolve(), "avatar_gen_example"),
                )

    def test_rejects_non_generated_avatar(self):
        with self.assertRaisesRegex(RuntimeError, "Only generated avatars"):
            avatar_layer_regeneration_paths({"id": "hiyori", "model3": "model.json"})


if __name__ == "__main__":
    unittest.main()
