"""Conversion settings."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any, Optional, Tuple


@dataclass(frozen=True)
class ConversionOptions:
    """Settings for the WebP encoder.

    Attributes:
        quality: 0-100. For lossy, higher is better quality; for lossless, higher is smaller/slower.
        lossless: Use lossless encoding.
        method: Compression effort, 0 (fast) to 6 (slowest, smallest).
        max_size: Optional ``(width, height)`` bound; larger images are downscaled keeping aspect ratio.
        keep_metadata: Copy EXIF and ICC profile into the output.
    """

    quality: int = 80
    lossless: bool = False
    method: int = 4
    max_size: Optional[Tuple[int, int]] = None
    keep_metadata: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.quality, int) or not 0 <= self.quality <= 100:
            raise ValueError(f"quality must be an int between 0 and 100, got {self.quality!r}")
        if not isinstance(self.method, int) or not 0 <= self.method <= 6:
            raise ValueError(f"method must be an int between 0 and 6, got {self.method!r}")
        if self.max_size is not None:
            try:
                w, h = self.max_size
            except (TypeError, ValueError):
                raise ValueError(f"max_size must be a (width, height) tuple, got {self.max_size!r}") from None
            if not (isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0):
                raise ValueError(f"max_size values must be positive ints, got {self.max_size!r}")
            object.__setattr__(self, "max_size", (w, h))


_FIELDS = {f.name for f in fields(ConversionOptions)}


def resolve_options(options: Optional[ConversionOptions], overrides: dict[str, Any]) -> ConversionOptions:
    """Combine an optional options object with keyword overrides."""
    unknown = set(overrides) - _FIELDS
    if unknown:
        raise TypeError(f"unexpected option(s): {', '.join(sorted(unknown))}")
    base = options or ConversionOptions()
    return replace(base, **overrides) if overrides else base
