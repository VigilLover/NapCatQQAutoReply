# NapCat QQ Auto Reply

一个独立的 QQ 群自动回复机器人：NapCat 运行在本机 Docker 容器中，Python bot、
Neo4j、Postgres 和 MCP 继续运行在 macOS 宿主机。项目不会导入或调用原社区自动回复
程序，也不包含其登录、帖子查询、发帖或图片上传逻辑。

```text
QQ群 ↔ NapCat（Docker）↔ OneBot WebSocket 127.0.0.1:3001
                              ↕
                      Python bot（宿主机）
                              ↕
             DeepSeek / Neo4j / Postgres / MCP / 图片 API
```

## 主要功能

- 仅处理 `QQ_GROUP_ALLOWLIST` 中的群，忽略私聊和机器人自身消息。
- 由 `@机器人` 或 `BOT_TRIGGER_WORDS` 中的人格关键词触发。
- 每群保留最近 20 条消息和 8 轮对话；短期上下文在 bot 重启后清空。
- 从 Neo4j `sentence_embeddings` 索引只读检索人格语料。
- QQ 长期记忆保存在独立 Postgres，用户只能管理自己的记忆。
- 支持联网搜索、MCP 工具、图片生成和参考图编辑。
- 支持 `【帮助】`、`【清除历史】`、`【投掷】ndm`、`【rua】`。

## 部署前准备

需要：

