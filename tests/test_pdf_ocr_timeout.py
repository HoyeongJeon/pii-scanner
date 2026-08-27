"""PDF 스캔본 OCR의 교착 방지 장치 테스트 (T-015).

poppler 호출 timeout · 페이지 상한 · 페이지 단위 예외 격리를 pdf2image 모킹으로 검증한다.
"""
import sys
import types

import pytest

from pii_scanner.core.extractors import pdf as pdfmod


def _fake_pdf2image(n_pages, fail_pages=()):
    m = types.ModuleType("pdf2image")
    m.pdfinfo_calls = []
    m.convert_calls = []

    def pdfinfo_from_path(path, timeout=None):
        m.pdfinfo_calls.append(timeout)
        return {"Pages": n_pages}

    def convert_from_path(path, first_page=None, last_page=None, timeout=None):
        m.convert_calls.append((first_page, timeout))
        if first_page in fail_pages:
            raise RuntimeError("poppler 멈춤/실패 모사")
        return [f"PAGE{first_page}"]      # 가짜 이미지 — ocr_image 를 모킹하므로 아무 객체나 OK

    m.pdfinfo_from_path = pdfinfo_from_path
    m.convert_from_path = convert_from_path
    return m


@pytest.fixture
def force_ocr(monkeypatch, tmp_path):
    """extract_text 를 빈 문자열로 만들어 OCR 폴백 경로를 강제하고, ocr_image 를 모킹."""
    monkeypatch.setattr(pdfmod, "extract_text", lambda p: "")
    import pii_scanner.core.extractors.ocr as ocrmod
    monkeypatch.setattr(ocrmod, "ocr_image", lambda img: f"ocr({img})")
    f = tmp_path / "scan.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    return str(f)


def test_poppler_calls_get_timeout(force_ocr, monkeypatch):
    fake = _fake_pdf2image(n_pages=3)
    monkeypatch.setitem(sys.modules, "pdf2image", fake)
    pdfmod.PdfExtractor().extract(force_ocr)
    # pdfinfo·convert 모두 POPPLER_TIMEOUT 을 받아야 함(멈춘 poppler 를 죽이는 핵심 방어)
    assert fake.pdfinfo_calls == [pdfmod.POPPLER_TIMEOUT]
    assert [t for _, t in fake.convert_calls] == [pdfmod.POPPLER_TIMEOUT] * 3


def test_page_cap_limits_ocr(force_ocr, monkeypatch):
    fake = _fake_pdf2image(n_pages=1000)
    monkeypatch.setitem(sys.modules, "pdf2image", fake)
    out = pdfmod.PdfExtractor().extract(force_ocr)
    assert len(fake.convert_calls) == pdfmod.OCR_MAX_PAGES     # 상한까지만 변환
    assert "OCR 생략" in out                                   # 생략 사실을 텍스트에 남김
    assert str(pdfmod.OCR_MAX_PAGES) in out


def test_page_failure_isolated(monkeypatch, tmp_path):
    # 실제 1×1 이미지로 정상 페이지를 처리 → ocr_image 모킹에 의존하지 않고 격리 구조만 검증
    # (실행 순서와 무관하게 견고). 한 페이지의 예외가 파일 전체·스캔을 막지 않아야 한다.
    from PIL import Image
    monkeypatch.setattr(pdfmod, "extract_text", lambda p: "")
    calls = []
    m = types.ModuleType("pdf2image")
    m.pdfinfo_from_path = lambda path, timeout=None: {"Pages": 5}

    def convert_from_path(path, first_page=None, last_page=None, timeout=None):
        calls.append(first_page)
        if first_page == 3:
            raise RuntimeError("poppler 멈춤/실패 모사")
        return [Image.new("RGB", (1, 1), "white")]

    m.convert_from_path = convert_from_path
    monkeypatch.setitem(sys.modules, "pdf2image", m)
    f = tmp_path / "scan.pdf"
    f.write_bytes(b"%PDF-1.4 fake")

    out = pdfmod.PdfExtractor().extract(str(f))   # 예외가 밖으로 전파되면 안 됨
    assert calls == [1, 2, 3, 4, 5]               # 실패(3) 이후에도 4·5 계속 시도
    assert out.count("OCR 실패") == 1             # 딱 한 페이지만 실패로 격리
    assert "페이지 3 OCR 실패" in out


def test_pdfminer_timeout_falls_back_to_ocr(monkeypatch, tmp_path):
    # pdfminer 가 timeout(CallTimeout)으로 끊기면 예외 없이 OCR 폴백으로 넘어가야 한다(T-016).
    from pii_scanner.core.timeout import CallTimeout

    def boom(p):
        raise CallTimeout("pdfminer 스핀 모사")

    monkeypatch.setattr(pdfmod, "extract_text", boom)
    fake = _fake_pdf2image(n_pages=2)
    monkeypatch.setitem(sys.modules, "pdf2image", fake)
    f = tmp_path / "bomb.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    pdfmod.PdfExtractor().extract(str(f))          # 예외 전파 없이 반환해야 함
    assert len(fake.convert_calls) == 2            # pdfminer 실패 → OCR 폴백 진입(2페이지 변환 시도)


def test_born_digital_skips_ocr(monkeypatch, tmp_path):
    # 텍스트 레이어가 충분하면 OCR 경로로 안 가야 함(pdf2image 미호출)
    monkeypatch.setattr(pdfmod, "extract_text", lambda p: "가" * 400)
    boom = types.ModuleType("pdf2image")
    boom.pdfinfo_from_path = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("born-digital 인데 OCR 경로 진입!"))
    monkeypatch.setitem(sys.modules, "pdf2image", boom)
    f = tmp_path / "digital.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    assert pdfmod.PdfExtractor().extract(str(f)) == "가" * 400
