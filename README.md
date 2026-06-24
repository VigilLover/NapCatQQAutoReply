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
- Docker Desktop（仅 NapCat 运行在容器中）
- Neo4j 中已存在 `sentence_embeddings` 向量索引和 `Sentence` 人格语料
- 独立的 PostgreSQL 数据库，并允许安装/使用 pgvector
- Docker Desktop 已允许共享项目所在的 `/Users` 目录

## 安装

推荐使用 `uv`：

```bash
uv sync --extra dev
```

编辑 `.env`：

- `NAPCAT_WS_URL` 指向 NapCat WebSocket 服务。
- `NAPCAT_ACCESS_TOKEN` 与自动生成的 OneBot 配置保持一致。
- `QQ_GROUP_ALLOWLIST` 使用逗号分隔群号。
- `NEO4J_DB_AUTH` 格式为 `用户名:密码`。
- `QQ_POSTGRES_DB_URI` 必须指向 QQ bot 专用数据库。
- `EMBEDDING_MODEL_NAME` 和 `EMBEDDING_DIMS` 必须与现有 Neo4j 数据一致。

## NapCat Docker 部署

复制配置并修改两个不同的强 Token、QQ 群白名单及其他服务连接：

```bash
cp .env.example .env
```

以下变量用于 NapCat：

- `NAPCAT_ACCESS_TOKEN`：OneBot WebSocket Token。
- `NAPCAT_WEBUI_TOKEN`：WebUI Token，必须与 OneBot Token 不同。
- `NAPCAT_ACCOUNT`：可选 QQ 号；留空时通过 WebUI 扫码登录。
- `NAPCAT_CONTAINER_GENERATED_IMAGE_DIR=/shared/generated_images`：容器内生成图目录。

启动 NapCat：

```bash
scripts/napcat.sh start
```

然后打开 <http://127.0.0.1:6099/webui> 完成首次登录。OneBot 端口和 WebUI
端口仅绑定 `127.0.0.1`，不会暴露给局域网。

常用运维命令：

```bash
scripts/napcat.sh status
scripts/napcat.sh logs
scripts/napcat.sh restart
scripts/napcat.sh stop
scripts/napcat.sh update  # 仅此命令主动拉取 latest
```

启动宿主机 Python bot：

```bash
uv run napcat-qq-bot
```

`scripts/napcat.sh start/restart/update` 会从 `.env` 原子生成 NapCat OneBot 与
WebUI 配置。不要设置容器的 `MODE=ws`，否则官方空 Token 模板会覆盖配置。

QQ 登录数据保存在 `deploy/napcat/runtime/qq`，NapCat 配置保存在
`deploy/napcat/runtime/config`；两者均被 Git 忽略。宿主
`data/generated_images` 会以只读方式挂载到容器 `/shared/generated_images`。

官方镜像与卷目录说明见
[NapCat-Docker](https://github.com/NapNeko/NapCat-Docker)。该镜像同时支持
`linux/amd64` 和 `linux/arm64`，Docker Desktop 会自动选择本机架构。

## 迁移与回滚

启动容器前先停止原生 NapCat，避免端口冲突和同一 QQ 重复登录。执行
`scripts/napcat.sh stop` 不会删除登录数据；如需恢复原生 NapCat，停止容器并将
`NAPCAT_CONTAINER_GENERATED_IMAGE_DIR` 留空，bot 会恢复发送宿主 `file://` URI。

## 数据边界

- Neo4j：只执行向量检索，按 `Sentence.userid = BOT_PERSONA` 过滤。
- Postgres：命名空间为 `qq_mention_memories/qq:<QQ号>`。
- 入站参考图：保存在 `data/inbound_images/`，启动时清理超过 24 小时的文件。
- 生成图：保存在 `data/generated_images/`，通过只读挂载交给 NapCat，不会上传到其他社区。
- `【清除历史】` 只清除当前群内存对话，不删除长期记忆。

## 测试

```bash
uv run pytest -q
uv run ruff check .
docker compose --env-file .env -f deploy/napcat/compose.yml config --quiet
bash -n scripts/napcat.sh
```

真实环境冒烟顺序：普通文本、引用回复、生图、带参考图编辑、长期记忆、联网搜索、
MCP 工具、断开并恢复 NapCat WebSocket。
