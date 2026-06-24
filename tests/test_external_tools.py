import pytest

from napcat_qq_auto_reply.tools.external import load_external_tools


@pytest.mark.asyncio
async def test_external_tools_include_search_and_mcp():
    search = object()
    mcp_tool = object()

    async def mcp_loader(url):
        assert url == "http://127.0.0.1:8000/sse"
        return [mcp_tool]

    tools = await load_external_tools(
        "http://127.0.0.1:8000/sse",
        search_factory=lambda: search,
        mcp_loader=mcp_loader,
    )
    assert tools == [search, mcp_tool]


@pytest.mark.asyncio
async def test_mcp_failure_keeps_search_available():
    search = object()

    async def failing_loader(url):
        raise OSError("offline")

    tools = await load_external_tools(
        "http://127.0.0.1:8000/sse",
        search_factory=lambda: search,
        mcp_loader=failing_loader,
    )
    assert tools == [search]
