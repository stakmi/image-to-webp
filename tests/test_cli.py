from __future__ import annotations

import subprocess
import sys

import pytest

from image_to_webp.cli import main


def test_success_and_summary(samples, tmp_path, capsys):
    assert main([str(samples), "-r", "-o", str(tmp_path / "o"), "-j", "1", "-v"]) == 0
    out = capsys.readouterr().out
    assert "Converted: 10, skipped: 0, failed: 0" in out
    assert "ok   " in out


def test_failure_exit_code(broken, capsys):
    assert main([str(broken), "-j", "1"]) == 1
    assert "FAIL" in capsys.readouterr().err


def test_dry_run_writes_nothing(samples, capsys):
    assert main([str(samples), "--dry-run"]) == 0
    assert "8 to convert" in capsys.readouterr().out
    assert not list(samples.glob("*.webp"))


def test_list_formats(capsys):
    assert main(["--list-formats"]) == 0
    out = capsys.readouterr().out
    assert ".png" in out and "Optional plugins" in out


@pytest.mark.parametrize("args", [[], ["x.png", "-q", "200"], ["x.png", "--max-size", "big"]])
def test_bad_args(args):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2


def test_python_m(tmp_path):
    r = subprocess.run([sys.executable, "-m", "image_to_webp", "--version"], capture_output=True, text=True)
    assert r.returncode == 0 and "0.1.0" in r.stdout
