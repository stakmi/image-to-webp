"""Format registry: which inputs can be read, and how to open them."""

from __future__ import annotations

import io
import logging
import sys
import threading
from pathlib import Path
from typing import IO, Callable, Dict, FrozenSet, Optional, Union

from PIL import Image, UnidentifiedImageError

from .errors import ConversionError, UnsupportedFormatError

log = logging.getLogger(__name__)

Source = Union[str, Path, bytes, IO[bytes]]
_Input = Union[Path, IO[bytes]]
Opener = Callable[[_Input], Image.Image]

RAW_EXTENSIONS = frozenset({
    ".3fr", ".ari", ".arw", ".bay", ".cr2", ".cr3", ".crw", ".dcr", ".dng",
    ".erf", ".fff", ".iiq", ".k25", ".kdc", ".mef", ".mos", ".mrw", ".nef",
    ".nrw", ".orf", ".pef", ".raf", ".raw", ".rw2", ".rwl", ".sr2", ".srf",
    ".srw", ".x3f",
})
SVG_EXTENSIONS = frozenset({".svg", ".svgz"})
HEIF_EXTENSIONS = frozenset({".heic", ".heics", ".heif", ".heifs", ".hif", ".avif", ".avifs"})

# Pillow can identify these but cannot decode pixels without extra handlers.
_UNDECODABLE = {"BUFR", "GRIB", "HDF5", "MPEG"} | (set() if sys.platform == "win32" else {"WMF"})

_EXTRA_FOR = {**{e: "heif" for e in HEIF_EXTENSIONS},
              **{e: "raw" for e in RAW_EXTENSIONS},
              **{e: "svg" for e in SVG_EXTENSIONS}}

_lock = threading.Lock()
_registry: Optional[Dict[str, Opener]] = None
_plugins: Dict[str, Optional[str]] = {}


def _open_pillow(src: _Input) -> Image.Image:
    return Image.open(src)


def _open_raw(src: _Input) -> Image.Image:
    import rawpy

    with rawpy.imread(str(src) if isinstance(src, Path) else src) as raw:
        rgb = raw.postprocess(use_camera_wb=True, output_bps=8)
    return Image.fromarray(rgb)


def _open_svg(src: _Input) -> Image.Image:
    import cairosvg

    if isinstance(src, Path):
        png = cairosvg.svg2png(url=str(src))
    else:
        png = cairosvg.svg2png(file_obj=src)
    img = Image.open(io.BytesIO(png))
    img.load()
    return img


def _try_import(label: str, setup: Callable[[], None]) -> bool:
    try:
        setup()
        _plugins[label] = None
        return True
    except Exception as exc:  # ImportError, OSError (missing system lib), ...
        msg = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        _plugins[label] = msg
        log.debug("plugin %s unavailable: %s", label, msg)
        return False


def _setup_heif() -> None:
    import pillow_heif

    pillow_heif.register_heif_opener()
    if hasattr(pillow_heif, "register_avif_opener"):
        try:
            pillow_heif.register_avif_opener()
        except Exception:
            pass


def _build() -> Dict[str, Opener]:
    _try_import("heif", _setup_heif)
    Image.init()
    reg: Dict[str, Opener] = {}
    for ext, fmt in Image.registered_extensions().items():
        if fmt in Image.OPEN and fmt not in _UNDECODABLE:
            reg[ext.lower()] = _open_pillow
    if _try_import("raw", lambda: __import__("rawpy")):
        reg.update(dict.fromkeys(RAW_EXTENSIONS, _open_raw))
    if _try_import("svg", lambda: __import__("cairosvg")):
        reg.update(dict.fromkeys(SVG_EXTENSIONS, _open_svg))
    return reg


def registry() -> Dict[str, Opener]:
    global _registry
    if _registry is None:
        with _lock:
            if _registry is None:
                _registry = _build()
    return _registry


def supported_extensions() -> FrozenSet[str]:
    """Lower-case file extensions (with dot) that can be converted in this environment."""
    return frozenset(registry())


def is_supported(path: Union[str, Path]) -> bool:
    """True if the file's extension can be converted in this environment."""
    return Path(path).suffix.lower() in registry()


def plugin_status() -> Dict[str, Optional[str]]:
    """Optional plugin name (``heif``, ``raw``, ``svg``) -> ``None`` if available, else the reason."""
    registry()
    return dict(_plugins)


def _missing_plugin_hint(ext: str) -> str:
    extra = _EXTRA_FOR.get(ext)
    if extra is None:
        return ""
    reason = plugin_status().get(extra)
    hint = f" (install with: pip install 'image-to-webp[{extra}]')"
    if extra == "svg" and reason and "cairo" in reason.lower():
        hint = " (SVG support needs the system cairo library)"
    return hint


def _sniff_opener(head: bytes) -> Optional[Opener]:
    reg = registry()
    stripped = head.lstrip()
    if stripped.startswith(b"<") and b"<svg" in head:
        return reg.get(".svg")
    if head[:2] == b"\x1f\x8b":  # gzip -> probably svgz
        return reg.get(".svgz")
    return None


def open_image(source: Source, filename: Optional[str] = None) -> Image.Image:
    """Open ``source`` (path, bytes or binary file object) as a PIL image.

    ``filename`` is an optional hint used to pick the decoder for bytes/file objects
    whose format can't be sniffed (e.g. camera RAW).

    Raises:
        UnsupportedFormatError: unknown format, or the optional plugin for it is missing.
        ConversionError: the file is unreadable or its data is corrupt.
    """
    reg = registry()
    src: _Input
    if isinstance(source, (str, Path)):
        src = Path(source)
        ext = src.suffix.lower()
        name = str(src)
        opener = reg.get(ext)
        if opener is None:
            raise UnsupportedFormatError(f"unsupported format '{ext or src.name}'{_missing_plugin_hint(ext)}")
        if not src.is_file():
            raise ConversionError(f"not a file: {src}")
    else:
        src = io.BytesIO(bytes(source)) if isinstance(source, (bytes, bytearray, memoryview)) else source
        ext = Path(filename).suffix.lower() if filename else ""
        name = filename or "<bytes>"
        opener = reg.get(ext)
        if opener is None:
            pos = src.tell()
            opener = _sniff_opener(src.read(512)) or _open_pillow
            src.seek(pos)

    try:
        return opener(src)
    except UnidentifiedImageError as exc:
        raise UnsupportedFormatError(f"cannot identify image {name}{_missing_plugin_hint(ext)}") from exc
    except Exception as exc:
        raise ConversionError(f"cannot decode {name}: {exc}") from exc
