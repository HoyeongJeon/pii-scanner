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


# ── 팀 관리자 API(Business) ───────────────────────────────────────────────────
# 팀 스코프(team_data.member·members.read 등)를 가진 토큰으로 팀 관리자가 각 멤버 계정의
# 파일을 as_user 로 직접 읽는다. 부서별 폴더 공유(팀 정책상 막힐 수 있음) 없이 전 부서 스캔.

def make_team_client(creds: dict) -> "dropbox.DropboxTeam":
    """팀 스코프 refresh token 으로 팀 클라이언트 생성(멤버 파일 접근·멤버 조회용).

    앱에 팀 스코프가 없으면 team_* 엔드포인트가 AuthError 로 실패한다.
    """
    return dropbox.DropboxTeam(
        oauth2_refresh_token=creds["refresh_token"], app_key=creds["app_key"])


def list_team_members(team: "dropbox.DropboxTeam") -> list[dict]:
    """팀 멤버 전체를 페이지네이션 처리해 {member_id, email, name, status} 목록으로 반환."""
    res = team.team_members_list_v2()
    raw = list(res.members)
    while res.has_more:
        res = team.team_members_list_continue_v2(res.cursor)
        raw += res.members
    out = []
    for m in raw:
        p = m.profile
        out.append({
            "member_id": p.team_member_id,
            "email": p.email,
            "name": p.name.display_name if getattr(p, "name", None) else "",
            "status": getattr(getattr(p, "status", None), "_tag", "?"),
        })
    return out


def find_member(team: "dropbox.DropboxTeam", *, email: str | None = None,
                name: str | None = None) -> dict:
    """이메일(정확·대소문자 무시) 또는 이름(부분 일치)으로 멤버 1명 해석.

    0명이면 조회 실패, 2명 이상이면 모호 — 둘 다 ValueError(이메일로 지정 유도).
    """
    if not email and not name:
        raise ValueError("email 또는 name 중 하나는 지정해야 합니다")
    hits = []
    for m in list_team_members(team):
        if email and m["email"].lower() == email.lower():
            hits.append(m)
        elif name and not email and name in m["name"]:
            hits.append(m)
    if not hits:
        raise ValueError(f"팀 멤버를 찾을 수 없습니다: email={email!r} name={name!r}")
    if len(hits) > 1:
        raise ValueError(
            f"이름 '{name}' 에 {len(hits)}명이 매칭됩니다 — 이메일로 지정하세요: "
            f"{[h['email'] for h in hits]}")
    return hits[0]


def member_client(team: "dropbox.DropboxTeam", member_id: str) -> "dropbox.Dropbox":
    """특정 팀 멤버로서(as_user, Select-User 헤더) 파일에 접근하는 사용자 클라이언트."""
    return team.as_user(member_id)
