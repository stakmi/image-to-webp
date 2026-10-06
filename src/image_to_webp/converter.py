"""Convert a single image to WebP."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import IO, Any, List, Optional, Union

from PIL import Image, ImageOps, ImageSequence

from .errors import ConversionError, ImageToWebPError
from .loaders import Source, open_image
from .options import ConversionOptions, resolve_options

PathLike = Union[str, "os.PathLike[str]"]

_ANIMATED_FORMATS = {"GIF", "PNG", "WEBP", "FLI"}


def _normalize_mode(img: Image.Image) -> Image.Image:
    """Convert to a mode the WebP encoder accepts (RGB or RGBA)."""
    if img.mode in ("RGB", "RGBA"):
        return img
    has_alpha = (
        img.mode in ("LA", "PA", "La", "RGBa")
        or (img.mode == "P" and "transparency" in img.info)
        or "A" in img.getbands()
    )
    if img.mode in ("I;16", "I;16B", "I;16L", "I"):
        img = img.point(lambda v: v * (1 / 256)).convert("L")
    elif img.mode == "F":
        img = img.convert("L")
    elif img.mode == "CMYK":
        img = img.convert("RGB")
    return img.convert("RGBA" if has_alpha else "RGB")


def _resize(img: Image.Image, opts: ConversionOptions) -> Image.Image:
    if opts.max_size and (img.width > opts.max_size[0] or img.height > opts.max_size[1]):
        img = img.copy()
        img.thumbnail(opts.max_size, Image.Resampling.LANCZOS)
    return img


def _pick_largest_icon(img: Image.Image) -> None:
    sizes = img.info.get("sizes")
    if img.format in ("ICO", "ICNS") and sizes:
        try:
            img.size = max(sizes)
        except Exception:
            pass


def _save_kwargs(img: Image.Image, opts: ConversionOptions) -> dict[str, Any]:
    kw: dict[str, Any] = {
        "format": "WEBP",
        "quality": opts.quality,
        "lossless": opts.lossless,
        "method": opts.method,
    }
    if opts.keep_metadata:
        if img.info.get("icc_profile"):
            kw["icc_profile"] = img.info["icc_profile"]
        src_exif = img.getexif()
        if src_exif:
            # Work on a copy: getexif() is cached and exif_transpose() still needs the orientation.
            exif = Image.Exif()
            exif.load(src_exif.tobytes())
            exif[0x0112] = 1  # orientation is applied to the pixels
            kw["exif"] = exif.tobytes()
    return kw


def _encode(img: Image.Image, opts: ConversionOptions, out: Union[Path, IO[bytes]]) -> None:
    try:
        kw = _save_kwargs(img, opts)
        if getattr(img, "is_animated", False) and img.format in _ANIMATED_FORMATS:
            frames: List[Image.Image] = []
            durations: List[int] = []
            for frame in ImageSequence.Iterator(img):
                durations.append(int(frame.info.get("duration") or img.info.get("duration") or 100))
                frames.append(_resize(frame.convert("RGBA"), opts))
            frames[0].save(out, save_all=True, append_images=frames[1:],
                           duration=durations, loop=img.info.get("loop", 0), **kw)
        else:
            _pick_largest_icon(img)
            frame = ImageOps.exif_transpose(img) or img
            _resize(_normalize_mode(frame), opts).save(out, **kw)
    except ImageToWebPError:
        raise
    except Exception as exc:
        raise ConversionError(f"cannot encode WebP: {exc}") from exc


def convert_image(image: Image.Image, options: Optional[ConversionOptions] = None, **kwargs: Any) -> bytes:
    """Encode a PIL image as WebP and return the bytes.

    Options can be given as a :class:`ConversionOptions` and/or keyword overrides
    (``quality``, ``lossless``, ``method``, ``max_size``, ``keep_metadata``).
    """
    opts = resolve_options(options, kwargs)
    buf = io.BytesIO()
    _encode(image, opts, buf)
    return buf.getvalue()


def convert_bytes(data: Union[bytes, IO[bytes]], options: Optional[ConversionOptions] = None,
                  *, filename: Optional[str] = None, **kwargs: Any) -> bytes:
    """Convert encoded image data (bytes or a binary file object) to WebP bytes.

    ``filename`` is an optional hint for formats that can't be detected from content (camera RAW).
    """
    opts = resolve_options(options, kwargs)
    src: Source = data
    with open_image(src, filename=filename) as img:
        buf = io.BytesIO()
        _encode(img, opts, buf)
        return buf.getvalue()


def default_output_path(src: PathLike) -> Path:
    """``photo.jpg`` -> ``photo.webp`` in the same directory."""
    return Path(src).with_suffix(".webp")


def convert_file(src: PathLike, dst: Optional[PathLike] = None,
                 options: Optional[ConversionOptions] = None, *, overwrite: bool = True,
                 **kwargs: Any) -> Path:
    """Convert the image file ``src`` to WebP and return the output path.

    ``dst`` defaults to ``src`` with a ``.webp`` extension. Parent directories are
    created as needed and the file is written atomically.

    Raises:
        FileExistsError: ``dst`` exists and ``overwrite`` is False.
        UnsupportedFormatError, ConversionError: see :func:`open_image`.
    """
    opts = resolve_options(options, kwargs)
    src_path = Path(src)
    dst_path = Path(dst) if dst is not None else default_output_path(src_path)
    if not overwrite and dst_path.exists():
        raise FileExistsError(f"output exists: {dst_path}")

    with open_image(src_path) as img:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst_path.with_name(f".{dst_path.name}.{os.getpid()}.part")
        try:
            _encode(img, opts, tmp)
            os.replace(tmp, dst_path)
        finally:
            if tmp.exists():
                tmp.unlink()
    return dst_path
