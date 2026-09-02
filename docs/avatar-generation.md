# Local avatar generation pipeline

The WebUI keeps Hiyori as its default avatar and stores generated avatars only
in git-ignored `local-assets/`. The selector order is:

1. Hiyori
2. Generate new…
3. Generated avatars, newest first

Once an avatar is loaded, the viewer's **Layer order** panel lists its Cubism
drawables front-to-back. Drag rows or use the arrow controls to preview a new
stack immediately, then save it. Per-avatar order is stored in the ignored
`local-assets/avatar-viewer-metadata.json` and reapplied after reload.

Each generated-avatar row also has a **✦ Regenerate** control. It edits the
finalized full-canvas layer consumed by the rig rather than rerunning
See-through. Matching left/right, front/back, and connected upper/lower layers
are included by default and can be opted out. Palette preservation, change
amount, and strict/balanced attachment locking are exposed per edit.
Generic See-through parts without side tokens (for example, two layers both
named `accessory`) are paired from mirrored canvas geometry. This keeps the
left/right option available for arms while excluding centered accessories.

## Targeted layer regeneration

The local server chooses an RGB chroma color by maximizing its minimum color
distance from every visible color across the selected input layers. It places
the finalized RGBA layer over that solid color before sending it to Gemini,
along with a cropped local character context and matching layers as references.
Image roles are explicitly labeled, and Gemini-facing instructions require one
uniformly keyed background and intentionally avoid language that asks the model
for alpha output.

After generation, the bridge flood-fills chroma shades connected to the image
border and removes edge spill. **Use a new layer mask from the chroma-keyed
result** is enabled by default. The recovered alpha stays in Gemini's original
full-canvas coordinates without being resized into the old layer bounds, so a
new hairstyle, sleeve, or garment can genuinely extend or contract. A narrow
strip of finalized pixels is blended at the proximal attachment seam; strict
lock preserves 6% (up to 16 pixels), while balanced lock preserves 3%.

Users can turn the option off for a recolor or surface-detail edit that must
retain the finalized outline exactly. In that mode, generated RGB is fitted
into the original occupied bounds, missing generated pixels fall back to the
finalized artwork, and the original alpha mask is restored byte-for-byte. A
near-full-canvas foreground is rejected as an accidental character/scene
response; when a valid paired layer exists, the bridge mirrors it into the
rejected counterpart and keeps that counterpart's original seam.

Accepted replacements live under the generated avatar's ignored
`layer-regeneration/overrides/` directory. Timestamped edit metadata and prior
accepted images are kept under `layer-regeneration/history/`. A later full
layer rebuild reapplies accepted overrides after PSD extraction and inpainting.
Every generated layer exposes right-aligned undo and redo controls beside its
name. Both remain visible and become disabled when their corresponding history
stack is empty. Undo restores the preceding accepted generation, or removes the
override when the preceding state was the finalized baseline; redo reapplies the
undone generation. Matching layers are restored together by default, and a new
generation clears the applicable redo history. The affected rows and status line
show spinners throughout the candidate-rig rebuild. See-through display names
such as `Topwear`, `Cape`, and side-specific footwear survive override rebuilds
instead of falling back to generic semantic roles. Row controls sit
in a horizontally scrollable strip that also supports thresholded drag-to-scroll,
so an ordinary click and release still activates its button. **Reset regenerated
art** remains available in the placement panel to jump directly to baseline.
Both operations rebuild and validate a candidate rig before replacing the
active model. Whole-pixel X/Y placement lives in
`layer-regeneration/metadata.json`; live sliders appear below each layer in the
Layer Order UI, and the saved value is applied non-destructively during every
rebuild and can also be reset.

Layers with accepted Gemini edits show a chevron on their thumbnail. Clicking
the thumbnail expands an inline visual picker containing the finalized original
and every accepted generated result, including the instruction that produced it.
The active result is marked and disabled; selecting another variant runs the
same transactional candidate-rig rebuild used by undo and redo. Older avatars
derive variant images from their existing history, while new generations archive
their accepted images directly in the matching history entry.
The picker is a browser top-layer popover so it draws above every sortable row
instead of being clipped by the scrolling layer list. Matching front/back,
left/right, and connected layers switch to the same accepted generation by
default. A checked option at the top of the picker lets the user opt out and
change only the selected layer.

Both newly accepted Gemini results and later variant switching compare the PNG
alpha planes using a cached decoder. Each rig build unions the finalized original,
current override, and archived accepted variants into per-drawable mesh guides,
then records the emitted triangle coverage. When every selected result fits that
coverage and no placement offset is baked, the server archives the generation,
updates the persisted override and existing Live2D texture file without invoking
the rigging bridge, and returns the new variant ID. The viewer then replaces the
corresponding Pixi/WebGL texture slots in place. A genuinely new silhouette outside
the recorded coverage takes the transactional rebuild path once; that rebuild
expands the guide so the accepted shape becomes texture-only on later switches.
`pnpm run dev` prefers the Pillow-enabled avatar virtual environment for fast mask
queries and falls back to the stdlib PNG decoder when that environment is absent.

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

- `community-quality` (default): seed 42, 1280 layer resolution, 768 depth
  resolution, 30 LayerDiff steps, 10 Marigold depth steps, left/right split,
  and PSD output.
- `mps-smoke`: seed 42, 768 layer/depth resolution, 20 LayerDiff
  steps, 10 depth steps, left/right split, PSD output. This profile completed
  locally on 2026-08-31.

Both profiles automatically select CUDA, then MPS, then CPU. Marigold output is
validated for finite values, normalized range, dimensions, and meaningful depth
variation before semantic extraction. If an MPS depth pass errors or fails those
checks, only Marigold is reloaded and retried on CPU; `depth-qa.json` records both
attempts. A failed retry stops generation before an avatar can be registered.

The first local run downloads roughly 10–15 GB of weights. Requests are queued
and processed one at a time to avoid competing for unified memory.

## Rigging and validation

`image2live2d` is called through `tools/rig_avatar.py` instead of its public CLI
because the public CLI currently emits a JSON-only Live2D bundle. The adapter
injects the project's tested native writer, producing the `.moc3` required by
Pixi Live2D, then records parts, parameters, physics count, and QA status.

The experimental decomposition can produce an incomplete or entirely missing
face plane even when eyes, mouth, ears, neck, and hair are usable. The adapter
first rebuilds the face from See-through's full-color `head.png`, subtracting
already-separated hair and facial-feature alpha so the source design and colors
are retained. Older artifacts without `head.png` retain the conservative
eye/mouth geometry and neck-color fallback. Rig QA now fails closed: an avatar
with unresolved semantic or rig warnings is left on disk for diagnosis but is
not registered as ready.

## Provenance

- See-through: `vendor/see-through`, pinned to the `tdw46/hallway_avatar_gen`
  `see-through-mps` branch with the focused upstream MPS patch.
- image2live2d: `vendor/image2live2d`, pinned upstream as an Apache-2.0 Git
  submodule.

Generated `.moc3` authoring is experimental. Review the Live2D SDK and
publication terms before distributing generated models in a product.
