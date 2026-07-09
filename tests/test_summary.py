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
