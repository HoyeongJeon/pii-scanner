import docx
import openpyxl
from pii_scanner.core.extractors.office import DocxExtractor, XlsxExtractor


def test_docx_extract(tmp_path):
    p = tmp_path / "a.docx"
    d = docx.Document()
    d.add_paragraph("홍길동 900101-1234568")
    d.save(str(p))
    assert "900101-1234568" in DocxExtractor().extract(str(p))


def test_xlsx_extract(tmp_path):
    p = tmp_path / "a.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "홍길동"
    ws["B1"] = "010-1234-5678"
    wb.save(str(p))
    text = XlsxExtractor().extract(str(p))
    assert "010-1234-5678" in text
