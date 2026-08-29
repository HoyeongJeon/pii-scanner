"""팀 관리자 API 헬퍼 테스트 — dropbox SDK 를 모킹해 네트워크 없이 로직만 검증."""
import types

import pytest

from pii_scanner.connectors import dropbox_client


# ── 가짜 SDK 객체 ─────────────────────────────────────────────────────────────
def _member(mid, email, name, status="active"):
    profile = types.SimpleNamespace(
        team_member_id=mid,
        email=email,
        name=types.SimpleNamespace(display_name=name),
        status=types.SimpleNamespace(_tag=status),
    )
    return types.SimpleNamespace(profile=profile)


class _Page:
    def __init__(self, members, has_more=False, cursor=None):
        self.members = members
        self.has_more = has_more
        self.cursor = cursor


class FakeTeam:
    """team_members_list_v2 / _continue_v2 / as_user 만 흉내낸다."""

    def __init__(self, pages):
        self._pages = pages
        self._idx = 0
        self.as_user_calls = []

    def team_members_list_v2(self):
        self._idx = 0
        return self._pages[0]

    def team_members_list_continue_v2(self, cursor):
        self._idx += 1
        return self._pages[self._idx]

    def as_user(self, member_id):
        self.as_user_calls.append(member_id)
        return f"user_client::{member_id}"


def _two_dept():
    return [
        _member("id1", "dept90@example.com", "Alpha Support"),
        _member("id2", "dept20@example.com", "Alpha Planning"),
    ]


# ── list_team_members ─────────────────────────────────────────────────────────
def test_list_members_single_page():
    team = FakeTeam([_Page(_two_dept())])
    out = dropbox_client.list_team_members(team)
    assert [m["email"] for m in out] == ["dept90@example.com", "dept20@example.com"]
    assert out[0] == {
        "member_id": "id1", "email": "dept90@example.com",
        "name": "Alpha Support", "status": "active",
    }


def test_list_members_paginated():
    team = FakeTeam([
        _Page([_two_dept()[0]], has_more=True, cursor="c1"),
        _Page([_two_dept()[1]], has_more=False),
    ])
    out = dropbox_client.list_team_members(team)
    assert len(out) == 2
    assert out[1]["member_id"] == "id2"


# ── find_member ───────────────────────────────────────────────────────────────
def test_find_by_email_is_case_insensitive():
    team = FakeTeam([_Page(_two_dept())])
    m = dropbox_client.find_member(team, email="DePt90@Example.COM")
    assert m["member_id"] == "id1"


def test_find_by_name_partial():
    team = FakeTeam([_Page(_two_dept())])
    m = dropbox_client.find_member(team, name="Alpha Sup")
    assert m["email"] == "dept90@example.com"


def test_find_ambiguous_name_raises():
    team = FakeTeam([_Page(_two_dept())])
    with pytest.raises(ValueError, match="매칭"):
        dropbox_client.find_member(team, name="Alpha")   # 둘 다 'Alpha' 포함


def test_find_missing_raises():
    team = FakeTeam([_Page(_two_dept())])
    with pytest.raises(ValueError, match="찾을 수 없"):
        dropbox_client.find_member(team, email="nobody@example.com")


def test_find_requires_selector():
    team = FakeTeam([_Page(_two_dept())])
    with pytest.raises(ValueError, match="지정"):
        dropbox_client.find_member(team)


# ── member_client / make_team_client ──────────────────────────────────────────
def test_member_client_uses_as_user():
    team = FakeTeam([_Page(_two_dept())])
    c = dropbox_client.member_client(team, "id1")
    assert c == "user_client::id1"
    assert team.as_user_calls == ["id1"]


def test_make_team_client_passes_creds(monkeypatch):
    captured = {}

    def fake_team(**kw):
        captured.update(kw)
        return "TEAM_CLIENT"

    monkeypatch.setattr(dropbox_client.dropbox, "DropboxTeam", fake_team)
    c = dropbox_client.make_team_client({"refresh_token": "rt", "app_key": "ak"})
    assert c == "TEAM_CLIENT"
    assert captured == {"oauth2_refresh_token": "rt", "app_key": "ak"}
