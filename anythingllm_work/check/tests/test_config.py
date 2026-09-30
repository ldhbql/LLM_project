from __future__ import annotations

import pytest

from anythingllm_mcp.config import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    ENV_API_KEY,
    ENV_BASE_URL,
    ENV_TIMEOUT,
    ENV_WORKSPACE_SLUG,
    ConfigError,
    find_dotenv,
    load_settings,
)

VALID_ENV = {
    ENV_API_KEY: "key-123",
    ENV_WORKSPACE_SLUG: "ws-slug",
}


def test_loads_required_values():
    settings = load_settings(VALID_ENV)
    assert settings.api_key == "key-123"
    assert settings.workspace_slug == "ws-slug"
    assert settings.base_url == DEFAULT_BASE_URL
    assert settings.timeout == DEFAULT_TIMEOUT
    assert settings.api_root == f"{DEFAULT_BASE_URL}/api"


def test_strips_whitespace_and_trailing_slash():
    settings = load_settings(
        {**VALID_ENV, ENV_BASE_URL: "http://host:1234/", ENV_WORKSPACE_SLUG: " ws "}
    )
    assert settings.base_url == "http://host:1234/"
    assert settings.api_root == "http://host:1234/api"
    assert settings.workspace_slug == "ws"


def test_missing_required_raises():
    with pytest.raises(ConfigError, match=ENV_API_KEY):
        load_settings({ENV_WORKSPACE_SLUG: "ws"})
    with pytest.raises(ConfigError, match=ENV_WORKSPACE_SLUG):
        load_settings({ENV_API_KEY: "key"})


def test_invalid_timeout_raises():
    with pytest.raises(ConfigError, match=ENV_TIMEOUT):
        load_settings({**VALID_ENV, ENV_TIMEOUT: "abc"})
    with pytest.raises(ConfigError, match=ENV_TIMEOUT):
        load_settings({**VALID_ENV, ENV_TIMEOUT: "0"})


def test_custom_timeout():
    assert load_settings({**VALID_ENV, ENV_TIMEOUT: "12.5"}).timeout == 12.5


def test_invalid_base_url_raises():
    with pytest.raises(ConfigError, match=ENV_BASE_URL):
        load_settings({**VALID_ENV, ENV_BASE_URL: "not-a-url"})


def test_find_dotenv_walks_up(tmp_path):
    (tmp_path / ".env").write_text("X=1", encoding="utf-8")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert find_dotenv(nested) == tmp_path.resolve() / ".env"
