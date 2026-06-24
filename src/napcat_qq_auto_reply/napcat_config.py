import json
import os
import tempfile
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values


def load_napcat_env_values(path: Path | str) -> dict[str, str]:
    return {
        key: value or ""
        for key, value in dotenv_values(path).items()
    }


def _required_token(values: Mapping[str, str], name: str) -> str:
    value = str(values.get(name, "")).strip()
    if not value:
        raise ValueError(f"{name} must be configured")
    return value


def _atomic_secure_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            os.fchmod(temporary.fileno(), 0o600)
            json.dump(payload, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
        path.chmod(0o600)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def render_napcat_configs(
    values: Mapping[str, str], output_dir: Path | str
) -> tuple[Path, Path]:
    onebot_token = _required_token(values, "NAPCAT_ACCESS_TOKEN")
    webui_token = _required_token(values, "NAPCAT_WEBUI_TOKEN")
    if onebot_token == webui_token:
        raise ValueError("NAPCAT_ACCESS_TOKEN and NAPCAT_WEBUI_TOKEN must be different")

    onebot = {
        "network": {
            "httpServers": [],
            "httpSseServers": [],
            "httpClients": [],
            "websocketServers": [
                {
                    "enable": True,
                    "name": "ws",
                    "host": "0.0.0.0",
                    "port": 3001,
                    "reportSelfMessage": False,
                    "enableForcePushEvent": True,
                    "messagePostFormat": "array",
                    "token": onebot_token,
                    "debug": False,
                    "heartInterval": 30000,
                }
            ],
            "websocketClients": [],
            "plugins": [],
        },
        "musicSignUrl": "",
        "enableLocalFile2Url": False,
        "parseMultMsg": False,
    }
    webui = {
        "host": "0.0.0.0",
        "prefix": "/webui",
        "port": 6099,
        "token": webui_token,
        "loginRate": 3,
    }
    directory = Path(output_dir)
    onebot_path = directory / "onebot11.json"
    webui_path = directory / "webui.json"
    _atomic_secure_json(onebot_path, onebot)
    _atomic_secure_json(webui_path, webui)
    return onebot_path, webui_path
