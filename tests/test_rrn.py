from pii_scanner.core.detectors.rrn import RrnDetector
from pii_scanner.core.checksum import rrn_checksum_valid
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


def test_valid_checksum_but_impossible_month_dropped():
    # 체크섬은 우연히 맞지만 13월 — 불가능한 날짜라 주민번호 아님(날짜 검증으로 드롭)
    assert rrn_checksum_valid("9013011234565")          # 전제: 체크섬은 통과
    assert list(D.find("9013011234565")) == []          # 그래도 13월이라 드롭


def test_valid_checksum_but_impossible_day_dropped():
    # 체크섬 통과하지만 32일 — 불가능한 날짜
    assert rrn_checksum_valid("9001321234565")
    assert list(D.find("9001321234565")) == []


def test_valid_date_and_checksum_still_detected():
    # 1990-01-01 유효 날짜 + 유효 체크섬 → 정상 탐지(과잉 드롭 방지)
    h = find_one("900101-1234568")
    assert h.pii_type is PiiType.RRN


def test_front_masked_still_detected_despite_no_date_check():
    # 앞자리가 가려지면 날짜 검증 불가 → 드롭하지 않음(뒤가 노출이면 탐지)
    h = find_one("******-1234567")
    assert h.status is Status.EXPOSED


def test_future_birth_year_dropped():
    # 성별코드 3 = 2000년대 출생인데 앞이 99 → 2099년생 = 불가능 → 드롭
    assert list(D.find("9901013000007")) == []


def test_past_birth_year_kept():
    # 성별코드 3 + 200101 → 2020년생 → 미래 아님 → 정상 탐지
    hits = list(D.find("2001013000004"))
    assert len(hits) == 1
    assert hits[0].status is Status.EXPOSED


def test_reference_year_controls_future_drop():
    # 2099년생: 기준연도 2098 이면 미래라 드롭, 2100 이면 미래 아니라 유지
    assert list(RrnDetector(reference_year=2098).find("9901013000007")) == []
    assert len(list(RrnDetector(reference_year=2100).find("9901013000007"))) == 1


def test_masked_gender_with_future_front_is_kept():
    # 앞자리는 99(미래연도처럼 보임)지만 성별코드가 가려져 세기를 알 수 없음
    # → 미래 판정 불가 → 드롭하면 안 됨(진짜 RRN 누락 방지). gender-게이트 회귀 가드.
    h = find_one("990101-*123456")
    assert h.status is Status.EXPOSED


def test_corp_reg_number_demoted_to_presumed():
    # RRN 체크섬 AND 법인 체크섬 둘 다 통과 → 법인번호 의심 → 추정 강등(드롭 안 함)
    h = find_one("9001011000006")
    assert h.status is Status.EXPOSED
    assert h.confidence is Confidence.PRESUMED
    assert h.snippet == "900101-1******"      # 원문 미노출 유지


def test_pure_rrn_stays_confirmed():
    # RRN 체크섬 통과, 법인 체크섬 실패 → 순수 주민번호 → confirmed 유지(회귀 없음)
    h = find_one("9001011000011")
    assert h.status is Status.EXPOSED
    assert h.confidence is Confidence.CONFIRMED


def test_corp_suspect_flag_marked_on_double_checksum():
    h = find_one("9001011000006")           # RRN+법인 양쪽 체크섬 통과
    assert h.corp_suspect is True
    assert h.confidence is Confidence.PRESUMED   # 기존 강등 유지


def test_pure_rrn_not_corp_suspect():
    h = find_one("9001011000011")           # RRN만 통과
    assert h.corp_suspect is False


def test_masked_hit_never_corp_suspect():
    h = find_one("900101-1******")          # 부분 마스킹 — 체크섬 검증 불가
    assert h.corp_suspect is False


# ---------------------------------------------------------------------------
# 구분자 매트릭스 — "줄 안쪽 서식 문자는 잡고, 줄/셀 경계는 안 잡는다".
# 잡아야 할 것과 잡으면 안 되는 것을 같은 표에 두어 어느 쪽으로 틀어져도 깨지게 한다.
# ---------------------------------------------------------------------------
import pytest as _pytest
from pii_scanner.core.detectors.foreign import ForeignDetector as _Foreign
from pii_scanner.core.detectors.driver import DriverDetector as _Driver

_SEP_CASES = [
    ("hyphen", "-", 1), ("space", " ", 1), ("tab", "\t", 1), ("nbsp", "\xa0", 1),
    ("newline", "\n", 0), ("cr", "\r", 0), ("formfeed", "\x0c", 0), ("vtab", "\v", 0),
    ("line_sep", " ", 0), ("para_sep", " ", 0),
]


@_pytest.mark.parametrize("name,sep,expected", _SEP_CASES)
def test_rrn_separator_matrix(name, sep, expected):
    text = "900101" + sep + "1123459"
    assert len(list(RrnDetector(reference_year=2026).find(text))) == expected


@_pytest.mark.parametrize("name,sep,expected", _SEP_CASES)
def test_foreign_separator_matrix(name, sep, expected):
    # ForeignDetector 는 RrnDetector 의 _PAT 를 상속한다 — 영향이 전파되는지 함께 고정.
    text = "900101" + sep + "5123456"
    assert len(list(_Foreign(reference_year=2026).find(text))) == expected


@_pytest.mark.parametrize("name,sep,expected", _SEP_CASES)
def test_driver_separator_matrix(name, sep, expected):
    text = sep.join(["11", "22", "334455", "66"])
    assert len(list(_Driver().find(text))) == expected


def test_crossline_match_does_not_swallow_the_real_rrn_after_it():
    """개행을 구분자에서 빼면, 줄을 넘겨 매치된 뒤 길이 검사로 버려지는 바람에
    바로 뒤의 진짜 번호까지 통째로 놓치던 미탐이 사라진다."""
    hits = list(RrnDetector(reference_year=2026).find(".111111\n9001011******"))
    assert len(hits) == 1
    assert hits[0].snippet == "900101-1******"


def test_crossline_match_does_not_swallow_the_real_driver_number_after_it():
    hits = list(_Driver().find("34\n56\n789012\n11-12-345678-90"))
    assert len(hits) == 1
