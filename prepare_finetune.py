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
import sqlite3

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(REPO_ROOT, "backend", "sql_app.db")
OUTPUT_DIR = os.path.join(REPO_ROOT, "finetune_channel_2")
SPEAKER = "sarah"
CHANNEL_ID = 2


def main():
    os.makedirs(os.path.join(OUTPUT_DIR, "wavs"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "labels"), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ac.chunk_id, ac.file_path, ac.transcript_text, ac.duration
        FROM audio_chunks ac
        JOIN videos v ON ac.video_id = v.id
        WHERE v.channel_id = ?
          AND ac.transcript_text IS NOT NULL
          AND ac.transcript_text != ''
        ORDER BY ac.id
        """,
        (CHANNEL_ID,),
    )
    rows = cur.fetchall()
    conn.close()

    print(f"Found {len(rows)} chunks with transcriptions")

    metadata_path = os.path.join(OUTPUT_DIR, "metadata.csv")
    skipped = 0
    written = 0

    with open(metadata_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["wav_path", "text", "speaker", "duration"])

        for chunk_id, db_path, text, duration in rows:
            # Convert Docker path (/app/data/...) to local path
            relative = db_path.replace("/app/data/", "")
            local_path = os.path.join(REPO_ROOT, "data", relative)

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
                f.write(text.strip())

            # Write metadata row
            writer.writerow([f"wavs/{wav_name}", text.strip(), SPEAKER, round(duration, 3)])
            written += 1

    print(f"Done: {written} samples written, {skipped} skipped (file not found)")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
