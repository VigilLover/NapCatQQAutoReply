import asyncio
from pathlib import Path

import pytest

from napcat_qq_auto_reply.onebot.client import (
    OneBotClient,
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
