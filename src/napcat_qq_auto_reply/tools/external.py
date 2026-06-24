import logging


async def _default_mcp_loader(url):
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {
            "default": {
                "transport": "sse",
                "url": url,
                "sse_read_timeout": 900,
            }
        }
    )
    return await client.get_tools()


def _default_search_factory():
    from langchain_community.tools import DuckDuckGoSearchResults

    return DuckDuckGoSearchResults(
        name="internet_search",
        description="Search the internet for current information.",
    )


async def load_external_tools(
    mcp_url,
    search_factory=None,
    mcp_loader=None,
):
    search_factory = search_factory or _default_search_factory
    mcp_loader = mcp_loader or _default_mcp_loader
    tools = [search_factory()]
    if not mcp_url:
        return tools
    try:
        tools.extend(await mcp_loader(mcp_url))
    except Exception:
        logging.exception("MCP server is unavailable; continuing without MCP tools")
    return tools
