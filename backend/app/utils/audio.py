import os
from pydub import AudioSegment, silence
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

def split_audio_on_silence(
    audio_path: str,
    output_dir: str,
    video_id: str,
    channel_id: int = None,
    min_silence_len: int = 700,
    silence_thresh: int = -40,
    min_chunk_len: int = 1000,
    max_chunk_len: int = 20000,
    sample_rate: int = 16000
) -> List[Dict[str, Any]]:
    """Split audio into chunks based on silence."""
    try:
        audio = AudioSegment.from_file(audio_path)
        # Convert to mono and set sample rate
        audio = audio.set_frame_rate(sample_rate).set_channels(1)
        
        # Detect non-silent segments
        from pydub.silence import detect_nonsilent
        nonsilent_ranges = detect_nonsilent(
            audio,
            min_silence_len=min_silence_len,
            silence_thresh=silence_thresh
        )
        
        processed_chunks = []
        if not nonsilent_ranges:
            return []

        current_group = []
        current_group_duration = 0
        
        def save_chunk(group, index):
            if not group: return
            start_time = group[0][0]
            end_time = group[-1][1]
            # Add some padding if possible
            start_pad = max(0, start_time - 200)
            end_pad = min(len(audio), end_time + 200)
            
            chunk_audio = audio[start_pad:end_pad]
            chunk_id = f"{video_id}_chunk_{index}"
            file_name = f"{chunk_id}.wav"
            
            # Use hierarchical structure if channel_id is provided
            if channel_id is not None:
                chunk_dir = os.path.join(output_dir, 'channels', str(channel_id), 'videos', str(video_id))
                os.makedirs(chunk_dir, exist_ok=True)
                file_path = os.path.join(chunk_dir, file_name)
            else:
                # Fallback to flat structure for backwards compatibility
                file_path = os.path.join(output_dir, file_name)
            
            chunk_audio.export(file_path, format="wav")
            
            processed_chunks.append({
                "chunk_id": chunk_id,
                "file_path": file_path,
                "duration": len(chunk_audio) / 1000.0,
                "start_time": start_pad / 1000.0,
                "end_time": end_pad / 1000.0
            })

        chunk_idx = 0
        import random
        
        # Determine randomized target for the first chunk
        current_target_len = random.randint(min_chunk_len, max_chunk_len)

        for start, end in nonsilent_ranges:
            seg_duration = end - start
            
            # If the segment itself is longer than current_target_len, 
            # we must split it even without silence
            if seg_duration > max_chunk_len: # Always use absolute max for giant segments
                # Save what we have so far
                if current_group:
                    save_chunk(current_group, chunk_idx)
                    chunk_idx += 1
                    current_group = []
                    current_group_duration = 0
                
                # Split this long segment into sub-chunks with random sizes
                sub_start = start
                while sub_start < end:
                    # Pick a random size for each piece
                    target = random.randint(min_chunk_len, max_chunk_len)
                    sub_end = min(sub_start + target, end)
                    
                    if (sub_end - sub_start) >= min_chunk_len or sub_end == end:
                        save_chunk([(sub_start, sub_end)], chunk_idx)
                        chunk_idx += 1
                    sub_start = sub_end
                
                # Reset target for next group
                current_target_len = random.randint(min_chunk_len, max_chunk_len)
                continue

            # Regular grouping logic
            if current_group_duration + seg_duration > current_target_len and current_group_duration >= min_chunk_len:
                save_chunk(current_group, chunk_idx)
                chunk_idx += 1
                current_group = [(start, end)]
                current_group_duration = seg_duration
                # Pick a new random target for the next chunk
                current_target_len = random.randint(min_chunk_len, max_chunk_len)
            else:
                current_group.append((start, end))
                current_group_duration += seg_duration
                
        # Save last group
        if current_group:
            save_chunk(current_group, chunk_idx)
            
        return processed_chunks
    except Exception as e:
        logger.error(f"Error splitting audio for {video_id}: {e}")
        return []

def get_audio_duration(file_path: str) -> float:
    """Get duration of audio file in seconds."""
    try:
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0
    except Exception:
        return 0.0

# VAD Model Singleton
_vad_model = None
_vad_utils = None

def get_vad_model():
    """Load Silero VAD model."""
    global _vad_model, _vad_utils
    if _vad_model is None:
        import torch
        # Load from torch hub - this handles caching automatically
        model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                      model='silero_vad',
                                      force_reload=False,
                                      trust_repo=True)
        _vad_model = model
        _vad_utils = utils
    return _vad_model, _vad_utils

def validate_speech(audio_path: str, min_speech_ratio: float = 0.2) -> bool:
    """
    Check if audio file contains enough speech using Silero VAD.
    Returns True if valid speech is detected, False otherwise.
    """
    import torch
    import torchaudio
    
    try:
        model, utils = get_vad_model()
        (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = utils
        
        # Read audio
        wav = read_audio(audio_path, sampling_rate=16000)
        
        # Get speech timestamps
        speech_timestamps = get_speech_timestamps(
            wav, 
            model,
            sampling_rate=16000,
            threshold=0.5,
            min_speech_duration_ms=250,
            min_silence_duration_ms=100
        )
        
        if not speech_timestamps:
            return False
            
        # Calculate total speech duration
        total_speech_samples = sum([t['end'] - t['start'] for t in speech_timestamps])
        total_samples = len(wav)
        
        speech_ratio = total_speech_samples / total_samples
        
        # Also ensure we have at least some absolute duration of speech (e.g. 0.5s)
        min_absolute_speech = 16000 * 0.5
        
        if total_speech_samples < min_absolute_speech:
            return False
            
        return True # For now, just existence of robust speech segments is enough
        
    except Exception as e:
        logger.error(f"VAD check failed for {audio_path}: {e}")
        # Default to True on error to avoid deleting valid files if VAD fails
        return True
