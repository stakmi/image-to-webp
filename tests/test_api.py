from __future__ import annotations

import io

import pytest
from PIL import Image, ImageChops

import image_to_webp as itw
from image_to_webp import (
    ConversionError,
    ConversionOptions,
    UnsupportedFormatError,
    convert_bytes,
    convert_file,
    convert_image,
)


def _open(data: bytes) -> Image.Image:
    im = Image.open(io.BytesIO(data))
    assert im.format == "WEBP"
    return im


def test_public_api():
    for name in itw.__all__:
        assert hasattr(itw, name)
    assert itw.__version__ == "0.1.0"


@pytest.mark.parametrize("kwargs", [{"quality": 101}, {"quality": -1}, {"method": 7},
                                    {"max_size": (0, 10)}, {"max_size": "big"}])
def test_options_validation(kwargs):
    with pytest.raises(ValueError):
        ConversionOptions(**kwargs)


def test_unknown_option_rejected(rgb):
    with pytest.raises(TypeError):
        convert_image(rgb, qualty=50)


def test_convert_image_bytes(rgb):
    im = _open(convert_image(rgb, quality=50))
    assert im.size == rgb.size and im.mode == "RGB"


def test_lossless_roundtrip(rgb):
    im = _open(convert_image(rgb, lossless=True))
    assert ImageChops.difference(im.convert("RGB"), rgb).getbbox() is None


def test_options_object_and_override(rgb):
    opts = ConversionOptions(max_size=(100, 100))
    assert _open(convert_image(rgb, opts)).size == (100, 75)
    assert _open(convert_image(rgb, opts, max_size=(200, 200))).size == (200, 150)


def test_resize_never_upscales(rgb):
    assert _open(convert_image(rgb, max_size=(4000, 4000))).size == rgb.size


def test_convert_bytes_keeps_alpha(rgb):
    rgba = rgb.convert("RGBA")
    rgba.putalpha(100)
    buf = io.BytesIO()
    rgba.save(buf, "PNG")
    assert _open(convert_bytes(buf.getvalue())).mode == "RGBA"


def test_convert_bytes_file_object(rgb):
    buf = io.BytesIO()
    rgb.save(buf, "JPEG")
    buf.seek(0)
    assert _open(convert_bytes(buf)).size == rgb.size


def test_convert_bytes_garbage():
    with pytest.raises(UnsupportedFormatError):
        convert_bytes(b"garbage")


def test_convert_file_default_dst(tmp_path, rgb):
    src = tmp_path / "x.png"
    rgb.save(src)
    out = convert_file(src)
    assert out == tmp_path / "x.webp" and out.exists()
    assert not list(tmp_path.glob("*.part"))


def test_convert_file_creates_dirs_and_overwrite(tmp_path, rgb):
    src = tmp_path / "x.png"
    rgb.save(src)
    dst = tmp_path / "deep" / "dir" / "y.webp"
    assert convert_file(src, dst) == dst
    with pytest.raises(FileExistsError):
        convert_file(src, dst, overwrite=False)
    convert_file(src, dst)  # overwrite=True by default


def test_exif_orientation_applied_and_metadata(tmp_path, rgb):
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 CW
    exif[0x010F] = "TestCam"
    src = tmp_path / "o.jpg"
    rgb.save(src, exif=exif.tobytes())

    out = convert_file(src, tmp_path / "o.webp", keep_metadata=True)
    im = Image.open(out)
    assert im.size == (rgb.height, rgb.width)
    e = im.getexif()
    assert e.get(0x010F) == "TestCam" and e.get(0x0112) == 1

    plain = Image.open(convert_file(src, tmp_path / "p.webp"))
    assert not plain.getexif()


def test_unsupported_extension(tmp_path):
    p = tmp_path / "doc.txt"
    p.write_text("hi")
    with pytest.raises(UnsupportedFormatError):
        convert_file(p)


def test_corrupt_file(broken):
    with pytest.raises((UnsupportedFormatError, ConversionError)):
        convert_file(broken)
    assert not broken.with_suffix(".webp").exists()


def test_missing_file(tmp_path):
    with pytest.raises(ConversionError):
        convert_file(tmp_path / "nope.png")


def test_errors_share_base_class():
    assert issubclass(UnsupportedFormatError, itw.ImageToWebPError)
    assert issubclass(ConversionError, itw.ImageToWebPError)
