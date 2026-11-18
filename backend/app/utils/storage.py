"""Filesystem helpers for deleting video/channel data safely."""

import logging
import os
import shutil

from . import paths

logger = logging.getLogger(__name__)


def remove_file(path: str) -> bool:
    if not path:
        return False
    try:
        if os.path.isfile(path):
            os.remove(path)
            return True
    except OSError as exc:
        logger.warning(f"Could not delete {path}: {exc}")
    return False


def delete_chunk_files(chunk) -> None:
    """Delete a chunk's audio file and its transcript sidecar."""
    if not chunk or not chunk.file_path:
        return
    audio_path = paths.resolve(chunk.file_path)
    remove_file(audio_path)
    remove_file(paths.transcript_path(chunk.file_path))


def delete_video_dir(channel_id, video_id) -> None:
    """Delete a whole per-video directory (chunks, sidecars, metadata)."""
    directory = paths.video_dir(channel_id, video_id)
    if os.path.isdir(directory):
        try:
            shutil.rmtree(directory)
            return
        except OSError as exc:
            logger.warning(f"Could not remove {directory}: {exc}")

    # Fallback for legacy layouts where files sat directly under data/.
    legacy_dir = paths.data_path()
    for suffix in ("_audio.wav", "_audio.mp4", "_audio.webm", "_audio.m4a", "_audio.mp3", "_transcript.txt", "_metadata.json"):
        remove_file(os.path.join(legacy_dir, f"{video_id}{suffix}"))


def delete_video_files(video) -> None:
    if video:
        delete_video_dir(video.channel_id, video.video_id)


def delete_channel_files(channel) -> None:
    """Delete a channel's whole directory tree."""
    if not channel:
        return
    delete_channel_dir(channel.id)


def delete_channel_dir(channel_id) -> None:
    directory = paths.channel_dir(channel_id)
    if os.path.isdir(directory):
        try:
            shutil.rmtree(directory)
        except OSError as exc:
            logger.warning(f"Could not remove {directory}: {exc}")


def cleanup_video_sources(video) -> int:
    """Remove raw download/legacy files but keep processed chunks and metadata.

    Returns the number of files deleted.
    """
    if not video:
        return 0
    deleted = 0
    directory = paths.video_dir(video.channel_id, video.video_id)
    for suffix in ("_audio.wav", "_audio.mp4", "_audio.webm", "_audio.m4a", "_audio.mp3", "_transcript.txt"):
        if remove_file(os.path.join(directory, f"{video.video_id}{suffix}")):
            deleted += 1

    # Legacy location (data/ root)
    for suffix in ("_audio.wav", "_audio.mp4", "_audio.webm", "_audio.m4a", "_audio.mp3", "_transcript.txt"):
        if remove_file(os.path.join(paths.data_path(), f"{video.video_id}{suffix}")):
            deleted += 1
    return deleted
