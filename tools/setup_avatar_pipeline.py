#!/usr/bin/env python3
"""Create the local Python 3.12 environment used by avatar generation."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv-avatar"
PYTHON = Path(os.environ.get("LIVE2D_PYTHON312", "/Users/tylerwalker/.local/bin/python3.12"))
UV = shutil.which("uv")


def run(command: list[str], cwd: Path = ROOT) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def interpreter_works(path: Path) -> bool:
    if not path.is_file():
        return False
    return subprocess.run(
        [str(path), "-c", "import sys; print(sys.version_info[:2])"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def main() -> None:
    if not PYTHON.is_file():
        raise SystemExit(f"Python 3.12 was not found at {PYTHON}")
    venv_python = VENV / "bin" / "python"
    if not interpreter_works(venv_python):
        if UV:
            run([UV, "venv", "--python", str(PYTHON), "--clear", str(VENV)])
        else:
            run([str(PYTHON), "-m", "venv", str(VENV)])
    if UV:
        install = [UV, "pip", "install", "--python", str(venv_python)]
    else:
        run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
        install = [str(venv_python), "-m", "pip", "install"]

    run([*install, "torch", "torchvision", "torchaudio"])
    run([*install, "-r", "requirements.txt"], cwd=ROOT / "vendor" / "see-through")
    run(
        [
            *install,
            "-e",
            f"{ROOT / 'vendor' / 'image2live2d'}[decompose,rig,mesh]",
        ]
    )
    assets_link = ROOT / "vendor" / "see-through" / "assets"
    if not assets_link.exists():
        assets_link.symlink_to("common/assets", target_is_directory=True)
    print(f"Avatar pipeline environment ready: {venv_python}")


if __name__ == "__main__":
    main()
