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
        # ⑦ 부모 패키지 속성도 되돌린다. import_module 이 pii_scanner.core.extractors.ocr
        # 속성을 '새 모듈'로 바꿔 놓는데, sys.modules 만 복구하면 둘이 갈린다 —
        # 그러면 `import ... as ocrmod` 는 죽은 모듈을, `from ... import ocr_image` 는
        # 원본을 집어서 이후 테스트의 ocr_image 모킹이 조용히 무력화된다.
        import pii_scanner.core.extractors as _pkg
        _pkg.ocr = orig
    # 이 테스트가 남긴 상태가 다른 테스트를 오염시키지 않는지 여기서 못박는다.
    assert sys.modules["pii_scanner.core.extractors.ocr"] is orig
    import pii_scanner.core.extractors as pkg
    assert pkg.ocr is orig, "부모 패키지 속성이 새 모듈을 가리키면 이후 ocr_image 모킹이 무력화된다"

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


def test_ocr_image_normalizes_unsupported_formats_and_modes():
    """MPO(폰 연사 JPEG)·CMYK 등 pytesseract 미지원 포맷/모드는 정규화 후 OCR — 예외 없이 통과 (T-013).

    실측: 어느 대형 스캔의 추출 실패 대부분이 MPO TypeError, 나머지가 CMYK PNG 저장 실패였다.
    """
    mpo = Image.new("RGB", (80, 24), "white")
    mpo.format = "MPO"                    # PIL이 폰 사진을 여는 실제 상태 재현
    ocr_image(mpo)                        # TypeError 없이 통과해야 함

    cmyk = Image.new("CMYK", (80, 24))
    ocr_image(cmyk)                       # OSError(cannot write mode CMYK as PNG) 없이 통과


def test_appledouble_sidecar_is_unsupported(tmp_path):
    """맥 리소스포크 사이드카(._xxx.jpg, AppleDouble)는 이미지가 아님 — UnsupportedFormat으로 건너뜀."""
    import pytest
    from pii_scanner.core.extractors import UnsupportedFormat
    p = tmp_path / "._사진.jpg"
    p.write_bytes(b"\x00\x05\x16\x07" + b"\x00" * 60)
    with pytest.raises(UnsupportedFormat):
        ImageOcrExtractor().extract(str(p))


def test_ocr_image_downscales_huge_images(monkeypatch):
    """초대형 이미지는 OCR 전에 축소 — 수천만 화소 사진이 장당 수백 MB를 먹어 OOM 기여(T-012).

    A4 300dpi(2480x3508, ~8.7MP) 문서 스캔은 무손실 통과해야 한다.
    """
    import pytesseract
    seen = []
    monkeypatch.setattr(pytesseract, "image_to_string",
                        lambda img, **kw: seen.append(img.size) or "")

    ocr_image(Image.new("RGB", (9000, 6000)))    # 54MP 사진
    w, h = seen[-1]
    assert w * h <= 4000 * 4000                  # 상한(16MP) 이하로 축소
    assert abs(w / h - 9000 / 6000) < 0.01      # 종횡비 보존(정수 반올림 오차 허용)

    ocr_image(Image.new("RGB", (2480, 3508)))    # A4 300dpi 문서
    assert seen[-1] == (2480, 3508)              # 문서 스캔은 원본 그대로