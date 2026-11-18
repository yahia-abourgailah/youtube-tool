"""Central path helpers.

The database stores chunk paths as ``./data/channels/...`` (older rows) and the
data directory can be configured with a relative ``DATA_PATH``. Resolving both
through these helpers keeps Docker (``/app``) and local runs (``backend/``)
consistent instead of depending on the current working directory.
"""

import os


def data_path() -> str:
    """Absolute path of the data directory."""
    return os.path.abspath(os.getenv("DATA_PATH", "data"))


def channel_dir(channel_id) -> str:
    return os.path.join(data_path(), "channels", str(channel_id))


def video_dir(channel_id, video_id) -> str:
    return os.path.join(channel_dir(channel_id), "videos", str(video_id))


def resolve(path: str) -> str:
    """Resolve a path stored in the database to an absolute path."""
    if not path:
        return path
    if os.path.isabs(path):
        # Rows created inside Docker start with /app/data. Remap them when the
        # project is run locally so downloads/streaming keep working.
        normalized = path.replace("\\", "/")
        marker = "/data/"
        if normalized.startswith("/app/data/"):
            return os.path.join(data_path(), normalized[len("/app/data/"):])
        if marker in normalized and normalized.startswith("/app/"):
            return os.path.join(data_path(), normalized.split(marker, 1)[1])
        return path

    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]

    # Older rows were stored relative to the project root as "data/..."
    if normalized == "data" or normalized.startswith("data/"):
        return os.path.join(data_path(), normalized[len("data"):].lstrip("/"))

    return os.path.abspath(path)


def transcript_path(audio_file_path: str) -> str:
    """Sidecar .txt file next to a chunk's .wav file."""
    return os.path.splitext(resolve(audio_file_path))[0] + ".txt"
