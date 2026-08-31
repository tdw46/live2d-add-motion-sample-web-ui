import tempfile
import unittest
from pathlib import Path

from tools.serve import select_semantic_psd


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


if __name__ == "__main__":
    unittest.main()
