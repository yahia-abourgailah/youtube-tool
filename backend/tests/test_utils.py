"""Unit tests for pure helpers (no database or ASR service required)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.utils.csv_safety import neutralize_csv_formula
from app.utils import paths, qa


def test_neutralize_csv_formula_prefixes_dangerous_cells():
    assert neutralize_csv_formula("=SUM(A1:A2)") == "'=SUM(A1:A2)"
    assert neutralize_csv_formula("+1") == "'+1"
    assert neutralize_csv_formula("-cmd") == "'-cmd"
    assert neutralize_csv_formula("@user") == "'@user"
    assert neutralize_csv_formula("\tindented") == "'\tindented"


def test_neutralize_csv_formula_keeps_normal_cells():
    assert neutralize_csv_formula("مرحبا") == "مرحبا"
    assert neutralize_csv_formula(12.5) == 12.5
    assert neutralize_csv_formula(None) is None


def test_resolve_relative_and_docker_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))

    relative = paths.resolve("./data/channels/1/videos/abc/abc_chunk_1.wav")
    assert relative == os.path.join(str(tmp_path), "channels/1/videos/abc/abc_chunk_1.wav")

    docker = paths.resolve("/app/data/channels/1/videos/abc/abc_chunk_1.wav")
    assert docker == relative

    assert paths.transcript_path("./data/channels/1/videos/abc/abc_chunk_1.wav") == (
        os.path.join(str(tmp_path), "channels/1/videos/abc/abc_chunk_1.txt")
    )


def test_classify_chunk_flags_common_problems():
    assert "missing_audio" in qa.classify_chunk("مرحبا", 2.0, file_exists=False)
    assert "empty_transcript" in qa.classify_chunk("", 2.0, file_exists=True)
    assert "no_arabic" in qa.classify_chunk("hello world", 2.0, file_exists=True)
    assert "too_dense" in qa.classify_chunk("ا" * 100, 1.0, file_exists=True)
    assert "too_slow" in qa.classify_chunk("ا", 60.0, file_exists=True)
    assert "very_short_chunk" in qa.classify_chunk("ا", 0.2, file_exists=True)


def test_classify_chunk_accepts_healthy_chunk():
    assert qa.classify_chunk("السلام عليكم ورحمة الله", 2.0, file_exists=True) == []
