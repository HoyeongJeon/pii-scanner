import pytest
pytest.importorskip("dropbox")
from unittest.mock import patch, MagicMock, ANY
from pii_scanner.cli import main


def test_cli_module_imports_without_touching_dropbox_at_top_level():
    # cli 진입점은 dropbox 를 최상단에서 import 하면 안 된다(로컬 스캔 base 설치 보호).
    import ast, pathlib
    src = pathlib.Path("pii_scanner/cli.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    top_imports = [
        n for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
        for n in [getattr(node, "module", None) or ""]
    ]
    for mod in top_imports:
        assert "dropbox" not in mod, f"cli 최상단에서 dropbox 의존 모듈 import 금지: {mod}"


def test_auth_subcommand_saves_token(tmp_path, capsys):
    cred = tmp_path / "credentials.json"
    with patch("pii_scanner.connectors.dropbox_client.run_oauth_flow",
               return_value="REFRESH") as flow, \
         patch("pii_scanner.connectors.credentials.default_path",
               return_value=str(cred)):
        rc = main(["auth", "--app-key", "APPKEY"])
    assert rc == 0
    flow.assert_called_once_with("APPKEY")
    assert cred.exists()


def test_dropbox_subcommand_runs_scan(tmp_path):
    out = tmp_path / "out"
    mock_dbx = MagicMock()
    with patch("pii_scanner.connectors.credentials.load_credentials",
               return_value={"app_key": "K", "refresh_token": "R"}), \
         patch("pii_scanner.connectors.dropbox_client.make_client",
               return_value=mock_dbx), \
         patch("pii_scanner.connectors.state.default_state_dir",
               return_value=str(tmp_path / "state")), \
         patch("pii_scanner.connectors.dropbox_conn.DropboxConnector") as Conn, \
         patch("pii_scanner.cli.scan_parallel") as scan_fn:
        from pii_scanner.core.models import ScanResult
        scan_fn.return_value = ScanResult()
        rc = main(["dropbox", "--root", "/팀/인사", "--out", str(out),
                   "--scan-id", "t1"])
    assert rc == 0
    assert (out / "report.html").exists()
    Conn.assert_called_once_with(mock_dbx, "/팀/인사", state=ANY)   # dbx·root·state 배선 검증


def test_dropbox_report_includes_resumed_files(tmp_path):
    # 재개 완료 후 리포트는 이번 실행분뿐 아니라 이전 실행 누적분까지 포함해야 한다(I1 회귀 방지).
    import openpyxl
    from pii_scanner.core.models import (
        FileResult, ScanResult, PiiHit, PiiType, Status, Confidence, RiskLevel)
    from pii_scanner.connectors.state import ScanState
    out = tmp_path / "out"
    state_dir = tmp_path / "state"

    def _hit():
        return PiiHit(PiiType.RRN, Status.EXPOSED, "900101-1******", 0, 14,
                      Confidence.CONFIRMED, RiskLevel.CRITICAL)

    def fake_scan(connector, config, state=None, max_workers=8):
        # 실제 scan 처럼 이번 실행분(B)만 상태에 기록하고, 반환값에도 B 만 담는다.
        state.record(FileResult(path="/팀/B.txt", hits=[_hit()]))
        r = ScanResult()
        r.files.append(FileResult(path="/팀/B.txt", hits=[_hit()]))
        return r

    with patch("pii_scanner.connectors.credentials.load_credentials",
               return_value={"app_key": "K", "refresh_token": "R"}), \
         patch("pii_scanner.connectors.dropbox_client.make_client", return_value=MagicMock()), \
         patch("pii_scanner.connectors.state.default_state_dir", return_value=str(state_dir)), \
         patch("pii_scanner.connectors.dropbox_conn.DropboxConnector"), \
         patch("pii_scanner.cli.scan_parallel", side_effect=fake_scan):
        # 이전 실행에서 A 가 이미 기록돼 있다고 가정(같은 scan-id).
        ScanState("rid", base_dir=str(state_dir)).record(
            FileResult(path="/팀/A.txt", hits=[_hit()]))
        rc = main(["dropbox", "--root", "/팀", "--out", str(out), "--scan-id", "rid"])
    assert rc == 0
    wb = openpyxl.load_workbook(str(out / "report.xlsx"))
    blob = " ".join(str(c.value) for ws in wb.worksheets
                    for row in ws.iter_rows() for c in row if c.value)
    # findings 시트에 두 파일 경로(이전 실행분 A + 이번 실행분 B)가 모두 나와야 한다.
    assert "/팀/A.txt" in blob and "/팀/B.txt" in blob


def test_dropbox_missing_credentials_clean_error(tmp_path, capsys):
    # 자격증명 부재 시 트레이스백 대신 안내 + 종료코드 1.
    with patch("pii_scanner.connectors.credentials.load_credentials",
               side_effect=FileNotFoundError("Dropbox 자격증명이 없습니다. 'pii-scan auth' ...")):
        rc = main(["dropbox", "--root", "/팀", "--out", str(tmp_path / "out")])
    assert rc == 1
    assert "pii-scan auth" in capsys.readouterr().err


