# image-to-webp

Convert images in almost any format to [WebP](https://developers.google.com/speed/webp), from Python or the command line.

- Over 70 input formats with Pillow alone: PNG, JPEG, GIF, BMP, TIFF, ICO/ICNS, TGA, PSD, JPEG 2000, PCX, PPM/PGM/PBM, DDS, SGI, QOI, WebP, …
- More formats through optional installs: HEIC/HEIF/AVIF, camera RAW (CR2, CR3, NEF, ARW, DNG, …) and SVG
- Applies EXIF rotation, keeps transparency, and turns animated GIF/APNG into animated WebP
- Converts files in parallel and writes each output in one step, so a failed run never leaves a half-written file

## Install

```bash
pip install image-to-webp            # core formats (Pillow only)
pip install "image-to-webp[all]"     # + HEIC/AVIF, RAW and SVG
```

| Optional install | Adds | Package |
|---|---|---|
| `[heif]` | HEIC / HEIF / AVIF | `pillow-heif` |
| `[raw]` | Camera RAW | `rawpy` |
| `[svg]` | SVG / SVGZ | `cairosvg` (also needs the system cairo library: `brew install cairo` or `apt install libcairo2`) |

Requires Python 3.9+.

## Library usage

```python
from image_to_webp import convert_file, convert_bytes, convert_image, convert_many, ConversionOptions

# One file -> photo.webp next to it (returns the output Path)
convert_file("photo.heic")
convert_file("photo.png", "out/photo.webp", quality=90)

# In memory
webp_bytes = convert_bytes(png_bytes, lossless=True)
webp_bytes = convert_bytes(open("img.cr2", "rb"), filename="img.cr2")  # filename hints RAW decoding
webp_bytes = convert_image(pil_image, quality=75)

# Reusable settings
opts = ConversionOptions(quality=85, method=6, max_size=(2560, 2560), keep_metadata=True)
convert_file("big.tif", options=opts)

# Batch: files and/or directories, in parallel
summary = convert_many(["images/", "extra.gif"], output_dir="webp", recursive=True,
                       jobs=4, on_result=lambda r: print(r.status, r.src))
print(summary.converted, summary.skipped, summary.failed, summary.bytes_saved)
```

### API reference

| Name | Description |
|---|---|
| `convert_file(src, dst=None, options=None, *, overwrite=True, **opts) -> Path` | Convert one file. `dst` defaults to `src` with a `.webp` extension. |
| `convert_bytes(data, options=None, *, filename=None, **opts) -> bytes` | Convert bytes or a binary file object. |
| `convert_image(image, options=None, **opts) -> bytes` | Encode a `PIL.Image.Image`. |
| `convert_many(inputs, output_dir=None, options=None, *, recursive, overwrite=False, delete_original, jobs, on_result, **opts) -> BatchSummary` | Convert many files. One failed file doesn't stop the run. |
| `plan_conversions(inputs, output_dir=None, *, recursive, overwrite)` | Preview what `convert_many` would do (dry run). |
| `ConversionOptions(quality=80, lossless=False, method=4, max_size=None, keep_metadata=False)` | Encoder settings, checked when created. |
| `ConversionResult` / `BatchSummary` | Results for each file and for the whole batch. |
| `supported_extensions()`, `is_supported(path)`, `plugin_status()` | See which formats work in the current environment. |
| `open_image(source, filename=None)` | Open any supported input as a PIL image. |
| `ImageToWebPError` → `UnsupportedFormatError`, `ConversionError` | Exceptions. |

`**opts` accepts the same keywords as `ConversionOptions` (`quality`, `lossless`, `method`, `max_size`, `keep_metadata`).
The library never prints. Messages go to Python's `logging` under the `image_to_webp` logger.

## Command line

```bash
image-to-webp photo.jpg                        # -> photo.webp next to source
image-to-webp ./images -r -o ./webp            # recursive, mirror tree into ./webp
image-to-webp *.png --lossless
image-to-webp ./raw -q 85 --max-size 2560x2560 -j 8
image-to-webp ./images -r --dry-run
image-to-webp --list-formats                   # formats + optional plugin status
python -m image_to_webp --help                 # same tool
```

| Option | Description |
|---|---|
| `-r, --recursive` | Search directories recursively |
| `-o, --output DIR` | Output directory (default: next to source) |
| `-q, --quality N` | Quality 0–100 (default 80) |
| `--lossless` | Lossless encoding |
| `-m, --method N` | Compression effort 0–6 (default 4) |
| `--max-size WxH` | Downscale to fit, keeping aspect ratio |
| `--keep-metadata` | Keep EXIF and ICC profile |
| `--overwrite` | Overwrite existing `.webp` (default: skip) |
| `--delete-original` | Delete source after successful conversion |
| `-j, --jobs N` | Parallel workers (default: CPU count) |
| `--dry-run` | Show what would be converted |
| `-v, --verbose` | Print each file |
| `--list-formats` | Show supported formats and plugin status |

Exit code is `0` on success, `1` if any file failed, `2` for invalid arguments.

> The command is called `image-to-webp`, not `img2webp`, because libwebp already ships a tool named `img2webp`.

## Development

```bash
./install.sh                    # .venv + editable install with all optional formats + link command to /usr/local/bin (macOS) or /usr/bin
./install.sh --uninstall        # remove the linked command
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
```

`install.sh` uses `sudo` only when the target directory isn't writable. Override with `BIN_DIR=~/.local/bin` or `CMD_NAME=...`.

## Releasing

1. Update `__version__` in `src/image_to_webp/__init__.py` and `CHANGELOG.md`.
2. Check the build locally:
   ```bash
   python -m build && python -m twine check --strict dist/*
   ```
3. Publish:
   - **Automated (recommended):** set up PyPI [trusted publishing](https://docs.pypi.org/trusted-publishers/) for `stakmi/image-to-webp` with workflow `publish.yml` and environment `pypi`, then create a GitHub release tagged `v<version>`.
   - **Manual:** `python -m twine upload dist/*`

## License

MIT
