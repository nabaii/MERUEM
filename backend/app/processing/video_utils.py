import tempfile
import ffmpeg
import os
import logging

logger = logging.getLogger(__name__)

def extract_audio(video_path: str) -> str:
    """
    Extracts the audio track from a video and saves it as an MP3 or WAV.
    Returns the path to the extracted audio file. The caller is responsible for deleting it.
    """
    fd, audio_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    
    try:
        # Extra ffmpeg call to extract audio
        (
            ffmpeg
            .input(video_path)
            .output(audio_path, acodec='libmp3lame', ac=1, ar='16k')
            .overwrite_output()
            .run(quiet=True)
        )
        return audio_path
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg failed to extract audio: {e.stderr.decode('utf-8') if e.stderr else str(e)}")
        os.remove(audio_path)
        raise

def extract_keyframes(video_path: str, duration_sec: float = 5.0, interval_sec: float = 0.5) -> list[str]:
    """
    Extracts frames from the video at intervals for the specified duration.
    Returns a list of image paths. The caller is responsible for deleting them.
    """
    frame_paths = []
    
    # We will loop through the time intervals and use ffmpeg to grab each frame.
    # An alternative is extracting all frames to a temp directory at X fps.
    temp_dir = tempfile.mkdtemp(prefix="tiktok_frames_")
    
    try:
        # ffmpeg -i video.mp4 -t 00:00:05 -vf fps=2 %04d.png
        fps = 1.0 / interval_sec
        output_pattern = os.path.join(temp_dir, "frame_%04d.png")
        
        (
            ffmpeg
            .input(video_path)
            .output(output_pattern, t=duration_sec, vf=f"fps={fps}")
            .overwrite_output()
            .run(quiet=True)
        )
        
        for file in sorted(os.listdir(temp_dir)):
            if file.endswith(".png"):
                frame_paths.append(os.path.join(temp_dir, file))
                
        return frame_paths
        
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg failed to extract frames: {e.stderr.decode('utf-8') if e.stderr else str(e)}")
        # Cleaner logic should be implemented here in case of failure
        raise