- macOS 与已启动的 Docker Desktop。
- Python 3.12+ 和 [uv](https://docs.astral.sh/uv/)。
- 已建立 `sentence_embeddings` 索引和 `Sentence` 人格语料的 Neo4j。
- 支持 pgvector 的独立 PostgreSQL 数据库。
- 可用的 DeepSeek 和图片生成 API。
- 可选的 MCP SSE 服务。

Docker Desktop 必须允许共享项目所在的 `/Users` 目录。开始前请停止原生 NapCat，
避免 3001/6099 端口冲突和同一 QQ 重复登录。

## 快速部署

以下命令均在项目根目录执行。

### 1. 安装 Python 依赖

```bash
uv sync
```

### 2. 创建本地配置

```bash
cp .env.example .env
```

编辑 `.env`，至少替换所有示例 Token、API Key、群号和数据库连接。不要提交 `.env`。

NapCat 相关配置：

| 变量 | 说明 | 建议值 |
| --- | --- | --- |
| `NAPCAT_WS_URL` | 宿主 bot 连接的 OneBot WebSocket | `ws://127.0.0.1:3001` |
| `NAPCAT_ACCESS_TOKEN` | OneBot WebSocket Token | 独立强随机值 |
| `NAPCAT_WEBUI_TOKEN` | WebUI 登录 Token，必须与 OneBot Token 不同 | 另一独立强随机值 |
| `NAPCAT_ACCOUNT` | 可选 QQ 号；首次扫码登录可留空 | 空或机器人 QQ 号 |
| `NAPCAT_CONTAINER_GENERATED_IMAGE_DIR` | NapCat 容器内生成图目录 | `/shared/generated_images` |

Bot 与外部服务配置：

| 变量 | 说明 |
| --- | --- |
| `QQ_GROUP_ALLOWLIST` | 允许回复的群号，多个群用英文逗号分隔 |
| `BOT_PERSONA` / `BOT_TRIGGER_WORDS` | 人格语料 ID 与群内触发词 |
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `NEO4J_DB_URL` / `NEO4J_DB_AUTH` | Neo4j 地址及 `用户名:密码` |
| `EMBEDDING_MODEL_NAME` / `EMBEDDING_DIMS` | 必须与 Neo4j 现有向量数据一致 |
| `QQ_POSTGRES_DB_URI` | QQ bot 专用 Postgres 数据库连接 |
| `IMAGE_GEN_API_URL` / `IMAGE_GEN_API_KEY` | 图片生成 API 地址和密钥 |
| `MCP_SERVER_URL` | 可选 MCP SSE 地址；不使用时留空 |

因为 Python bot 运行在宿主机，宿主机上的 Neo4j、Postgres 和 MCP 通常继续使用
`127.0.0.1` 地址，不要改成 Compose 服务名。

### 3. 启动 NapCat 容器

```bash
scripts/napcat.sh start
```

该命令会：

1. 从 `.env` 生成 `onebot11.json` 和 `webui.json`，权限设为 `0600`。
2. 创建 NapCat 配置、QQ 登录数据和生成图片目录。
3. 注入当前 macOS 用户的 UID/GID。
4. 使用 `mlikiowa/napcat-docker:latest` 启动容器。

普通 `start` 和 `restart` 不主动拉取镜像；只有 `update` 会拉取最新镜像。

### 4. 首次登录 QQ

打开 [http://127.0.0.1:6099/webui](http://127.0.0.1:6099/webui)，使用
`NAPCAT_WEBUI_TOKEN` 登录并完成 QQ 扫码。QQ 登录状态会保存在
`deploy/napcat/runtime/qq`，容器重启后无需重复扫码。

查看 NapCat 状态和日志：

```bash
scripts/napcat.sh status
scripts/napcat.sh logs
```

### 5. 启动 Python bot

另开一个终端，在项目根目录执行：

```bash
uv run napcat-qq-bot
```

日志出现 `Connected to NapCat as QQ ...` 表示 OneBot WebSocket 已连接。随后在白名单群中
`@机器人` 或发送人格触发词进行测试。

### 6. 验证功能

建议依次验证：

1. `@机器人 你好`：文本回复。
2. `@机器人 【帮助】`：命令路由。
3. 请求生成图片：确认文字和图片均能发送。
4. 引用一张群图片并要求修改：确认参考图编辑可用。
5. 明确要求记住一项偏好，再在后续对话中查询。
6. 触发联网搜索和 MCP 工具。

## 常用运维命令

| 命令 | 行为 |
| --- | --- |
| `scripts/napcat.sh start` | 生成配置并启动 NapCat，使用本地已有镜像 |
| `scripts/napcat.sh stop` | 停止容器，保留配置和 QQ 登录数据 |
| `scripts/napcat.sh restart` | 重新生成配置并重建容器，不拉取镜像 |
| `scripts/napcat.sh logs` | 持续查看 NapCat 日志，按 `Ctrl-C` 退出 |
| `scripts/napcat.sh status` | 查看容器状态 |
| `scripts/napcat.sh update` | 拉取 `latest` 并重建容器 |

升级后应重新执行文本、图片、引用图和 WebSocket 重连测试。

## 数据与安全边界

- OneBot 3001 和 WebUI 6099 均只绑定 `127.0.0.1`，不会暴露给局域网。
- `NAPCAT_ACCESS_TOKEN` 与 `NAPCAT_WEBUI_TOKEN` 必须非空且不同。
- `deploy/napcat/runtime/config` 保存 NapCat 配置，包含 Token。
- `deploy/napcat/runtime/qq` 保存 QQ 登录数据。
- 上述 runtime 目录与 `.env` 均被 Git 忽略。
- `data/generated_images` 只读挂载到容器 `/shared/generated_images`。
- bot 会将宿主图片路径改写成容器路径，并拒绝目录越界或符号链接逃逸。
- 入站参考图保存在 `data/inbound_images`，启动时清理超过 24 小时的缓存。
- Neo4j 仅用于人格向量检索；QQ 长期记忆使用独立 Postgres 命名空间。

官方镜像、架构和卷目录说明见
[NapCat-Docker](https://github.com/NapNeko/NapCat-Docker)。镜像支持
`linux/amd64` 和 `linux/arm64`，Docker Desktop 会自动选择本机架构。

## 故障排查

### bot 无法连接 NapCat

```bash
scripts/napcat.sh status
scripts/napcat.sh logs
lsof -nP -iTCP:3001 -sTCP:LISTEN
```

确认容器已启动、3001 未被原生 NapCat 占用，并检查 `.env` 中的
`NAPCAT_WS_URL`。修改 Token 后执行 `scripts/napcat.sh restart`，让自动生成的配置生效。

### WebUI 无法打开

确认 Docker Desktop 正在运行，并检查 6099 端口：

```bash
lsof -nP -iTCP:6099 -sTCP:LISTEN
scripts/napcat.sh logs
```

WebUI 仅能从本机通过 `http://127.0.0.1:6099/webui` 访问。

### 文本正常但图片发送失败

确认 `.env` 中：

```dotenv
NAPCAT_CONTAINER_GENERATED_IMAGE_DIR=/shared/generated_images
```

检查生成图是否同时能被宿主和容器读取：

```bash
ls -la data/generated_images
docker exec napcat ls -la /shared/generated_images
```

如果项目不在 `/Users` 下，请在 Docker Desktop 中显式允许共享项目所在目录。

### 修改 `.env` 后没有生效

执行：

```bash
scripts/napcat.sh restart
```

该命令会重新生成 NapCat 配置并重建容器。仅重启 Python bot 不会更新容器内配置。

## 迁移与回滚

从原生 NapCat 迁移前先退出原进程，再启动容器。`scripts/napcat.sh stop` 或以下命令
都不会删除 bind mount 中的配置和 QQ 登录数据：

```bash
docker compose --env-file .env -f deploy/napcat/compose.yml down
```

如需恢复原生 NapCat：

1. 执行 `scripts/napcat.sh stop`。
2. 将 `.env` 中 `NAPCAT_CONTAINER_GENERATED_IMAGE_DIR` 留空。
3. 启动原生 NapCat，并保持 `NAPCAT_WS_URL` 和 OneBot Token 与其配置一致。
4. 重启 Python bot。

## 开发与测试

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check .
uv run python -m compileall -q src scripts
bash -n scripts/napcat.sh
docker compose --env-file .env.example -f deploy/napcat/compose.yml config --quiet
```

自动测试覆盖 OneBot 消息解析、群路由、上下文、数据库隔离、图片附件、容器路径映射、
NapCat 配置生成和 Compose 部署边界。
