import asyncio
import logging
from collections import defaultdict
from dataclasses import replace

from napcat_qq_auto_reply.onebot.models import BotResponse, GroupEvent, InboundImage
from napcat_qq_auto_reply.onebot.parser import parse_group_event


class BotDispatcher:
    def __init__(
        self,
        *,
        client,
        bot_id: int,
        router,
        context,
        commands,
        agent,
        attachment_store,
        max_parallel_groups: int = 4,
    ):
        self.client = client
        self.bot_id = bot_id
        self.router = router
        self.context = context
        self.commands = commands
        self.agent = agent
        self.attachment_store = attachment_store
        self._group_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._parallel_gate = asyncio.Semaphore(max_parallel_groups)

    async def _cache_images(self, event: GroupEvent) -> GroupEvent:
        cached: list[InboundImage] = []
        for image in event.images:
            try:
                attachment_id = await self.attachment_store.cache_url(image.source)
                cached.append(InboundImage(source="cached", file_name=attachment_id))
            except Exception:
                logging.exception("Failed to cache inbound QQ image")
        return replace(event, images=tuple(cached))

    async def _cache_reference_images(self, images) -> set[str]:
        attachment_ids: set[str] = set()
        for image in images:
            try:
                attachment_ids.add(
                    await self.attachment_store.cache_url(image.source)
                )
            except Exception:
                logging.exception("Failed to cache image from quoted QQ message")
        return attachment_ids

    async def handle_payload(self, payload: dict) -> None:
        event = parse_group_event(payload)
        if event is None:
            return
        if (
            event.group_id not in self.router.allowed_groups
            or event.user.qq_id == self.bot_id
        ):
            return
        if event.images:
            event = await self._cache_images(event)
        self.context.add_event(event)
        routed = self.router.route(event, self.bot_id)
        if routed is None:
            return

        async with self._parallel_gate, self._group_locks[event.group_id]:
            try:
                quoted_text = ""
                quoted_attachment_ids: set[str] = set()
                if event.reply_id is not None:
                    quoted = await self.client.get_message_content(event.reply_id)
                    quoted_text = quoted.text
                    quoted_attachment_ids = await self._cache_reference_images(
                        quoted.images
                    )
                    if quoted_attachment_ids:
                        quoted_text += "\n引用图片 attachment_id: " + ", ".join(
                            sorted(quoted_attachment_ids)
                        )

                command_text = None
                if self.commands is not None:
                    command_text = await self.commands.handle(
                        routed.prompt,
                        event.group_id,
                        event.user.qq_id,
                        event.user.display_name,
                    )
                if command_text is not None:
                    response = BotResponse(command_text)
                else:
                    recent_events = self.context.recent(event.group_id)
                    attachment_ids = {
                        image.file_name
                        for item in recent_events
                        for image in item.images
                        if image.file_name
                    }
                    attachment_ids.update(quoted_attachment_ids)
                    response = await self.agent.respond(
                        group_id=event.group_id,
                        user=event.user,
                        prompt=routed.prompt,
                        recent_events=recent_events[:-1],
                        history=self.context.history(event.group_id),
                        quoted_text=quoted_text,
                        attachment_ids=attachment_ids,
                    )
                    self.context.add_turn(event.group_id, routed.prompt, response.text)
                await self.client.send_group_response(
                    event.group_id, event.message_id, response
                )
            except Exception:
                logging.exception("Failed to process QQ group message")
                try:
                    await self.client.send_group_response(
                        event.group_id,
                        event.message_id,
                        BotResponse("抱歉，处理这条消息时遇到了错误，请稍后再试。"),
                    )
                except Exception:
                    logging.exception("Failed to send QQ error response")
