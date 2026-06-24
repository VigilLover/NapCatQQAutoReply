import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


def _required(values: Mapping[str, str], name: str) -> str:
    value = str(values.get(name, "")).strip()
    if not value:
        raise ValueError(f"Missing required configuration: {name}")
    return value


def _csv_set(raw: str) -> frozenset[str]:
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True, slots=True)
class AppConfig:
    napcat_ws_url: str
    napcat_access_token: str
    allowed_groups: frozenset[int]
    persona: str
    trigger_words: frozenset[str]
    deepseek_api_key: str
    deepseek_model: str
    deepseek_fallback_model: str
    deepseek_thinking: str
    neo4j_url: str
    neo4j_auth: tuple[str, str]
    postgres_uri: str
    embedding_model: str
    embedding_dims: int
    embedding_cache_folder: str | None
    image_api_url: str
    image_api_key: str
    image_model: str
    mcp_server_url: str | None
    data_dir: Path
    max_parallel_groups: int

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> "AppConfig":
        raw_groups = _csv_set(_required(values, "QQ_GROUP_ALLOWLIST"))
        try:
            allowed_groups = frozenset(int(item) for item in raw_groups)
        except ValueError as exc:
            raise ValueError("QQ_GROUP_ALLOWLIST must contain numeric group ids") from exc
        if not allowed_groups:
            raise ValueError("QQ_GROUP_ALLOWLIST cannot be empty")

        raw_auth = _required(values, "NEO4J_DB_AUTH")
        if ":" not in raw_auth:
            raise ValueError("NEO4J_DB_AUTH must use username:password")
        username, password = raw_auth.split(":", 1)
        if not username or not password:
            raise ValueError("NEO4J_DB_AUTH must use username:password")

        return cls(
            napcat_ws_url=_required(values, "NAPCAT_WS_URL"),
            napcat_access_token=_required(values, "NAPCAT_ACCESS_TOKEN"),
            allowed_groups=allowed_groups,
            persona=str(values.get("BOT_PERSONA", "wolf_lumine")).strip()
            or "wolf_lumine",
            trigger_words=_csv_set(
                str(values.get("BOT_TRIGGER_WORDS", "【小狼】"))
            ),
            deepseek_api_key=_required(values, "DEEPSEEK_API_KEY"),
            deepseek_model=str(values.get("DEEPSEEK_MENTION_MODEL", "deepseek-v4-pro")),
            deepseek_fallback_model=str(
                values.get("DEEPSEEK_MENTION_FALLBACK_MODEL", "deepseek-v4-flash")
            ),
            deepseek_thinking=str(
                values.get("DEEPSEEK_MENTION_THINKING", "enabled")
            ).lower(),
            neo4j_url=_required(values, "NEO4J_DB_URL"),
            neo4j_auth=(username, password),
            postgres_uri=_required(values, "QQ_POSTGRES_DB_URI"),
            embedding_model=str(values.get("EMBEDDING_MODEL_NAME", "moka-ai/m3e-base")),
            embedding_dims=int(_required(values, "EMBEDDING_DIMS")),
            embedding_cache_folder=str(values.get("EMBEDDING_CACHE_FOLDER") or "") or None,
            image_api_url=_required(values, "IMAGE_GEN_API_URL"),
            image_api_key=_required(values, "IMAGE_GEN_API_KEY"),
            image_model=str(values.get("IMAGE_GEN_MODEL", "gpt-image-2")),
            mcp_server_url=str(values.get("MCP_SERVER_URL") or "").strip() or None,
            data_dir=Path(values.get("BOT_DATA_DIR", "data")).expanduser().resolve(),
            max_parallel_groups=int(values.get("MAX_PARALLEL_GROUPS", "4")),
        )

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls.from_mapping(os.environ)
