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


def test_html_hits_table_shows_location(tmp_path):
    sr = ScanResult()
    fr = FileResult(path="/x/a.pdf")
    fr.hits.append(PiiHit(PiiType.EMAIL, Status.EXPOSED, "ho****@x.com", 0, 12,
                          Confidence.CONFIRMED, RiskLevel.MEDIUM,
                          location="p.2 L5"))
    sr.files.append(fr)
    out = tmp_path / "r.html"
    write_html(sr, str(out))
    html = out.read_text(encoding="utf-8")
    assert "위치" in html          # 컬럼 헤더
    assert "p.2 L5" in html        # 위치 값


def test_html_stream_caps_hits_table_and_notes_skipped(tmp_path):
    # T-014: 탐지 목록이 상한을 넘으면 생략 안내를 남기고 KPI 집계는 전체 기준 유지
    from pii_scanner.reporters.html import write_html_stream
    from pii_scanner.reporters.summary import summarize
    sr = ScanResult()
    fr = FileResult(path="/x/many.txt")
    for i in range(5):
        fr.hits.append(PiiHit(PiiType.PHONE, Status.EXPOSED, f"010-****-{i:04d}",
                              0, 13, Confidence.CONFIRMED, RiskLevel.HIGH))
    sr.files.append(fr)
    out = tmp_path / "r.html"
    write_html_stream(iter(sr.files), str(out), summarize(sr), max_hits=3)
    html = out.read_text(encoding="utf-8")
    assert "010-****-0002" in html          # 상한 내 행은 표시
    assert "010-****-0003" not in html      # 상한 초과 행은 생략
    assert "2건 생략" in html               # 생략 안내
    assert ">5<" in html                    # 노출 건수 KPI 는 전체(5)


def test_html_shows_corp_filtered_card(tmp_path):
    sr = ScanResult()
    fr = FileResult(path="/x/a.xlsx")
    fr.corp_filtered = 7
    sr.files.append(fr)
    out = tmp_path / "r.html"
    write_html(sr, str(out))
    html = out.read_text(encoding="utf-8")
    assert "법인번호 오탐 제거" in html
    assert ">7<" in html


def test_html_stream_keeps_key_pii_rows_when_cap_reached(tmp_path):
    """HTML 탐지 목록도 상한이 차면 고유식별정보부터 지켜야 한다 — 엑셀과 같은 이유(T-017 후속)."""
    from pii_scanner.reporters.html import write_html_stream
    from pii_scanner.reporters.summary import summarize
    sr = ScanResult()
    noisy = FileResult(path="/x/contacts.csv")
    for i in range(10):
        noisy.hits.append(PiiHit(PiiType.EMAIL, Status.EXPOSED, f"a{i}@ex***.com", 0, 12,
                                 Confidence.CONFIRMED, RiskLevel.MEDIUM))
    late = FileResult(path="/x/late.xlsx")
    late.hits.append(PiiHit(PiiType.RRN, Status.EXPOSED, "900101-1******", 0, 13,
                            Confidence.CONFIRMED, RiskLevel.CRITICAL))
    sr.files.extend([noisy, late])

    out = tmp_path / "r.html"
    write_html_stream(iter(sr.files), str(out), summarize(sr), max_hits=3)

    html = out.read_text(encoding="utf-8")
    assert "900101-1******" in html          # 뒤에 나와도 반드시 표에 남는다


def test_html_stream_prefers_exposed_key_pii_over_masked(tmp_path):
    """고유식별정보 안에서도 '노출'이 '마스킹'보다 먼저다 — 마스킹이 노출을 밀어내면 안 된다.

    실측: 마스킹 건수가 노출의 80배가 넘는 스캔에서, 상한이 전부 고유식별정보로 차더라도
    마스킹이 앞자리를 먹어 노출이 절반 넘게 잘려나갔다(T-017 후속2).
    """
    from pii_scanner.reporters.html import write_html_stream
    from pii_scanner.reporters.summary import summarize
    sr = ScanResult()
    bulk = FileResult(path="/x/masked.xlsx")
    for i in range(10):
        bulk.hits.append(PiiHit(PiiType.RRN, Status.MASKED, f"9001{i:02d}-*******", 0, 13,
                                Confidence.CONFIRMED, RiskLevel.CRITICAL))
    late = FileResult(path="/x/late.xlsx")
    late.hits.append(PiiHit(PiiType.RRN, Status.EXPOSED, "800215-1******", 0, 13,
                            Confidence.CONFIRMED, RiskLevel.CRITICAL))
    sr.files.extend([bulk, late])

    out = tmp_path / "r.html"
    write_html_stream(iter(sr.files), str(out), summarize(sr), max_hits=3)

    assert "800215-1******" in out.read_text(encoding="utf-8")   # 뒤에 나온 노출이 남아야