def test_local_scan_backward_compatible(tmp_path):
    (tmp_path / "a.txt").write_text("폰 010-1234-5678", encoding="utf-8")
    out = tmp_path / "out"
    rc = main([str(tmp_path), "--out", str(out)])            # 기존 사용법
    assert rc == 0
    assert (out / "report.xlsx").exists()


def test_dropbox_passes_profile_and_namespace(tmp_path):
    out = tmp_path / "out"
    with patch("pii_scanner.connectors.credentials.load_credentials",
               return_value={"app_key": "K", "refresh_token": "R"}) as load, \
         patch("pii_scanner.connectors.dropbox_client.make_client",
               return_value=MagicMock()) as mk, \
         patch("pii_scanner.connectors.state.default_state_dir",
               return_value=str(tmp_path / "state")), \
         patch("pii_scanner.connectors.dropbox_conn.DropboxConnector"), \
         patch("pii_scanner.cli.scan_parallel") as scan_fn:
        from pii_scanner.core.models import ScanResult
        scan_fn.return_value = ScanResult()
        rc = main(["dropbox", "--root", "/x", "--out", str(out),
                   "--profile", "hr", "--namespace", "team"])
    assert rc == 0
    load.assert_called_once_with(profile="hr")
    assert mk.call_args.kwargs.get("namespace") == "team"


def test_dropbox_bad_root_friendly_error(tmp_path, capsys):
    import dropbox
    out = tmp_path / "out"
    err = dropbox.exceptions.ApiError("rid", "ListFolderError", "msg", None)
    with patch("pii_scanner.connectors.credentials.load_credentials",
               return_value={"app_key": "K", "refresh_token": "R"}), \
         patch("pii_scanner.connectors.dropbox_client.make_client", return_value=MagicMock()), \
         patch("pii_scanner.connectors.state.default_state_dir", return_value=str(tmp_path / "state")), \
         patch("pii_scanner.connectors.dropbox_conn.DropboxConnector"), \
         patch("pii_scanner.cli.scan_parallel", side_effect=err):
        rc = main(["dropbox", "--root", "/nope", "--out", str(out)])
    assert rc == 1
    assert "경로/네임스페이스" in capsys.readouterr().err


def test_auth_with_profile_saves_to_profile_file(tmp_path):
    cred = tmp_path / "credentials-hr.json"
    with patch("pii_scanner.connectors.dropbox_client.run_oauth_flow", return_value="REFRESH"), \
         patch("pii_scanner.connectors.credentials.default_path",
               side_effect=lambda profile=None: str(tmp_path / (
                   f"credentials-{profile}.json" if profile else "credentials.json"))):
        rc = main(["auth", "--app-key", "AK", "--profile", "hr"])
    assert rc == 0
    assert cred.exists()


def test_dropbox_passes_workers_to_scan_parallel(tmp_path):
    out = tmp_path / "out"
    with patch("pii_scanner.connectors.credentials.load_credentials",
               return_value={"app_key": "K", "refresh_token": "R"}), \
         patch("pii_scanner.connectors.dropbox_client.make_client", return_value=MagicMock()), \
         patch("pii_scanner.connectors.state.default_state_dir",
               return_value=str(tmp_path / "state")), \
         patch("pii_scanner.connectors.dropbox_conn.DropboxConnector"), \
         patch("pii_scanner.cli.scan_parallel") as sp:
        from pii_scanner.core.models import ScanResult
        sp.return_value = ScanResult()
        rc = main(["dropbox", "--root", "/x", "--out", str(out), "--workers", "12"])
    assert rc == 0
    assert sp.call_args.kwargs.get("max_workers") == 12


def test_dropbox_workers_defaults_to_8(tmp_path):
    out = tmp_path / "out"
    with patch("pii_scanner.connectors.credentials.load_credentials",
               return_value={"app_key": "K", "refresh_token": "R"}), \
         patch("pii_scanner.connectors.dropbox_client.make_client", return_value=MagicMock()), \
         patch("pii_scanner.connectors.state.default_state_dir",
               return_value=str(tmp_path / "state")), \
         patch("pii_scanner.connectors.dropbox_conn.DropboxConnector"), \
         patch("pii_scanner.cli.scan_parallel") as sp:
        from pii_scanner.core.models import ScanResult
        sp.return_value = ScanResult()
        rc = main(["dropbox", "--root", "/x", "--out", str(out)])
    assert rc == 0
    assert sp.call_args.kwargs.get("max_workers") == 8


def test_dropbox_rejects_nonpositive_workers(capsys):
    import pytest
    # parser.error 로 즉시 종료(SystemExit) + 친절한 메시지. 자격증명/네트워크 이전에 차단.
    with pytest.raises(SystemExit):
        main(["dropbox", "--root", "/x", "--out", "/tmp/o", "--workers", "0"])
    assert "--workers" in capsys.readouterr().err
