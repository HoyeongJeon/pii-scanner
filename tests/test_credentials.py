import os
import stat
import pytest
from pii_scanner.connectors import credentials as cr


def test_save_then_load_roundtrip(tmp_path):
    p = tmp_path / "credentials.json"
    saved = cr.save_credentials("APPKEY", "REFRESH", path=str(p))
    assert saved == str(p)                       # 저장 경로를 반환(CLI 확인 출력용)
    creds = cr.load_credentials(path=str(p))
    assert creds == {"app_key": "APPKEY", "refresh_token": "REFRESH"}


def test_saved_file_is_0600(tmp_path):
    p = tmp_path / "credentials.json"
    cr.save_credentials("A", "B", path=str(p))
    mode = stat.S_IMODE(os.stat(str(p)).st_mode)
    assert mode == 0o600


def test_reauth_overwrite_preserves_0600_and_content(tmp_path):
    # 재인증(토큰 회전) 시 덮어써도 0600 유지 + 새 값 반영 — 원자적 생성 회귀 방지.
    p = tmp_path / "credentials.json"
    cr.save_credentials("OLD", "OLDTOK", path=str(p))
    cr.save_credentials("NEW", "NEWTOK", path=str(p))
    assert stat.S_IMODE(os.stat(str(p)).st_mode) == 0o600
    assert cr.load_credentials(path=str(p)) == {"app_key": "NEW", "refresh_token": "NEWTOK"}


def test_env_overrides_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DROPBOX_APP_KEY", "ENVKEY")
    monkeypatch.setenv("DROPBOX_REFRESH_TOKEN", "ENVTOK")
    creds = cr.load_credentials(path=str(tmp_path / "nope.json"))
    assert creds == {"app_key": "ENVKEY", "refresh_token": "ENVTOK"}


def test_missing_credentials_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("DROPBOX_APP_KEY", raising=False)
    monkeypatch.delenv("DROPBOX_REFRESH_TOKEN", raising=False)
    with pytest.raises(FileNotFoundError, match="pii-scan auth"):
        cr.load_credentials(path=str(tmp_path / "nope.json"))


def test_default_path_profile_naming():
    assert cr.default_path().endswith("credentials.json")
    assert cr.default_path("hr").endswith("credentials-hr.json")


def test_profile_save_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(cr, "default_path",
                        lambda profile=None: str(tmp_path / (
                            f"credentials-{profile}.json" if profile else "credentials.json")))
    cr.save_credentials("AK", "RT", profile="hr")
    assert (tmp_path / "credentials-hr.json").exists()
    assert cr.load_credentials(profile="hr") == {"app_key": "AK", "refresh_token": "RT"}


def test_profile_rejects_path_traversal():
    for bad in ["../evil", "a/b", ".."]:
        with pytest.raises(ValueError):
            cr.save_credentials("A", "B", profile=bad)
        with pytest.raises(ValueError):
            cr.load_credentials(profile=bad)
