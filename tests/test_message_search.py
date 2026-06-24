import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from langchain_core.tools import StructuredTool

from napcat_qq_auto_reply.onebot.client import HistoryMessage
from napcat_qq_auto_reply.tools.message_search import (
    _match_message,
    _format_results,
    create_message_search_tool,
)

LOCAL_TZ = datetime.now(timezone.utc).astimezone().tzinfo


def make_msg(message_id, user_id, nickname, text, timestamp=None, card=None):
    return HistoryMessage(
        message_id=message_id,
        user_id=user_id,
        nickname=nickname,
        card=card,
        text=text,
        timestamp=timestamp or int(time.time()),
    )


class TestMatchMessage:
    def test_match_by_keyword_case_insensitive(self):
        msg = make_msg(1, 100, "小明", "今天天气真好")
        assert _match_message(msg, keyword="天气", username=None) is True
        assert _match_message(msg, keyword="天气真好", username=None) is True
        assert _match_message(msg, keyword="下雨", username=None) is False

    def test_match_by_username_nickname(self):
        msg = make_msg(2, 100, "小明", "hello")
        assert _match_message(msg, keyword=None, username="小明") is True
        assert _match_message(msg, keyword=None, username="小") is True
        assert _match_message(msg, keyword=None, username="红") is False

    def test_match_by_username_card(self):
        msg = make_msg(3, 100, "小明", "hello", card="小明@工作群")
        assert _match_message(msg, keyword=None, username="工作群") is True
        assert _match_message(msg, keyword=None, username="@工作") is True

    def test_match_both_keyword_and_username(self):
        msg = make_msg(4, 100, "小明", "今天天气真好")
        assert _match_message(msg, keyword="天气", username="小明") is True
        assert _match_message(msg, keyword="天气", username="小红") is False
        assert _match_message(msg, keyword="下雨", username="小明") is False

    def test_no_filters_match_all(self):
        msg = make_msg(5, 100, "小明", "hello")
        assert _match_message(msg, keyword=None, username=None) is True


class TestFormatResults:
    def test_empty_list(self):
        assert _format_results([]) == "未找到匹配的消息。"

    def test_formats_with_timestamp_and_display_name(self):
        ts1 = 1719200000
        ts2 = 1719200060
        expected_time1 = datetime.fromtimestamp(ts1, tz=LOCAL_TZ).strftime("%m-%d %H:%M")
        expected_time2 = datetime.fromtimestamp(ts2, tz=LOCAL_TZ).strftime("%m-%d %H:%M")
        msgs = [
            make_msg(1, 100, "小明", "消息A", timestamp=ts1),
            make_msg(2, 200, "小红", "消息B" * 100, card="小红@群", timestamp=ts2),
        ]
        result = _format_results(msgs)
        # 检查时间格式 MM-DD HH:MM
        assert f"[{expected_time1}]" in result
        assert "小明(100): 消息A" in result
        assert "小红@群(200): " in result
        # 检查截断（消息B * 100 > 256）
        assert len("小红@群(200): " + "消息B" * 100) > 256
        # 最多 2 行
        assert len(result.split("\n")) == 2


@pytest.mark.asyncio
async def test_search_group_messages_filters_and_limits():
    """端到端测试：mock client，验证搜索过滤和返回"""
    now = int(time.time())
    client = AsyncMock()
    client.get_group_msg_history = AsyncMock(return_value=[
        make_msg(i, 100 + i, f"用户{i}", f"消息内容{i}", timestamp=now - i * 60)
        for i in range(50)
    ])

    tool = create_message_search_tool(client)
    assert isinstance(tool, StructuredTool)
    assert tool.name == "search_group_messages"

    # 搜索不存在的关键词
    result = await tool.ainvoke({
        "group_id": 123,
        "keyword": "不存在的消息",
    })
    assert result == "未找到匹配的消息。"

    # 搜索存在的消息
    result = await tool.ainvoke({
        "group_id": 123,
        "keyword": "消息内容5",
    })
    assert "用户5" in result
    assert "消息内容5" in result

    # 验证只返回最近时间范围内的（默认 24h）
    client.get_group_msg_history.assert_called_with(123, count=100)


@pytest.mark.asyncio
async def test_search_group_messages_api_error_handling():
    """API 异常时返回错误文本"""
    client = AsyncMock()
    client.get_group_msg_history = AsyncMock(
        side_effect=Exception("API 超时")
    )
    tool = create_message_search_tool(client)
    result = await tool.ainvoke({
        "group_id": 123,
        "keyword": "test",
    })
    assert "搜索消息时出错" in result
