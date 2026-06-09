import openpyxl
from pii_scanner.reporters.excel import write_excel
from pii_scanner.core.models import (
    ScanResult, FileResult, PiiHit, PiiType, Status, Confidence, RiskLevel,
)


def _result():
    sr = ScanResult()
    fr = FileResult(path="/x/a.txt")
    fr.hits.append(PiiHit(PiiType.RRN, Status.EXPOSED, "900101-1******", 0, 13,
                          Confidence.CONFIRMED, RiskLevel.CRITICAL))
    sr.files.append(fr)
    sr.files.append(FileResult(path="/x/bad.txt", error="추출 실패: X"))
    return sr


def test_excel_has_three_sheets_and_no_raw(tmp_path):
    out = tmp_path / "r.xlsx"
    write_excel(_result(), str(out))
    wb = openpyxl.load_workbook(str(out))
    assert set(wb.sheetnames) == {"findings", "errors", "summary"}
    # findings 에 마스킹 스니펫만, 원문 없음
    findings_text = " ".join(
        str(c.value) for row in wb["findings"].iter_rows() for c in row if c.value
    )
    assert "900101-1******" in findings_text
    assert "1234568" not in findings_text   # 원문 절대 미기록
