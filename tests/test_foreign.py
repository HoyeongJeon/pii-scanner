from pii_scanner.core.detectors.foreign import ForeignDetector
from pii_scanner.core.models import Status, Confidence, PiiType

D = ForeignDetector()


def find_one(text):
    hits = list(D.find(text))
    assert len(hits) == 1, hits
    return hits[0]


def test_foreign_gender_5to8_is_detected():
    h = find_one("등록번호 900101-5234561 입니다")
    assert h.pii_type is PiiType.FOREIGN
    assert h.status is Status.EXPOSED
    # 체크섬 신뢰 불가 → 통과여부와 무관히 드롭하지 않음
    assert h.confidence in (Confidence.CONFIRMED, Confidence.PRESUMED)
    assert h.snippet == "900101-5******"


def test_rrn_gender_not_claimed_by_foreign():
    assert list(D.find("900101-1234568")) == []  # 성별 1 → 내국인


def test_foreign_back_masked_is_masked():
    h = find_one("900101-5******")
    assert h.status is Status.MASKED


def test_foreign_future_birth_year_dropped():
    # 외국인 성별코드 7 = 2000년대 + 990101 → 2099년생 → 미래 → 드롭(상속된 가드)
    assert list(ForeignDetector().find("9901017000008")) == []
