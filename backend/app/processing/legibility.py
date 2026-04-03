import os
import logging
from typing import Optional

from app.processing.video_utils import extract_audio, extract_keyframes
from app.processing.whisper_asr import WhisperASR
from app.processing.ocr_safe_zone import OCRSafeZone

logger = logging.getLogger(__name__)

class LegibilityAuditor:
    """
    Unifies ASR, OCR, and Caption Keyword density checks into one audit.
    """
    def __init__(self):
        self.asr = WhisperASR()
        self.ocr = OCRSafeZone()
        
    def check_caption_density(self, caption: str, primary_keyword: str, secondary_keywords: list[str]) -> tuple[bool, float]:
        """
        Validates if the first 150 characters contain the primary keyword and at least
        one secondary keyword. Returns boolean passed and a density ratio (if applicable).
        """
        if not caption:
            return False, 0.0
            
        first_150 = caption[:150].lower()
        primary_k_lower = primary_keyword.lower()
        
        has_primary = primary_k_lower in first_150
        has_secondary = any(sek.lower() in first_150 for sek in secondary_keywords)
        
        passed = has_primary and has_secondary
        
        matched_chars = 0
        if has_primary:
            matched_chars += len(primary_keyword)
        for sek in secondary_keywords:
            if sek.lower() in first_150:
                matched_chars += len(sek)
                
        density = matched_chars / 150.0
        return passed, density
        
    def run_audit(self, video_path: str, caption: str, primary_keyword: str, secondary_keywords: list[str]) -> dict:
        """
        Runs the full AI processing pipeline against a video to measure
        Algorithmic Legibility logic for TikTok.
        """
        report = {
            "asr_passed": False,
            "ocr_passed": False,
            "caption_passed": False,
            "asr_text": "",
            "caption_density": 0.0,
            "violating_ocr_boxes": []
        }
        
        # 1. Caption Density
        passed_caption, density = self.check_caption_density(caption, primary_keyword, secondary_keywords)
        report["caption_passed"] = passed_caption
        report["caption_density"] = density
        
        # 2. ASR Check (Audio Extraction + Whisper)
        audio_path = None
        try:
            audio_path = extract_audio(video_path)
            passed_asr, asr_text = self.asr.check_keyword_placement(audio_path, primary_keyword, max_time_sec=3.0)
            report["asr_passed"] = passed_asr
            report["asr_text"] = asr_text
        except Exception as e:
            logger.error(f"Legibility ASR check fail: {str(e)}")
        finally:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
                
        # 3. OCR Safe Zone (Keyframes + PyTesseract)
        frame_paths = []
        try:
            frame_paths = extract_keyframes(video_path, duration_sec=5.0, interval_sec=0.5)
            ocr_passed_overall = False
            violating_boxes_all = []
            
            for f in frame_paths:
                boxes = self.ocr.get_text_and_boxes(f)
                passed_frame, violations = self.ocr.verify_safe_zone(boxes, primary_keyword)
                
                if passed_frame:
                    ocr_passed_overall = True
                
                violating_boxes_all.extend(violations)
                
            report["ocr_passed"] = ocr_passed_overall
            report["violating_ocr_boxes"] = violating_boxes_all
        except Exception as e:
            logger.error(f"Legibility OCR check fail: {str(e)}")
        finally:
            for f in frame_paths:
                if os.path.exists(f):
                    os.remove(f)
                    
        return report

