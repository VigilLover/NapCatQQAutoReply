from types import SimpleNamespace

import pytest

from napcat_qq_auto_reply.database.memory import QQMemoryService, qq_memory_key
from napcat_qq_auto_reply.database.neo4j_style import Neo4jStyleRepository


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def data(self):
        return self.rows


class FakeSession:
    def __init__(self, driver):
        self.driver = driver

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def run(self, query, **params):
        self.driver.query = query
        self.driver.params = params
        return FakeResult([{"text": "像小狼一样说话", "score": 0.91}])


class FakeDriver:
    def session(self, **kwargs):
        self.session_kwargs = kwargs
        return FakeSession(self)


class FakeEmbedder:
    def embed_query(self, text):
        assert text == "你好"
        return [0.1, 0.2]


@pytest.mark.asyncio
async def test_neo4j_style_query_is_read_only_and_persona_scoped():
    driver = FakeDriver()
    repo = Neo4jStyleRepository(driver=driver, embedder=FakeEmbedder())

    results = await repo.search("wolf_lumine", "你好", top_k=8)

    assert results[0].text == "像小狼一样说话"
    assert driver.params["persona"] == "wolf_lumine"
    assert driver.params["top_k"] == 8
    assert "node.userid = $persona" in driver.query
    assert "sentence_embeddings" in driver.query
    assert driver.session_kwargs["default_access_mode"] == "READ"


class FakeStore:
    def __init__(self):
        self.puts = []

    async def aput(self, namespace, key, value):
        self.puts.append((namespace, key, value))

    async def asearch(self, namespace, **kwargs):
        return [SimpleNamespace(key="m1", value={"content": "用户喜欢咖啡"})]

    async def adelete(self, namespace, key):
        self.deleted = (namespace, key)


@pytest.mark.asyncio
async def test_memory_uses_qq_namespace_and_only_current_user():
    store = FakeStore()
    memory = QQMemoryService(store)
    assert qq_memory_key(12345) == "qq:12345"

    result = await memory.manage(
        actor_qq_id=12345,
        target_qq_id=12345,
        action="create",
        content="用户喜欢咖啡",
    )
    assert result == "已记住。"
    assert store.puts[0][0] == ("qq_mention_memories", "qq:12345")

    denied = await memory.manage(
        actor_qq_id=12345,
        target_qq_id=999,
        action="create",
        content="错误信息",
    )
    assert denied == "只能管理你自己的长期记忆。"


@pytest.mark.asyncio
async def test_memory_search_formats_results():
    result = await QQMemoryService(FakeStore()).search(12345, "咖啡")
    assert "用户喜欢咖啡" in result
    assert "m1" not in result
