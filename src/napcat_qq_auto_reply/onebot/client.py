import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import BotResponse, InboundImage
from .path_mapping import ContainerPathMapper


class OneBotActionError(RuntimeError):
    pass


def build_group_message(
    response: BotResponse,
    reply_to_message_id: int,
    path_mapper: ContainerPathMapper | None = None,
) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = [
        {"type": "reply", "data": {"id": str(reply_to_message_id)}}
    ]
    if response.text:
        segments.append({"type": "text", "data": {"text": response.text}})
    for attachment in response.attachments:
        path = Path(attachment.path).expanduser().resolve()
        file_uri = path_mapper.to_file_uri(path) if path_mapper else path.as_uri()
        segments.append({"type": "image", "data": {"file": file_uri}})
    return segments


@dataclass(frozen=True, slots=True)
class MessageContent:
    text: str
    images: tuple[InboundImage, ...] = ()


def parse_message_content(message: object) -> MessageContent:
    if isinstance(message, str):
        return MessageContent(message.strip())
    if not isinstance(message, list):
        return MessageContent("")
    parts = []
    images = []
    for segment in message:
        if not isinstance(segment, dict):
            continue
        data = segment.get("data") or {}
        if segment.get("type") == "text":
            parts.append(str(data.get("text") or ""))
        elif segment.get("type") == "image":
            parts.append("[图片]")
            source = str(data.get("url") or data.get("file") or "").strip()
            if source:
                images.append(
                    InboundImage(source=source, file_name=str(data.get("file") or ""))
                )
    return MessageContent("".join(parts).strip(), tuple(images))


class OneBotClient:
    def __init__(
        self,
        url: str,
        access_token: str,
        action_timeout: float = 30,
        path_mapper: ContainerPathMapper | None = None,
    ):
        self.url = url
        self.access_token = access_token
        self.action_timeout = action_timeout
        self.path_mapper = path_mapper
        self._session = None
        self._ws = None
        self._pending: dict[str, asyncio.Future] = {}

    async def connect(self) -> None:
        import aiohttp

        await self.close()
        self._session = aiohttp.ClientSession()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        self._ws = await self._session.ws_connect(
            self.url,
            headers=headers,
            heartbeat=30,
            receive_timeout=None,
        )

    async def call(self, action: str, params: dict[str, Any]) -> Any:
        if self._ws is None:
            raise ConnectionError("OneBot WebSocket is not connected")
        echo = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self._pending[echo] = future
        try:
            await self._ws.send_json({"action": action, "params": params, "echo": echo})
            return await asyncio.wait_for(future, timeout=self.action_timeout)
        finally:
            self._pending.pop(echo, None)

    def handle_payload(self, payload: dict[str, Any]) -> bool:
        echo = payload.get("echo")
        if not echo:
            return False
        future = self._pending.get(str(echo))
        if future is None or future.done():
            return True
        if payload.get("status") == "ok" and int(payload.get("retcode", 0)) == 0:
            future.set_result(payload.get("data"))
        else:
            future.set_exception(
                OneBotActionError(
                    f"OneBot action failed: retcode={payload.get('retcode')} "
                    f"message={payload.get('message') or payload.get('wording')}"
                )
            )
        return True

    async def listen(
        self, on_event: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        import aiohttp

        if self._ws is None:
            raise ConnectionError("OneBot WebSocket is not connected")
        try:
            async for message in self._ws:
                if message.type == aiohttp.WSMsgType.TEXT:
                    try:
                        payload = message.json()
                    except Exception:
                        logging.warning("Ignoring invalid OneBot JSON payload")
                        continue
                    if not isinstance(payload, dict) or self.handle_payload(payload):
                        continue
                    asyncio.create_task(on_event(payload))
                elif message.type in {
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.ERROR,
                }:
                    break
        finally:
            error = ConnectionError("OneBot WebSocket disconnected")
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(error)
            self._pending.clear()

    async def get_login_info(self) -> dict[str, Any]:
        return await self.call("get_login_info", {})

    async def get_message_text(self, message_id: int) -> str:
        return (await self.get_message_content(message_id)).text

    async def get_message_content(self, message_id: int) -> MessageContent:
        data = await self.call("get_msg", {"message_id": message_id})
        return parse_message_content((data or {}).get("message"))

    async def send_group_response(
        self,
        group_id: int,
        reply_id: int,
        response: BotResponse,
    ) -> Any:
        return await self.call(
            "send_group_msg",
            {
                "group_id": group_id,
                "message": build_group_message(response, reply_id, self.path_mapper),
            },
        )

    async def close(self) -> None:
        if self._ws is not None and not getattr(self._ws, "closed", False):
            await self._ws.close()
        self._ws = None
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
