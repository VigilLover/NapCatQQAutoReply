import uuid


MEMORY_ROOT = "qq_mention_memories"


def qq_memory_key(qq_id: int) -> str:
    return f"qq:{qq_id}"


class QQMemoryService:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def namespace(qq_id: int) -> tuple[str, str]:
        return (MEMORY_ROOT, qq_memory_key(qq_id))

    async def manage(
        self,
        *,
        actor_qq_id: int,
        target_qq_id: int,
        action: str = "create",
        content: str | None = None,
        memory_id: str | None = None,
    ) -> str:
        if actor_qq_id != target_qq_id:
            return "只能管理你自己的长期记忆。"
        namespace = self.namespace(actor_qq_id)
        if action == "create":
            normalized = (content or "").strip()
            if not normalized:
                return "要记住的内容不能为空。"
            await self.store.aput(namespace, str(uuid.uuid4()), {"content": normalized})
            return "已记住。"
        if action == "update":
            normalized = (content or "").strip()
            if not memory_id or not normalized:
                return "更新记忆需要 memory_id 和非空内容。"
            await self.store.aput(namespace, memory_id, {"content": normalized})
            return "已更新记忆。"
        if action == "delete":
            if not memory_id:
                return "删除记忆需要 memory_id。"
            await self.store.adelete(namespace, memory_id)
            return "已忘记。"
        return "无效的记忆操作。"

    async def search(self, qq_id: int, query: str | None = None, limit: int = 5) -> str:
        items = await self.store.asearch(
            self.namespace(qq_id),
            query=(query or "").strip() or None,
            limit=max(1, min(limit, 20)),
        )
        contents = [str(item.value.get("content", "")).strip() for item in items]
        contents = [content for content in contents if content]
        return "\n".join(f"- {content}" for content in contents) or "无相关长期记忆"


async def open_postgres_memory_store(conn_string: str, embedder, dims: int):
    from langgraph.store.postgres.aio import AsyncPostgresStore

    context = AsyncPostgresStore.from_conn_string(
        conn_string,
        index={"dims": dims, "embed": embedder, "fields": ["content"]},
    )
    store = await context.__aenter__()
    await store.setup()
    return context, store
