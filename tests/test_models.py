from pii_scanner.core.models import (
    PiiType, RiskLevel, Status, Confidence, PiiHit, FileResult, ScanResult
)


def test_pii_hit_holds_masked_snippet_not_raw():
    hit = PiiHit(
        pii_type=PiiType.RRN,
        status=Status.EXPOSED,
        snippet="900101-1******",
        start=10,
        end=24,
        confidence=Confidence.CONFIRMED,
        risk=RiskLevel.CRITICAL,
    )
    assert hit.snippet == "900101-1******"
    assert hit.pii_type is PiiType.RRN
    assert hit.status is Status.EXPOSED


def test_scan_result_aggregates_files():
    fr = FileResult(path="/x/a.txt")
    fr.hits.append(
        PiiHit(PiiType.EMAIL, Status.EXPOSED, "ho****@x.com", 0, 12,
               Confidence.CONFIRMED, RiskLevel.MEDIUM)
    )
    sr = ScanResult()
    sr.files.append(fr)
    assert len(sr.files) == 1
    assert sr.files[0].hits[0].pii_type is PiiType.EMAIL


def test_file_result_can_record_error():
    fr = FileResult(path="/x/bad.hwp", error="추출 실패: 손상 파일")
    assert fr.error == "추출 실패: 손상 파일"
    assert fr.hits == []
