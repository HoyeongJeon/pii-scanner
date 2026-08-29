"""process_file 의 breadcrumb(현재 처리 파일 흔적) 동작 검증 (T-016 교착 복구용).

PII_BREADCRUMB_DIR 설정 시에만 동작하고, 추출 도중 흔적이 존재하다 종료 후 사라져야 한다.
"""
from pii_scanner.core import scanner


class FakeSF:
    def __init__(self, logical_path):
        self.logical_path = logical_path

    def __enter__(self):
        return "/tmp/fake_local_path"

    def __exit__(self, *exc):
        return False


def test_breadcrumb_present_during_extraction_and_removed_after(monkeypatch, tmp_path):
    bcdir = tmp_path / "crumbs"
    bcdir.mkdir()
    monkeypatch.setenv("PII_BREADCRUMB_DIR", str(bcdir))
    seen = {}

    class FakeExtractor:
        def extract_located(self, path):
            seen["during"] = [p.read_text(encoding="utf-8") for p in bcdir.iterdir()]
            return "", None

    monkeypatch.setattr(scanner, "get_extractor", lambda p: FakeExtractor())
    scanner.process_file(FakeSF("/dept/doc.pdf"), [])

    assert seen["during"] == ["/dept/doc.pdf"]   # 추출 중 흔적 존재
    assert list(bcdir.iterdir()) == []                       # 종료 후 제거


def test_no_breadcrumb_when_env_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("PII_BREADCRUMB_DIR", raising=False)
    bcdir = tmp_path / "crumbs"
    bcdir.mkdir()

    class FakeExtractor:
        def extract_located(self, path):
            return "", None

    monkeypatch.setattr(scanner, "get_extractor", lambda p: FakeExtractor())
    scanner.process_file(FakeSF("/dept/doc.pdf"), [])

    assert list(bcdir.iterdir()) == []                       # env 미설정 → 무동작


def test_breadcrumb_removed_even_on_extractor_error(monkeypatch, tmp_path):
    bcdir = tmp_path / "crumbs"
    bcdir.mkdir()
    monkeypatch.setenv("PII_BREADCRUMB_DIR", str(bcdir))

    class BoomExtractor:
        def extract_located(self, path):
            raise RuntimeError("추출 폭발")

    monkeypatch.setattr(scanner, "get_extractor", lambda p: BoomExtractor())
    fr = scanner.process_file(FakeSF("/dept/doc.pdf"), [])

    assert fr.error and "추출 실패" in fr.error               # 에러 격리는 그대로
    assert list(bcdir.iterdir()) == []                       # 예외에도 흔적 정리(finally)
