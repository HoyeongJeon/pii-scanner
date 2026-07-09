import os
import tempfile
import pytest
pytest.importorskip("dropbox")
from unittest.mock import MagicMock
import dropbox as _dbx
from pii_scanner.connectors.dropbox_conn import DropboxSourceFile, DropboxConnector
from pii_scanner.config import ScanConfig


def test_sourcefile_downloads_to_systemp_and_deletes():
    dbx = MagicMock()
    captured = {}
    def fake_dl(local, path):
        captured["local"] = local; captured["path"] = path
        with open(local, "wb") as f:
            f.write(b"data")
    dbx.files_download_to_file.side_effect = fake_dl

    sf = DropboxSourceFile(dbx, "/팀/a.xlsx", "/팀/a.xlsx")
    with sf as local:
        assert os.path.exists(local)
        assert local.startswith(tempfile.gettempdir())     # 동기화 폴더 밖(시스템 temp)
        assert captured["path"] == "/팀/a.xlsx"             # path_lower 로 다운로드
    assert not os.path.exists(local)                         # __exit__ 에서 삭제
    assert sf.logical_path == "/팀/a.xlsx"


def test_sourcefile_deletes_temp_even_on_exception():
    dbx = MagicMock()
    dbx.files_download_to_file.side_effect = lambda local, path: open(local, "wb").close()
    sf = DropboxSourceFile(dbx, "/팀/b.pdf", "/팀/b.pdf")
    try:
        with sf as local:
            raise RuntimeError("boom")          # with 블록 내부 예외
    except RuntimeError:
        pass
    assert not os.path.exists(local)                         # 예외에도 정리


def test_sourcefile_cleans_temp_when_download_fails():
    # 다운로드(__enter__) 자체가 실패하면 with 는 __exit__ 를 안 부른다 →
    # __enter__ 가 스스로 temp 를 정리하고 예외를 전파해야 한다.
    dbx = MagicMock()
    captured = {}
    def fail_dl(local, path):
        captured["local"] = local
        open(local, "wb").close()               # temp 가 이미 만들어진 상태
        raise RuntimeError("download failed")
    dbx.files_download_to_file.side_effect = fail_dl
    sf = DropboxSourceFile(dbx, "/팀/gone.txt", "/팀/gone.txt")
    with pytest.raises(RuntimeError):
        sf.__enter__()
    assert not os.path.exists(captured["local"])             # __enter__ 실패에도 temp 정리


def test_retry_honors_zero_backoff():
    # backoff=0(즉시 재시도)을 1초로 바꾸지 않는다(I2 회귀 방지).
    from pii_scanner.connectors.dropbox_conn import _retry
    import dropbox
    slept = []
    calls = {"n": 0}
    def fn():
        calls["n"] += 1
        if calls["n"] == 1:
            raise dropbox.exceptions.RateLimitError("rid", None, backoff=0)
        return "ok"
    assert _retry(fn, sleep=slept.append, rand=lambda: 0.0) == "ok"
    assert slept == [0]


def test_retry_rejects_zero_max_tries():
    # max_tries<1 이면 raise None(TypeError) 대신 명확한 ValueError(I1 회귀 방지).
    from pii_scanner.connectors.dropbox_conn import _retry
    with pytest.raises(ValueError):
        _retry(lambda: 1, max_tries=0)


def _file(name, path):
    m = MagicMock(spec=_dbx.files.FileMetadata)
    m.name = name; m.path_lower = path.lower(); m.path_display = path
    return m


def _folder():
    return MagicMock(spec=_dbx.files.FolderMetadata)


def test_iter_files_paginates_and_filters():
    dbx = MagicMock()
    page1 = MagicMock(entries=[_file("a.xlsx", "/팀/a.xlsx"), _folder(),
                               _file("skip.bin", "/팀/skip.bin")],
                      cursor="C1", has_more=True)
    page2 = MagicMock(entries=[_file("b.pdf", "/팀/b.pdf")],
                      cursor="C2", has_more=False)
    dbx.files_list_folder.return_value = page1
    dbx.files_list_folder_continue.return_value = page2

    conn = DropboxConnector(dbx, "/팀")
    paths = [sf.logical_path for sf in conn.iter_files(ScanConfig())]
    assert paths == ["/팀/a.xlsx", "/팀/b.pdf"]              # 폴더·비대상 확장자 제외
    dbx.files_list_folder.assert_called_once_with("/팀", recursive=True)
    dbx.files_list_folder_continue.assert_called_once_with("C1")


