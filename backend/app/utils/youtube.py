import os
import subprocess
from pytubefix import YouTube, Channel, Playlist
from pytubefix.exceptions import VideoUnavailable
from typing import List, Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)

def get_channel_videos(channel_url: str) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """Fetch all videos from a channel or playlist URL. Returns (videos, channel_name)."""
    try:
        logger.info(f"Fetching videos for channel: {channel_url}")
        is_playlist = "list=" in channel_url
        c = Playlist(channel_url) if is_playlist else Channel(channel_url)
        # Some versions of pytubefix need standard Channel init, but we can try to force it to use WEB client
        # if the default fails. For now, standard is safer for whole channel iteration.
        videos = []
        channel_name = None
        
        # Try to get channel name
        try:
            # Someytubefix versions might fail here if the channel page layout changed
            channel_name = c.title if is_playlist else c.channel_name
            logger.info(f"Channel name: {channel_name}")
        except Exception as name_err:
            logger.warning(f"Could not fetch channel name for {channel_url}: {str(name_err)}")
            # Fallback to a cleaner version of the URL or just None
            channel_name = channel_url.split('/')[-1] if '/' in channel_url else channel_url
        
        # Attempt to access videos property - this can be slow
        video_count = 0
        for video in c.videos:
            try:
                # Access properties within a try block to catch unavailable videos
                videos.append({
                    "video_id": video.video_id,
                    "title": video.title,
                    "duration": video.length,
                    "upload_date": str(video.publish_date) if video.publish_date else None
                })
                video_count += 1
                if video_count % 10 == 0:
                    logger.info(f"Found {video_count} videos so far for {channel_url}...")
            except VideoUnavailable:
                logger.warning(f"Video {getattr(video, 'video_id', 'unknown')} is unavailable (private or deleted), skipping.")
                continue
            except Exception as vid_err:
                logger.warning(f"Skipping video in channel {channel_url} due to error: {str(vid_err)}")
                continue
        
        logger.info(f"Successfully fetched {len(videos)} videos for channel: {channel_url}")
        return videos, channel_name
    except Exception as e:
        logger.error(f"Error fetching channel videos for {channel_url}: {str(e)}", exc_info=True)
        return [], None

def download_audio(video_id: str, output_path: str) -> Optional[str]:
    """Download audio from a YouTube video and convert to WAV."""
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        yt = YouTube(url, use_oauth=False, allow_oauth_cache=True)
        
        # Videos can carry extra AI-dubbed audio tracks (e.g. English); always take the
        # original (default) track, at the highest bitrate
        audio_streams = yt.streams.filter(only_audio=True)
        original = [s for s in audio_streams if getattr(s, "is_default_audio_track", True)]
        audio_stream = max(original or audio_streams, key=lambda s: s.bitrate or 0, default=None)
        if not audio_stream:
            logger.error(f"No audio stream found for {video_id}")
            return None
        
        # Download temp file
        temp_filename = f"{video_id}_temp.{audio_stream.subtype}"
        temp_path = audio_stream.download(output_path=output_path, filename=temp_filename)
        
        # Convert straight to 16 kHz mono WAV with ffmpeg. It streams the file instead of
        # loading hours of audio into memory, and the output is ~6x smaller than full-rate stereo.
        wav_filename = f"{video_id}_audio.wav"
        wav_path = os.path.join(output_path, wav_filename)

        logger.info(f"Converting {temp_path} to 16 kHz mono WAV...")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", temp_path, "-vn", "-ac", "1", "-ar", "16000", wav_path],
            check=True,
        )
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        logger.info(f"Successfully downloaded and converted audio to WAV for {video_id}")
        return wav_path
    except Exception as e:
        logger.error(f"Error downloading audio for {video_id}: {str(e)}", exc_info=True)
        return None

def download_transcript(video_id: str, output_path: str) -> Optional[str]:
    """Download Arabic transcript for a YouTube video."""
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        yt = YouTube(url)
        
        # Try to find Arabic captions using caption_tracks
        ar_caption = None
        for track in yt.caption_tracks:
            if track.code == 'ar':
                ar_caption = track
                break
            if track.code == 'a.ar': # Auto-generated
                ar_caption = track
        
        if ar_caption:
            transcript_text = ar_caption.generate_srt_captions()
            file_name = f"{video_id}_transcript.txt"
            full_path = os.path.join(output_path, file_name)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(transcript_text)
            return full_path
        
        return None
    except Exception as e:
        logger.error(f"Error downloading transcript for {video_id}: {e}")
        return None

def save_metadata(video_id: str, metadata: Dict[str, Any], output_path: str):
    """Save video metadata as JSON."""
    file_name = f"{video_id}_metadata.json"
    full_path = os.path.join(output_path, file_name)
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)
    return full_path
