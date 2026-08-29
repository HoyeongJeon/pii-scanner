from pii_scanner.connectors.local_fs import LocalFsConnector
from pii_scanner.connectors.base import SourceFile
from pii_scanner.config import ScanConfig


def test_local_connector_yields_sourcefiles(tmp_path):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "b.bin").write_text("y", encoding="utf-8")   # 비대상 확장자
    conn = LocalFsConnector([str(tmp_path)])
    files = list(conn.iter_files(ScanConfig()))
    assert all(isinstance(sf, SourceFile) for sf in files)
    paths = {sf.logical_path for sf in files}
    assert str(tmp_path / "a.txt") in paths
    assert str(tmp_path / "b.bin") not in paths


def test_local_sourcefile_enter_returns_real_path_exit_noop(tmp_path):
    f = tmp_path / "a.txt"; f.write_text("x", encoding="utf-8")
    conn = LocalFsConnector([str(tmp_path)])
    sf = next(conn.iter_files(ScanConfig()))
    with sf as local:
        assert local == sf.logical_path        # 실제 경로 그대로
    assert f.exists()                            # __exit__ 는 원본 보존(no-op)


# ---------------------------------------------------------------------------
# 폴더 접근 실패는 조용히 삼키지 않는다.
# 이 가드가 없으면 "그 폴더에 개인정보 없음"과 "그 폴더를 열지도 못했음"이 완전히 같은
# 출력(파일 0건·노출 0건·종료코드 0)이 되어 경로 오타·ACL 차단을 아무도 알아챌 수 없다.
# _ACCESS_REASONS 표는 항목마다 테스트를 둔다 — 표에서 한 줄 지워도 전부 통과하면
# 회귀 가드가 아니다.
# ---------------------------------------------------------------------------
import os
import pytest
from pii_scanner.connectors.local_fs import walk_files


def _access_errors(conn, cfg=None):
    list(conn.iter_files(cfg or ScanConfig()))       # 순회를 끝까지 소비해야 목록이 완전해진다
    return list(conn.iter_access_errors())


def test_missing_root_is_reported_not_silently_clean(tmp_path):
    conn = LocalFsConnector([str(tmp_path / "없는폴더")])
    errs = _access_errors(conn)
    assert len(errs) == 1
    assert errs[0].unreadable is True
    assert errs[0].path == str(tmp_path / "없는폴더")
    assert errs[0].error == "접근 실패: 경로 없음"          # ENOENT


def test_file_given_as_root_is_reported(tmp_path):
    f = tmp_path / "a.txt"; f.write_text("x", encoding="utf-8")
    errs = _access_errors(LocalFsConnector([str(f)]))
    assert [e.error for e in errs] == ["접근 실패: 디렉터리가 아님"]   # ENOTDIR
    assert errs[0].path == str(f)


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0,
                    reason="POSIX 권한 검사 — root 는 chmod 000 도 읽을 수 있어 무력화됨")
def test_unreadable_subdirectory_is_reported(tmp_path):
    locked = tmp_path / "hr"; locked.mkdir()
    (locked / "a.csv").write_text("홍길동", encoding="utf-8")
    (tmp_path / "ok.txt").write_text("x", encoding="utf-8")
    locked.chmod(0o000)
    try:
        conn = LocalFsConnector([str(tmp_path)])
        files = list(conn.iter_files(ScanConfig()))
        errs = list(conn.iter_access_errors())
    finally:
        locked.chmod(0o755)                            # 다른 테스트·정리에 지장 없게 복구
    assert str(tmp_path / "ok.txt") in {sf.logical_path for sf in files}   # 나머지는 계속 스캔
    assert [e.error for e in errs] == ["접근 실패: 권한 없음"]              # EACCES
    assert errs[0].path == str(locked)


def test_access_errors_do_not_accumulate_across_iterations(tmp_path):
    conn = LocalFsConnector([str(tmp_path / "없는폴더")])
    assert len(_access_errors(conn)) == 1
    assert len(_access_errors(conn)) == 1              # 두 번 순회해도 1건 (중복 누적 금지)


def test_walk_files_without_callback_keeps_old_silent_behavior(tmp_path):
    # on_error 기본값(None)은 예전 동작 — 하위호환. 예외를 밖으로 던지지 않는다.
    assert list(walk_files([str(tmp_path / "없는폴더")], ScanConfig())) == []


def test_connector_base_reports_no_access_errors_by_default():
    # 순회 실패를 모르는 커넥터(Dropbox 등)는 빈 목록 — 없는 걸 0으로 단정하지 않기 위한 계약.
    from pii_scanner.connectors.base import Connector

    class _Bare(Connector):
        def iter_files(self, config):
            return iter(())

    assert list(_Bare().iter_access_errors()) == []
