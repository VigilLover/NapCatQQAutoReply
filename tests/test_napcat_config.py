import json
import stat

import pytest

from napcat_qq_auto_reply.napcat_config import (
    load_napcat_env_values,
    render_napcat_configs,
)


def test_render_napcat_configs_writes_secure_onebot_and_webui_files(tmp_path):
    render_napcat_configs(
        {
            "NAPCAT_ACCESS_TOKEN": "onebot-secret",
            "NAPCAT_WEBUI_TOKEN": "webui-secret",
        },
        tmp_path,
    )

    onebot_path = tmp_path / "onebot11.json"
    webui_path = tmp_path / "webui.json"
    onebot = json.loads(onebot_path.read_text(encoding="utf-8"))
    webui = json.loads(webui_path.read_text(encoding="utf-8"))

    server = onebot["network"]["websocketServers"][0]
    assert server["host"] == "0.0.0.0"
    assert server["port"] == 3001
    assert server["messagePostFormat"] == "array"
    assert server["token"] == "onebot-secret"
    assert webui == {
        "host": "0.0.0.0",
        "prefix": "/webui",
        "port": 6099,
        "token": "webui-secret",
        "loginRate": 3,
    }
    assert stat.S_IMODE(onebot_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(webui_path.stat().st_mode) == 0o600


@pytest.mark.parametrize(
    ("onebot_token", "webui_token", "message"),
    [
        ("", "webui", "NAPCAT_ACCESS_TOKEN"),
        ("onebot", "", "NAPCAT_WEBUI_TOKEN"),
        ("same", "same", "must be different"),
    ],
)
def test_render_napcat_configs_rejects_invalid_tokens(
    tmp_path, onebot_token, webui_token, message
):
    with pytest.raises(ValueError, match=message):
        render_napcat_configs(
            {
                "NAPCAT_ACCESS_TOKEN": onebot_token,
                "NAPCAT_WEBUI_TOKEN": webui_token,
            },
            tmp_path,
        )
    assert not list(tmp_path.iterdir())


def test_env_file_is_authoritative_over_exported_process_values(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "NAPCAT_ACCESS_TOKEN=file-onebot\nNAPCAT_WEBUI_TOKEN=file-webui\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NAPCAT_ACCESS_TOKEN", "stale-exported-token")

    values = load_napcat_env_values(env_path)

    assert values["NAPCAT_ACCESS_TOKEN"] == "file-onebot"
    assert values["NAPCAT_WEBUI_TOKEN"] == "file-webui"
