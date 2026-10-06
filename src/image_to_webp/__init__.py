"""Convert images in almost any format to WebP.

Quick start::

    from image_to_webp import convert_file, convert_bytes, convert_many

    convert_file("photo.heic")                       # -> photo.webp
    webp = convert_bytes(png_bytes, quality=90)      # in memory
    summary = convert_many("images/", recursive=True, output_dir="webp")
"""

from .batch import BatchSummary, ConversionResult, convert_many, plan_conversions
from .converter import convert_bytes, convert_file, convert_image, default_output_path
from .errors import ConversionError, ImageToWebPError, UnsupportedFormatError
from .loaders import is_supported, open_image, plugin_status, supported_extensions
from .options import ConversionOptions

__version__ = "0.1.0"

__all__ = [
    "BatchSummary",
    "ConversionError",
    "ConversionOptions",
    "ConversionResult",
    "ImageToWebPError",
    "UnsupportedFormatError",
    "__version__",
    "convert_bytes",
    "convert_file",
    "convert_image",
    "convert_many",
    "default_output_path",
    "is_supported",
    "open_image",
    "plan_conversions",
    "plugin_status",
    "supported_extensions",
]
