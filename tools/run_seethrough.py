#!/usr/bin/env python3
"""Run the vendored See-through companion with a reproducible profile."""

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SEE_THROUGH = ROOT / "vendor" / "see-through"
INFERENCE_SCRIPT = SEE_THROUGH / "inference" / "scripts" / "inference_psd.py"
DEFAULT_OUTPUT = ROOT / "local-assets" / "see-through-output"

PROFILES = {
    "mps-smoke": [
        "--seed", "42",
        "--resolution", "768",
        "--resolution_depth", "768",
        "--inference_steps", "20",
        "--inference_steps_depth", "10",
    ],
    "community-quality": [
        "--seed", "42",
        "--resolution", "1280",
        "--resolution_depth", "768",
        "--inference_steps", "30",
        "--inference_steps_depth", "10",
    ],
}

DEFAULT_PROFILE = "community-quality"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a layered PSD with the vendored See-through companion"
    )
    parser.add_argument("input", help="Source anime illustration")
    parser.add_argument(
        "--profile",
        choices=PROFILES,
        default=DEFAULT_PROFILE,
        help="community-quality is the default; mps-smoke is the faster diagnostic profile",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved command without starting model inference",
    )
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    if not input_path.exists():
        parser.error(f"input does not exist: {input_path}")
    if not INFERENCE_SCRIPT.exists():
        parser.error(
            "See-through companion is missing; run "
            "git submodule update --init --recursive"
        )

    command = [
        sys.executable,
        str(INFERENCE_SCRIPT),
        "--srcp", str(input_path),
        "--save_dir", str(output_path),
        *PROFILES[args.profile],
        "--tblr_split",
        "--save_to_psd",
    ]
    if args.dry_run:
        print(shlex.join(command))
        return

    output_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(command, cwd=SEE_THROUGH, check=True)


if __name__ == "__main__":
    main()
