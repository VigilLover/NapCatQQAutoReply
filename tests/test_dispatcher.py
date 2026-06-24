from pathlib import Path

import pytest

from napcat_qq_auto_reply.bot.context import ContextStore
from napcat_qq_auto_reply.bot.dispatcher import BotDispatcher
from napcat_qq_auto_reply.bot.routing import MessageRouter
from napcat_qq_auto_reply.onebot.models import BotResponse
from napcat_qq_auto_reply.onebot.client import MessageContent
from napcat_qq_auto_reply.onebot.models import InboundImage
from napcat_qq_auto_reply.tools.attachments import AttachmentStore


def payload(message_id, text, *, user_id=300, group_id=100, mentions=None, reply_id=None):
    segments = []
    if mentions:
        segments.append({"type": "at", "data": {"qq": str(mentions)}})
    if reply_id:
        segments.append({"type": "reply", "data": {"id": str(reply_id)}})
    segments.append({"type": "text", "data": {"text": text}})
    return {
        "post_type": "message",
        "message_type": "group",
        "group_id": group_id,
        "message_id": message_id,
        "user_id": user_id,
        "sender": {"nickname": "用户"},
        "message": segments,
    }


class FakeClient:
    def __init__(self):
        self.sent = []

    async def get_message_content(self, message_id):
        return MessageContent(
            text=f"引用-{message_id}",
            images=(InboundImage("https://example.invalid/ref.jpg"),),
        )

    async def send_group_response(self, group_id, reply_id, response):
        self.sent.append((group_id, reply_id, response))


class FakeAgent:
    async def respond(self, **kwargs):
        self.kwargs = kwargs
        return BotResponse("agent reply")


@pytest.mark.asyncio
async def test_dispatcher_keeps_normal_context_and_replies_to_trigger(tmp_path: Path):
    async def downloader(url):
        return b"ref", "image/jpeg"

    client = FakeClient()
    agent = FakeAgent()
    context = ContextStore()
    dispatcher = BotDispatcher(
        client=client,
        bot_id=42,
        router=MessageRouter({100}, {"【小狼】"}),
        context=context,
        commands=None,
        agent=agent,
        attachment_store=AttachmentStore(tmp_path / "inbound", downloader=downloader),
    )

    await dispatcher.handle_payload(payload(1, "普通群聊"))
    await dispatcher.handle_payload(payload(2, "问候", mentions=42, reply_id=1))

    assert [event.text for event in context.recent(100)] == ["普通群聊", "问候"]
    assert client.sent[0][0:2] == (100, 2)
    assert agent.kwargs["quoted_text"].startswith("引用-1")
    assert "attachment_id" in agent.kwargs["quoted_text"]
    assert len(agent.kwargs["attachment_ids"]) == 1
    assert context.history(100) == [("用户", "问候", "agent reply")]
