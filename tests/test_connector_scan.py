import pytest
from pii_scanner.connectors.base import SourceFile, Connector


def test_sourcefile_is_abstract():
    with pytest.raises(TypeError):
        SourceFile()                      # 추상 — 직접 인스턴스화 불가


def test_connector_is_abstract():
    with pytest.raises(TypeError):
        Connector()


def test_concrete_sourcefile_works_as_context_manager():
    class _SF(SourceFile):
        def __init__(self, p):
            self.logical_path = p
            self.entered = self.exited = False
        def __enter__(self):
            self.entered = True
            return "/tmp/local"
        def __exit__(self, *exc):
            self.exited = True

    sf = _SF("/dropbox/a.txt")
    with sf as local:
        assert local == "/tmp/local"
    assert sf.entered and sf.exited
    assert sf.logical_path == "/dropbox/a.txt"


from pii_scanner.core.scanner import scan
from pii_scanner.config import ScanConfig
from pii_scanner.core.extractors import EncryptedFileError
from pii_scanner.core.extractors.base import Extractor


class _FakeSF(SourceFile):
    """진입 성공을 시뮬레이션하는 가짜 SourceFile. __exit__ 호출 여부를 기록한다.

    실패는 __enter__ 가 아니라 추출기에서 주입한다(실제 흐름과 동일 — 추출 단계 실패는
    with 블록 내부라 with 가 __exit__ 를 보장한다).
    """
    def __init__(self, path):
        self.logical_path = path
        self.exited = False
    def __enter__(self):
        return self.logical_path
    def __exit__(self, *exc):
        self.exited = True


class _FakeConn(Connector):
    def __init__(self, sfs):
        self.sfs = sfs
    def iter_files(self, config):
        yield from self.sfs


def test_scan_detects_isolates_classifies_and_cleans(monkeypatch):
    # 추출기를 주입해 경로별로 텍스트 반환 또는 예외 발생을 시뮬레이션한다.
    import pii_scanner.core.scanner as scn
    behavior = {
        "/d/good.txt": "주민 900101-1234568",            # 텍스트 → 탐지
        "/d/broken.txt": ValueError("boom"),             # 추출 예외 → error
        "/d/locked.docx": EncryptedFileError("locked"),  # 암호화 예외 → encrypted
    }
    class _Ext(Extractor):
        def __init__(self, path): self.path = path
        def extract(self, local):
            v = behavior[self.path]
            if isinstance(v, Exception):
                raise v
            return v
    monkeypatch.setattr(scn, "get_extractor", lambda path: _Ext(path))

    good = _FakeSF("/d/good.txt")
    broken = _FakeSF("/d/broken.txt")
    enc = _FakeSF("/d/locked.docx")
    result = scan(_FakeConn([good, broken, enc]), ScanConfig())
    by = {fr.path: fr for fr in result.files}

    assert by["/d/good.txt"].hits                            # 탐지됨
    assert by["/d/broken.txt"].error and not by["/d/broken.txt"].encrypted
    assert by["/d/locked.docx"].encrypted and by["/d/locked.docx"].error is None
    assert good.exited and broken.exited and enc.exited      # with 가 __exit__ 보장


def test_scan_paths_still_works(tmp_path):
    (tmp_path / "a.txt").write_text("폰 010-1234-5678", encoding="utf-8")
    from pii_scanner.core.scanner import scan_paths
    result = scan_paths([str(tmp_path)], ScanConfig())
    assert len(result.files) == 1


def test_scan_with_state_skips_done_and_records(tmp_path, monkeypatch):
    import pii_scanner.core.scanner as scn
    from pii_scanner.connectors.state import ScanState

    texts = {"/d/a.txt": "주민 900101-1234568", "/d/b.txt": "폰 010-1234-5678"}
    class _Ext(Extractor):
        def extract(self, path):
            return texts[path]
    monkeypatch.setattr(scn, "get_extractor", lambda path: _Ext())

    a = _FakeSF("/d/a.txt")
    st = ScanState("s1", base_dir=str(tmp_path))
    scn.scan(_FakeConn([a]), ScanConfig(), state=st)        # 1차: a 만 스캔
    assert st.is_done("/d/a.txt")

    st2 = ScanState("s1", base_dir=str(tmp_path))           # 재개(완료 path 로드)
    a2 = _FakeSF("/d/a.txt")
    b2 = _FakeSF("/d/b.txt")
    scn.scan(_FakeConn([a2, b2]), ScanConfig(), state=st2)  # a 건너뜀, b 만 진입
    assert a2.exited is False                                # a 는 __enter__ 안 됨(스킵)
    assert b2.exited is True
    assert st2.is_done("/d/b.txt")
