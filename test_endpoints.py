import requests
import os
import sys
import time
import json
import subprocess
import tempfile
from pathlib import Path

# ─── AUDIO FILES TO TEST ─────────────────────────────────────────────
AUDIO_FOLDER = "/home/yahia/Desktop/github-repos/youtube-audio-extractor/data/channels/1/videos/-hIgi5DXI3M/"
NUM_TEST_FILES = 3  # how many files to test

# ─── ENDPOINTS CONFIGURATION ─────────────────────────────────────────
# Add/remove/edit endpoints here. Each entry needs:
#   name     : display name
#   url      : full endpoint URL
#   headers  : dict of headers (auth, etc.)
#   file_key : the form field name for the audio file (usually "audio" or "file")
#   parse    : function to extract text from the JSON response

ENDPOINTS = [
    {
        "name": "ASR Endpoint (Current)",
        "url": "http://107.170.20.205:8000/transcribe",
        "headers": {
            "X-API-Key": os.environ["ASR_API_KEY"],
            "X-API-Secret": os.environ["ASR_API_SECRET"],
        },
        "file_key": "audio",
        "parse": lambda data: data.get("text", data.get("transcription", "")),
    },
    # ── Add more endpoints below ──
    # {
    #     "name": "Whisper API",
    #     "url": "https://your-whisper-endpoint.com/v1/audio/transcriptions",
    #     "headers": {
    #         "Authorization": "Bearer YOUR_TOKEN",
    #     },
    #     "file_key": "file",
    #     "parse": lambda data: data.get("text", ""),
    # },
    # {
    #     "name": "Another ASR",
    #     "url": "http://localhost:9000/transcribe",
    #     "headers": {},
    #     "file_key": "audio",
    #     "parse": lambda data: data.get("transcription", ""),
    # },
]

TIMEOUT = 180


def get_test_files(folder, count):
    """Pick first N audio files from the folder."""
    extensions = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}
    files = sorted(f for f in Path(folder).iterdir() if f.suffix.lower() in extensions)
    return files[:count]


def convert_to_mp3(audio_path):
    """Convert non-MP3 audio to MP3 temp file. Returns (mp3_path, is_temp)."""
    if audio_path.suffix.lower() == ".mp3":
        return str(audio_path), False
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(audio_path), "-ar", "16000", "-ac", "1", tmp.name],
        capture_output=True, timeout=30,
    )
    return tmp.name, True


def transcribe(endpoint, audio_path):
    """Send audio to an endpoint and return (text, duration, error)."""
    mp3_path, is_temp = convert_to_mp3(audio_path)
    try:
        with open(mp3_path, "rb") as f:
            safe_name = "chunk.mp3"
            files = {endpoint["file_key"]: (safe_name, f, "audio/mpeg")}
            start = time.time()
            resp = requests.post(
                endpoint["url"],
                headers=endpoint["headers"],
                files=files,
                timeout=TIMEOUT,
            )
            elapsed = round(time.time() - start, 2)

        if resp.status_code == 200:
            data = resp.json()
            text = endpoint["parse"](data)
            return text, elapsed, None
        else:
            return None, elapsed, f"HTTP {resp.status_code}: {resp.text[:200]}"

    except requests.exceptions.Timeout:
        return None, TIMEOUT, "Timeout"
    except Exception as e:
        return None, 0, str(e)
    finally:
        if is_temp and os.path.exists(mp3_path):
            os.unlink(mp3_path)


def main():
    num_files = int(sys.argv[1]) if len(sys.argv) > 1 else NUM_TEST_FILES
    audio_files = get_test_files(AUDIO_FOLDER, num_files)

    if not audio_files:
        print(f"No audio files found in {AUDIO_FOLDER}")
        return

    if not ENDPOINTS:
        print("No endpoints configured. Edit ENDPOINTS list in the script.")
        return

    print(f"Testing {len(ENDPOINTS)} endpoint(s) with {len(audio_files)} audio file(s)\n")
    print("=" * 80)

    results = []

    for i, audio_path in enumerate(audio_files, 1):
        print(f"\n[{i}/{len(audio_files)}] {audio_path.name}")
        print("-" * 80)

        file_results = {"file": audio_path.name}

        for ep in ENDPOINTS:
            print(f"  >> {ep['name']}...", end=" ", flush=True)
            text, elapsed, error = transcribe(ep, audio_path)

            if error:
                print(f"FAILED ({elapsed}s) - {error}")
                file_results[ep["name"]] = {"error": error, "time": elapsed}
            else:
                print(f"OK ({elapsed}s)")
                print(f"     {text[:120]}{'...' if text and len(text) > 120 else ''}")
                file_results[ep["name"]] = {"text": text, "time": elapsed}

        results.append(file_results)

    # ── Summary ──
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for ep in ENDPOINTS:
        name = ep["name"]
        texts = [r[name].get("text") for r in results if "text" in r.get(name, {})]
        errors = [r[name].get("error") for r in results if "error" in r.get(name, {})]
        times = [r[name]["time"] for r in results if name in r]
        avg_time = round(sum(times) / len(times), 2) if times else 0

        print(f"\n  {name}")
        print(f"    Success: {len(texts)}/{len(results)}")
        print(f"    Failed:  {len(errors)}/{len(results)}")
        print(f"    Avg time: {avg_time}s")

    # ── Save detailed results ──
    output_path = "test_endpoints_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nDetailed results saved to: {output_path}")


if __name__ == "__main__":
    main()
