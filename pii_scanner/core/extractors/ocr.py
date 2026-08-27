from __future__ import annotations

from pii_scanner.core.extractors.base import Extractor

MAX_OCR_PIXELS = 4000 * 4000   # 16MP 상한 — A4 300dpi 문서(~8.7MP)는 무손실 통과.
                               # 수천만 화소 사진은 장당 수백 MB로 워커 12개 동시 처리 시 OOM 기여(T-012).

# pytesseract가 임시 저장을 지원하는 포맷/모드 (T-013 실측: MPO 498건·CMYK 27건이 여기서 죽음).
# format=None(메모리 생성/복사본)은 pytesseract가 PNG로 저장하므로 허용.
_TESS_FORMATS = {None, "JPEG", "PNG", "TIFF", "BMP", "GIF", "WEBP"}
_TESS_MODES = {"1", "L", "RGB", "RGBA"}    # PNG 저장 가능 모드

_APPLEDOUBLE_MAGIC = b"\x00\x05\x16\x07"   # 맥 리소스포크 사이드카(._xxx) — 이미지 본문 아님


def ocr_image(img) -> str:
    """PIL 이미지 한 장을 OCR해 텍스트 반환. lang/psm 설정의 단일 출처.

    상한(MAX_OCR_PIXELS) 초과 이미지는 종횡비를 유지해 축소 — 문서 스캔 해상도는
    건드리지 않으면서 초대형 사진의 메모리·OCR 시간만 깎는다.
    """
    import pytesseract  # lazy
    w, h = img.size
    if w * h > MAX_OCR_PIXELS:
        scale = (MAX_OCR_PIXELS / (w * h)) ** 0.5
        target = (max(1, int(w * scale)), max(1, int(h * scale)))
        img.draft(None, target)   # JPEG는 디코드 단계부터 축소(메모리 절감), 그 외 포맷은 no-op
        img = img.resize(target)
    if img.mode not in _TESS_MODES:
        img = img.convert("RGB")       # CMYK·팔레트·16비트 등 → PNG 저장 가능 모드(format도 None이 됨)
    elif img.format not in _TESS_FORMATS:
        img = img.copy()               # MPO(폰 연사 JPEG) 등 — 복사로 포맷 태그 제거 → PNG 경로
    return pytesseract.image_to_string(img, lang='kor+eng', config='--psm 6')

class ImageOcrExtractor(Extractor):
    def extract(self, path: str) -> str:
        from PIL import Image, ImageFile  # lazy
        from pii_scanner.core.extractors import UnsupportedFormat  # lazy — 패키지 순환 import 회피
        with open(path, "rb") as f:
            if f.read(4) == _APPLEDOUBLE_MAGIC:
                raise UnsupportedFormat("AppleDouble 메타파일(맥 ._사이드카) — 이미지 본문 아님")
        # 손상/부분 업로드 이미지도 있는 데이터까지는 OCR (T-013: truncated 5건)
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        # PIL 폭탄 가드(1.8억 화소) 완화 — 16MP 축소(ocr_image)와 RLIMIT_AS가 방어 (T-013: 초대형 9건)
        Image.MAX_IMAGE_PIXELS = 500_000_000
        img = Image.open(path)
        return ocr_image(img)
