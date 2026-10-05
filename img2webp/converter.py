"""Convert a single image to WebP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageOps, ImageSequence

from .loaders import opener_for


@dataclass
class Options:
    quality: int = 80
    lossless: bool = False
    method: int = 4
    max_size: Optional[Tuple[int, int]] = None
    keep_metadata: bool = False


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


def _resize(img: Image.Image, max_size: Optional[Tuple[int, int]]) -> Image.Image:
    if max_size and (img.width > max_size[0] or img.height > max_size[1]):
        img = img.copy()
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
    return img


def _pick_frame(img: Image.Image) -> Image.Image:
    """For ICO/ICNS pick the largest size; otherwise the first frame."""
    if img.format in ("ICO", "ICNS") and hasattr(img, "info") and img.info.get("sizes"):
        try:
            img.size = max(img.info["sizes"])
        except Exception:
            pass
    return img


def convert(src: Path, dst: Path, opts: Options) -> int:
    """Convert src to dst (WebP). Returns the output size in bytes."""
    opener = opener_for(src)
    if opener is None:
        raise ValueError(f"unsupported format: {src.suffix}")

    img = opener(src)
    try:
        save_kw = {
            "format": "WEBP",
            "quality": opts.quality,
            "lossless": opts.lossless,
            "method": opts.method,
        }
        if opts.keep_metadata:
            if img.info.get("icc_profile"):
                save_kw["icc_profile"] = img.info["icc_profile"]
            exif = img.getexif()
            if exif:
                # Orientation is baked into pixels, so reset it.
                exif[0x0112] = 1
                save_kw["exif"] = exif.tobytes()

        animated = getattr(img, "is_animated", False) and img.format in ("GIF", "PNG", "WEBP", "FLI")

        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".part")
        if animated:
            frames: List[Image.Image] = []
            durations: List[int] = []
            for frame in ImageSequence.Iterator(img):
                durations.append(int(frame.info.get("duration", img.info.get("duration", 100)) or 100))
                frames.append(_resize(frame.convert("RGBA"), opts.max_size))
            frames[0].save(
                tmp,
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=img.info.get("loop", 0),
                **save_kw,
            )
        else:
            img = _pick_frame(img)
            out = ImageOps.exif_transpose(img) or img
            out = _resize(_normalize_mode(out), opts.max_size)
            out.save(tmp, **save_kw)
        tmp.replace(dst)
        return dst.stat().st_size
    finally:
        img.close()
