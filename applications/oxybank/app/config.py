import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("oxybank.config")


@dataclass
class ESConfig:
    hosts: list | str = "http://localhost:9200"
    user: str = ""
    password: str = ""
    index_prefix: str = "oxybank"
    timeout: int = 60


@dataclass
class VearchConfig:
    master_url: str = "http://localhost:8817"
    router_url: str = "http://localhost:9001"
    db_name: str = "oxybank"


@dataclass
class TritonConfig:
    url: str = "http://localhost:8001/v2/models/embedding/infer"
    batch_size: int = 32
    max_concurrent: int = 4


@dataclass
class OpenAIEmbeddingConfig:
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "text-embedding-ada-002"
    batch_size: int = 100
    max_concurrent: int = 4


@dataclass
class LLMConfig:
    api_key: str = "EMPTY"
    base_url: str = "http://localhost:8080/v1"
    model: str = "qwen25-32b-native"


@dataclass
class AnnotationConfig:
    max_concurrency: int = 5
    event_queue_size: int = 10000
    max_cascade_depth: int = 10
    agent_timeout: int = 120


@dataclass
class ChunkingConfig:
    chunk_size: int = 512
    chunk_overlap: int = 50


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8080


@dataclass
class AuthConfig:
    secret_key: str = "oxybank-secret-change-me"
    algorithm: str = "HS256"
    token_expire_hours: int = 72
    enabled: bool = True


@dataclass
class AppConfig:
    es: ESConfig = field(default_factory=ESConfig)
    vearch: VearchConfig = field(default_factory=VearchConfig)
    triton: TritonConfig = field(default_factory=TritonConfig)
    openai: OpenAIEmbeddingConfig = field(default_factory=OpenAIEmbeddingConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    annotation: AnnotationConfig = field(default_factory=AnnotationConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)


_config: AppConfig | None = None


def _apply_dict(obj, d: dict):
    for k, v in d.items():
        if hasattr(obj, k):
            attr = getattr(obj, k)
            if isinstance(v, dict) and hasattr(attr, "__dataclass_fields__"):
                _apply_dict(attr, v)
            else:
                setattr(obj, k, v)


def load_config(config_path: str | None = None, env: str | None = None) -> AppConfig:
    global _config
    if _config is not None:
        return _config

    cfg = AppConfig()
    env = env or os.getenv("OXYBANK_ENV", "development")

    path = Path(config_path) if config_path else Path(__file__).parent.parent / "config.json"
    if path.exists():
        with open(path) as f:
            raw = json.load(f)
        if "default" in raw:
            _apply_dict(cfg, raw["default"])
        if env in raw:
            _apply_dict(cfg, raw[env])
        logger.info("Loaded config from %s (env=%s)", path, env)
    else:
        logger.warning("No config file at %s, using defaults", path)

    _config = cfg
    return cfg


def get_config() -> AppConfig:
    if _config is None:
        return load_config()
    return _config
