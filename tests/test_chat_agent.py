import asyncio
from pathlib import Path

from langchain_core.messages import AIMessage

from napcat_qq_auto_reply.agent.chat import QQChatAgent, parse_model_content
from napcat_qq_auto_reply.agent.runtime import AgentToolRuntime
from napcat_qq_auto_reply.onebot.models import GroupEvent, LocalImage, QQUser


class FakeBoundModel:
    def __init__(self):
        self.invocations = []

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    async def ainvoke(self, messages):
        self.invocations.append(messages)
        return AIMessage(content="  小狼回复  ")


class RepeatingToolCallModel:
    def __init__(self):
        self.invocations = 0

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    async def ainvoke(self, messages):
        self.invocations += 1
        return AIMessage(
            content="",
            tool_calls=[{
                "name": "search_qq_memory",
                "args": {"query": "咖啡", "limit": 5},
                "id": f"call_{self.invocations}",
            }],
        )


class FakeStyle:
    async def search(self, persona, query, top_k=8):
        return [type("Match", (), {"text": "语气参考"})()]


class FakeMemory:
    async def search(self, qq_id, query=None, limit=5):
        return "- 用户喜欢咖啡"

    async def manage(self, **kwargs):
        return "ok"


class FakeImages:
    async def generate(self, *args, **kwargs):
        return LocalImage(Path("/tmp/image.jpg"))


def test_parse_model_content_handles_provider_blocks():
    assert parse_model_content("  hello ") == "hello"
    assert parse_model_content([{"text": "你"}, {"text": "好"}]) == "你好"


def test_chat_agent_uses_group_context_and_returns_clean_text():
    async def scenario():
        llm = FakeBoundModel()
        memory = FakeMemory()
        runtime = AgentToolRuntime(memory, FakeImages())
        agent = QQChatAgent(
            llm=llm,
            persona="wolf_lumine",
            style_repository=FakeStyle(),
            memory=memory,
            tool_runtime=runtime,
            external_tools=[],
        )
        recent = [GroupEvent(1, 1, QQUser(2, "路人", None), "刚才在聊咖啡")]
        response = await agent.respond(
            group_id=1,
            user=QQUser(123, "当前用户", None),
            prompt="你喜欢什么？",
            recent_events=recent,
            history=[("某用户", "前一个问题", "前一个回答")],
            quoted_text="被引用的内容",
            attachment_ids={"current-image"},
        )
        assert response.text == "小狼回复"
        rendered = "\n".join(str(message.content) for message in llm.invocations[0])
        assert "刚才在聊咖啡" in rendered
        assert "被引用的内容" in rendered
        assert "用户喜欢咖啡" in rendered
        assert "语气参考" in rendered
        assert "current-image" in rendered

    asyncio.run(scenario())


def test_chat_agent_returns_fallback_when_tool_calls_do_not_converge():
    async def scenario():
        llm = RepeatingToolCallModel()
        memory = FakeMemory()
        runtime = AgentToolRuntime(memory, FakeImages())
        agent = QQChatAgent(
            llm=llm,
            persona="wolf_lumine",
            style_repository=FakeStyle(),
            memory=memory,
            tool_runtime=runtime,
            external_tools=[],
        )

        response = await agent.respond(
            group_id=1,
            user=QQUser(123, "当前用户", None),
            prompt="查一下我的咖啡记忆",
            recent_events=[],
            history=[],
        )

        assert "工具" in response.text
        assert llm.invocations > 1

    asyncio.run(scenario())
