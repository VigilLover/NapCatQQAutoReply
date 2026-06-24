import asyncio
from pathlib import Path

import pytest

from unittest.mock import AsyncMock

from napcat_qq_auto_reply.onebot.client import (
    OneBotClient,
    _parse_history_message,
    build_group_message,
    parse_message_content,
)
from napcat_qq_auto_reply.onebot.models import BotResponse, LocalImage
from napcat_qq_auto_reply.onebot.path_mapping import ContainerPathMapper


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send_json(self, payload):
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_call_correlates_echo_response():
    client = OneBotClient("ws://127.0.0.1:3001", "token", action_timeout=1)
    client._ws = FakeWebSocket()
    task = asyncio.create_task(client.call("get_login_info", {}))
    await asyncio.sleep(0)
    echo = client._ws.sent[0]["echo"]
    client.handle_payload({"status": "ok", "retcode": 0, "data": {"user_id": 42}, "echo": echo})
    assert await task == {"user_id": 42}


def test_build_group_message_uses_reply_text_and_local_image():
    response = BotResponse(
        "你好",
        (LocalImage(Path("/tmp/generated image.jpg"), "image/jpeg"),),
    )
    segments = build_group_message(response, reply_to_message_id=99)
    assert segments[0] == {"type": "reply", "data": {"id": "99"}}
    assert segments[1] == {"type": "text", "data": {"text": "你好"}}
    assert segments[2]["type"] == "image"
    assert segments[2]["data"]["file"].startswith("file://")
    assert "%20" in segments[2]["data"]["file"]


def test_build_group_message_maps_host_image_to_container(tmp_path: Path):
    generated = tmp_path / "generated_images"
    generated.mkdir()
    image_path = generated / "小狼 image.jpg"
    image_path.write_bytes(b"image")
    mapper = ContainerPathMapper(generated, "/shared/generated_images")

    segments = build_group_message(
        BotResponse("", (LocalImage(image_path),)),
        reply_to_message_id=99,
        path_mapper=mapper,
    )

    uri = segments[1]["data"]["file"]
    assert uri.startswith("file:///shared/generated_images/")
    assert "%20" in uri
    assert "%E5%B0%8F%E7%8B%BC" in uri


def test_container_path_mapper_rejects_missing_and_outside_files(tmp_path: Path):
    generated = tmp_path / "generated_images"
    generated.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"outside")
    mapper = ContainerPathMapper(generated, "/shared/generated_images")

    with pytest.raises(ValueError, match="does not exist"):
        mapper.to_file_uri(generated / "missing.jpg")
    with pytest.raises(ValueError, match="outside"):
        mapper.to_file_uri(outside)


def test_container_path_mapper_rejects_symlink_escape(tmp_path: Path):
    generated = tmp_path / "generated_images"
    generated.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"outside")
    link = generated / "link.jpg"
    link.symlink_to(outside)

    mapper = ContainerPathMapper(generated, "/shared/generated_images")
    with pytest.raises(ValueError, match="outside"):
        mapper.to_file_uri(link)


def test_parse_quoted_message_keeps_image_sources():
    content = parse_message_content(
        [
            {"type": "text", "data": {"text": "看这张"}},
            {"type": "image", "data": {"url": "https://example.invalid/ref.jpg"}},
        ]
    )
    assert content.text == "看这张[图片]"
    assert content.images[0].source == "https://example.invalid/ref.jpg"


# ── HistoryMessage & _parse_history_message ─────────────────────────────


def test_parse_history_message_complete():
    raw = {
        "message_id": 12345,
        "user_id": 67890,
        "sender": {"nickname": "小明", "card": "小明@群名片"},
        "time": 1719200000,
        "message": [{"type": "text", "data": {"text": "今天天气真好"}}],
    }
    msg = _parse_history_message(raw)
    assert msg.message_id == 12345
    assert msg.user_id == 67890
    assert msg.nickname == "小明"
    assert msg.card == "小明@群名片"
    assert msg.text == "今天天气真好"
    assert msg.timestamp == 1719200000
    assert msg.display_name == "小明@群名片"


def test_parse_history_message_minimal_fields():
    """缺失字段时使用默认值"""
    raw = {
        "message_id": 1,
        "user_id": 2,
        "sender": {},
        "time": 0,
    }
    msg = _parse_history_message(raw)
    assert msg.message_id == 1
    assert msg.user_id == 2
    assert msg.nickname == ""
    assert msg.card is None
    assert msg.text == ""
    assert msg.timestamp == 0
    assert msg.display_name == "2"


def test_parse_history_message_string_message():
    """message 字段为纯字符串而非 segments 数组"""
    raw = {
        "message_id": 3,
        "user_id": 4,
        "sender": {"nickname": "小红"},
        "time": 1719200100,
        "message": "纯文本消息",
    }
    msg = _parse_history_message(raw)
    assert msg.text == "纯文本消息"


def test_parse_history_message_mixed_segments():
    """message 包含文本和图片 segments"""
    raw = {
        "message_id": 5,
        "user_id": 6,
        "sender": {"nickname": "小刚", "card": None},
        "time": 1719200200,
        "message": [
            {"type": "text", "data": {"text": "看这张图"}},
            {"type": "image", "data": {"url": "http://example.com/pic.jpg"}},
            {"type": "text", "data": {"text": "好看吗"}},
        ],
    }
    msg = _parse_history_message(raw)
    assert msg.text == "看这张图[图片]好看吗"
    assert msg.display_name == "小刚"


# ── get_group_msg_history ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_group_msg_history_returns_parsed_messages():
    """mock call() 返回原始 JSON，验证 get_group_msg_history 解析结果"""
    client = OneBotClient.__new__(OneBotClient)
    client.call = AsyncMock(return_value={
        "messages": [
            {
                "message_id": 100,
                "user_id": 200,
                "sender": {"nickname": "测试", "card": "测试名片"},
                "time": 1719200000,
                "message": [{"type": "text", "data": {"text": "hello"}}],
            },
            {
                "message_id": 101,
                "user_id": 201,
                "sender": {"nickname": "用户二"},
                "time": 1719200060,
                "message": "纯文本",
            },
        ]
    })
    result = await client.get_group_msg_history(12345, count=50)
    assert len(result) == 2
    assert result[0].message_id == 100
    assert result[0].display_name == "测试名片"
    assert result[1].text == "纯文本"
    client.call.assert_called_once_with(
        "get_group_msg_history", {"group_id": 12345, "count": 50}
    )


@pytest.mark.asyncio
async def test_get_group_msg_history_empty_response():
    """API 返回空 messages 列表"""
    client = OneBotClient.__new__(OneBotClient)
    client.call = AsyncMock(return_value={"messages": []})
    result = await client.get_group_msg_history(12345)
    assert result == []


@pytest.mark.asyncio
async def test_get_group_msg_history_non_dict_data():
    """API 返回非字典 data（如列表）"""
    client = OneBotClient.__new__(OneBotClient)
    client.call = AsyncMock(return_value=[])
    result = await client.get_group_msg_history(12345)
    assert result == []
