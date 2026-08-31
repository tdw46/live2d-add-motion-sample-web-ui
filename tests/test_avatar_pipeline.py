import tempfile
import unittest
from pathlib import Path

from tools.serve import select_semantic_psd, validate_layer_order


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


if __name__ == "__main__":
    unittest.main()
