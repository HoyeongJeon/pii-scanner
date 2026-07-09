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
