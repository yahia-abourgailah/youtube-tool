"""Dataset quality checks shared by the QA API and tests."""

import re
from typing import Iterable, Optional

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

ISSUE_LABELS = {
    "missing_audio": "Audio file is missing on disk",
    "empty_transcript": "Chunk has no transcript",
    "short_transcript": "Transcript is suspiciously short",
    "no_arabic": "Transcript contains no Arabic characters",
    "too_slow": "Transcript is far too short for the audio duration",
    "too_dense": "Transcript is far too long for the audio duration",
    "very_short_chunk": "Audio chunk is shorter than 0.5s but has a transcript",
}


def classify_chunk(
    text: Optional[str],
    duration: Optional[float],
    file_exists: bool,
    min_chars: int = 2,
    min_chars_per_second: float = 0.3,
    max_chars_per_second: float = 25.0,
) -> list[str]:
    """Return issue codes for one chunk."""
    issues: list[str] = []
    if not file_exists:
        issues.append("missing_audio")

    cleaned = (text or "").strip()
    if not cleaned:
        issues.append("empty_transcript")
        return issues

    if len(cleaned) < max(1, min_chars):
        issues.append("short_transcript")

    if not ARABIC_RE.search(cleaned):
        issues.append("no_arabic")

    if duration and duration > 0:
        chars_per_second = len(cleaned) / duration
        if chars_per_second < min_chars_per_second:
            issues.append("too_slow")
        elif chars_per_second > max_chars_per_second:
            issues.append("too_dense")
        if duration < 0.5:
            issues.append("very_short_chunk")

    return issues


def issue_counts(issues: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {code: 0 for code in ISSUE_LABELS}
    for code in issues:
        counts[code] = counts.get(code, 0) + 1
    return counts
