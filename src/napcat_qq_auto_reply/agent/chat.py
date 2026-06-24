import logging
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from napcat_qq_auto_reply.onebot.models import BotResponse, GroupEvent, QQUser

from .prompts import build_chat_prompt_template, format_recent_context


class ChatState(TypedDict, total=False):
    user: QQUser
    group_id: int
    prompt: str
    recent_events: list[GroupEvent]
    history: list[tuple[str, str, str]]
    quoted_text: str
    attachment_ids: set[str]
    style_context: str
    memory_context: str
    messages: Annotated[list[AnyMessage], add_messages]


def parse_model_content(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text") is not None:
                parts.append(str(item["text"]))
            elif getattr(item, "text", None) is not None:
                parts.append(str(item.text))
        return "".join(parts).strip()
    return str(content).strip()


class QQChatAgent:
    def __init__(
        self,
        *,
        llm,
        persona: str,
        style_repository,
        memory,
        tool_runtime,
        external_tools: list,
        message_search_tool=None,
    ):
        self.persona = persona
        self.style_repository = style_repository
        self.memory = memory
        self.tool_runtime = tool_runtime
        self.tools = tool_runtime.langchain_tools() + list(external_tools)
        if message_search_tool is not None:
            self.tools.append(message_search_tool)
        self.llm = llm.bind_tools(self.tools)
        self.prompt = build_chat_prompt_template(
            persona,
            image_generation_enabled=tool_runtime.image_generation_enabled,
        )
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(ChatState)
        workflow.add_node("retrieve", self._retrieve)
        workflow.add_node("prepare", self._prepare)
        workflow.add_node("model", self._call_model)
        workflow.add_node("tools", ToolNode(self.tools, handle_tool_errors=True))
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "prepare")
        workflow.add_edge("prepare", "model")
        workflow.add_conditional_edges(
            "model", tools_condition, {"tools": "tools", END: END}
        )
        workflow.add_edge("tools", "model")
        return workflow.compile()

    async def _retrieve(self, state: ChatState) -> ChatState:
        try:
            matches = await self.style_repository.search(
                self.persona, state["prompt"], top_k=8
            )
            style_context = "\n".join(match.text for match in matches)
        except Exception:
            logging.exception("Style retrieval failed; continuing without style context")
            style_context = ""
        try:
            memory_context = await self.memory.search(
                state["user"].qq_id, state["prompt"], 5
            )
        except Exception:
            logging.exception("Memory retrieval failed; continuing without memory")
            memory_context = "无相关长期记忆"
        return {"style_context": style_context, "memory_context": memory_context}

    async def _prepare(self, state: ChatState) -> ChatState:
        attachment_ids = sorted(state.get("attachment_ids", set()))

        # 将对话历史元组转换为 LangChain 消息格式
        chat_history_messages: list[AnyMessage] = []
        for user_name, question, answer in state["history"]:
            chat_history_messages.extend([
                HumanMessage(content=f"[{user_name}]: {question}"),
                AIMessage(content=answer),
            ])

        current_message = HumanMessage(
            content=(
                f"当前用户：{state['user'].display_name}({state['user'].qq_id})\n"
                f"引用消息：{state.get('quoted_text') or '无'}\n"
                f"当前发言：{state['prompt']}"
            )
        )

        prompt_value = self.prompt.invoke({
            "group_id": state.get("group_id", 0),
            "user_id": state["user"].qq_id,
            "display_name": state["user"].display_name,
            "recent_msgs": format_recent_context(state["recent_events"]),
            "long_term_memory": state.get("memory_context", "无相关长期记忆"),
            "style_context": state.get("style_context") or "无",
            "attachment_ids": ", ".join(attachment_ids) or "无",
            "chat_history": chat_history_messages,
            "messages": [current_message],
        })
        return {"messages": prompt_value.to_messages()}

    async def _call_model(self, state: ChatState) -> ChatState:
        return {"messages": [await self.llm.ainvoke(state["messages"])]}

    async def respond(
        self,
        *,
        group_id: int,
        user: QQUser,
        prompt: str,
        recent_events: list[GroupEvent],
        history: list[tuple[str, str, str]],
        quoted_text: str = "",
        attachment_ids: set[str] | None = None,
    ) -> BotResponse:
        token = self.tool_runtime.begin_request(user.qq_id, attachment_ids or set())
        try:
            state: ChatState = {
                "user": user,
                "group_id": group_id,
                "prompt": prompt,
                "recent_events": recent_events,
                "history": history,
                "quoted_text": quoted_text,
                "attachment_ids": attachment_ids or set(),
            }
            result = await self.graph.ainvoke(state, config={"recursion_limit": 16})
            final_message = result["messages"][-1]
            text = parse_model_content(getattr(final_message, "content", final_message))
            if not text:
                text = "抱歉，我暂时没有生成有效回复，请稍后再试。"
            return BotResponse(text=text, attachments=self.tool_runtime.current_attachments())
        finally:
            self.tool_runtime.end_request(token)
