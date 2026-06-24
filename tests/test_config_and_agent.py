import base64
from pathlib import Path

import pytest

from napcat_qq_auto_reply.agent.prompts import build_chat_prompt_template, format_recent_context
from napcat_qq_auto_reply.agent.runtime import AgentToolRuntime
from napcat_qq_auto_reply.config import AppConfig
from napcat_qq_auto_reply.onebot.models import GroupEvent, LocalImage, QQUser
from napcat_qq_auto_reply.tools.openai_images import image_size_for_aspect, parse_image_response


def complete_config():
    return {
        "NAPCAT_WS_URL": "ws://127.0.0.1:3001",
        "NAPCAT_ACCESS_TOKEN": "secret",
        "QQ_GROUP_ALLOWLIST": "100, 200",
        "BOT_PERSONA": "wolf_lumine",
        "BOT_TRIGGER_WORDS": "【小狼】,小狼bot",
        "DEEPSEEK_API_KEY": "key",
        "NEO4J_DB_URL": "bolt://127.0.0.1:7687",
        "NEO4J_DB_AUTH": "neo4j:password",
        "QQ_POSTGRES_DB_URI": "postgresql://u:p@localhost/db",
        "EMBEDDING_DIMS": "768",
        "IMAGE_GEN_API_URL": "https://images.invalid/v1",
        "IMAGE_GEN_API_KEY": "image-key",
        "NAPCAT_CONTAINER_GENERATED_IMAGE_DIR": "/shared/generated_images",
    }


def test_config_parses_required_values():
    config = AppConfig.from_mapping(complete_config())
    assert config.allowed_groups == frozenset({100, 200})
    assert config.trigger_words == frozenset({"【小狼】", "小狼bot"})
    assert config.neo4j_auth == ("neo4j", "password")
    assert config.embedding_dims == 768
    assert config.container_generated_image_dir == "/shared/generated_images"


def test_container_image_directory_is_optional():
    values = complete_config()
    values.pop("NAPCAT_CONTAINER_GENERATED_IMAGE_DIR")
    assert AppConfig.from_mapping(values).container_generated_image_dir is None


def test_image_generation_is_optional_when_api_key_is_blank():
    values = complete_config()
    values["IMAGE_GEN_API_KEY"] = ""
    values["IMAGE_GEN_API_URL"] = ""

    config = AppConfig.from_mapping(values)

    assert config.image_api_key == ""
    assert config.image_api_url == ""


def test_image_generation_requires_url_when_api_key_is_configured():
    values = complete_config()
    values["IMAGE_GEN_API_URL"] = ""

    with pytest.raises(ValueError, match="IMAGE_GEN_API_URL"):
        AppConfig.from_mapping(values)


def test_config_rejects_missing_required_value():
    values = complete_config()
    values.pop("QQ_POSTGRES_DB_URI")
    with pytest.raises(ValueError, match="QQ_POSTGRES_DB_URI"):
        AppConfig.from_mapping(values)


def _invoke_template(template, **overrides):
    """用一组默认值渲染模板，便于测试断言。"""
    defaults = {
        "group_id": 0,
        "user_id": 0,
        "display_name": "测试用户",
        "recent_msgs": "无近期群消息",
        "long_term_memory": "无相关长期记忆",
        "style_context": "无",
        "attachment_ids": "无",
        "chat_history": [],
        "messages": [],
    }
    defaults.update(overrides)
    return template.invoke(defaults).to_messages()[0].content


def test_prompt_is_qq_specific_and_formats_recent_messages():
    template = build_chat_prompt_template("wolf_lumine")
    prompt_text = _invoke_template(template)
    assert "QQ群" in prompt_text
    assert "水源" not in prompt_text
    assert "wolf_lumine" in prompt_text
    events = [
        GroupEvent(1, 1, QQUser(2, "昵称", None), "你好"),
        GroupEvent(1, 2, QQUser(3, "另一个人", "群名片"), "晚安"),
    ]
    context = format_recent_context(events)
    assert "昵称(2): 你好" in context
    assert "群名片(3): 晚安" in context


def test_prompt_omits_image_instructions_when_image_generation_is_disabled():
    template = build_chat_prompt_template("wolf_lumine", image_generation_enabled=False)
    prompt_text = _invoke_template(template)
    assert "图片生成功能未启用" in prompt_text
    assert "不要调用 generate_image" in prompt_text


class FakeMemory:
    async def search(self, qq_id, query=None, limit=5):
        return f"memory:{qq_id}:{query}"

    async def manage(self, **kwargs):
        assert kwargs["actor_qq_id"] == kwargs["target_qq_id"] == 123
        return "已记住。"


class FakeImages:
    async def generate(self, prompt, reference_ids=None, aspect_ratio="1:1"):
        return LocalImage(Path("/tmp/generated.jpg"), "image/jpeg")


def test_agent_runtime_omits_image_tool_when_disabled():
    runtime = AgentToolRuntime(FakeMemory(), images=None)
    assert {tool.name for tool in runtime.langchain_tools()} == {
        "search_qq_memory",
        "manage_qq_memory",
    }


@pytest.mark.asyncio
async def test_agent_runtime_scopes_memory_and_collects_images():
    runtime = AgentToolRuntime(FakeMemory(), FakeImages())
    token = runtime.begin_request(123, {"allowed-ref"})
    try:
        assert await runtime.search_memory("咖啡") == "memory:123:咖啡"
        assert await runtime.manage_memory("create", "喜欢咖啡") == "已记住。"
        result = await runtime.generate_image("画图", ["allowed-ref"], "1:1")
        assert "图片已生成" in result
        assert runtime.current_attachments() == (
            LocalImage(Path("/tmp/generated.jpg"), "image/jpeg"),
        )
        with pytest.raises(ValueError, match="参考图片"):
            await runtime.generate_image("画图", ["not-allowed"], "1:1")
    finally:
        runtime.end_request(token)


def test_parse_image_response_accepts_base64():
    raw = base64.b64encode(b"jpeg-data").decode()
    assert parse_image_response({"data": [{"b64_json": raw}]}) == b"jpeg-data"


def test_image_size_preserves_common_orientation():
    assert image_size_for_aspect("1:1") == "1024x1024"
    assert image_size_for_aspect("16:9") == "1824x1024"
    assert image_size_for_aspect("9:16") == "1024x1824"
