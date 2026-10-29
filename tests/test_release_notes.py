"""Unit tests for scripts/extract-release-notes.py (BK-0044)."""

import subprocess
import sys
from pathlib import Path


def test_extract_release_notes_current_version():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "extract-release-notes.py"
    res = subprocess.run(
        [sys.executable, str(script_path), "--version", "0.3.0"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "# 🚀 bdpan-cli v0.3.0 发布说明" in res.stdout
    assert "uv tool install bdpan-cli@0.3.0" in res.stdout
    assert "pip install --upgrade bdpan-cli==0.3.0" in res.stdout
    assert "bdpan-linux-amd64" in res.stdout
    assert "BK-0045" in res.stdout
    assert "BaiduPan" in res.stdout


def test_extract_release_notes_previous_version():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "extract-release-notes.py"
    res = subprocess.run(
        [sys.executable, str(script_path), "--version", "0.2.0"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "# 🚀 bdpan-cli v0.2.0 发布说明" in res.stdout
    assert "uv tool install bdpan-cli@0.2.0" in res.stdout
    assert "pip install --upgrade bdpan-cli==0.2.0" in res.stdout
    assert "BK-0043" in res.stdout
    assert "bdpan auth config" in res.stdout


def test_extract_release_notes_to_file(tmp_path):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "extract-release-notes.py"
    out_file = tmp_path / "RELEASE_NOTES.md"
    res = subprocess.run(
        [sys.executable, str(script_path), "--tag", "v0.1.0", "--output", str(out_file)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "# 🚀 bdpan-cli v0.1.0 发布说明" in content
    assert "BK-0042" in content
