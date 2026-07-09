"""Dropbox OAuth 2.0(PKCE/offline) 인증 흐름 및 팀 공유 공간 클라이언트 팩토리."""
from __future__ import annotations

import dropbox


def run_oauth_flow(app_key: str, input_fn=input, print_fn=print) -> str:
    """PKCE + offline 흐름으로 refresh token 1회 발급(수동 복붙).

    잘못된 코드를 붙여넣으면 requests.HTTPError 가 전파된다 — 호출부(CLI)에서 처리한다.
    """
    flow = dropbox.DropboxOAuth2FlowNoRedirect(
        app_key, use_pkce=True, token_access_type="offline")
    url = flow.start()
    print_fn(f"1) 브라우저에서 열어 승인하세요:\n   {url}")
    print_fn("2) 표시된 인증 코드를 붙여넣으세요.")
    code = input_fn("인증 코드: ").strip()
    result = flow.finish(code)
    return result.refresh_token


def make_client(creds: dict, namespace: str = "home") -> "dropbox.Dropbox":
    """refresh token 으로 SDK 클라이언트 생성.

    namespace="home"(기본): 계정의 홈 네임스페이스(Path-Root 미설정) — 각 계정의 실제 문서가 있는 곳.
    namespace="team": 팀 공유 공간 루트(Path-Root = root_namespace_id).
    """
    dbx = dropbox.Dropbox(
        oauth2_refresh_token=creds["refresh_token"], app_key=creds["app_key"])
    if namespace == "team":
        ns = dbx.users_get_current_account().root_info.root_namespace_id
        dbx = dbx.with_path_root(dropbox.common.PathRoot.root(ns))
    return dbx
