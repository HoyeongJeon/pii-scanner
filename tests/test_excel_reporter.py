import openpyxl
from pii_scanner.reporters.excel import write_excel
from pii_scanner.core.models import (
    ScanResult, FileResult, PiiHit, PiiType, Status, Confidence, RiskLevel,
)


def _result():
    sr = ScanResult()
    fr = FileResult(path="/x/a.txt")
    fr.hits.append(PiiHit(PiiType.RRN, Status.EXPOSED, "900101-1******", 0, 13,
                          Confidence.CONFIRMED, RiskLevel.CRITICAL,
                          location="Sheet1!C5"))
    sr.files.append(fr)
    sr.files.append(FileResult(path="/x/bad.txt", error="추출 실패: X"))
    return sr


def test_excel_has_four_sheets_and_no_raw(tmp_path):
    out = tmp_path / "r.xlsx"
    write_excel(_result(), str(out))
    wb = openpyxl.load_workbook(str(out))
    assert set(wb.sheetnames) == {"findings", "errors", "summary", "encrypted"}
    # findings 에 마스킹 스니펫만, 원문 없음
    findings_text = " ".join(
        str(c.value) for row in wb["findings"].iter_rows() for c in row if c.value
    )
    assert "900101-1******" in findings_text
    assert "1234568" not in findings_text   # 원문 절대 미기록


def test_excel_findings_include_location_column(tmp_path):
    out = tmp_path / "r.xlsx"
    write_excel(_result(), str(out))
    wb = openpyxl.load_workbook(str(out))
    rows = list(wb["findings"].iter_rows(values_only=True))
    header = rows[0]
    assert "위치" in header
    assert rows[1][header.index("위치")] == "Sheet1!C5"


def test_excel_summary_shows_corp_filtered(tmp_path):
    sr = _result()
    sr.files[0].corp_filtered = 7
    out = tmp_path / "r.xlsx"
    write_excel(sr, str(out))
    wb = openpyxl.load_workbook(str(out))
    rows = {str(r[0]): r[1] for r in wb["summary"].iter_rows(values_only=True) if r[0]}
    assert rows["법인등록번호 오탐 제거"] == 7
