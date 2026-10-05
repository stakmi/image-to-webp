"""Command-line interface for img2webp."""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from . import __version__
from .converter import Options, convert
from .loaders import plugin_status, registry

Job = Tuple[Path, Path]


def _parse_size(value: str) -> Tuple[int, int]:
    try:
        w, h = value.lower().split("x")
        size = (int(w), int(h))
        if size[0] <= 0 or size[1] <= 0:
            raise ValueError
        return size
    except ValueError:
        raise argparse.ArgumentTypeError("expected WIDTHxHEIGHT, e.g. 1920x1080")


def _int_range(lo: int, hi: int):
    def check(value: str) -> int:
        n = int(value)
        if not lo <= n <= hi:
            raise argparse.ArgumentTypeError(f"must be between {lo} and {hi}")
        return n

    return check


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="image-to-webp",
        description="Convert images (PNG, JPEG, GIF, TIFF, HEIC, RAW, SVG, ...) to WebP.",
    )
    p.add_argument("inputs", nargs="*", type=Path, help="image files and/or directories")
    p.add_argument("-r", "--recursive", action="store_true", help="search directories recursively")
    p.add_argument("-o", "--output", type=Path, help="output directory (default: next to source)")
    p.add_argument("-q", "--quality", type=_int_range(0, 100), default=80, help="quality 0-100 (default 80)")
    p.add_argument("--lossless", action="store_true", help="use lossless encoding")
    p.add_argument("-m", "--method", type=_int_range(0, 6), default=4,
                   help="compression effort 0 (fast) - 6 (slow, smaller) (default 4)")
    p.add_argument("--max-size", type=_parse_size, metavar="WxH", help="downscale to fit within WxH")
    p.add_argument("--keep-metadata", action="store_true", help="keep EXIF and ICC profile")
    p.add_argument("--overwrite", action="store_true", help="overwrite existing .webp files")
    p.add_argument("--delete-original", action="store_true", help="delete source after successful conversion")
    p.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1, help="parallel workers (default: CPU count)")
    p.add_argument("--dry-run", action="store_true", help="show what would be converted")
    p.add_argument("-v", "--verbose", action="store_true", help="print every file")
    p.add_argument("--list-formats", action="store_true", help="list supported input formats and exit")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _discover(inputs: List[Path], recursive: bool, output: Optional[Path]) -> Iterator[Job]:
    exts = registry()
    for item in inputs:
        if item.is_file():
            dst_dir = output if output else item.parent
            yield item, dst_dir / (item.stem + ".webp")
        elif item.is_dir():
            files = item.rglob("*") if recursive else item.iterdir()
            for f in sorted(files):
                if not f.is_file() or f.suffix.lower() not in exts or f.suffix.lower() == ".webp":
                    continue
                if output:
                    dst_dir = output / f.parent.relative_to(item)
                else:
                    dst_dir = f.parent
                yield f, dst_dir / (f.stem + ".webp")
        else:
            print(f"warning: not found: {item}", file=sys.stderr)


def _worker(src: Path, dst: Path, opts: Options, delete_original: bool) -> Tuple[int, int]:
    in_size = src.stat().st_size
    out_size = convert(src, dst, opts)
    if delete_original and src.resolve() != dst.resolve():
        src.unlink()
    return in_size, out_size


def _human(n: float) -> str:
    sign = "-" if n < 0 else ""
    n = abs(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{sign}{n:.1f} {unit}"
        n /= 1024
    return f"{sign}{n:.1f} TB"


def _list_formats() -> int:
    exts = sorted(registry())
    print(f"Supported input extensions ({len(exts)}):")
    line = ""
    for e in exts:
        if len(line) + len(e) + 1 > 78:
            print("  " + line)
            line = ""
        line += e + " "
    if line:
        print("  " + line)
    print("\nOptional plugins:")
    for name, err in plugin_status().items():
        print(f"  [{'x' if err is None else ' '}] {name}" + ("" if err is None else f"  ({err})"))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_formats:
        return _list_formats()
    if not args.inputs:
        build_parser().error("no inputs given")

    opts = Options(
        quality=args.quality,
        lossless=args.lossless,
        method=args.method,
        max_size=args.max_size,
        keep_metadata=args.keep_metadata,
    )

    jobs: List[Job] = []
    skipped = 0
    seen = set()
    for src, dst in _discover(args.inputs, args.recursive, args.output):
        if dst in seen:
            print(f"skip (duplicate output name): {src}", file=sys.stderr)
            skipped += 1
            continue
        seen.add(dst)
        if dst.exists() and not args.overwrite:
            if args.verbose:
                print(f"skip (exists): {dst}")
            skipped += 1
            continue
        jobs.append((src, dst))

    if args.dry_run:
        for src, dst in jobs:
            print(f"{src} -> {dst}")
        print(f"\n{len(jobs)} to convert, {skipped} skipped (dry run)")
        return 0

    converted = failed = 0
    total_in = total_out = 0
    workers = max(1, min(args.jobs, len(jobs) or 1))

    def report(src: Path, dst: Path, result=None, error=None) -> None:
        nonlocal converted, failed, total_in, total_out
        if error is not None:
            failed += 1
            print(f"FAIL {src}: {error}", file=sys.stderr)
            return
        converted += 1
        in_size, out_size = result
        total_in += in_size
        total_out += out_size
        if args.verbose:
            print(f"ok   {src} -> {dst} ({_human(in_size)} -> {_human(out_size)})")

    if workers == 1:
        for src, dst in jobs:
            try:
                report(src, dst, _worker(src, dst, opts, args.delete_original))
            except Exception as exc:
                report(src, dst, error=exc)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_worker, src, dst, opts, args.delete_original): (src, dst)
                for src, dst in jobs
            }
            for fut in as_completed(futures):
                src, dst = futures[fut]
                try:
                    report(src, dst, fut.result())
                except Exception as exc:
                    report(src, dst, error=exc)

    saved = total_in - total_out
    pct = f" ({saved / total_in * 100:.1f}%)" if total_in else ""
    print(
        f"Converted: {converted}, skipped: {skipped}, failed: {failed}. "
        f"{_human(total_in)} -> {_human(total_out)}, saved {_human(saved)}{pct}"
    )
    return 1 if failed else 0
