import os
import pytest
from pii_scanner.cli import main


def test_cli_scans_and_writes_reports(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    (src / "a.txt").write_text("홍길동 900101-1234568", encoding="utf-8")
    outdir = tmp_path / "out"
    rc = main([str(src), "--out", str(outdir)])
    assert rc == 0
    assert os.path.exists(outdir / "report.xlsx")
    assert os.path.exists(outdir / "report.html")


def test_cli_disable_detector(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    (src / "a.txt").write_text("ho@example.com", encoding="utf-8")
    outdir = tmp_path / "out"
    rc = main([str(src), "--out", str(outdir), "--disable", "email"])
    assert rc == 0


def test_cli_unknown_disable_key_errors(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    (src / "a.txt").write_text("x", encoding="utf-8")
    # 오타("emial")는 조용히 무시되지 않고 에러로 종료해야 함
    with pytest.raises(SystemExit):
        main([str(src), "--out", str(tmp_path / "out"), "--disable", "emial"])
