from pii_scanner.connectors.local_fs import walk_files
from pii_scanner.config import ScanConfig


def test_walk_finds_supported_only(tmp_path):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "b.docx").write_text("x", encoding="utf-8")
    (tmp_path / "skip.zip").write_text("x", encoding="utf-8")
    found = {p.split("/")[-1] for p in walk_files([str(tmp_path)], ScanConfig())}
    assert found == {"a.txt", "b.docx"}


def test_walk_excludes_configured_dirs(tmp_path):
    sub = tmp_path / "__pycache__"
    sub.mkdir()
    (sub / "c.txt").write_text("x", encoding="utf-8")
    (tmp_path / "d.txt").write_text("x", encoding="utf-8")
    found = [p for p in walk_files([str(tmp_path)], ScanConfig())]
    assert any(p.endswith("d.txt") for p in found)
    assert not any("__pycache__" in p for p in found)


def test_multiple_roots(tmp_path):
    r1 = tmp_path / "r1"; r1.mkdir(); (r1 / "a.txt").write_text("x", encoding="utf-8")
    r2 = tmp_path / "r2"; r2.mkdir(); (r2 / "b.txt").write_text("x", encoding="utf-8")
    found = list(walk_files([str(r1), str(r2)], ScanConfig()))
    assert len(found) == 2
