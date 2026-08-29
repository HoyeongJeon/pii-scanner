"""도구 버전은 리포트에 찍히는 감사 증적이다 — 두 곳의 값이 갈리면 안 된다."""
import pathlib
import tomllib

import pii_scanner


def test_version_matches_pyproject():
    root = pathlib.Path(__file__).resolve().parent.parent
    meta = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert pii_scanner.__version__ == meta["project"]["version"]
