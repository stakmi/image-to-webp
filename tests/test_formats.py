from __future__ import annotations

import pytest
from PIL import Image

from image_to_webp import convert_file, is_supported, plugin_status, supported_extensions

from .conftest import make_rgb


def test_core_extensions_supported():
    exts = supported_extensions()
    for e in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".ico", ".tga", ".webp", ".jp2"):
        assert e in exts, e
    assert ".grib" not in exts
    assert is_supported("A.PNG") and not is_supported("a.txt")


def test_plugin_status_keys():
    assert set(plugin_status()) == {"heif", "raw", "svg"}


@pytest.mark.parametrize("name,mode", [
    ("a.jpg", "RGB"), ("b.png", "RGBA"), ("c.bmp", "RGB"), ("d.tif", "RGB"), ("e.tga", "RGB"),
    ("f.ppm", "RGB"), ("g.ico", "RGB"), ("sub/h.pcx", "RGB"), ("sub/i16.png", "RGB"),
])
def test_core_formats(samples, tmp_path, name, mode):
    out = convert_file(samples / name, tmp_path / "out.webp")
    im = Image.open(out)
    assert im.format == "WEBP" and im.mode == mode


def test_ico_uses_largest_size(samples, tmp_path):
    im = Image.open(convert_file(samples / "g.ico", tmp_path / "g.webp"))
    assert im.size == (256, 192)


def test_animated_gif(samples, tmp_path):
    im = Image.open(convert_file(samples / "anim.gif", tmp_path / "anim.webp"))
    assert im.is_animated and im.n_frames == 3


def test_heic(tmp_path):
    pillow_heif = pytest.importorskip("pillow_heif")
    pillow_heif.register_heif_opener()
    src = tmp_path / "x.heic"
    make_rgb().save(src)
    assert Image.open(convert_file(src)).size == (400, 300)


def test_svg(tmp_path):
    if plugin_status()["svg"] is not None:
        pytest.skip("cairosvg/cairo not available")
    src = tmp_path / "x.svg"
    src.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="80" height="60">'
                   '<rect width="80" height="60" fill="green"/></svg>')
    im = Image.open(convert_file(src))
    assert im.size == (80, 60)


def test_svg_bytes_sniffed(tmp_path):
    if plugin_status()["svg"] is not None:
        pytest.skip("cairosvg/cairo not available")
    from image_to_webp import convert_bytes

    data = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'
    assert convert_bytes(data)[:4] == b"RIFF"


def test_raw_extension_registered_when_available():
    if plugin_status()["raw"] is not None:
        pytest.skip("rawpy not available")
    assert is_supported("photo.CR2") and is_supported("x.dng")
