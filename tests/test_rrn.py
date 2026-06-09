from pii_scanner.core.detectors.rrn import RrnDetector
from pii_scanner.core.models import Status, Confidence, PiiType, RiskLevel

D = RrnDetector()


def find_one(text):
    hits = list(D.find(text))
    assert len(hits) == 1, hits
    return hits[0]


def test_valid_rrn_is_exposed_confirmed():
    h = find_one("성명 홍길동 900101-1234568 끝")
    assert h.pii_type is PiiType.RRN
    assert h.status is Status.EXPOSED
    assert h.confidence is Confidence.CONFIRMED
    assert h.risk is RiskLevel.CRITICAL
    assert h.snippet == "900101-1******"   # 원문 미노출


def test_invalid_checksum_is_dropped():
    assert list(D.find("9001011234567")) == []  # 체크섬 불일치 → 주민번호 아님


def test_back_fully_masked_is_masked_status():
    h = find_one("900101-1******")
    assert h.status is Status.MASKED
    assert h.snippet == "900101-1******"


def test_back_all_masked_is_masked():
    h = find_one("900101-*******")
    assert h.status is Status.MASKED


def test_partial_mask_is_exposed_presumed():
    h = find_one("900101-123****")  # 뒤 4자리만 가림 → 부족 → 노출
    assert h.status is Status.EXPOSED
    assert h.confidence is Confidence.PRESUMED


def test_front_masked_back_exposed_is_exposed():
    h = find_one("******-1234567")
    assert h.status is Status.EXPOSED


def test_foreign_gender_code_not_claimed_by_rrn():
    # 성별코드 5 → 외국인 → RRN 탐지기는 잡지 않음
    assert list(D.find("900101-5234561")) == []
