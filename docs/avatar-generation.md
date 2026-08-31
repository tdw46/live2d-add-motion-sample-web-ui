# Local avatar generation pipeline

The WebUI keeps Hiyori as its default avatar and stores generated avatars only
in git-ignored `local-assets/`. The selector order is:

1. Hiyori
2. Generate new…
3. Generated avatars, newest first

## Data flow

```text
description
  -> local-only tools/serve.py
  -> Gemini image API (front-facing full-body concept)
  -> vendor/see-through on Apple MPS (layered PSD)
  -> vendor/image2live2d (mesh, rig, physics, motions)
  -> tools/rig_avatar.py native moc3 writer
  -> local-assets/avatar-registry.json
  -> browser reloads with ?avatar=<generated id>
```

See-through also emits a sibling `*_depth.psd` for internal depth data. The
bridge explicitly selects the semantic color-layer PSD and refuses depth/debug
PSDs so grayscale depth planes cannot be mistaken for avatar artwork.

`tools/serve.py` reads `GEMINI_API_KEY` from
`/Users/tylerwalker/dev/Hallway/hallway-anime-facial-landmark-classifier/.env`
unless `LIVE2D_HALLWAY_ENV` points to another file. It never returns the key to
the browser, writes it to generated metadata, or includes it in request logs.
The server binds to `127.0.0.1` by default.

## Setup

```bash
git submodule update --init --recursive
python3 tools/setup_avatar_pipeline.py
python3 tools/serve.py
```

The setup script creates `.venv-avatar` with Python 3.12, the normal macOS
PyTorch wheels, See-through requirements, and the image2live2d rigging extras.
The environment and all downloaded/generated artifacts are ignored by Git.

## Profiles

- `mps-smoke` (default): seed 42, 768 layer/depth resolution, 20 LayerDiff
  steps, 10 depth steps, left/right split, PSD output. This profile completed
  locally on 2026-08-31.
- `community-quality`: seed 42, 1280 layer resolution, 768 depth resolution,
  30 LayerDiff steps, left/right split, PSD output. Start the server with
  `SEE_THROUGH_PROFILE=community-quality python3 tools/serve.py`.

The first local run downloads roughly 10–15 GB of weights. Requests are queued
and processed one at a time to avoid competing for unified memory.

## Rigging and validation

`image2live2d` is called through `tools/rig_avatar.py` instead of its public CLI
because the public CLI currently emits a JSON-only Live2D bundle. The adapter
injects the project's tested native writer, producing the `.moc3` required by
Pixi Live2D, then records parts, parameters, physics count, and QA status.

The experimental MPS path can produce an incomplete face plane even when eyes,
mouth, ears, neck, and hair are correctly separated. The adapter detects a
sparse face layer and rebuilds a conservative skin plane from the eye/mouth
geometry and neck skin tone before rigging. This is a recovery path, not a
replacement for visual review.

## Provenance

- See-through: `vendor/see-through`, pinned to the `tdw46/hallway_avatar_gen`
  `see-through-mps` branch with the focused upstream MPS patch.
- image2live2d: `vendor/image2live2d`, pinned upstream as an Apache-2.0 Git
  submodule.

Generated `.moc3` authoring is experimental. Review the Live2D SDK and
publication terms before distributing generated models in a product.
