"""``image-to-webp`` command-line interface."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from . import __version__
from .batch import CONVERTED, FAILED, PENDING, SKIPPED, ConversionResult, convert_many, plan_conversions
from .loaders import plugin_status, supported_extensions
from .options import ConversionOptions

_EXTRA_LABELS = {"heif": "HEIC / HEIF / AVIF", "raw": "camera RAW", "svg": "SVG"}


def _parse_size(value: str) -> Tuple[int, int]:
    try:
        w, h = value.lower().split("x")
        size = (int(w), int(h))
        if size[0] <= 0 or size[1] <= 0:
            raise ValueError
        return size
    except ValueError:
        raise argparse.ArgumentTypeError("expected WIDTHxHEIGHT, e.g. 1920x1080") from None


def _int_range(lo: int, hi: int):
    def check(value: str) -> int:
        try:
            n = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"expected an integer, got {value!r}") from None
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
    p.add_argument("-j", "--jobs", type=_int_range(1, 1024), default=os.cpu_count() or 1,
                   help="parallel workers (default: CPU count)")
    p.add_argument("--dry-run", action="store_true", help="show what would be converted")
    p.add_argument("-v", "--verbose", action="store_true", help="print every file")
    p.add_argument("--list-formats", action="store_true", help="list supported input formats and exit")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _human(n: float) -> str:
    sign = "-" if n < 0 else ""
    n = abs(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{sign}{n:.1f} {unit}"
        n /= 1024
    return f"{sign}{n:.1f} TB"


def _list_formats() -> int:
    exts = sorted(supported_extensions())
    print(f"Supported input extensions ({len(exts)}):")
    line = ""
    for e in exts:
        if len(line) + len(e) + 1 > 78:
            print("  " + line.rstrip())
            line = ""
        line += e + " "
    if line:
        print("  " + line.rstrip())
    print("\nOptional plugins:")
    for name, err in plugin_status().items():
        label = f"{name} ({_EXTRA_LABELS.get(name, name)})"
        if err is None:
            print(f"  [x] {label}")
        else:
            print(f"  [ ] {label}: {err}  -> pip install 'image-to-webp[{name}]'")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_formats:
        return _list_formats()
    if not args.inputs:
        parser.error("no inputs given")

    options = ConversionOptions(
        quality=args.quality,
        lossless=args.lossless,
        method=args.method,
        max_size=args.max_size,
        keep_metadata=args.keep_metadata,
    )

    if args.dry_run:
        planned = plan_conversions(args.inputs, args.output, recursive=args.recursive, overwrite=args.overwrite)
        for r in planned:
            if r.status == PENDING:
                print(f"{r.src} -> {r.dst}")
            elif args.verbose or r.status == FAILED:
                print(f"{r.status}: {r.src} ({r.error})", file=sys.stderr if r.status == FAILED else sys.stdout)
        n = sum(r.status == PENDING for r in planned)
        print(f"\n{n} to convert, {sum(r.status == SKIPPED for r in planned)} skipped (dry run)")
        return 1 if any(r.status == FAILED for r in planned) else 0

    def report(r: ConversionResult) -> None:
        if r.status == FAILED:
            print(f"FAIL {r.src}: {r.error}", file=sys.stderr)
        elif r.status == SKIPPED:
            if args.verbose or r.error == "duplicate output name":
                print(f"skip {r.src} ({r.error})", file=sys.stdout if args.verbose else sys.stderr)
        elif r.status == CONVERTED and args.verbose:
            print(f"ok   {r.src} -> {r.dst} ({_human(r.in_size)} -> {_human(r.out_size)})")

    summary = convert_many(
        args.inputs,
        args.output,
        options,
        recursive=args.recursive,
        overwrite=args.overwrite,
        delete_original=args.delete_original,
        jobs=args.jobs,
        on_result=report,
    )

    pct = f" ({summary.bytes_saved / summary.bytes_in * 100:.1f}%)" if summary.bytes_in else ""
    print(
        f"Converted: {summary.converted}, skipped: {summary.skipped}, failed: {summary.failed}. "
        f"{_human(summary.bytes_in)} -> {_human(summary.bytes_out)}, saved {_human(summary.bytes_saved)}{pct}"
    )
    return 0 if summary.ok else 1
