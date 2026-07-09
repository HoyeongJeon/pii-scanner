from __future__ import annotations

from pii_scanner.core.extractors.base import Extractor

def ocr_image(img) -> str:
    """PIL 이미지 한 장을 OCR해 텍스트 반환. lang/psm 설정의 단일 출처."""
    import pytesseract  # lazy
    return pytesseract.image_to_string(img, lang='kor+eng', config='--psm 6')

class ImageOcrExtractor(Extractor):
    def extract(self, path: str) -> str:
        from PIL import Image # lazy
        img = Image.open(path)
        return ocr_image(img)
