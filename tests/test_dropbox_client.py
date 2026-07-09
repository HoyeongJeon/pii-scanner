import pytest
pytest.importorskip("dropbox")
from unittest.mock import MagicMock, patch
from pii_scanner.connectors import dropbox_client as dc


def test_run_oauth_flow_returns_refresh_token():
    fake_flow = MagicMock()
    fake_flow.start.return_value = "https://auth.url"
    fake_flow.finish.return_value = MagicMock(refresh_token="REFRESH123")
    printed = []
    with patch("dropbox.DropboxOAuth2FlowNoRedirect", return_value=fake_flow) as ctor:
        tok = dc.run_oauth_flow(
            "APPKEY", input_fn=lambda _="": "CODE", print_fn=printed.append)
    assert tok == "REFRESH123"
    # app_key 는 첫 위치인자(consumer_key)로, PKCE + offline 로 호출됐는지
    args, kwargs = ctor.call_args
    assert args[0] == "APPKEY"
    assert kwargs.get("use_pkce") is True
    assert kwargs.get("token_access_type") == "offline"
    fake_flow.finish.assert_called_once_with("CODE")
    # 보안 불변식: refresh token 은 절대 출력되지 않는다.
    assert not any("REFRESH123" in str(m) for m in printed)


def test_make_client_sets_path_root_to_team_namespace():
    fake_dbx = MagicMock()
    fake_dbx.users_get_current_account.return_value = MagicMock(
        root_info=MagicMock(root_namespace_id="NS42"))
    with patch("dropbox.Dropbox", return_value=fake_dbx) as Dctor, \
         patch("dropbox.common.PathRoot") as PathRoot:
        out = dc.make_client({"app_key": "K", "refresh_token": "R"}, namespace="team")
    # refresh token 으로 생성
    _, kwargs = Dctor.call_args
    assert kwargs.get("oauth2_refresh_token") == "R"
    assert kwargs.get("app_key") == "K"
    PathRoot.root.assert_called_once_with("NS42")
    fake_dbx.with_path_root.assert_called_once()
    assert out is fake_dbx.with_path_root.return_value


def test_make_client_home_default_no_path_root():
    # 기본 namespace=home → Path-Root 미설정(계정 홈), with_path_root 호출 안 함.
    fake_dbx = MagicMock()
    with patch("dropbox.Dropbox", return_value=fake_dbx) as Dctor:
        out = dc.make_client({"app_key": "K", "refresh_token": "R"})
    _, kwargs = Dctor.call_args
    assert kwargs.get("oauth2_refresh_token") == "R"
    fake_dbx.with_path_root.assert_not_called()
    assert out is fake_dbx
