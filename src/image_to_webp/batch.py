"""Convert many files, optionally in parallel."""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional, Union

from .converter import PathLike, convert_file, default_output_path
from .loaders import supported_extensions
from .options import ConversionOptions, resolve_options

PENDING = "pending"
CONVERTED = "converted"
SKIPPED = "skipped"
FAILED = "failed"


@dataclass
class ConversionResult:
    """Outcome for one input file.

    ``status`` is one of ``"pending"`` (planned only), ``"converted"``, ``"skipped"`` or ``"failed"``.
    """

    src: Path
    dst: Optional[Path]
    status: str = PENDING
    in_size: int = 0
    out_size: int = 0
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status in (CONVERTED, SKIPPED)


@dataclass
class BatchSummary:
    """Aggregate result of :func:`convert_many`."""

    results: List[ConversionResult] = field(default_factory=list)

    def _count(self, status: str) -> int:
        return sum(r.status == status for r in self.results)

    @property
    def converted(self) -> int:
        return self._count(CONVERTED)

    @property
    def skipped(self) -> int:
        return self._count(SKIPPED)

    @property
    def failed(self) -> int:
        return self._count(FAILED)

    @property
    def bytes_in(self) -> int:
        return sum(r.in_size for r in self.results if r.status == CONVERTED)

    @property
    def bytes_out(self) -> int:
        return sum(r.out_size for r in self.results if r.status == CONVERTED)

    @property
    def bytes_saved(self) -> int:
        return self.bytes_in - self.bytes_out

    @property
    def ok(self) -> bool:
        return self.failed == 0


def _as_list(inputs: Union[PathLike, Iterable[PathLike]]) -> List[Path]:
    if isinstance(inputs, (str, os.PathLike)):
        return [Path(inputs)]
    return [Path(p) for p in inputs]


def plan_conversions(
    inputs: Union[PathLike, Iterable[PathLike]],
    output_dir: Optional[PathLike] = None,
    *,
    recursive: bool = False,
    overwrite: bool = False,
) -> List[ConversionResult]:
    """Work out what :func:`convert_many` would do, without converting anything.

    Files given explicitly are always included; files found in directories are
    included only if their extension is supported (and not already ``.webp``).
    Output paths mirror the directory tree under ``output_dir`` when given.
    """
    exts = supported_extensions()
    out_root = Path(output_dir) if output_dir is not None else None
    results: List[ConversionResult] = []
    seen: set = set()

    def add(src: Path, dst: Path) -> None:
        key = os.path.normcase(os.path.abspath(dst))
        if key in seen:
            results.append(ConversionResult(src, dst, SKIPPED, error="duplicate output name"))
        elif dst.exists() and not overwrite:
            results.append(ConversionResult(src, dst, SKIPPED, error="output exists"))
        else:
            results.append(ConversionResult(src, dst))
        seen.add(key)

    for item in _as_list(inputs):
        if item.is_file():
            add(item, (out_root / f"{item.stem}.webp") if out_root else default_output_path(item))
        elif item.is_dir():
            files = item.rglob("*") if recursive else item.iterdir()
            for f in sorted(files):
                ext = f.suffix.lower()
                if ext == ".webp" or ext not in exts or not f.is_file():
                    continue
                dst_dir = out_root / f.parent.relative_to(item) if out_root else f.parent
                add(f, dst_dir / f"{f.stem}.webp")
        else:
            results.append(ConversionResult(item, None, FAILED, error="no such file or directory"))
    return results


def _run_one(src: Path, dst: Path, opts: ConversionOptions, delete_original: bool) -> ConversionResult:
    try:
        in_size = src.stat().st_size
        convert_file(src, dst, opts)
        if delete_original and src.resolve() != dst.resolve():
            src.unlink()
        return ConversionResult(src, dst, CONVERTED, in_size, dst.stat().st_size)
    except Exception as exc:
        return ConversionResult(src, dst, FAILED, error=str(exc) or type(exc).__name__)


def convert_many(
    inputs: Union[PathLike, Iterable[PathLike]],
    output_dir: Optional[PathLike] = None,
    options: Optional[ConversionOptions] = None,
    *,
    recursive: bool = False,
    overwrite: bool = False,
    delete_original: bool = False,
    jobs: Optional[int] = None,
    on_result: Optional[Callable[[ConversionResult], None]] = None,
    **kwargs: Any,
) -> BatchSummary:
    """Convert files and/or directories to WebP.

    Args:
        inputs: a path or iterable of paths (files or directories).
        output_dir: where to write output; default is next to each source.
        options: :class:`ConversionOptions`; keyword overrides (``quality=...``) are also accepted.
        recursive: descend into sub-directories.
        overwrite: replace existing ``.webp`` files (default: skip them).
        delete_original: remove each source after it converts successfully.
        jobs: worker processes (default: CPU count; 1 = run in this process).
        on_result: called with each :class:`ConversionResult` as it completes (in the calling process).

    Individual failures never raise; check :attr:`BatchSummary.failed`.
    """
    opts = resolve_options(options, kwargs)
    planned = plan_conversions(inputs, output_dir, recursive=recursive, overwrite=overwrite)
    summary = BatchSummary()

    def done(result: ConversionResult) -> None:
        summary.results.append(result)
        if on_result is not None:
            on_result(result)

    todo = []
    for r in planned:
        if r.status == PENDING:
            todo.append(r)
        else:
            done(r)

    workers = max(1, min(jobs or os.cpu_count() or 1, len(todo) or 1))
    if workers == 1:
        for r in todo:
            done(_run_one(r.src, r.dst, opts, delete_original))  # type: ignore[arg-type]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_run_one, r.src, r.dst, opts, delete_original): r for r in todo}
            for fut in as_completed(futures):
                r = futures[fut]
                try:
                    done(fut.result())
                except Exception as exc:  # worker crashed
                    done(ConversionResult(r.src, r.dst, FAILED, error=str(exc) or type(exc).__name__))
    return summary
