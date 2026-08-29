from pii_scanner.reporters.summary import summarize
from pii_scanner.core.models import (
    ScanResult, FileResult, PiiHit, PiiType, Status, Confidence, RiskLevel,
)


def _hit(status):
    return PiiHit(PiiType.RRN, status, "900101-1******", 0, 13,
                 Confidence.CONFIRMED, RiskLevel.CRITICAL)


def test_masking_rate_and_counts():
    sr = ScanResult()
    fr = FileResult(path="/x/a.txt")
    fr.hits = [_hit(Status.EXPOSED), _hit(Status.EXPOSED), _hit(Status.MASKED)]
    sr.files.append(fr)
    sr.files.append(FileResult(path="/x/bad.txt", error="추출 실패: X"))

    s = summarize(sr)
    assert s.total_files == 2
    assert s.error_files == 1
    assert s.exposed == 2
    assert s.masked == 1
    assert round(s.masking_rate, 1) == 33.3   # 1 / (2+1) * 100
    assert s.by_type[PiiType.RRN]["exposed"] == 2


def test_zero_pii_gives_100_percent():
    s = summarize(ScanResult())
    assert s.masking_rate == 100.0


def test_summary_sums_corp_filtered():
    sr = ScanResult()
    a = FileResult(path="/x/a.xlsx"); a.corp_filtered = 3
    b = FileResult(path="/x/b.xls");  b.corp_filtered = 2
    sr.files.extend([a, b])
    assert summarize(sr).corp_filtered == 5


def test_unreadable_paths_counted_separately_not_as_scanned_files():
    """읽지 못한 폴더는 '스캔한 파일'도 '추출 실패'도 아니다 — 섞으면 커버리지가 좋아 보인다."""
    from pii_scanner.core.models import FileResult, ScanResult
    from pii_scanner.reporters.summary import summarize

    r = ScanResult()
    r.files.append(FileResult(path="/a.txt"))
    r.files.append(FileResult(path="/hr", error="접근 실패: 권한 없음", unreadable=True))
    s = summarize(r)
    assert s.unreadable_paths == 1
    assert s.total_files == 1        # 폴더는 파일 수에 안 들어간다
    assert s.error_files == 0        # 추출 실패로도 안 센다


def test_stamp_scan_meta_records_provenance_deterministically():
    import datetime
    from pii_scanner.config import ScanConfig
    from pii_scanner.reporters.summary import Summary, stamp_scan_meta
    import pii_scanner

    s = stamp_scan_meta(Summary(), ScanConfig(),
                        now=datetime.datetime(2026, 8, 28, 9, 30, 0, 123456))
    assert s.scanned_at == "2026-08-28T09:30:00"      # ISO8601, 마이크로초 제거
    assert s.tool_version == pii_scanner.__version__
    assert "주민등록번호" in s.active_types
    assert any("외국인등록번호" in t for t in s.inactive_types)
