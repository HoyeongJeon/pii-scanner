import os

import pdf2image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from pii_scanner.core.extractors.pdf import PdfExtractor

FIXTURE_PNG = os.path.join(os.path.dirname(__file__), "fixtures", "ocr_sample.png")


def _boom(*args, **kwargs):
    raise AssertionError("born-digital인데 OCR(convert_from_path) 경로로 진입함")


def test_borndigital_fast_path_no_ocr(tmp_path, monkeypatch):
    """텍스트 레이어가 충분한(>=300자) PDF는 OCR을 타지 않고 텍스트만 반환한다."""
    p = tmp_path / "a.pdf"
    c = canvas.Canvas(str(p))
    filler = "born digital document line with enough text here. "  # ~50자
    y = 800
    for _ in range(12):                       # 약 12줄 * 50자 = 600자+ (>=300 보장)
        c.drawString(40, y, filler)
        y -= 20
    c.drawString(40, y, "contact ho@example.com")
    c.save()

    # OCR 경로로 새면 즉시 실패 — fast-path(텍스트 충분)는 convert_from_path를 부르면 안 됨
    monkeypatch.setattr(pdf2image, "convert_from_path", _boom)

    text = PdfExtractor().extract(str(p))
    assert "ho@example.com" in text


def test_scanned_pdf_ocr_fallback(tmp_path):
    """텍스트 레이어 없는 스캔본 PDF는 OCR 폴백으로 한글이 추출돼야 한다."""
    pdf = tmp_path / "scanned.pdf"
    # 이미지만 그린 PDF = 텍스트 레이어 없음(=스캔본). Pillow의 PDF 저장은 이 환경에서
    # JPEG 인코더 경로를 타다 깨져, reportlab로 PNG를 임베드해 같은 효과를 낸다.
    c = canvas.Canvas(str(pdf), pagesize=(1100, 320))
    c.drawImage(ImageReader(FIXTURE_PNG), 0, 0, width=1100, height=320)
    c.save()

    text = PdfExtractor().extract(str(pdf))
    norm = text.replace(" ", "")
    assert "홍길동" in norm
    assert "900101-1234567" in norm


def test_multipage_scanned_pdf_ocr_streams_pages(tmp_path, monkeypatch):
    """여러 페이지 스캔본은 한 장씩 변환·OCR해야 한다 — 전체 일괄 변환은 대형 PDF에서 OOM(T-011)."""
    pdf = tmp_path / "multi.pdf"
    c = canvas.Canvas(str(pdf), pagesize=(1100, 320))
    for _ in range(3):
        c.drawImage(ImageReader(FIXTURE_PNG), 0, 0, width=1100, height=320)
        c.showPage()
    c.save()

    calls = []
    real = pdf2image.convert_from_path

    def spy(path, *args, **kwargs):
        calls.append((kwargs.get("first_page"), kwargs.get("last_page")))
        return real(path, *args, **kwargs)

    monkeypatch.setattr(pdf2image, "convert_from_path", spy)

    text = PdfExtractor().extract(str(pdf))
    norm = text.replace(" ", "")
    assert norm.count("홍길동") == 3          # 세 페이지 모두 OCR됨
    assert calls == [(1, 1), (2, 2), (3, 3)]  # 호출마다 정확히 한 페이지만 요청


def test_thin_text_layer_triggers_ocr(tmp_path):
    """표지에 소량 텍스트(<300자)가 있는 스캔본도 OCR을 타고, 텍스트+OCR이 합쳐져야 한다."""
    pdf = tmp_path / "thin.pdf"
    c = canvas.Canvas(str(pdf), pagesize=(1100, 400))
    c.drawString(20, 360, "SCAN COVER doc-2026-001")   # 얇은 텍스트 레이어(<300자)
    c.drawImage(ImageReader(FIXTURE_PNG), 0, 0, width=1100, height=320)
    c.save()

    text = PdfExtractor().extract(str(pdf))
    norm = text.replace(" ", "")
    assert "doc-2026-001" in norm     # 텍스트 레이어 보존(합치기)
    assert "홍길동" in norm            # OCR 발동
    assert "900101-1234567" in norm   # OCR 발동


def test_corrupt_pdf_falls_back_to_ocr(tmp_path, monkeypatch):
    """pdfminer가 파싱 실패하는 비표준/손상 PDF는 OCR 폴백으로 살린다(T-013 — poppler가 더 관대).

    실측: PDFSyntaxError 25건 중 일부·PSEOF 6건은 poppler로는 렌더 가능한 실제 PDF.
    """
    from pdfminer.pdfparser import PDFSyntaxError
    import pii_scanner.core.extractors.pdf as pdfmod

    pdf = tmp_path / "corrupt.pdf"
    c = canvas.Canvas(str(pdf), pagesize=(1100, 320))
    c.drawImage(ImageReader(FIXTURE_PNG), 0, 0, width=1100, height=320)
    c.save()

    def boom(path):
        raise PDFSyntaxError("No /Root object!")
    monkeypatch.setattr(pdfmod, "extract_text", boom)

    text = PdfExtractor().extract(str(pdf))
    assert "홍길동" in text.replace(" ", "")


def test_empty_pdf_gets_clean_error(tmp_path):
    """0바이트 파일(업로드 실패 잔재)은 명확한 에러 메시지로 — 실측 PDFSyntaxError 25건 중 다수."""
    import pytest
    p = tmp_path / "empty.pdf"
    p.write_bytes(b"")
    with pytest.raises(ValueError, match="빈 파일"):
        PdfExtractor().extract(str(p))


def test_pdf_extract_located_labels_pages(tmp_path):
    # 2페이지 born-digital PDF — 총 300자 이상이라 OCR 미발동(빠른 경로)
    pdf = tmp_path / "two_pages.pdf"
    c = canvas.Canvas(str(pdf), pagesize=(600, 800))
    for i in range(30):
        c.drawString(40, 760 - i * 24, f"first page filler line number {i:02d} with padding")
    c.showPage()
    c.drawString(40, 760, "second-page-marker@example.com")
    c.save()

    text, locator = PdfExtractor().extract_located(str(pdf))
    assert locator.label(text.index("first page filler")) == "p.1 L1"
    assert locator.label(text.index("second-page-marker")).startswith("p.2 ")
