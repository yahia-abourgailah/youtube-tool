#!/usr/bin/env python3
"""
Prepare fine-tuning dataset from channel 2 audio chunks.

Creates:
  data/channels/2/finetune/
  ├── wavs/         - all .wav files
  ├── labels/       - .txt files with transcription (same name as wav)
  └── metadata.csv  - wav_path | text | speaker | duration
"""

import csv
import os
import shutil

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(REPO_ROOT, ".env"))
DATABASE_URL = os.environ["DATABASE_URL"]
DATA_PATH = os.path.abspath(os.getenv("DATA_PATH", os.path.join(REPO_ROOT, "data")))
OUTPUT_DIR = os.path.abspath(
    os.getenv("FINETUNE_OUTPUT_DIR", os.path.join(REPO_ROOT, "finetune_channel_2"))
)
SPEAKER = os.getenv("FINETUNE_SPEAKER", "sarah")
CHANNEL_ID = int(os.getenv("FINETUNE_CHANNEL_ID", "2"))


def resolve_chunk_path(db_path: str) -> str:
    """Resolve a stored chunk path, tolerating relative and Docker-style values."""
    normalized = (db_path or "").replace("\\", "/")
    if normalized.startswith("/app/data/"):
        normalized = normalized[len("/app/data/"):]
    elif normalized.startswith("data/"):
        normalized = normalized[len("data/"):]
    return os.path.join(DATA_PATH, normalized.lstrip("./"))


def main():
    os.makedirs(os.path.join(OUTPUT_DIR, "wavs"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "labels"), exist_ok=True)

    engine = create_engine(DATABASE_URL)
    query = text(
        """
        SELECT ac.chunk_id, ac.file_path, ac.transcript_text, ac.duration
        FROM audio_chunks ac
        JOIN videos v ON ac.video_id = v.id
        WHERE v.channel_id = :channel_id
          AND ac.transcript_text IS NOT NULL
          AND ac.transcript_text != ''
        ORDER BY ac.id
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"channel_id": CHANNEL_ID}).fetchall()

    print(f"Found {len(rows)} chunks with transcriptions")

    metadata_path = os.path.join(OUTPUT_DIR, "metadata.csv")
    skipped = 0
    written = 0

    with open(metadata_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["wav_path", "text", "speaker", "duration"])

        for chunk_id, db_path, transcript, duration in rows:
            local_path = resolve_chunk_path(db_path)

            if not os.path.exists(local_path):
                skipped += 1
                continue

            wav_name = f"{chunk_id}.wav"
            txt_name = f"{chunk_id}.txt"

            # Copy wav
            dst_wav = os.path.join(OUTPUT_DIR, "wavs", wav_name)
            if not os.path.exists(dst_wav):
                shutil.copy2(local_path, dst_wav)

            # Write label
            dst_txt = os.path.join(OUTPUT_DIR, "labels", txt_name)
            with open(dst_txt, "w", encoding="utf-8") as f:
                f.write(transcript.strip())

            # Write metadata row
            writer.writerow([f"wavs/{wav_name}", transcript.strip(), SPEAKER, round(duration, 3)])
            written += 1

    print(f"Done: {written} samples written, {skipped} skipped (file not found)")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
