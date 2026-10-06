"""Exceptions raised by image_to_webp."""


class ImageToWebPError(Exception):
    """Base class for all image_to_webp errors."""


class UnsupportedFormatError(ImageToWebPError, ValueError):
    """The input format cannot be read (unknown, or its optional plugin is missing)."""


class ConversionError(ImageToWebPError):
    """The input was recognised but could not be decoded or encoded."""
