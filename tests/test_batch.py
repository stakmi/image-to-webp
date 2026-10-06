from __future__ import annotations

from PIL import Image

from image_to_webp import convert_many, plan_conversions

CORE = 10  # images in the samples fixture (all levels)
TOP = 8    # images in the top level only


def test_plan_non_recursive(samples):
    planned = plan_conversions(samples)
    assert len(planned) == TOP
    assert all(r.status == "pending" for r in planned)
    assert all(r.dst.parent == samples for r in planned)


def test_recursive_mirrors_tree(samples, tmp_path):
    out = tmp_path / "out"
    seen = []
    summary = convert_many(samples, out, recursive=True, jobs=1, on_result=seen.append)
    assert summary.converted == CORE and summary.failed == 0 and summary.ok
    assert len(seen) == CORE
    assert (out / "sub" / "h.webp").exists()
    assert summary.bytes_in > summary.bytes_out > 0


def test_parallel(samples, tmp_path):
    summary = convert_many([samples], tmp_path / "out", recursive=True, jobs=4)
    assert summary.converted == CORE


def test_skip_existing_then_overwrite(samples, tmp_path):
    out = tmp_path / "out"
    convert_many(samples, out, jobs=1)
    again = convert_many(samples, out, jobs=1)
    assert again.converted == 0 and again.skipped == TOP
    forced = convert_many(samples, out, jobs=1, overwrite=True, quality=10)
    assert forced.converted == TOP


def test_failures_collected(samples, broken, tmp_path):
    summary = convert_many([samples / "a.jpg", broken, tmp_path / "missing.png"], tmp_path / "o", jobs=1)
    assert summary.converted == 1 and summary.failed == 2 and not summary.ok
    errors = {r.src.name: r.error for r in summary.results if r.status == "failed"}
    assert "no such file" in errors["missing.png"]


def test_duplicate_output_names(tmp_path):
    a, b = tmp_path / "x.png", tmp_path / "x.jpg"
    Image.new("RGB", (8, 8)).save(a)
    Image.new("RGB", (8, 8)).save(b)
    summary = convert_many([a, b], tmp_path / "o", jobs=1)
    assert summary.converted == 1 and summary.skipped == 1


def test_delete_original(tmp_path):
    src = tmp_path / "x.png"
    Image.new("RGB", (8, 8)).save(src)
    summary = convert_many(src, delete_original=True, jobs=1)
    assert summary.converted == 1 and not src.exists() and (tmp_path / "x.webp").exists()


def test_webp_files_in_directories_ignored(tmp_path):
    Image.new("RGB", (8, 8)).save(tmp_path / "already.webp")
    assert plan_conversions(tmp_path) == []
