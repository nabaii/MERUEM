import logging
from PIL import Image
import pytesseract

logger = logging.getLogger(__name__)

class OCRSafeZone:
    """
    Extracts text and bounding boxes from video keyframes.
    Checks if extracted text falls within the TikTok safe zone.
    """
    def __init__(self, tesseract_cmd: str | None = None):
        # Allow custom path for windows or specific tesseract installs
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            
    def get_text_and_boxes(self, image_path: str) -> list[dict]:
        """
        Runs Tesseract OCR on a single frame. returns a list of dictionaries 
        containing bounding boxes and the detected text.
        """
        results = []
        try:
            img = Image.open(image_path)
            # image_to_data returns tsv data: level, page_num, block_num, par_num, line_num, word_num, left, top, width, height, conf, text
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            
            for i in range(len(data["text"])):
                conf = int(data["conf"][i])
                text = data["text"][i].strip()
                
                # Filter out weak detections and empty strings
                if conf > 60 and len(text) > 2:
                    results.append({
                        "text": text,
                        "left": data["left"][i],
                        "top": data["top"][i],
                        "width": data["width"][i],
                        "height": data["height"][i]
                    })
        except Exception as e:
            logger.error(f"Failed to run OCR on {image_path}: {str(e)}")
            
        return results

    def verify_safe_zone(self, boxes: list[dict], target_keyword: str) -> tuple[bool, list[dict]]:
        """
        Verifies if the target_keyword appears in the boxes and is positioned
        at least 150px from the top of the frame.
        """
        if not target_keyword:
            return True, []
            
        keyword_lower = target_keyword.lower()
        violating_boxes = []
        passed = False
        
        for box in boxes:
            box_text = box["text"].lower()
            if keyword_lower in box_text:
                if box["top"] >= 150:
                    passed = True
                else:
                    violating_boxes.append(box)
                    
        return passed, violating_boxes
