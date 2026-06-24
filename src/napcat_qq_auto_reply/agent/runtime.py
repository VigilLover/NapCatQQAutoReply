from contextvars import ContextVar, Token
from dataclasses import dataclass, field

from napcat_qq_auto_reply.onebot.models import LocalImage


@dataclass(slots=True)
class RequestToolContext:
    qq_id: int
    allowed_attachment_ids: frozenset[str]
    attachments: list[LocalImage] = field(default_factory=list)


class AgentToolRuntime:
    def __init__(self, memory, images):
        self.memory = memory
        self.images = images
        self._context: ContextVar[RequestToolContext | None] = ContextVar(
            "agent_tool_context", default=None
        )

    @property
    def image_generation_enabled(self) -> bool:
        return self.images is not None

    def _current(self) -> RequestToolContext:
        context = self._context.get()
        if context is None:
            raise RuntimeError("Agent tool called outside a request")
        return context

    def begin_request(
        self, qq_id: int, allowed_attachment_ids: set[str]
    ) -> Token[RequestToolContext | None]:
        return self._context.set(
            RequestToolContext(qq_id, frozenset(allowed_attachment_ids))
        )

    def end_request(self, token: Token[RequestToolContext | None]) -> None:
        self._context.reset(token)

    async def search_memory(self, query: str | None = None, limit: int = 5) -> str:
        context = self._current()
        return await self.memory.search(context.qq_id, query, limit)

    async def manage_memory(
        self,
        action: str,
        content: str | None = None,
        memory_id: str | None = None,
    ) -> str:
        context = self._current()
        return await self.memory.manage(
            actor_qq_id=context.qq_id,
            target_qq_id=context.qq_id,
            action=action,
            content=content,
            memory_id=memory_id,
        )

    async def generate_image(
        self,
        prompt: str,
        reference_attachment_ids: list[str] | None = None,
        aspect_ratio: str = "1:1",
    ) -> str:
        if self.images is None:
            raise RuntimeError("图片生成功能未启用")
        context = self._current()
        requested = reference_attachment_ids or []
        if any(item not in context.allowed_attachment_ids for item in requested):
            raise ValueError("参考图片 attachment_id 不属于当前上下文")
        image = await self.images.generate(prompt, requested, aspect_ratio)
        context.attachments.append(image)
        return "图片已生成，将作为QQ图片消息随最终回复发送。"

    def current_attachments(self) -> tuple[LocalImage, ...]:
        return tuple(self._current().attachments)

    def langchain_tools(self):
        from langchain_core.tools import StructuredTool

        tools = [
            StructuredTool.from_function(
                coroutine=self.search_memory,
                name="search_qq_memory",
                description="搜索当前QQ用户自己的长期记忆。",
            ),
            StructuredTool.from_function(
                coroutine=self.manage_memory,
                name="manage_qq_memory",
                description=(
                    "创建、更新或删除当前QQ用户自己的长期记忆。"
                    "只有用户明确要求记住或忘记时才能调用。"
                ),
            ),
        ]
        if self.image_generation_enabled:
            tools.append(
                StructuredTool.from_function(
                    coroutine=self.generate_image,
                    name="generate_image",
                    description=(
                        "生成或修改图片。参考图只能使用当前提示中列出的 attachment_id。"
                        "返回成功后，图片会由QQ网关自动作为图片消息发送。"
                    ),
                )
            )
        return tools
