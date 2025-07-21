# -*- coding: utf-8 -*-
"""Get environment variables."""

import os
import socket
from typing import List, Type, Union


def get_env(key, default_val=None):
    """Get environment variables, return default value if not exsit :param key:

    :param default_val:
    :return:
    """
    return os.getenv(key) if os.getenv(key) else default_val


def get_env_var(
    key: str, expected_type: Type = str, default_val=None
) -> Union[str, List[str]]:
    """Get environment variable with type checking.

    Args:
        key (str): Environment variable name.
        expected_type (Type): Expected type, e.g. str or list.
        default_val: Default value if env var is not set.

    Returns:
        Union[str, List[str]]: The environment variable value.

    Raises:
        ValueError: If the environment variable is not set, or type is invalid.
    """
    value = os.getenv(key, default_val)

    if value is None:
        raise ValueError(
            f"Environment variable '{key}' is not set and no default value provided. Please check your .env or system env."
        )

    # If expected type is str, simply check and return
    if expected_type is str:
        if not isinstance(value, str):
            raise ValueError(
                f"Environment variable '{key}' type error: expected str, got {type(value).__name__}."
            )
        return value

    # If expected type is List[str], parse by comma splitting
    if expected_type is list or expected_type is List[str]:
        if not isinstance(value, str):
            raise ValueError(
                f"Environment variable '{key}' type error: expected string to parse as List[str], got {type(value).__name__}."
            )
        value_list = [v.strip() for v in value.split(",")]
        if not all(isinstance(v, str) for v in value_list):
            raise ValueError(
                f"Environment variable '{key}' parsed as List[str] contains non-string elements."
            )
        return value_list

    raise ValueError(
        f"Unsupported expected_type '{expected_type}' for environment variable '{key}'."
    )


def get_env_for_log_path():
    """Get log path :return:"""
    return get_env(key="LOG_PATH", default_val="/export/Logs")


def get_env_for_cpu_count():
    """Get value of avaliable cpu cores :return:"""
    return int(get_env(key="AVAILABLE_CORES", default_val=2))


def get_env_for_run_attr():
    """Get http service run attr Use in bin/start.sh, only for backups here :return:"""
    try:
        return int(get_env(key="RUN_ATTR", default_val=-1))
    except Exception:
        return -1


def get_env_for_run_profile():
    """Get running environment of yachain :return:"""
    return get_env(key="YACHAIN_RUN_PROFILE", default_val="local")


def get_schedule_profile():
    """Get schedule profile, used in task scheduling :return:"""
    return get_env(key="SCHEDULE_JOB", default_val="false")


def get_engine_intelligent_profile():
    """Get engine intelligent profile, used in task scheduling :return:"""
    return get_env(key="ENGINE", default_val="yachain_group")


def get_env_for_deployment_stage():
    """Differentiate the running environment :return: int 1-production 2-development
    3-local debug."""
    deployment_stage = get_env(key="DEPLOYMENT_STAGE", default_val="local")
    if deployment_stage == "prod":
        return 1
    elif deployment_stage == "dev":
        return 2
    else:
        return 3


def is_prod_env():
    deployment_stage = get_env(key="DEPLOYMENT_STAGE", default_val="local")
    if deployment_stage == "prod":
        return True
    else:
        return False


def get_local_ip():
    """Get local ip :return: str."""
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"
    return local_ip


def get_env_for_group_id():
    """Get group id of the machine :return: int."""
    group_id = get_env(key="GROUP_ID", default_val="0")
    return int(group_id)
