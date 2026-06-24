import asyncio
import logging
from collections.abc import Iterator

from napcat_qq_auto_reply.agent.chat import QQChatAgent
from napcat_qq_auto_reply.agent.deepseek import build_deepseek_llm
from napcat_qq_auto_reply.agent.runtime import AgentToolRuntime
from napcat_qq_auto_reply.bot.commands import CommandHandler
from napcat_qq_auto_reply.bot.context import ContextStore
from napcat_qq_auto_reply.bot.dispatcher import BotDispatcher
from napcat_qq_auto_reply.bot.routing import MessageRouter
from napcat_qq_auto_reply.config import AppConfig
from napcat_qq_auto_reply.database.memory import (
    QQMemoryService,
    open_postgres_memory_store,
)
from napcat_qq_auto_reply.database.neo4j_style import create_neo4j_style_repository
from napcat_qq_auto_reply.embeddings import LocalTextEmbeddings
from napcat_qq_auto_reply.onebot.client import OneBotClient
from napcat_qq_auto_reply.onebot.path_mapping import ContainerPathMapper
from napcat_qq_auto_reply.tools.attachments import AttachmentStore, download_http_image
from napcat_qq_auto_reply.tools.external import load_external_tools
from napcat_qq_auto_reply.tools.image_generation import ImageGenerationService
from napcat_qq_auto_reply.tools.openai_images import OpenAIImageGenerator


def reconnect_delays() -> Iterator[int]:
    delay = 1
    while True:
        yield delay
        delay = min(30, delay * 2)


async def run_bot(config: AppConfig) -> None:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    embeddings = LocalTextEmbeddings(
        config.embedding_model, cache_folder=config.embedding_cache_folder
    )
    style_repository = create_neo4j_style_repository(
        config.neo4j_url, config.neo4j_auth, embeddings
    )
    postgres_context, postgres_store = await open_postgres_memory_store(
        config.postgres_uri, embeddings, config.embedding_dims
    )
    memory = QQMemoryService(postgres_store)

    attachment_store = AttachmentStore(
        config.data_dir / "inbound_images", downloader=download_http_image
    )
    removed = attachment_store.cleanup(86400)
    if removed:
        logging.info("Removed %d expired inbound image(s)", removed)
    image_generator = OpenAIImageGenerator(
        config.image_api_url,
        config.image_api_key,
        config.image_model,
    )
    images = ImageGenerationService(
        config.data_dir / "generated_images", attachment_store, image_generator
    )
    tool_runtime = AgentToolRuntime(memory, images)
    external_tools = await load_external_tools(config.mcp_server_url)
    agent = QQChatAgent(
        llm=build_deepseek_llm(config),
        persona=config.persona,
        style_repository=style_repository,
        memory=memory,
        tool_runtime=tool_runtime,
        external_tools=external_tools,
    )
    context = ContextStore(recent_limit=20, history_turn_limit=8)
    commands = CommandHandler(context, config.data_dir)
    router = MessageRouter(set(config.allowed_groups), set(config.trigger_words))
    path_mapper = None
    if config.container_generated_image_dir:
        path_mapper = ContainerPathMapper(
            config.data_dir / "generated_images",
            config.container_generated_image_dir,
        )
    client = OneBotClient(
        config.napcat_ws_url,
        config.napcat_access_token,
        path_mapper=path_mapper,
    )
    dispatcher = None

    try:
        delays = reconnect_delays()
        while True:
            try:
                await client.connect()
                login = await client.get_login_info()
                bot_id = int(login["user_id"])
                if dispatcher is None or dispatcher.bot_id != bot_id:
                    dispatcher = BotDispatcher(
                        client=client,
                        bot_id=bot_id,
                        router=router,
                        context=context,
                        commands=commands,
                        agent=agent,
                        attachment_store=attachment_store,
                        max_parallel_groups=config.max_parallel_groups,
                    )
                logging.info("Connected to NapCat as QQ %s", bot_id)
                delays = reconnect_delays()
                await client.listen(dispatcher.handle_payload)
                raise ConnectionError("NapCat WebSocket closed")
            except asyncio.CancelledError:
                raise
            except Exception:
                delay = next(delays)
                logging.exception("NapCat connection failed; retrying in %ds", delay)
                await client.close()
                await asyncio.sleep(delay)
    finally:
        await client.close()
        await style_repository.close()
        await postgres_context.__aexit__(None, None, None)
