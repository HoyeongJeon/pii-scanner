from examples.make_demo_data import build_demo


def test_build_demo_creates_synthetic_files(tmp_path):
    build_demo(str(tmp_path))
    files = list(tmp_path.iterdir())
    assert len(files) >= 2
    # 합성 데이터만 — 실제 PII 없음(검증용 가짜 RRN 체크섬만 유효)
    content = (tmp_path / "sample1.txt").read_text(encoding="utf-8")
    assert "900101-1234568" in content
