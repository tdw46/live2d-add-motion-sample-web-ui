#!/usr/bin/env python3
"""Model setup: copy a model (folder or zip) into models/ as the working copy
and register it in model.config.json. The WebUI and all tools read that config.

Usage:
  python3 tools/setup_model.py                  # auto-detect under local-assets/
  python3 tools/setup_model.py <folder|zip>     # use a model at any location

When a zip is given, it is extracted into local-assets/models/ first.
"""
import glob
import json
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL = os.path.join(ROOT, "local-assets")
MODELS = os.path.join(ROOT, "models")
CONFIG = os.path.join(ROOT, "model.config.json")


def find_model3(base):
    return sorted(glob.glob(os.path.join(base, "**", "*.model3.json"), recursive=True))


def main():
    src = os.path.expanduser(sys.argv[1]) if len(sys.argv) > 1 else None

    if src and src.lower().endswith(".zip"):
        name = os.path.splitext(os.path.basename(src))[0]
        dest = os.path.join(LOCAL, "models", name)
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest, exist_ok=True)
        with zipfile.ZipFile(src) as z:
            z.extractall(dest)
        print(f"unzipped: {src} -> {dest}")
        src = dest

    search_base = src or LOCAL
    if not os.path.isdir(search_base):
        sys.exit(f"ERROR: {search_base} がありません。モデルのフォルダかzipのパスを指定してください。")

    candidates = find_model3(search_base)
    # Never treat models/ (the working copy) as a source
    candidates = [c for c in candidates
                  if not os.path.abspath(c).startswith(os.path.abspath(MODELS) + os.sep)]
    if not candidates:
        sys.exit(f"ERROR: {search_base} に *.model3.json が見つかりません。\n"
                 f"モデル(runtimeフォルダを含む)を local-assets/ に置くか、パスを引数で指定してください。")
    if len(candidates) > 1:
        listing = "\n".join(f"  - {c}" for c in candidates)
        sys.exit(f"ERROR: モデルが複数見つかりました。使うモデルのフォルダを引数で指定してください:\n{listing}")

    model3 = candidates[0]
    src_dir = os.path.dirname(model3)
    stem = os.path.basename(model3).replace(".model3.json", "")
    target = os.path.join(MODELS, stem)

    shutil.rmtree(target, ignore_errors=True)
    os.makedirs(MODELS, exist_ok=True)
    shutil.copytree(src_dir, target)

    rel_model3 = os.path.relpath(os.path.join(target, os.path.basename(model3)), ROOT)
    with open(CONFIG, "w") as fh:
        json.dump({"name": stem, "model3": rel_model3.replace(os.sep, "/")},
                  fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"copied:     {src_dir} -> {target}")
    print(f"registered: {CONFIG} (model3: {rel_model3})")
    print("next:       python3 tools/analyze_model.py でパラメータを確認")


if __name__ == "__main__":
    main()
