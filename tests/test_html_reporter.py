from pii_scanner.reporters.html import write_html
from pii_scanner.core.models import (
    ScanResult, FileResult, PiiHit, PiiType, Status, Confidence, RiskLevel,
)


def test_html_contains_kpi_and_no_raw(tmp_path):
    sr = ScanResult()
    fr = FileResult(path="/x/a.txt")
    fr.hits.append(PiiHit(PiiType.RRN, Status.EXPOSED, "900101-1******", 0, 13,
                          Confidence.CONFIRMED, RiskLevel.CRITICAL))
    fr.hits.append(PiiHit(PiiType.RRN, Status.MASKED, "900101-1******", 0, 13,
                          Confidence.CONFIRMED, RiskLevel.CRITICAL))
    sr.files.append(fr)
    out = tmp_path / "r.html"
    write_html(sr, str(out))
    html = out.read_text(encoding="utf-8")
    assert "마스킹률" in html
    assert "50.0" in html            # 1 masked / 2 total
    assert "900101-1******" in html
    assert "1234568" not in html     # 원문 미기록


def test_html_escapes_path_metacharacters(tmp_path):
    """파일 경로/이름의 HTML 메타문자가 이스케이프되어야 함 (XSS/레이아웃 깨짐 방지)."""
    sr = ScanResult()
    # 경로에 < > & " 가 포함된 극단 케이스
    danger_path = '/data/<b>weird</b> & "name".txt'
    fr = FileResult(path=danger_path)
    fr.hits.append(PiiHit(PiiType.EMAIL, Status.EXPOSED, "ho****@x.com", 0, 12,
                          Confidence.CONFIRMED, RiskLevel.MEDIUM))
    sr.files.append(fr)
    out = tmp_path / "r.html"
    write_html(sr, str(out))
    html = out.read_text(encoding="utf-8")
    # 원시 태그 <b>...</b> 가 그대로 마크업으로 나오면 안 됨
    assert "<b>weird</b>" not in html
    # 이스케이프된 형태로 존재해야 함
    assert "&lt;b&gt;" in html
    assert "&amp;" in html