def test_iter_files_resumes_from_saved_cursor(tmp_path):
    from pii_scanner.connectors.state import ScanState
    dbx = MagicMock()
    dbx.files_list_folder_continue.return_value = MagicMock(
        entries=[_file("c.txt", "/팀/c.txt")], cursor="C9", has_more=False)
    st = ScanState("s", base_dir=str(tmp_path)); st.save_cursor("SAVED")

    conn = DropboxConnector(dbx, "/팀", state=st)
    paths = [sf.logical_path for sf in conn.iter_files(ScanConfig())]
    assert paths == ["/팀/c.txt"]
    dbx.files_list_folder.assert_not_called()                # 처음부터 안 훑음
    dbx.files_list_folder_continue.assert_called_once_with("SAVED")
    assert st.load_cursor() == "C9"                          # 페이지 소진 후 커서 갱신


def test_iter_files_saves_cursor_across_pages_with_state(tmp_path):
    # state 가 있을 때 페이지마다 커서가 저장되는지(다중 페이지) — save 분기 회귀 방지.
    from pii_scanner.connectors.state import ScanState
    dbx = MagicMock()
    page1 = MagicMock(entries=[_file("a.xlsx", "/팀/a.xlsx")], cursor="C1", has_more=True)
    page2 = MagicMock(entries=[_file("b.pdf", "/팀/b.pdf")], cursor="C2", has_more=False)
    dbx.files_list_folder.return_value = page1
    dbx.files_list_folder_continue.return_value = page2
    st = ScanState("s2", base_dir=str(tmp_path))

    paths = [sf.logical_path for sf in DropboxConnector(dbx, "/팀", state=st).iter_files(ScanConfig())]
    assert paths == ["/팀/a.xlsx", "/팀/b.pdf"]
    dbx.files_list_folder_continue.assert_called_once_with("C1")  # 다음 페이지는 C1 로
    assert st.load_cursor() == "C2"                               # 마지막 페이지 커서까지 저장


def test_retry_respects_rate_limit_backoff():
    # 429: Retry-After(backoff) 만큼 정확히 대기 후 재시도.
    from pii_scanner.connectors.dropbox_conn import _retry
    import dropbox
    slept = []
    calls = {"n": 0}
    def fn():
        calls["n"] += 1
        if calls["n"] == 1:
            raise dropbox.exceptions.RateLimitError("rid", None, backoff=7.0)
        return "ok"
    assert _retry(fn, sleep=slept.append, rand=lambda: 0.0) == "ok"
    assert slept == [7.0]


def test_retry_backs_off_on_server_error_then_succeeds():
    # 5xx: 지수 백오프(지터 0 일 때 1,2초) 후 성공.
    from pii_scanner.connectors.dropbox_conn import _retry
    import dropbox
    slept = []
    calls = {"n": 0}
    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise dropbox.exceptions.InternalServerError("rid", 500, "boom")
        return "ok"
    assert _retry(fn, sleep=slept.append, rand=lambda: 0.0) == "ok"
    assert slept == [1.0, 2.0]


def test_retry_does_not_swallow_api_error():
    # 409 등 ApiError 는 재시도하지 않고 즉시 전파(스킵+기록은 호출부 몫).
    from pii_scanner.connectors.dropbox_conn import _retry
    import dropbox
    def fn():
        raise dropbox.exceptions.ApiError("rid", "err", "msg", None)
    with pytest.raises(dropbox.exceptions.ApiError):
        _retry(fn, sleep=lambda *_: None)


def test_iter_batches_groups_pages_and_filters():
    dbx = MagicMock()
    page1 = MagicMock(entries=[_file("a.xlsx", "/팀/a.xlsx"), _folder(),
                               _file("c.docx", "/팀/c.docx"),
                               _file("skip.bin", "/팀/skip.bin")],
                      cursor="C1", has_more=True)
    page2 = MagicMock(entries=[_file("b.pdf", "/팀/b.pdf")],
                      cursor="C2", has_more=False)
    dbx.files_list_folder.return_value = page1
    dbx.files_list_folder_continue.return_value = page2

    conn = DropboxConnector(dbx, "/팀")
    batches = [[sf.logical_path for sf in b] for b in conn.iter_batches(ScanConfig())]
    assert batches == [["/팀/a.xlsx", "/팀/c.docx"], ["/팀/b.pdf"]]
    dbx.files_list_folder.assert_called_once_with("/팀", recursive=True)
    dbx.files_list_folder_continue.assert_called_once_with("C1")


