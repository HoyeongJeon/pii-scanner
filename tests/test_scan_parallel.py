import threading
from pii_scanner.core.scanner import scan, scan_parallel
from pii_scanner.config import ScanConfig
from pii_scanner.connectors.base import SourceFile, Connector
from pii_scanner.connectors.state import ScanState
from pii_scanner.core.extractors.base import Extractor


class _FakeSF(SourceFile):
    def __init__(self, path):
        self.logical_path = path
        self.exited = False
    def __enter__(self):
        return self.logical_path
    def __exit__(self, *exc):
        self.exited = True


class _BatchConn(Connector):
    """iter_batches 를 직접 정의해 페이지 경계를 제어하는 가짜 커넥터."""
    def __init__(self, batches):
        self.batches = batches
    def iter_files(self, config):
        for b in self.batches:
            yield from b
    def iter_batches(self, config):
        yield from self.batches


def _patch_ext(monkeypatch, behavior):
    import pii_scanner.core.scanner as scn
    class _Ext(Extractor):
        def __init__(self, path): self.path = path
        def extract(self, local):
            v = behavior[self.path]
            if isinstance(v, Exception):
                raise v
            return v
    monkeypatch.setattr(scn, "get_extractor", lambda path: _Ext(path))


def test_scan_parallel_processes_all_files(monkeypatch):
    _patch_ext(monkeypatch, {"/d/a.txt": "주민 900101-1234568",
                             "/d/b.txt": "메일 ho@example.com"})
    conn = _BatchConn([[_FakeSF("/d/a.txt"), _FakeSF("/d/b.txt")]])
    result = scan_parallel(conn, ScanConfig(), max_workers=4)
    assert {fr.path for fr in result.files} == {"/d/a.txt", "/d/b.txt"}


def test_scan_parallel_isolates_errors(monkeypatch):
    _patch_ext(monkeypatch, {"/d/ok.txt": "주민 900101-1234568",
                             "/d/bad.txt": ValueError("boom")})
    conn = _BatchConn([[_FakeSF("/d/ok.txt"), _FakeSF("/d/bad.txt")]])
    by = {fr.path: fr for fr in scan_parallel(conn, ScanConfig(), max_workers=4).files}
    assert by["/d/ok.txt"].hits
    assert by["/d/bad.txt"].error is not None


def test_scan_parallel_records_each_file_once(tmp_path, monkeypatch):
    paths = [f"/d/f{i}.txt" for i in range(50)]
    _patch_ext(monkeypatch, {p: "폰 010-1234-5678" for p in paths})
    conn = _BatchConn([[_FakeSF(p) for p in paths]])
    st = ScanState("p1", base_dir=str(tmp_path))
    scan_parallel(conn, ScanConfig(), state=st, max_workers=8)
    recorded = [fr.path for fr in ScanState("p1", base_dir=str(tmp_path)).load_results().files]
    assert sorted(recorded) == sorted(paths)
    assert len(recorded) == len(set(recorded))


def test_scan_parallel_skips_done_on_resume(tmp_path, monkeypatch):
    _patch_ext(monkeypatch, {"/d/a.txt": "주민 900101-1234568",
                             "/d/b.txt": "폰 010-1234-5678"})
    st = ScanState("p2", base_dir=str(tmp_path))
    scan_parallel(_BatchConn([[_FakeSF("/d/a.txt")]]), ScanConfig(), state=st, max_workers=2)

    st2 = ScanState("p2", base_dir=str(tmp_path))
    a2, b2 = _FakeSF("/d/a.txt"), _FakeSF("/d/b.txt")
    scan_parallel(_BatchConn([[a2, b2]]), ScanConfig(), state=st2, max_workers=2)
    assert a2.exited is False
    assert b2.exited is True
    assert st2.is_done("/d/b.txt")


def test_scan_parallel_records_whole_batch_before_advancing_page(monkeypatch):
    _patch_ext(monkeypatch, {p: "폰 010-1234-5678"
                             for p in ["/d/a", "/d/b", "/d/c", "/d/d"]})
    log = []
    lock = threading.Lock()

    class _SpyConn(Connector):
        def iter_files(self, config):
            raise NotImplementedError
        def iter_batches(self, config):
            for i, batch in enumerate([[_FakeSF("/d/a"), _FakeSF("/d/b")],
                                       [_FakeSF("/d/c"), _FakeSF("/d/d")]]):
                yield batch
                with lock:
                    log.append(("advance", i))

    class _SpyState:
        def is_done(self, path): return False
        def record(self, fr):
            with lock:
                log.append(("record", fr.path))

    scan_parallel(_SpyConn(), ScanConfig(), state=_SpyState(), max_workers=2)

    adv0 = log.index(("advance", 0))
    batch0 = {e[1] for e in log[:adv0] if e[0] == "record"}
    assert batch0 == {"/d/a", "/d/b"}
    after = {e[1] for e in log[adv0 + 1:] if e[0] == "record"}
    assert after == {"/d/c", "/d/d"}


def test_scan_parallel_matches_sequential(monkeypatch):
    behavior = {"/d/a.txt": "주민 900101-1234568", "/d/b.txt": "메일 ho@example.com",
                "/d/bad.docx": ValueError("boom")}
    _patch_ext(monkeypatch, behavior)
    seq = scan(_BatchConn([[_FakeSF("/d/a.txt"), _FakeSF("/d/b.txt"),
                            _FakeSF("/d/bad.docx")]]), ScanConfig())
    _patch_ext(monkeypatch, behavior)
    par = scan_parallel(_BatchConn([[_FakeSF("/d/a.txt"), _FakeSF("/d/b.txt"),
                                     _FakeSF("/d/bad.docx")]]), ScanConfig(), max_workers=4)

    def summary(r):
        return {fr.path: (tuple(sorted(h.pii_type.value for h in fr.hits)),
                          fr.error is not None, fr.encrypted)
                for fr in r.files}
    assert summary(seq) == summary(par)
