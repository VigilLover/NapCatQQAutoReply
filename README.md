# NapCat QQ Auto Reply

一个完全独立的 QQ 群自动回复机器人。它通过 NapCat 的 OneBot 11 WebSocket
接收和发送消息，使用 DeepSeek、Neo4j 人格语料、独立 Postgres 长期记忆、MCP、
联网搜索和图片生成服务。

该项目不会导入原自动回复程序，也不包含原社区的登录、帖子查询、发帖或图片上传逻辑。

## 功能

- 仅处理 `QQ_GROUP_ALLOWLIST` 中的群；忽略私聊和机器人自身消息。
- 由 `@机器人` 或 `BOT_TRIGGER_WORDS` 中的人格关键词触发。
- 每群保留最近 20 条消息和 8 轮对话，进程重启后清空。
- 使用现有 Neo4j `sentence_embeddings` 索引读取人格语料，运行时只读。
- QQ 长期记忆保存到独立 Postgres，用户只能管理自己的记忆。
- 自动加载联网搜索；配置 `MCP_SERVER_URL` 后自动加载同一 MCP 服务的工具。
- 图片生成结果保存到 `data/generated_images/`，通过 OneBot 本地文件消息发送。
- 支持 `【帮助】`、`【清除历史】`、`【投掷】ndm`、`【rua】`。

## 环境要求

- Python 3.12+
- NapCat 已登录 QQ，并启用 OneBot 11 WebSocket 服务
- Neo4j 中已存在 `sentence_embeddings` 向量索引和 `Sentence` 人格语料
- 独立的 PostgreSQL 数据库，并允许安装/使用 pgvector
- NapCat 与本程序能访问相同的 `data/generated_images/` 绝对路径

## 安装

推荐使用 `uv`：

```bash
uv sync --extra dev
cp .env.example .env
```

编辑 `.env`：

- `NAPCAT_WS_URL` 指向 NapCat WebSocket 服务。
- NapCat 的 Access Token 与 `NAPCAT_ACCESS_TOKEN` 保持一致。
- `QQ_GROUP_ALLOWLIST` 使用逗号分隔群号。
- `NEO4J_DB_AUTH` 格式为 `用户名:密码`。
- `QQ_POSTGRES_DB_URI` 必须指向 QQ bot 专用数据库。
- `EMBEDDING_MODEL_NAME` 和 `EMBEDDING_DIMS` 必须与现有 Neo4j 数据一致。

启动：

```bash
uv run napcat-qq-bot
```

## NapCat 消息配置

在 NapCat 中启用 OneBot 11 WebSocket 服务端，建议仅监听 `127.0.0.1`，并设置强
Access Token。默认示例地址是 `ws://127.0.0.1:3001`。程序作为 WebSocket 客户端
连接，无需开放额外 HTTP 端口。

## 数据边界

- Neo4j：只执行向量检索，按 `Sentence.userid = BOT_PERSONA` 过滤。
- Postgres：命名空间为 `qq_mention_memories/qq:<QQ号>`。
- 入站参考图：保存在 `data/inbound_images/`，启动时清理超过 24 小时的文件。
- 生成图：保存在 `data/generated_images/`，不会上传到其他社区。
- `【清除历史】` 只清除当前群内存对话，不删除长期记忆。

## 测试

```bash
uv run pytest -q
uv run ruff check .
```

真实环境冒烟顺序：普通文本、引用回复、生图、带参考图编辑、长期记忆、联网搜索、
MCP 工具、断开并恢复 NapCat WebSocket。