def test_iter_batches_saves_cursor_after_each_page(tmp_path):
    from pii_scanner.connectors.state import ScanState
    dbx = MagicMock()
    page1 = MagicMock(entries=[_file("a.xlsx", "/팀/a.xlsx")], cursor="C1", has_more=True)
    page2 = MagicMock(entries=[_file("b.pdf", "/팀/b.pdf")], cursor="C2", has_more=False)
    dbx.files_list_folder.return_value = page1
    dbx.files_list_folder_continue.return_value = page2
    st = ScanState("b1", base_dir=str(tmp_path))

    list(DropboxConnector(dbx, "/팀", state=st).iter_batches(ScanConfig()))
    assert st.load_cursor() == "C2"


def test_iter_batches_resumes_from_saved_cursor(tmp_path):
    from pii_scanner.connectors.state import ScanState
    dbx = MagicMock()
    dbx.files_list_folder_continue.return_value = MagicMock(
        entries=[_file("c.txt", "/팀/c.txt")], cursor="C9", has_more=False)
    st = ScanState("b2", base_dir=str(tmp_path)); st.save_cursor("SAVED")

    conn = DropboxConnector(dbx, "/팀", state=st)
    batches = [[sf.logical_path for sf in b] for b in conn.iter_batches(ScanConfig())]
    assert batches == [["/팀/c.txt"]]
    dbx.files_list_folder.assert_not_called()
    dbx.files_list_folder_continue.assert_called_once_with("SAVED")
    assert st.load_cursor() == "C9"


def test_retry_retries_on_connection_error_then_succeeds():
    # 일시적 네트워크 끊김(ConnectionError)도 지수 백오프(지터 0 → 1,2초)로 재시도 후 성공.
    from pii_scanner.connectors.dropbox_conn import _retry
    import requests
    slept = []
    calls = {"n": 0}
    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.exceptions.ConnectionError("RemoteDisconnected")
        return "ok"
    assert _retry(fn, sleep=slept.append, rand=lambda: 0.0) == "ok"
    assert slept == [1.0, 2.0]


def test_retry_retries_on_timeout():
    from pii_scanner.connectors.dropbox_conn import _retry
    import requests
    calls = {"n": 0}
    def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise requests.exceptions.Timeout("read timed out")
        return "ok"
    assert _retry(fn, sleep=lambda *_: None, rand=lambda: 0.0) == "ok"


def test_retry_reraises_connection_error_after_max_tries():
    # 영속적 네트워크 오류는 max_tries 후 그대로 전파(무한 재시도 금지).
    from pii_scanner.connectors.dropbox_conn import _retry
    import requests
    def fn():
        raise requests.exceptions.ConnectionError("down")
    with pytest.raises(requests.exceptions.ConnectionError):
        _retry(fn, max_tries=3, sleep=lambda *_: None, rand=lambda: 0.0)


def test_iter_batches_drives_scan_parallel_end_to_end(tmp_path, monkeypatch):
    # 실제 DropboxConnector.iter_batches → scan_parallel 종단 경로: 2페이지를 병렬 기록하고
    # 페이지마다 커서가 진행돼 최종 커서까지 저장되는지(통합 seam) 검증.
    from pii_scanner.connectors.state import ScanState
    from pii_scanner.core.scanner import scan_parallel
    import pii_scanner.core.scanner as scn

    dbx = MagicMock()
    page1 = MagicMock(entries=[_file("a.txt", "/팀/a.txt"), _file("b.txt", "/팀/b.txt")],
                      cursor="C1", has_more=True)
    page2 = MagicMock(entries=[_file("c.txt", "/팀/c.txt")], cursor="C2", has_more=False)
    dbx.files_list_folder.return_value = page1
    dbx.files_list_folder_continue.return_value = page2
    # files_download_to_file 은 no-op(MagicMock 기본). 추출기는 패치해 텍스트 반환.
    class _Ext:
        def extract(self, local): return "주민 900101-1234568"
    monkeypatch.setattr(scn, "get_extractor", lambda path: _Ext())

    st = ScanState("e2e", base_dir=str(tmp_path / "state"))
    conn = DropboxConnector(dbx, "/팀", state=st)
    result = scan_parallel(conn, ScanConfig(), state=st, max_workers=4)

    assert sorted(fr.path for fr in result.files) == ["/팀/a.txt", "/팀/b.txt", "/팀/c.txt"]
    # 재기록 없이 각 1회 + 최종 커서 저장
    recorded = sorted(fr.path for fr in
                      ScanState("e2e", base_dir=str(tmp_path / "state")).load_results().files)
    assert recorded == ["/팀/a.txt", "/팀/b.txt", "/팀/c.txt"]
    assert st.load_cursor() == "C2"
