import glob
import json
import os
import shutil
from datetime import datetime, timezone
from typing import Optional

from ..celery_app import celery_app
from .. import models, database
from ..utils import dataset, logging as activity_log, slack, paths
import logging

logger = logging.getLogger(__name__)


def _save_splits(hf_dataset, export_path: str, val_ratio: float, test_ratio: float):
    """Save train/val/test parquet files per channel subset.

    Returns ``(files_written, split_counts)``.
    """
    from datasets import DatasetDict

    if not isinstance(hf_dataset, DatasetDict):
        return 0, {}

    written = 0
    counts = {}
    holdout = max(0.0, val_ratio) + max(0.0, test_ratio)
    if holdout <= 0 or holdout >= 1:
        return 0, {}

    for name, ds in hf_dataset.items():
        if len(ds) < 3 or holdout * len(ds) < 2:
            # Too small to split; keep the data as a single train file rather
            # than silently dropping this channel from the export.
            logger.warning(f"Skipping split for '{name}': only {len(ds)} samples")
            ds.to_parquet(f"{export_path}_{name}_train.parquet")
            written += 1
            counts[name] = {"train": len(ds)}
            continue

        first = ds.train_test_split(test_size=holdout, seed=42)
        train, rest = first["train"], first["test"]

        test = None
        val = rest
        if test_ratio > 0 and len(rest) >= 2:
            share = test_ratio / holdout
            second = rest.train_test_split(test_size=share, seed=42)
            val, test = second["train"], second["test"]

        train.to_parquet(f"{export_path}_{name}_train.parquet")
        written += 1
        counts[name] = {"train": len(train)}

        if len(val):
            val.to_parquet(f"{export_path}_{name}_val.parquet")
            written += 1
            counts[name]["val"] = len(val)
        if test is not None and len(test):
            test.to_parquet(f"{export_path}_{name}_test.parquet")
            written += 1
            counts[name]["test"] = len(test)

    return written, counts


