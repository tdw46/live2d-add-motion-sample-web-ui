import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.rig_avatar import version_model_resources
from tools.serve import (
    avatar_layer_regeneration_paths,
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
