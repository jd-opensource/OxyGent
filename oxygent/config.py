"""Configments of the mas."""

import json
import logging
import os
import re


def deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, dict) and k in d and isinstance(d[k], dict):
            deep_update(d[k], v)
        else:
            d[k] = v


def replace_env_var(val):
    """Convert ${VAR} in strings to environment variables recursively."""
    pattern = re.compile(r"\$\{(\w+)\}")
    if isinstance(val, str):

        def replacer(match):
            var_name = match.group(1)
            return os.environ.get(var_name, "")

        return pattern.sub(replacer, val)
    elif isinstance(val, dict):
        return {k: replace_env_var(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [replace_env_var(v) for v in val]
    else:
        return val


class Config:
    _env = "default"
    _config = {
        "app": {
            "name": "app",
            "version": "1.0.0",
        },
        "log": {
            "path": "./cache_dir/app.log",
            "level_root": "INFO",
            "level_terminal": "INFO",
            "level_file": "INFO",
            "color_is_on_background": False,
            "is_bright": False,
            "only_message_color": True,
            "color_tool_call": "YELLOW",
            "color_observation": "CYAN",
            "is_detailed_tool_call": True,
            "is_detailed_observation": True,
        },
        "llm": {
            "cls": "oxygent.llms.OllamaLLM",
            "base_url": "http://localhost:11434",
            "temperature": 0.1,
            "max_tokens": 4096,
            "top_p": 1,
        },
        "cache": {
            "save_dir": "./cache_dir",
        },
        "message": {
            "is_send_tool_call": True,
            "is_send_observation": True,
            "is_send_think": True,
            "is_send_answer": True,
            "is_stored": False,
            "is_show_in_terminal": False,
            "is_send_full_arguments": False,
        },
        "vearch": {},
        "es": {},
        "es_schema": {
            "shared_data": {"type": "text"},
            "group_data": {"type": "text"},
        },
        "es_settings": {
            "number_of_shards": 1,
            "number_of_replicas": 1,
        },
        "redis": {},
        "redis_param": {
            "expire_time": 86400,  # 24 hours 60 * 60 * 24
            "max_size": 1024,
            "max_length": 20480,  # 20MB
        },
        "server": {
            "host": "127.0.0.1",
            "port": 8080,
            "auto_open_webpage": True,
            "log_level": "INFO",
        },
        "agent": {
            "prompt": "",
            "llm_model": "",
            "input_schema": {
                "properties": {"query": {"description": "Query question"}},
                "required": ["query"],
            },
            "short_memory_size": 10,
            "welcome_message": "Hi, I’m OxyGent. How can I assist you?",
        },
        "tool": {
            "mcp_is_keep_alive": True,
            "is_concurrent_init": True,
        },
    }

    @classmethod
    def load_from_json(cls, path="./config.json", env=None):
        with open(path, "r", encoding="utf-8") as f:
            all_cfg = json.load(f)
        if not env:
            env = os.environ.get("APP_ENV", "default")
        cls._env = env
        # Merge default
        if "default" in all_cfg:
            cfg = replace_env_var(all_cfg["default"])
            deep_update(cls._config, cfg)
        # Merge assigned env
        if env in all_cfg:
            cfg = replace_env_var(all_cfg[env])
            deep_update(cls._config, cfg)

    @classmethod
    def set_module_config(cls, module, key, value=None):
        if module not in cls._config:
            cls._config[module] = {}
        if value is None:
            cls._config[module] = key
        else:
            cls._config[module][key] = value

    @classmethod
    def get_module_config(cls, module, key=None, default=None):
        mod_cfg = cls._config.get(module, {})
        if key is None:
            return mod_cfg
        return mod_cfg.get(key, default)

    """ app """

    @classmethod
    def set_app_config(cls, app_config):
        return cls.set_module_config("app", app_config)

    @classmethod
    def get_app_config(cls):
        return cls.get_module_config("app")

    @classmethod
    def set_app_name(cls, name):
        cls.set_module_config("app", "name", name)

    @classmethod
    def get_app_name(cls):
        return cls.get_module_config("app", "name")

    @classmethod
    def set_app_version(cls, version):
        cls.set_module_config("app", "version", version)

    @classmethod
    def get_app_version(cls):
        return cls.get_module_config("app", "version")

    """ log """

    @classmethod
    def set_log_config(cls, log_config):
        return cls.set_module_config("log", log_config)

    @classmethod
    def get_log_config(cls):
        return cls.get_module_config("log")

    @classmethod
    def set_log_path(cls, path):
        cls.set_module_config("log", "path", path)

    @classmethod
    def get_log_path(cls):
        return cls.get_module_config("log", "path")

    @classmethod
    def set_log_level_root(cls, level_root):
        cls.set_module_config("log", "level_root", level_root)
        logger = logging.getLogger()
        logger.setLevel(level_root)

    @classmethod
    def get_log_level_root(cls):
        return cls.get_module_config("log", "level_root")

    @classmethod
    def set_log_level_terminal(cls, level_terminal):
        cls.set_module_config("log", "level_terminal", level_terminal)
        logger = logging.getLogger()
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(level_terminal)

    @classmethod
    def get_log_level_terminal(cls):
        return cls.get_module_config("log", "level_terminal")

    @classmethod
    def set_log_level_file(cls, level_file):
        cls.set_module_config("log", "level_file", level_file)
        logger = logging.getLogger()
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.setLevel(level_file)

    @classmethod
    def get_log_level_file(cls):
        return cls.get_module_config("log", "level_file")

    @classmethod
    def set_log_color_is_on_background(cls, color_is_on_background=True):
        cls.set_module_config("log", "color_is_on_background", color_is_on_background)

    @classmethod
    def get_log_color_is_on_background(cls):
        return cls.get_module_config("log", "color_is_on_background")

    @classmethod
    def set_log_is_bright(cls, is_bright=True):
        cls.set_module_config("log", "is_bright", is_bright)

    @classmethod
    def get_log_is_bright(cls):
        return cls.get_module_config("log", "is_bright")

    @classmethod
    def set_log_only_message_color(cls, only_message_color=True):
        cls.set_module_config("log", "only_message_color", only_message_color)

    @classmethod
    def get_log_only_message_color(cls):
        return cls.get_module_config("log", "only_message_color")

    @classmethod
    def set_log_color_tool_call(cls, color_tool_call=True):
        cls.set_module_config("log", "color_tool_call", color_tool_call)

    @classmethod
    def get_log_color_tool_call(cls):
        return cls.get_module_config("log", "color_tool_call")

    @classmethod
    def set_log_color_observation(cls, color_observation=True):
        cls.set_module_config("log", "color_observation", color_observation)

    @classmethod
    def get_log_color_observation(cls):
        return cls.get_module_config("log", "color_observation")

    @classmethod
    def set_log_is_detailed_tool_call(cls, is_detailed_tool_call=True):
        cls.set_module_config("log", "is_detailed_tool_call", is_detailed_tool_call)

    @classmethod
    def get_log_is_detailed_tool_call(cls):
        return cls.get_module_config("log", "is_detailed_tool_call")

    @classmethod
    def set_log_is_detailed_observation(cls, is_detailed_observation=True):
        cls.set_module_config("log", "is_detailed_observation", is_detailed_observation)

    @classmethod
    def get_log_is_detailed_observation(cls):
        return cls.get_module_config("log", "is_detailed_observation")

    """ llm """

    @classmethod
    def set_llm_config(cls, llm_config):
        return cls.set_module_config("llm", llm_config)

    @classmethod
    def get_llm_config(cls):
        return cls.get_module_config("llm")

    """ cache """

    @classmethod
    def set_cache_config(cls, cache_config):
        return cls.set_module_config("cache", cache_config)

    @classmethod
    def get_cache_config(cls):
        return cls.get_module_config("cache")

    @classmethod
    def set_cache_save_dir(cls, save_dir):
        cls.set_module_config("cache", "save_dir", save_dir)

    @classmethod
    def get_cache_save_dir(cls):
        save_dir = cls.get_module_config("cache", "save_dir")
        import os

        if not os.path.exists(save_dir):
            os.makedirs(save_dir, exist_ok=True)
        return save_dir

    """ message """

    @classmethod
    def set_message_config(cls, message_config):
        return cls.set_module_config("message", message_config)

    @classmethod
    def get_message_config(cls):
        return cls.get_module_config("message")

    @classmethod
    def set_message_is_send_tool_call(cls, is_send_tool_call):
        cls.set_module_config("message", "is_send_tool_call", is_send_tool_call)

    @classmethod
    def get_message_is_send_tool_call(cls):
        return cls.get_module_config("message", "is_send_tool_call")

    @classmethod
    def set_message_is_send_observation(cls, is_send_observation):
        cls.set_module_config("message", "is_send_observation", is_send_observation)

    @classmethod
    def get_message_is_send_observation(cls):
        return cls.get_module_config("message", "is_send_observation")

    @classmethod
    def set_message_is_send_think(cls, is_send_think):
        cls.set_module_config("message", "is_send_think", is_send_think)

    @classmethod
    def get_message_is_send_think(cls):
        return cls.get_module_config("message", "is_send_think")

    @classmethod
    def set_message_is_send_answer(cls, is_send_answer):
        cls.set_module_config("message", "is_send_answer", is_send_answer)

    @classmethod
    def get_message_is_send_answer(cls):
        return cls.get_module_config("message", "is_send_answer")

    @classmethod
    def set_message_is_stored(cls, is_stored=True):
        cls.set_module_config("message", "is_stored", is_stored)

    @classmethod
    def get_message_is_stored(cls):
        return cls.get_module_config("message", "is_stored")

    @classmethod
    def set_message_is_show_in_terminal(cls, is_show_in_terminal=True):
        cls.set_module_config("message", "is_show_in_terminal", is_show_in_terminal)

    @classmethod
    def get_message_is_show_in_terminal(cls):
        return cls.get_module_config("message", "is_show_in_terminal")

    @classmethod
    def set_message_is_send_full_arguments(cls, is_send_full_arguments=True):
        cls.set_module_config(
            "message", "is_send_full_arguments", is_send_full_arguments
        )

    @classmethod
    def get_message_is_send_full_arguments(cls):
        return cls.get_module_config("message", "is_send_full_arguments")

    """ es """

    @classmethod
    def set_es_config(cls, es_config):
        cls.set_module_config("es", es_config)

    @classmethod
    def get_es_config(cls):
        return cls.get_module_config("es")

    """ es_schema """

    @classmethod
    def set_es_schema_config(cls, es_schema_config):
        cls.set_module_config("es_schema", es_schema_config)

    @classmethod
    def get_es_schema_config(cls) -> dict:
        return cls.get_module_config("es_schema")

    @classmethod
    def set_es_schema_shared_data(cls, es_schema_config):
        return cls.set_module_config("es_schema", "shared_data", es_schema_config)

    @classmethod
    def get_es_schema_shared_data(cls) -> dict:
        shared_data_schema = cls.get_module_config("es_schema", "shared_data")
        if "properties" in shared_data_schema and "type" in shared_data_schema:
            del shared_data_schema["type"]
        return shared_data_schema

    @classmethod
    def set_es_schema_group_data(cls, es_schema_config):
        return cls.set_module_config("es_schema", "group_data", es_schema_config)

    @classmethod
    def get_es_schema_group_data(cls) -> dict:
        group_data_schema = cls.get_module_config("es_schema", "group_data")
        if "properties" in group_data_schema and "type" in group_data_schema:
            del group_data_schema["type"]
        return group_data_schema

    """ es_settings """

    @classmethod
    def set_es_settings_config(cls, es_settings_config):
        cls.set_module_config("es_settings", es_settings_config)

    @classmethod
    def get_es_settings_config(cls) -> dict:
        return cls.get_module_config("es_settings")

    """ vearch """

    @classmethod
    def set_vearch_config(cls, vearch_config):
        cls.set_module_config("vearch", vearch_config)

    @classmethod
    def get_vearch_config(cls):
        return cls.get_module_config("vearch")

    @classmethod
    def get_vearch_embedding_model_url(cls):
        return cls.get_module_config("vearch", "embedding_model_url")

    """ redis """

    @classmethod
    def set_redis_config(cls, redis_config):
        cls.set_module_config("redis", redis_config)

    @classmethod
    def get_redis_config(cls):
        return cls.get_module_config("redis")

    """ redis_param """

    @classmethod
    def set_redis_expire_time(cls, expire_time):
        cls.set_module_config("redis_param", "expire_time", expire_time)

    @classmethod
    def get_redis_expire_time(cls):
        return cls.get_module_config("redis_param", "expire_time")

    @classmethod
    def set_redis_max_size(cls, max_size):
        cls.set_module_config("redis_param", "max_size", max_size)

    @classmethod
    def get_redis_max_size(cls):
        return cls.get_module_config("redis_param", "max_size")

    @classmethod
    def set_redis_max_length(cls, max_length):
        cls.set_module_config("redis_param", "max_length", max_length)

    @classmethod
    def get_redis_max_length(cls):
        return cls.get_module_config("redis_param", "max_length")

    """ server """

    @classmethod
    def set_server_config(cls, server_config):
        cls.set_module_config("server", server_config)

    @classmethod
    def get_server_config(cls):
        return cls.get_module_config("server")

    @classmethod
    def set_server_host(cls, host):
        cls.set_module_config("server", "host", host)

    @classmethod
    def get_server_host(cls):
        return cls.get_module_config("server", "host")

    @classmethod
    def set_server_port(cls, port):
        cls.set_module_config("server", "port", port)

    @classmethod
    def get_server_port(cls):
        return cls.get_module_config("server", "port")

    @classmethod
    def set_server_auto_open_webpage(cls, auto_open_webpage=True):
        cls.set_module_config("server", "auto_open_webpage", auto_open_webpage)

    @classmethod
    def get_server_auto_open_webpage(cls):
        return cls.get_module_config("server", "auto_open_webpage")

    @classmethod
    def set_server_on_latest_webpage(cls, on_latest_webpage=True):
        cls.set_module_config("server", "on_latest_webpage", on_latest_webpage)

    @classmethod
    def get_server_on_latest_webpage(cls):
        return cls.get_module_config("server", "on_latest_webpage")

    @classmethod
    def set_server_log_level(cls, log_level):
        cls.set_module_config("server", "log_level", log_level)

    @classmethod
    def get_server_log_level(cls):
        return cls.get_module_config("server", "log_level")

    """ agent """

    @classmethod
    def set_agent_config(cls, agent_config):
        cls.set_module_config("agent", agent_config)

    @classmethod
    def get_agent_config(cls):
        return cls.get_module_config("agent")

    @classmethod
    def set_agent_prompt(cls, prompt):
        cls.set_module_config("agent", "prompt", prompt)

    @classmethod
    def get_agent_prompt(cls):
        return cls.get_module_config("agent", "prompt")

    @classmethod
    def set_agent_llm_model(cls, llm_model):
        cls.set_module_config("agent", "llm_model", llm_model)

    @classmethod
    def get_agent_llm_model(cls):
        return cls.get_module_config("agent", "llm_model")

    @classmethod
    def set_agent_input_schema(cls, input_schema):
        cls.set_module_config("agent", "input_schema", input_schema)

    @classmethod
    def get_agent_input_schema(cls):
        return cls.get_module_config("agent", "input_schema")

    @classmethod
    def set_agent_short_memory_size(cls, short_memory_size):
        cls.set_module_config("agent", "short_memory_size", short_memory_size)

    @classmethod
    def get_agent_short_memory_size(cls):
        return cls.get_module_config("agent", "short_memory_size")

    @classmethod
    def set_agent_welcome_message(cls, welcome_message):
        cls.set_module_config("agent", "welcome_message", welcome_message)

    @classmethod
    def get_agent_welcome_message(cls):
        return cls.get_module_config("agent", "welcome_message")

    """ tool """

    @classmethod
    def set_tool_config(cls, tool_config):
        cls.set_module_config("tool", tool_config)

    @classmethod
    def get_tool_config(cls):
        return cls.get_module_config("tool")

    @classmethod
    def set_tool_mcp_is_keep_alive(cls, mcp_is_keep_alive):
        cls.set_module_config("tool", "mcp_is_keep_alive", mcp_is_keep_alive)

    @classmethod
    def get_tool_mcp_is_keep_alive(cls):
        return cls.get_module_config("tool", "mcp_is_keep_alive")

    @classmethod
    def set_tool_is_concurrent_init(cls, is_concurrent_init):
        cls.set_module_config("tool", "is_concurrent_init", is_concurrent_init)

    @classmethod
    def get_tool_is_concurrent_init(cls):
        return cls.get_module_config("tool", "is_concurrent_init")
