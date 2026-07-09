from __future__ import annotations

from pdfminer.high_level import extract_text
from pdfminer.pdfdocument import PDFEncryptionError

from pii_scanner.core.extractors.base import Extractor, EncryptedFileError
from pii_scanner.core.locate import Locator, PageLineLocator

OCR_TEXT_THRESHOLD = 300   # 글자수 미만이면 스캔본으로 보고 OCR 폴백 (DECISIONLOG D-028 근거)


class PdfExtractor(Extractor):
    def extract(self, path: str) -> str:
        try:
            text = extract_text(path) or ""
        except PDFEncryptionError as exc:
            raise EncryptedFileError(f"암호화된 PDF: {path}") from exc
        if len(text.strip()) >= OCR_TEXT_THRESHOLD:
            return text             # born-digital — 빠른 텍스트 경로
        # 텍스트 레이어가 사실상 없음(빈 것 포함) = 스캔본 → 페이지 OCR 후 합치기
        from pdf2image import convert_from_path
        from pii_scanner.core.extractors.ocr import ocr_image
        pages = convert_from_path(path)
        ocr_text = "\n".join(ocr_image(img) for img in pages)
        return f"{text}\n{ocr_text}" if text.strip() else ocr_text

    def extract_located(self, path: str) -> tuple[str, Locator]:
        text = self.extract(path)
        # pdfminer가 넣는 \x0c 페이지 경계 기반. OCR 합본(스캔본) 구간은 page/line 근사.
        return text, PageLineLocator(text)
