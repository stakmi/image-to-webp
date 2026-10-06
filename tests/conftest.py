from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw


def make_rgb(size=(400, 300)) -> Image.Image:
    im = Image.new("RGB", size, "red")
    ImageDraw.Draw(im).ellipse((50, 50, size[0] - 50, size[1] - 50), fill="blue")
    return im


@pytest.fixture
def rgb() -> Image.Image:
    return make_rgb()


@pytest.fixture
def samples(tmp_path: Path) -> Path:
    """Directory of sample images in many core (Pillow-only) formats."""
    d = tmp_path / "in"
    (d / "sub").mkdir(parents=True)
    im = make_rgb()
    rgba = im.convert("RGBA")
    rgba.putalpha(128)
    im.save(d / "a.jpg")
    rgba.save(d / "b.png")
    im.save(d / "c.bmp")
    im.convert("CMYK").save(d / "d.tif")
    im.save(d / "e.tga")
    im.save(d / "f.ppm")
    im.save(d / "g.ico")
    im.save(d / "sub" / "h.pcx")
    im.convert("I;16").save(d / "sub" / "i16.png")
    frames = [Image.new("RGB", (64, 64), c) for c in ("red", "green", "blue")]
    frames[0].save(d / "anim.gif", save_all=True, append_images=frames[1:], duration=150, loop=0)
    (d / "notes.txt").write_text("ignore me")
    return d


@pytest.fixture
def broken(tmp_path: Path) -> Path:
    p = tmp_path / "broken.png"
    p.write_bytes(b"not an image")
    return p
