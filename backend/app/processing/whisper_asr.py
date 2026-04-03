import logging
from typing import Optional
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

class WhisperASR:
    """
    Interfaces with OpenAI Whisper API for transcriptions.
    Extracts spoken words and their timestamps to verify if a keyword
    is mentioned within the first N seconds.
    """
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        
    def transcribe_with_timestamps(self, audio_path: str) -> dict:
        """
        Transcribes audio using OpenAI Whisper API and returns the word-level timestamps.
        Expected return format: {"words": [{"word": "hello", "start": 0.0, "end": 0.5}], "text": "..."}
        """
        if not self.client:
            logger.warning("OpenAI API key missing. ASR check skipped.")
            return {"words": [], "text": ""}
            
        try:
            with open(audio_path, "rb") as audio_file:
                # Use verbose_json to get word-level timestamps
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["word"]
                )
                
            words = response.words if hasattr(response, 'words') else response.get('words', [])
            
            # OpenAI returns words as objects with 'word', 'start', 'end'
            processed_words = []
            for w in words:
                processed_words.append({
                    "word": w.word if hasattr(w, 'word') else w.get('word', ''),
                    "start": w.start if hasattr(w, 'start') else w.get('start', 0.0),
                    "end": w.end if hasattr(w, 'end') else w.get('end', 0.0)
                })
                
            text = response.text if hasattr(response, 'text') else response.get('text', '')
            
            return {
                "words": processed_words,
                "text": text
            }
            
        except Exception as e:
            logger.error(f"Failed to transcribe audio via Whisper API: {str(e)}")
            return {"words": [], "text": ""}
            
    def check_keyword_placement(self, audio_path: str, target_keyword: str, max_time_sec: float = 3.0) -> tuple[bool, str]:
        """
        Runs transcription and checks if target_keyword is spoken within max_time_sec limit.
        Returns a tuple: (Passed Boolean, Full Text)
        """
        if not target_keyword:
            return True, ""
            
        transcription = self.transcribe_with_timestamps(audio_path)
        words = transcription["words"]
        text = transcription["text"]
        
        if not words:
            # If nothing was transcribed or API skipped
            return False, text
            
        target_keyword_lower = target_keyword.lower()
        
        # Check if the keyword exists at or before the max_time_sec mark
        for w in words:
            word_str = w["word"].lower().strip(".,!?\"")
            if target_keyword_lower in word_str and w["start"] <= max_time_sec:
                return True, text
                
        return False, text
