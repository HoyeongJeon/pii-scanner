import pytest

from pii_scanner.connectors.state import ScanState
from pii_scanner.core.models import FileResult, PiiHit, PiiType, Status, Confidence, RiskLevel


def _hit():
    return PiiHit(PiiType.RRN, Status.EXPOSED, "900101-1******", 0, 14,
                  Confidence.CONFIRMED, RiskLevel.CRITICAL)


def test_truncated_last_line_is_tolerated(tmp_path):
    # 크래시로 마지막 줄이 잘려도 앞선 유효 레코드는 읽혀야 한다(재개 가능).
    st = ScanState("scan1", base_dir=str(tmp_path))
    st.record(FileResult(path="/d/a.txt", hits=[_hit()]))
    with open(st.jsonl_path, "a", encoding="utf-8") as f:
        f.write('{"path": "/d/partial.txt", "hi')   # 잘린 줄(개행 없음)
    st2 = ScanState("scan1", base_dir=str(tmp_path))
    assert st2.is_done("/d/a.txt")                   # 유효 레코드 보존
    assert not st2.is_done("/d/partial.txt")         # 잘린 줄은 건너뜀
    assert len(st2.load_results().files) == 1


def test_scan_id_rejects_path_traversal(tmp_path):
    for bad in ["../evil", "a/b", "..", "x/../y", ""]:
        with pytest.raises(ValueError):
            ScanState(bad, base_dir=str(tmp_path))


def test_record_appends_and_marks_done(tmp_path):
    st = ScanState("scan1", base_dir=str(tmp_path))
    assert not st.is_done("/d/a.txt")
    fr = FileResult(path="/d/a.txt", hits=[_hit()])
    st.record(fr)
    assert st.is_done("/d/a.txt")


def test_done_set_reloaded_on_reopen(tmp_path):
    st = ScanState("scan1", base_dir=str(tmp_path))
    st.record(FileResult(path="/d/a.txt"))
    st.record(FileResult(path="/d/locked.docx", encrypted=True))
    st2 = ScanState("scan1", base_dir=str(tmp_path))      # 재개 시뮬레이션
    assert st2.is_done("/d/a.txt") and st2.is_done("/d/locked.docx")


def test_load_results_roundtrips_hits_and_flags(tmp_path):
    st = ScanState("scan1", base_dir=str(tmp_path))
    st.record(FileResult(path="/d/a.txt", hits=[_hit()]))
    st.record(FileResult(path="/d/locked.docx", encrypted=True))
    res = ScanState("scan1", base_dir=str(tmp_path)).load_results()
    by = {fr.path: fr for fr in res.files}
    assert by["/d/a.txt"].hits[0].pii_type is PiiType.RRN
    assert by["/d/a.txt"].hits[0].snippet == "900101-1******"
    assert by["/d/locked.docx"].encrypted is True


def test_cursor_persist(tmp_path):
    st = ScanState("scan1", base_dir=str(tmp_path))
    assert st.load_cursor() is None
    st.save_cursor("CUR123")
    assert ScanState("scan1", base_dir=str(tmp_path)).load_cursor() == "CUR123"


def test_load_results_roundtrips_hit_location(tmp_path):
    # D-030 갭: location 이 state 에 저장 안 되면 재개 스캔 리포트에서 위치가 유실된다
    st = ScanState("loc1", base_dir=str(tmp_path))
    h = _hit()
    h.location = "Sheet1!C5"
    st.record(FileResult(path="/d/a.xlsx", hits=[h]))
    res = ScanState("loc1", base_dir=str(tmp_path)).load_results()
    assert res.files[0].hits[0].location == "Sheet1!C5"


def test_load_results_tolerates_old_state_without_location(tmp_path):
    # 구형 state 파일(location 키 없음) 호환 — 기본 None
    import json
    st = ScanState("loc2", base_dir=str(tmp_path))
    with open(st.jsonl_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "path": "/d/old.txt", "error": None, "encrypted": False,
            "hits": [{"pii_type": "주민등록번호", "status": "노출",
                      "snippet": "900101-1******", "start": 0, "end": 14,
                      "confidence": "confirmed", "risk": "최상"}],
        }, ensure_ascii=False) + "\n")
    res = ScanState("loc2", base_dir=str(tmp_path)).load_results()
    assert res.files[0].hits[0].location is None


def test_load_results_roundtrips_corp_filtered(tmp_path):
    st = ScanState("cf1", base_dir=str(tmp_path))
    fr = FileResult(path="/d/a.xlsx")
    fr.corp_filtered = 4
    st.record(fr)
    res = ScanState("cf1", base_dir=str(tmp_path)).load_results()
    assert res.files[0].corp_filtered == 4     # 구형 파일은 d.get 기본값 0
