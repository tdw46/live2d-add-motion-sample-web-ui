# See-through Apple Silicon companion

This investigation branch vendors See-through as a Git submodule at
`vendor/see-through`. The submodule tracks the isolated `see-through-mps`
branch in `tdw46/hallway_avatar_gen`; that repository's existing `main` branch
and hallway-avatar history are unchanged.

## Why this implementation

The companion starts from the official
[`shitagaki-lab/see-through`](https://github.com/shitagaki-lab/see-through)
`main` branch and carries the focused implementation from
[upstream PR #33](https://github.com/shitagaki-lab/see-through/pull/33).
That patch adds CUDA/MPS/CPU device selection and routes MPS-incompatible 5D
median reductions through CPU.

The patch author reported a successful 23-layer PSD run on an M4 Pro. An
upstream collaborator reported inconsistent Marigold depth output on an M2
Max, so this integration is deliberately labeled experimental and pinned to a
specific commit rather than presented as production-ready Metal support.

See-through generates a semantically separated, layered PSD. As the upstream
project notes, it does not create a fully meshed and rigged Live2D model by
itself; it supplies the layer-decomposition stage that can feed a later rigging
pipeline.

## Initialize the companion

```bash
git submodule update --init --recursive
```

The submodule is pinned for reproducibility. To review a newer companion
revision without silently changing the parent repository:

```bash
git submodule update --remote vendor/see-through
git diff --submodule=log
```

## Profiles

`tools/run_seethrough.py` keeps the input/output paths in this repository while
running inference from the companion's required working directory.

The default `mps-smoke` profile is the MPS author's reported reproduction:
fixed seed `42`, layer/depth resolution `768`, 20 LayerDiff steps, 10 depth
steps, left/right splitting, and PSD export.

```bash
python3 tools/run_seethrough.py path/to/input.png --dry-run
python3 tools/run_seethrough.py path/to/input.png
```

The `community-quality` profile preserves the standard workflow in the
community ComfyUI integration and Tyler's existing workflow checkpoint: fixed
seed `42`, layer resolution `1280`, depth resolution `768`, 30 LayerDiff steps,
left/right splitting, and PSD export.

```bash
python3 tools/run_seethrough.py path/to/input.png \
  --profile community-quality
```

Outputs default to `local-assets/see-through-output/`, which is git-ignored.
Start with `mps-smoke`; move to `community-quality` only after confirming both
layer generation and depth ordering on the target Mac.

## Environment and limits

Follow `vendor/see-through/APPLE_SILICON.md` for the Python 3.12 environment.
Install normal macOS PyTorch wheels, not the upstream CUDA wheel command. Do
not enable group offload during initial MPS validation; the successful MPS
report did not use it.

This branch does not download model weights or claim runtime success on this
Mac yet. A real inference run requires the Python environment, Hugging Face
model downloads, substantial unified memory, and visual inspection of the
generated layers and depth ordering.
