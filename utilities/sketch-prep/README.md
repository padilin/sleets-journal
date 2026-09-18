# Sketch preparation utility

This utility turns photographed sketches into two complementary web treatments while preserving the source photograph. It is designed for small drawings whose paper continues outside the photograph; four visible page edges are not required.

- **Natural page** retains restrained paper color, texture, and margins.
- **Clean sketch** normalizes uneven lighting, converts to grayscale, and crops around the marks.

Each image also receives a lossless rectified master, a side-by-side comparison, a page-detection overlay, and machine-readable metadata.

## Setup

From this directory, create an isolated Python environment and install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If `python` is not on `PATH` in Codex, use the Python location shown by the workspace dependency loader for the first command.

## Process one image

From `utilities/sketch-prep`:

```powershell
.\.venv\Scripts\python.exe .\prepare_sketches.py ..\..\sketch-1.jpg
```

Generated files appear under `output/sketch-1/`:

```text
rectified.png       lossless corrected master
natural.webp        paper-preserving web treatment
clean.webp          normalized, tightly cropped web treatment
comparison.jpg      natural and clean versions side by side
detection-debug.jpg detected content bounds or page corners
content-mask.png     pencil marks considered during content detection
metadata.json       source hash, geometry, confidence, and output details
```

Existing output is not replaced unless `--force` is supplied.

## Batch processing

Pass a directory to process supported images recursively:

```powershell
.\.venv\Scripts\python.exe .\prepare_sketches.py D:\photos\journal-sketches
```

Or pass several files and choose an output directory:

```powershell
.\.venv\Scripts\python.exe .\prepare_sketches.py first.jpg second.jpg --output D:\prepared-sketches
```

The tool continues when one item fails and exits nonzero when any batch item failed. It deliberately ignores its own configured output tree when a parent directory is used as input.

## Processing modes

### Content mode (default)

Content mode estimates the local paper brightness, identifies dark stroke-like marks, rejects frame edges and long page-boundary lines, groups nearby marks, and crops the strongest drawing region with configurable padding. It does not apply a speculative perspective transform.

This is the expected mode for small sketches. The initial `sketch-1.jpg` configuration supplies only a rotation; its crop is detected from the drawing itself.

### Page mode (optional)

Set `mode: page` for an individual file only when the photograph genuinely contains a four-sided page:

```yaml
overrides:
  full-sheet-example.jpg:
    mode: page
    rotation_degrees_clockwise: 0
```

Page mode looks for a large four-sided contour, scores its area and geometry, and applies a four-point perspective transform only when the score meets the configured confidence threshold.

### Manual mode

Use the crop editor when an environmental line sits too close to the drawing for automatic content detection to distinguish safely:

```powershell
.\.venv\Scripts\python.exe .\manual_crop.py ..\..\sketch-1.jpg
```

Drag a blue rectangle around every intentional mark, then select **Save crop** or press Enter. **Rotate 90°** changes orientation and clears the current selection; Esc closes without saving.

The editor writes a small sidecar such as `overrides/sketch-1.jpg.yaml`. It does not modify the photograph or rewrite `config.yaml`. Rerun preparation to apply it:

```powershell
.\.venv\Scripts\python.exe .\prepare_sketches.py ..\..\sketch-1.jpg --force
```

Exact coordinates can also be saved without opening a window:

```powershell
.\.venv\Scripts\python.exe .\manual_crop.py ..\..\sketch-1.jpg `
  --rotation 270 --bounds 2300 1550 5250 3200
```

Manual coordinates are measured against the photograph after the configured rotation. The debug overlay and metadata show the applied rectangle.

## Detection and review

If the selected mode cannot find trustworthy geometry, the oriented original frame is used and `metadata.json` records `review_required: true` and `geometry_applied: false`.

Always inspect `detection-debug.jpg` when review is requested. Light paper against a light surface, cropped-off page corners, hands, clips, or strong shadows can make a fully automatic result ambiguous.

Small per-image overrides may live in `config.yaml`; the crop editor writes isolated files under `overrides/`. Overrides may specify:

- `rotation_degrees_clockwise`: `0`, `90`, `180`, or `270`.
- `mode`: `content`, `page`, or `manual`.
- `bounds`: manual `[left, top, right, bottom]` coordinates after rotation.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

The tests exercise content detection without page edges as well as automatic full-page detection and perspective correction.
