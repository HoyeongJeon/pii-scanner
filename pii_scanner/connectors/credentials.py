from __future__ import annotations

import json
import os
import re

# --profile 이름은 파일명 구성요소(사용자 입력)가 되므로 경로 순회를 차단한다.
_PROFILE_RE = re.compile(r"[\w\-]+")


def _check_profile(profile: str | None) -> None:
    if profile is not None and not _PROFILE_RE.fullmatch(profile):
        raise ValueError(
            f"profile 은 영문/숫자/_/- 만 허용됩니다(경로 순회 차단): {profile!r}"
        )


def default_path(profile: str | None = None) -> str:
    base = os.path.join(os.path.expanduser("~"), ".config", "pii-scanner")
    name = "credentials.json" if not profile else f"credentials-{profile}.json"
    return os.path.join(base, name)


def save_credentials(app_key: str, refresh_token: str, profile: str | None = None,
                     path: str | None = None) -> str:
    _check_profile(profile)
    path = path or default_path(profile)
    # 디렉터리도 소유자 전용(0700) — 타 사용자에게 토큰 존재/메타 노출 차단.
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    # 파일을 처음부터 0600 으로 원자적 생성한다. open()+chmod 는 그 사이에 토큰이
    # 잠시 0644(타 사용자 읽기 가능)로 노출되는 TOCTOU 창이 생기므로 쓰지 않는다.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"app_key": app_key, "refresh_token": refresh_token}, f)
    return path


def load_credentials(profile: str | None = None, path: str | None = None) -> dict:
    _check_profile(profile)
    if profile is None:                          # env override 는 기본 프로필에만 적용
        env_key = os.environ.get("DROPBOX_APP_KEY")
        env_tok = os.environ.get("DROPBOX_REFRESH_TOKEN")
        if env_key and env_tok:
            return {"app_key": env_key, "refresh_token": env_tok}
    path = path or default_path(profile)
    if not os.path.exists(path):
        raise FileNotFoundError(
            "Dropbox 자격증명이 없습니다. "
            "'pii-scan auth --app-key <APP_KEY> [--profile <NAME>]' 로 먼저 인증하세요."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)
