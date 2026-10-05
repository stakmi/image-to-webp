# image-to-webp

Command-line tool that converts images in many formats to WebP.

## Install

```bash
./install.sh
```

Creates a local `.venv`, installs the dependencies, and installs an `image-to-webp` command system-wide:

- macOS: `/usr/local/bin/image-to-webp` (`/usr/bin` is read-only due to System Integrity Protection)
- Linux: `/usr/bin/image-to-webp`
- `sudo` is used only if the directory isn't writable
- Override: `BIN_DIR=~/.local/bin ./install.sh`, `CMD_NAME=mywebp ./install.sh`
- Remove: `./install.sh --uninstall`

The command is not called `img2webp` because that name belongs to libwebp's own tool (shipped by Homebrew `webp` and Anaconda).

Installed plugins:

| Plugin | Adds |
|---|---|
| `pillow-heif` | HEIC / HEIF / AVIF |
| `rawpy` | Camera RAW (CR2, CR3, NEF, ARW, DNG, ORF, RW2, RAF, …) |
| `cairosvg` | SVG / SVGZ (requires system cairo: `brew install cairo`) |

Pillow itself covers PNG, JPEG, GIF, BMP, TIFF, ICO, ICNS, TGA, PSD, JPEG 2000, PCX, PPM/PGM/PBM, DDS, SGI, QOI, WebP and more. Run `image-to-webp --list-formats` for the full list.

## Usage

`./img2webp-run` in the project folder works the same without the system install.

```bash
image-to-webp photo.jpg                       # -> photo.webp next to source
image-to-webp ./images -r -o ./webp           # recursive, mirror tree into ./webp
image-to-webp *.png --lossless                # lossless
image-to-webp ./raw -q 85 --max-size 2560x2560 -j 8
image-to-webp ./images -r --dry-run
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

Notes: EXIF orientation is applied, transparency is preserved, animated GIF/APNG become animated WebP, ICO uses the largest icon. Exit code is `1` if any file failed.
