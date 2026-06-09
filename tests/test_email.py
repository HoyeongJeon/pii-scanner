from pii_scanner.core.detectors.email import EmailDetector
from pii_scanner.core.models import Status, PiiType, RiskLevel

D = EmailDetector()


def test_email_detected_medium_risk():
    hits = list(D.find("문의 hong.gildong@example.com 으로"))
    assert len(hits) == 1
    assert hits[0].pii_type is PiiType.EMAIL
    assert hits[0].risk is RiskLevel.MEDIUM
    assert hits[0].status is Status.EXPOSED
    assert hits[0].snippet == "ho*****@example.com"


def test_short_local_part_masked_snippet():
    hits = list(D.find("a@b.com"))
    assert hits[0].snippet == "a*@b.com"


def test_no_false_positive_without_at():
    assert list(D.find("그냥 텍스트 example.com")) == []
