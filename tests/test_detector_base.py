from pii_scanner.core.detectors.base import Detector
from pii_scanner.core.models import PiiType, RiskLevel, Status, Confidence, PiiHit


class _Dummy(Detector):
    pii_type = PiiType.EMAIL
    risk = RiskLevel.MEDIUM

    def find(self, text):
        if "x" in text:
            yield PiiHit(self.pii_type, Status.EXPOSED, "x****",
                         0, 1, Confidence.CONFIRMED, self.risk)


def test_detector_is_iterable_source_of_hits():
    hits = list(_Dummy().find("xyz"))
    assert len(hits) == 1
    assert hits[0].pii_type is PiiType.EMAIL


def test_detector_requires_find():
    import pytest
    with pytest.raises(TypeError):
        Detector()  # 추상클래스 직접 생성 불가
