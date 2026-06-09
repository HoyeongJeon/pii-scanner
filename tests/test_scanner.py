from pii_scanner.core.scanner import scan_paths
from pii_scanner.config import ScanConfig
from pii_scanner.core.models import Status, PiiType


def test_scan_detects_across_files(tmp_path):
    (tmp_path / "a.txt").write_text("홍길동 900101-1234568", encoding="utf-8")
    (tmp_path / "b.txt").write_text("메일 ho@example.com", encoding="utf-8")
    result = scan_paths([str(tmp_path)], ScanConfig())
    all_types = {h.pii_type for fr in result.files for h in fr.hits}
    assert PiiType.RRN in all_types
    assert PiiType.EMAIL in all_types


def test_extraction_error_is_recorded_not_fatal(tmp_path):
    good = tmp_path / "good.txt"
    good.write_text("900101-1234568", encoding="utf-8")
    bad = tmp_path / "bad.docx"          # docx 인데 내용이 깨짐 → 추출 실패
    bad.write_text("not a real docx", encoding="utf-8")
    result = scan_paths([str(tmp_path)], ScanConfig())
    by_name = {fr.path.split("/")[-1]: fr for fr in result.files}
    assert by_name["bad.docx"].error is not None       # 에러 기록됨
    assert any(h.status is Status.EXPOSED for h in by_name["good.txt"].hits)  # 계속 진행


def test_masked_only_file_counts_masked(tmp_path):
    (tmp_path / "m.txt").write_text("900101-1******", encoding="utf-8")
    result = scan_paths([str(tmp_path)], ScanConfig())
    statuses = [h.status for fr in result.files for h in fr.hits]
    assert Status.MASKED in statuses