def _write_manifest(data_dir: str, chunks_by_channel: dict, split_counts: dict, split: bool,
                    val_ratio: float, test_ratio: float, skipped_chunks: int) -> str:
    """Write a machine-readable manifest next to the parquet files."""
    channels = {}
    for name, rows in chunks_by_channel.items():
        channels[name] = {
            "chunks": len(rows),
            "display_name": rows[0].get("channel_name") if rows else None,
            "speaker": rows[0].get("speaker") if rows else None,
            "channel_url": rows[0].get("channel_url") if rows else None,
            "splits": split_counts.get(name, {"train": len(rows)}),
        }

    files = sorted(
        os.path.basename(path)
        for path in glob.glob(os.path.join(data_dir, "hf_dataset*.parquet"))
    )
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_chunks": sum(len(rows) for rows in chunks_by_channel.values()),
        "skipped_missing_audio": skipped_chunks,
        "split": split,
        "val_ratio": val_ratio,
        "test_ratio": test_ratio,
        "channels": channels,
        "files": files,
    }
    manifest_path = os.path.join(data_dir, "hf_dataset_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest_path


@celery_app.task(bind=True)
def export_dataset_task(
    self,
    job_id: int,
    repo_id: Optional[str] = None,
    hf_token: Optional[str] = None,
    private: bool = True,
    channel_ids: Optional[list[int]] = None,
    channel_names: Optional[dict[str, str]] = None,
    split: bool = False,
    val_ratio: float = 0.05,
    test_ratio: float = 0.05,
):
    """Export transcribed chunks to a HuggingFace dataset with channel-based subsets."""
    db = database.SessionLocal()
    try:
        job = db.query(models.Job).filter(models.Job.id == job_id).first()
        if not job:
            return "Job not found"

        activity_log.log_activity(db, "Starting dataset export...", level="info")
        job.status = "processing"
        db.commit()

        # Get channels
        query = db.query(models.Channel)
        if channel_ids:
            query = query.filter(models.Channel.id.in_(channel_ids))

        channels = query.all()

        if not channels:
            raise Exception("No channels found in database")

        chunks_by_channel = {}
        total_chunks = 0
        skipped_chunks = 0

        for channel in channels:
            # Only export chunks that actually have a transcript and an audio file
            chunks = db.query(models.AudioChunk).join(
                models.Video
            ).filter(
                models.Video.channel_id == channel.id,
                models.AudioChunk.transcript_text != None,
                models.AudioChunk.transcript_text != "",
            ).all()

            if not chunks:
                logger.warning(f"No transcribed chunks found for channel: {channel.name or channel.url}")
                continue

            # Determine folder name for channel subset
            channel_name = channel.name or f"channel_{channel.id}"

            # Override with custom name if provided
            if channel_names and str(channel.id) in channel_names:
                custom_name = channel_names[str(channel.id)].strip()
                if custom_name:
                    import re
                    # Sanitize folder name: remove special chars, replace spaces with underscores
                    # Allow alphanumeric, underscore, hyphen
                    custom_name = re.sub(r'[^a-zA-Z0-9_\-]', '', custom_name.replace(' ', '_'))
                    if custom_name:
                        channel_name = custom_name

            chunks_data = []

            for chunk in chunks:
                audio_path = paths.resolve(chunk.file_path)
                if not chunk.file_path or not os.path.exists(audio_path):
                    skipped_chunks += 1
                    continue
                chunks_data.append({
                    "chunk_id": chunk.chunk_id,
                    "audio": audio_path,
                    "transcript_text": chunk.transcript_text,
                    "duration": chunk.duration,
                    "original_video_id": chunk.video.video_id,
                    "channel_name": channel_name,
                    "channel_url": channel.url,
                    "speaker": channel.speaker,
                    "asr_model": chunk.asr_model,
                    "asr_version": chunk.asr_version,
                    "confidence": chunk.confidence,
                    "language": chunk.language,
                })

            if not chunks_data:
                continue

            # Key subsets by the same sanitized name the DatasetDict uses, so the
            # manifest's split counts line up with the saved files. Non-Latin
            # names (e.g. Arabic) sanitize to "unknown", so make the key unique
            # instead of silently overwriting an earlier channel.
            base_name = dataset.sanitize_config_name(channel_name)
            config_name = base_name
            suffix = 2
            while config_name in chunks_by_channel:
                config_name = f"{base_name}_{suffix}"
                suffix += 1
            chunks_by_channel[config_name] = chunks_data
            total_chunks += len(chunks_data)
            logger.info(f"Channel '{config_name}': {len(chunks_data)} chunks")

        if not chunks_by_channel:
            raise Exception("No transcribed chunks with audio files found for any channel")

        activity_log.log_activity(
            db,
            f"Creating dataset with {len(chunks_by_channel)} channel subsets ({total_chunks} total chunks, "
            f"{skipped_chunks} skipped for missing audio)...",
            level="info"
        )

        # Create dataset with channel-based subsets
        hf_dataset = dataset.create_hf_dataset_with_subsets(chunks_by_channel)
        if not hf_dataset:
            raise Exception("Failed to create dataset object")

        # Save locally first. This must not depend on a Hub token or a successful push.
        data_dir = paths.data_path()
        os.makedirs(data_dir, exist_ok=True)
        export_path = os.path.join(data_dir, "hf_dataset")

        # Remove files from a previous export so a split export does not silently
        # ship stale non-split parquet files (and vice versa), and so removed
        # channels do not linger in the Arrow directory.
        for stale in glob.glob(os.path.join(data_dir, "hf_dataset*.parquet")):
            try:
                os.remove(stale)
            except OSError as exc:
                logger.warning(f"Could not remove old export {stale}: {exc}")
        if os.path.isdir(export_path):
            try:
                shutil.rmtree(export_path)
            except OSError as exc:
                logger.warning(f"Could not remove old Arrow export {export_path}: {exc}")

        written, split_counts = (
            _save_splits(hf_dataset, export_path, val_ratio, test_ratio) if split else (0, {})
        )
        if written:
            activity_log.log_activity(
                db, f"Saved {written} split parquet file(s) under {data_dir}.", level="info"
            )
        else:
            local_path, parquet_path = dataset.save_dataset_locally(hf_dataset, export_path)
            if not local_path:
                raise Exception("Failed to save dataset locally")
            activity_log.log_activity(db, f"Dataset saved locally at {parquet_path}", level="info")

        manifest_path = _write_manifest(
            data_dir, chunks_by_channel, split_counts, split, val_ratio, test_ratio, skipped_chunks
        )
        activity_log.log_activity(db, f"Dataset manifest written to {manifest_path}", level="info")

        # Push to the Hub only when both a repo and a token are provided
        if repo_id and hf_token:
            activity_log.log_activity(db, f"Pushing dataset to Hub: {repo_id}...", level="info")
            success = dataset.push_to_hub(hf_dataset, repo_id, hf_token, private=private)
            if not success:
                raise Exception("Failed to push dataset to HuggingFace Hub. Check logs for details.")

            activity_log.log_activity(db, "Successfully pushed to HuggingFace Hub!", level="success")

            subset_list = "\n".join([f"  • {name} ({len(data)} chunks)" for name, data in chunks_by_channel.items()])
            slack.notify_slack(
                f"✅ *Dataset Export Completed*\n"
                f"Repository: {repo_id}\n"
                f"Total Chunks: {total_chunks}\n"
                f"Channel Subsets ({len(chunks_by_channel)}):\n{subset_list}\n"
                f"Private: {private}"
            )
        elif repo_id and not hf_token:
            activity_log.log_activity(
                db, "No HuggingFace token provided; skipping Hub push and exporting locally.", level="warning"
            )

        job.status = "completed"
        job.progress = 100
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error exporting dataset: {e}", exc_info=True)
        if 'job' in locals() and job:
            activity_log.log_activity(db, f"Dataset export failed: {str(e)}", level="error")
            job.status = "failed"
            db.commit()

            # Send Slack notification on failure
            slack.notify_slack(
                f"🚨 *Dataset Export Failed*\n"
                f"Error: {str(e)}"
            )
        return str(e)
    finally:
        db.close()

    return "Export completed"
