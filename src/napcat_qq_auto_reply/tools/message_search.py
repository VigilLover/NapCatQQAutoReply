import logging
import time
from datetime import datetime, timezone

from langchain_core.tools import StructuredTool

from napcat_qq_auto_reply.onebot.client import HistoryMessage, OneBotClient

LOCAL_TZ = datetime.now(timezone.utc).astimezone().tzinfo


def _match_message(
    msg: HistoryMessage,
    keyword: str | None,
    username: str | None,
) -> bool:
    """检查单条消息是否匹配所有筛选条件（AND 逻辑，大小写不敏感）"""
    if keyword and keyword.lower() not in msg.text.lower():
        return False
    if username and username.lower() not in msg.display_name.lower():
        return False
    return True


def _format_results(messages: list[HistoryMessage]) -> str:
    """将匹配的消息格式化为 LLM 可读的文本"""
    if not messages:
        return "未找到匹配的消息。"
    lines: list[str] = []
    for m in messages:
        dt = datetime.fromtimestamp(m.timestamp, tz=LOCAL_TZ)
        time_str = dt.strftime("%m-%d %H:%M")
        text = m.text[:256] if m.text else "[无文本]"
        lines.append(f"[{time_str}] {m.display_name}({m.user_id}): {text}")
    return "\n".join(lines)


def create_message_search_tool(client: OneBotClient) -> StructuredTool:
    """创建群聊消息搜索工具

    工具参数：
    - group_id (int, 必填): 群号
    - keyword (str, 可选): 按内容关键词搜索
    - username (str, 可选): 按发送者昵称搜索
    - hours_ago (int, 可选, 默认24): 往前搜索多少小时
    """

    async def search_group_messages(
        group_id: int,
        keyword: str | None = None,
        username: str | None = None,
        hours_ago: int = 24,
    ) -> str:
        try:
            messages = await client.get_group_msg_history(group_id, count=100)
        except Exception as exc:
            logging.exception("Failed to fetch group message history")
            return f"搜索消息时出错：{exc}"

        cutoff = time.time() - hours_ago * 3600
        recent = [m for m in messages if m.timestamp >= cutoff]
        matched = [
            m for m in recent
            if _match_message(m, keyword, username)
        ]
        return _format_results(matched[:20])

    return StructuredTool.from_function(
        coroutine=search_group_messages,
        name="search_group_messages",
        description=(
            "搜索当前群聊的历史消息。可按关键词(keyword)搜索消息内容、"
            "按发送者昵称(username)搜索、按时间范围(hours_ago，默认24小时)筛选。"
            "返回匹配的消息列表，每条包含时间、发送者昵称/QQ号和消息内容。"
            "用于了解群里最近聊了什么、某个人之前说过什么、或回顾历史消息。"
        ),
    )
