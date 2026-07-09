import os
from pii_scanner.core.extractors.ocr import ImageOcrExtractor, ocr_image
from PIL import Image

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "ocr_sample.png")

# ---------------------------------------------------------------------------
# Import-smoke: ImageOcrExtractor 클래스 자체는 pytesseract 없어도 import 가능해야 한다.
# ---------------------------------------------------------------------------

def test_class_importable_without_pytesseract(monkeypatch):
    """pytesseract 미설치 환경에서도 ocr 모듈이 import 돼야 한다(지연 import 보증)"""
    import sys, importlib
    orig = sys.modules["pii_scanner.core.extractors.ocr"] # ① 원본 모듈 백업(나중에 복구)
    monkeypatch.setitem(sys.modules, "pytesseract", None) # ② pytesseract '없는 척'(import 시 ImportError)
    try:
        del sys.modules["pii_scanner.core.extractors.ocr"] # ③ ocr 캐시 제거 → 새로 import 강제
        fresh = importlib.import_module("pii_scanner.core.extractors.ocr") # ④ 최상단 코드 재실행
        assert fresh.ImageOcrExtractor is not None # ⑤ 지연 import면 클래스 멀쩡히 로드됨
    finally:
        sys.modules["pii_scanner.core.extractors.ocr"] = orig # ⑥ 원본 복구(다른 테스트 격리)

def test_ocr_extracts_text():
    text = ImageOcrExtractor().extract(FIXTURE)
    norm = text.replace(" ", "")
    assert "홍길동" in norm
    assert "900101-1234567" in norm

def test_ocr_image_reads_korea():
    """공유 함수 ocr_image: PIL 이미지 한 장을 받아 한글 텍스트를 뽑는다."""
    img = Image.open(FIXTURE)
    norm = ocr_image(img).replace(" ", "")
    assert "홍길동" in norm
    assert "900101-1234567" in norm