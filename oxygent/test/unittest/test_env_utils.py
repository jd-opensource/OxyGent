"""Unit tests for oxygent.utils.env_utils."""

import os
import socket
import pytest

import oxygent.utils.env_utils as env_utils


# ---------- helpers ---------------------------------------------------------


@pytest.fixture(autouse=True)
def restore_environ():
    """Save & restore os.environ between tests."""
    old = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(old)


# ---------- get_env / get_env_var -------------------------------------------


@pytest.mark.parametrize(
    "key, value, default, expected",
    [
        ("STR_KEY", "hello", None, "hello"),
        ("ABSENT", None, "default", "default"),
    ],
)
def test_get_env_and_get_env_var_str(monkeypatch, key, value, default, expected):
    if value is not None:
        monkeypatch.setenv(key, value)

    assert env_utils.get_env(key, default) == expected
    assert env_utils.get_env_var(key, str, default) == expected


def test_get_env_var_list(monkeypatch):
    monkeypatch.setenv("LIST_KEY", "a, b ,c")
    assert env_utils.get_env_var("LIST_KEY", list) == ["a", "b", "c"]


# @pytest.mark.parametrize(
#     "raw, expected_type",
#     [("abc", list), (["not_str"], str)],
# )
# def test_get_env_var_type_error(monkeypatch, raw, expected_type):
#     monkeypatch.setenv("BAD_KEY", raw if isinstance(raw, str) else "dummy")
#     with pytest.raises(ValueError):
#         env_utils.get_env_var("BAD_KEY", expected_type)


def test_get_env_var_missing(monkeypatch):
    with pytest.raises(ValueError):
        env_utils.get_env_var("NOT_SET", str)


# ---------- simple getters --------------------------------------------------


def test_get_env_for_log_path(monkeypatch):
    monkeypatch.setenv("LOG_PATH", "/tmp/logs")
    assert env_utils.get_env_for_log_path() == "/tmp/logs"


def test_get_env_for_cpu_count(monkeypatch):
    monkeypatch.setenv("AVAILABLE_CORES", "8")
    assert env_utils.get_env_for_cpu_count() == 8


def test_get_env_for_deployment_stage(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_STAGE", "prod")
    assert env_utils.get_env_for_deployment_stage() == 1
    monkeypatch.setenv("DEPLOYMENT_STAGE", "dev")
    assert env_utils.get_env_for_deployment_stage() == 2
    monkeypatch.delenv("DEPLOYMENT_STAGE", raising=False)
    assert env_utils.get_env_for_deployment_stage() == 3


def test_is_prod_env(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_STAGE", "prod")
    assert env_utils.is_prod_env() is True
    monkeypatch.setenv("DEPLOYMENT_STAGE", "dev")
    assert env_utils.is_prod_env() is False


# ---------- get_local_ip ----------------------------------------------------


def test_get_local_ip(monkeypatch):
    """Mock socket to return deterministic IP."""
    monkeypatch.setattr(socket, "gethostname", lambda: "dummy-host")
    monkeypatch.setattr(socket, "gethostbyname", lambda host: "10.0.0.1")
    assert env_utils.get_local_ip() == "10.0.0.1"


def test_get_local_ip_failure(monkeypatch):
    def raise_err(_):  # noqa: D401
        raise OSError("no network")

    monkeypatch.setattr(socket, "gethostname", lambda: "dummy-host")
    monkeypatch.setattr(socket, "gethostbyname", raise_err)
    assert env_utils.get_local_ip() == "127.0.0.1"


# ---------- GROUP_ID --------------------------------------------------------


def test_get_env_for_group_id(monkeypatch):
    monkeypatch.setenv("GROUP_ID", "42")
    assert env_utils.get_env_for_group_id() == 42
    monkeypatch.delenv("GROUP_ID", raising=False)
    assert env_utils.get_env_for_group_id() == 0
