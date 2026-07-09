import openpyxl
from pii_scanner.core.models import ScanResult, FileResult
from pii_scanner.reporters.summary import summarize
from pii_scanner.reporters.excel import write_excel
from pii_scanner.reporters.html import write_html


def _result():
    r = ScanResult()
    r.files.append(FileResult(path="/d/a.txt"))                       # 정상(무탐지)
    fr = FileResult(path="/d/locked.docx"); fr.encrypted = True
    r.files.append(fr)
    r.files.append(FileResult(path="/d/bad.pdf", error="추출 실패: X"))
    return r


def test_summary_counts_encrypted():
    s = summarize(_result())
    assert s.encrypted_files == 1
    assert s.error_files == 1
    # 암호화 파일이 hits 집계로 새지 않는지(단락 회귀 방지)
    assert s.exposed == 0
    assert s.masked == 0


def test_excel_has_encrypted_count(tmp_path):
    out = tmp_path / "r.xlsx"; write_excel(_result(), str(out))
    wb = openpyxl.load_workbook(str(out))
    blob = " ".join(
        str(c.value) for ws in wb.worksheets for row in ws.iter_rows()
        for c in row if c.value is not None
    )
    assert "암호화" in blob


def test_html_has_encrypted_card(tmp_path):
    out = tmp_path / "r.html"; write_html(_result(), str(out))
    assert "암호화" in out.read_text(encoding="utf-8")


def test_html_lists_encrypted_file_paths(tmp_path):
    # 카운트뿐 아니라 '어떤 파일'이 암호화로 건너뛰어졌는지도 보여야 한다(커버리지 정직성).
    out = tmp_path / "r.html"; write_html(_result(), str(out))
    assert "/d/locked.docx" in out.read_text(encoding="utf-8")
