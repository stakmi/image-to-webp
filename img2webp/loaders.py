"""Format registry: maps file extensions to image openers, with optional plugins."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Callable, Dict, Optional

from PIL import Image

Opener = Callable[[Path], Image.Image]

RAW_EXTENSIONS = {
    ".3fr", ".ari", ".arw", ".bay", ".cr2", ".cr3", ".crw", ".dcr", ".dng",
    ".erf", ".fff", ".iiq", ".k25", ".kdc", ".mef", ".mos", ".mrw", ".nef",
    ".nrw", ".orf", ".pef", ".raf", ".raw", ".rw2", ".rwl", ".sr2", ".srf",
    ".srw", ".x3f",
}
SVG_EXTENSIONS = {".svg", ".svgz"}
# Pillow can identify these but cannot decode pixels without extra handlers.
_UNDECODABLE = {"BUFR", "GRIB", "HDF5", "MPEG"} | (set() if sys.platform == "win32" else {"WMF"})

_plugins: Dict[str, Optional[str]] = {}


def _register_heif() -> None:
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
        if hasattr(pillow_heif, "register_avif_opener"):
            try:
                pillow_heif.register_avif_opener()
            except Exception:
                pass
        _plugins["pillow-heif (HEIC/HEIF/AVIF)"] = None
    except Exception as exc:
        _plugins["pillow-heif (HEIC/HEIF/AVIF)"] = str(exc)
    try:
        import pillow_avif  # noqa: F401

        _plugins["pillow-avif-plugin (AVIF)"] = None
    except Exception:
        pass


def _raw_available() -> bool:
    try:
        import rawpy  # noqa: F401

        _plugins["rawpy (camera RAW)"] = None
        return True
    except Exception as exc:
        _plugins["rawpy (camera RAW)"] = str(exc)
        return False


def _svg_available() -> bool:
    try:
        import cairosvg  # noqa: F401

        _plugins["cairosvg (SVG)"] = None
        return True
    except Exception as exc:
        _plugins["cairosvg (SVG)"] = str(exc).splitlines()[0] if str(exc) else repr(exc)
        return False


def _open_raw(path: Path) -> Image.Image:
    import rawpy

    with rawpy.imread(str(path)) as raw:
        rgb = raw.postprocess(use_camera_wb=True, output_bps=8)
    return Image.fromarray(rgb)


def _open_svg(path: Path) -> Image.Image:
    import cairosvg

    png = cairosvg.svg2png(url=str(path))
    img = Image.open(io.BytesIO(png))
    img.load()
    return img


def _open_pillow(path: Path) -> Image.Image:
    return Image.open(path)


_REGISTRY: Optional[Dict[str, Opener]] = None


def registry() -> Dict[str, Opener]:
    """Return {extension: opener} for every readable format."""
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY
    _register_heif()
    Image.init()
    reg: Dict[str, Opener] = {}
    for ext, fmt in Image.registered_extensions().items():
        if fmt in Image.OPEN and fmt not in _UNDECODABLE:
            reg[ext.lower()] = _open_pillow
    if _raw_available():
        for ext in RAW_EXTENSIONS:
            reg[ext] = _open_raw
    if _svg_available():
        for ext in SVG_EXTENSIONS:
            reg[ext] = _open_svg
    _REGISTRY = reg
    return reg


def plugin_status() -> Dict[str, Optional[str]]:
    """Plugin name -> None if available, else the error message."""
    registry()
    return dict(_plugins)


def opener_for(path: Path) -> Optional[Opener]:
    return registry().get(path.suffix.lower())
