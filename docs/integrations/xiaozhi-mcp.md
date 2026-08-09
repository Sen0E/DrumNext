# DrumNext MCP 独立服务开发文档

状态：待实现  
适用项目：DrumNext  
目标环境：Python 3.11+、Raspberry Pi OS 64-bit  
最后更新：2026-08-09

## 1. 文档目的

本文档只描述 DrumNext MCP 服务的设计与实现，不包含小智固件开发、设备激活、
音频链路或 MCP 接入点申请流程。

前置条件如下：

- 小智设备已经可以正常联网和语音交互。
- 已经从小智平台取得可用的 MCP WebSocket 接入点。
- DrumNext FastAPI 可以通过现有 `/api/v1/*` 接口控制播放。

本功能是在当前仓库内新增一个独立 MCP 服务。它与现有 `drumnext` 服务分别启动、
分别退出、分别记录日志，双方只通过公开 REST API 通信。MCP 服务不得导入或直接
访问现有服务的内存状态。

## 2. 目标与边界

### 2.1 目标

- 将现有 DrumNext 播放 API 暴露为标准 MCP tools。
- 主动连接配置文件中的小智 MCP 接入点。
- 支持查询状态、查询乐谱、播放、暂停、恢复、停止、跳转和调速。
- 网络断开后自动退避重连。
- DrumNext 后端暂时不可用时返回稳定错误，后端恢复后自动恢复工具调用。
- 所有运行参数集中存放在独立 JSON 配置文件中。
- MCP 服务作为独立进程部署，不进入现有 FastAPI 生命周期。

### 2.2 非目标

- 不修改小智固件。
- 不修改小智服务端。
- 不实现 ASR、LLM、TTS 或音频传输。
- 不修改投影端代码或投影 WebSocket 协议。
- 不在现有 FastAPI 中挂载 MCP HTTP/SSE 路由。
- 不直接调用 `PlaybackService`、`EventHub`、`ScoreStore` 或 `app.state`。
- 不为 MCP 增加现有后端专用接口；第一版只调用已经存在的 REST API。
- 不开放布局、投影视觉设置、文件写入、系统命令、升级或重启工具。
- 不依赖当前仓库之外的脚本、虚拟环境或运行时文件。

## 3. 解耦原则

MCP 服务与现有服务必须满足以下边界：

| 维度 | 约束 |
| --- | --- |
| 代码 | 使用独立 Python 包 `drumnext_mcp`，不得导入 `drumnext` 包 |
| 状态 | MCP 不保存权威播放状态，每次以 REST 响应为准 |
| 进程 | 使用独立命令和独立 systemd unit |
| 生命周期 | 任一服务启动、退出或重启不直接控制另一个服务 |
| 通信 | 只通过现有 `/api/v1/*` HTTP 接口通信 |
| 配置 | 使用独立 `xiaozhi-mcp.json`，不复用 FastAPI Settings 对象 |
| 日志 | MCP 只写自己的 stderr/systemd journal |
| 故障 | MCP 故障不影响投影和手机控制；后端故障不使 MCP 进程退出 |

不得出现以下导入：

```python
from drumnext.main import app
from drumnext.playback.service import PlaybackService
from drumnext.transport.events import EventHub
```

CI 应使用下列检查或等价测试维持代码边界：

```bash
rg -n "^(from|import) drumnext" backend/drumnext_mcp
```

预期没有匹配结果。

## 4. 总体架构

```text
小智 MCP 接入点
        │
        │ MCP JSON-RPC over WSS
        ▼
┌──────────────────────────────────────┐
│ drumnext-mcp 独立服务                │
│                                      │
│ WSS Bridge                           │
│   ↕ MCP JSON-RPC over stdio          │
│ FastMCP Tool Server                  │
│   ↓                                  │
│ Restricted DrumNext REST Client      │
└──────────────────┬───────────────────┘
                   │ HTTP
                   ▼
┌──────────────────────────────────────┐
│ 现有 drumnext FastAPI                │
│ /api/v1/*                            │
└──────────────────┬───────────────────┘
                   │ WebSocket
                   ▼
                投影端
```

`drumnext-mcp` 对用户表现为一个独立服务。服务内部由桥接主进程启动一个 stdio
FastMCP 子进程：

- 桥接主进程负责接入点连接、重连和子进程生命周期。
- FastMCP 子进程负责标准 MCP 握手、工具发现和工具调用。
- 工具通过 HTTP 调用现有 DrumNext API。

采用 stdio 子进程是为了复用标准 MCP Server 实现，同时保持小智 WebSocket
桥接透明。子进程属于 MCP 服务内部实现，不与原有 FastAPI 进程耦合。

## 5. 标准目录结构

实现完成后的 MCP 相关文件使用以下结构。文件按开发阶段创建，不提交空占位文件。

```text
DrumNext/
├── pyproject.toml
├── uv.lock
├── .gitignore
├── config/
│   ├── xiaozhi-mcp.example.json        # 可提交的完整配置模板
│   └── xiaozhi-mcp.json                # 本机真实配置，必须被 Git 忽略
├── docs/
│   └── integrations/
│       └── xiaozhi-mcp.md              # 本文档
├── backend/
│   ├── drumnext/                       # 现有服务，不依赖 MCP
│   ├── drumnext_mcp/                   # 新增的独立 Python 包
│   │   ├── __init__.py
│   │   ├── __main__.py                 # 支持 python -m drumnext_mcp
│   │   ├── api_client.py               # 受限 REST 客户端
│   │   ├── bridge.py                   # WSS/stdin/stdout 桥接与重连
│   │   ├── config.py                   # JSON 配置加载、校验和脱敏
│   │   ├── errors.py                   # 稳定错误码与异常映射
│   │   ├── models.py                   # 独立 DTO，不导入 drumnext 模型
│   │   ├── server.py                   # FastMCP stdio Server
│   │   └── tools.py                    # MCP 工具定义
│   └── tests/
│       └── mcp/
│           ├── test_api_client.py
│           ├── test_bridge.py
│           ├── test_config.py
│           ├── test_protocol.py
│           └── test_tools.py
├── shared/
│   └── fixtures/
│       └── mcp/
│           ├── initialize.json
│           ├── tools-list.json
│           └── tools-call-play.json
└── deploy/
    └── systemd/
        └── drumnext-mcp.service
```

`pyproject.toml` 仍是仓库唯一 Python 项目配置，但必须同时打包两个互不导入的包：

```toml
[tool.hatch.build.targets.wheel]
packages = ["backend/drumnext", "backend/drumnext_mcp"]
```

不建立嵌套 Git 仓库、嵌套虚拟环境或第二份 lock 文件。

## 6. 模块职责

### 6.1 `config.py`

- 从 JSON 文件加载全部 MCP 运行配置。
- 使用 Pydantic 模型校验类型、范围、必填项和未知字段。
- 默认配置路径为项目根目录 `config/xiaozhi-mcp.json`。
- 支持命令行 `--config /absolute/path/config.json` 覆盖路径。
- 提供脱敏后的日志视图，任何情况下不输出完整 endpoint。
- 不读取 endpoint、后端地址或重连参数的环境变量。

### 6.2 `api_client.py`

- 只实现本文列出的固定 API 方法。
- 不提供 `request(method, url)` 之类的通用代理接口给工具层。
- 统一处理连接、超时、HTTP 状态码和响应校验。
- 每次返回现有 API 的最终状态，不建立本地状态缓存。
- 目标 URL 只能来自配置文件，不能来自 MCP tool 参数。

### 6.3 `models.py`

- 独立定义 MCP 所需的 PlaybackSnapshot、ScoreSummary 和工具返回 DTO。
- JSON 字段与现有 REST 响应保持兼容。
- 不从 `drumnext.domain` 导入模型，避免包级耦合。
- 对服务端新增字段采用明确的兼容策略；第一版允许忽略未知响应字段，但必填字段
  缺失必须报错。

### 6.4 `tools.py`

- 定义八个允许暴露的工具。
- 提供适合中文语音模型理解的工具描述。
- 完成秒到毫秒等边界转换。
- 将 REST 错误转换为 MCP tool error。
- 不进行文件、Shell、数据库或进程操作。

### 6.5 `server.py`

- 创建名为 `DrumNext` 的 FastMCP Server。
- 只声明 tools capability。
- 以 stdio transport 运行。
- stdout 只允许 MCP JSON-RPC，应用日志只能写 stderr。
- endpoint 不传给该子进程，缩小凭据暴露范围。

### 6.6 `bridge.py`

- 作为 `drumnext-mcp` 命令入口。
- 加载配置并连接小智 WSS endpoint。
- 使用当前 Python 解释器启动 `python -m drumnext_mcp.server`。
- 双向转发 WebSocket 文本帧和逐行 stdio 消息。
- 转发子进程 stderr 到 MCP 服务日志。
- 处理退出信号、任务取消、子进程清理和退避重连。

## 7. 配置文件规范

### 7.1 文件选择

配置使用 JSON，与当前项目 `config/` 下的配置风格保持一致。

- `config/xiaozhi-mcp.example.json`：完整安全模板，提交 Git。
- `config/xiaozhi-mcp.json`：真实运行配置，加入 `.gitignore`。
- 生产环境也可以使用 `/etc/drumnext/xiaozhi-mcp.json`，通过 `--config` 指定。

除了配置文件路径，运行时不得再要求 endpoint 相关环境变量或命令行参数。这样可以
避免凭据出现在 shell history 和进程列表中。

### 7.2 完整配置示例

```json
{
  "schemaVersion": 1,
  "endpoint": {
    "url": "wss://replace-with-your-xiaozhi-mcp-endpoint",
    "connectTimeoutSeconds": 10,
    "pingIntervalSeconds": 20,
    "pingTimeoutSeconds": 20
  },
  "drumnext": {
    "baseUrl": "http://127.0.0.1:8000",
    "requestTimeoutSeconds": 5
  },
  "reconnect": {
    "initialDelaySeconds": 1,
    "maxDelaySeconds": 60,
    "multiplier": 2,
    "jitterRatio": 0.2,
    "stableResetSeconds": 30
  },
  "limits": {
    "maxMessageBytes": 1048576,
    "maxScoresReturned": 100
  },
  "process": {
    "shutdownGraceSeconds": 5,
    "terminateGraceSeconds": 3
  },
  "logging": {
    "level": "INFO",
    "format": "text"
  }
}
```

### 7.3 字段定义

| 字段 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- |
| `schemaVersion` | 是 | 当前只能为 `1` | 配置格式版本 |
| `endpoint.url` | 是 | `ws://` 或 `wss://` | 小智 MCP 接入点，按凭据处理 |
| `endpoint.connectTimeoutSeconds` | 是 | `1..120` | 建连超时 |
| `endpoint.pingIntervalSeconds` | 是 | `5..300` | WebSocket ping 间隔 |
| `endpoint.pingTimeoutSeconds` | 是 | `5..300` | ping 响应超时 |
| `drumnext.baseUrl` | 是 | HTTP(S) 根地址 | 现有 FastAPI 地址，不包含 `/api/v1` |
| `drumnext.requestTimeoutSeconds` | 是 | `0.1..120` | 单次 REST 请求总超时 |
| `reconnect.initialDelaySeconds` | 是 | `0.1..60` | 第一次重连等待 |
| `reconnect.maxDelaySeconds` | 是 | 不小于 initial | 最大重连等待 |
| `reconnect.multiplier` | 是 | `1..10` | 指数退避倍率 |
| `reconnect.jitterRatio` | 是 | `0..1` | 随机抖动比例 |
| `reconnect.stableResetSeconds` | 是 | `1..3600` | 稳定连接多久后重置失败计数 |
| `limits.maxMessageBytes` | 是 | `1024..16777216` | 单条 MCP 消息上限 |
| `limits.maxScoresReturned` | 是 | `1..1000` | 单次工具最多返回的乐谱数 |
| `process.shutdownGraceSeconds` | 是 | `0.1..60` | 子进程正常退出宽限 |
| `process.terminateGraceSeconds` | 是 | `0.1..60` | terminate 后宽限 |
| `logging.level` | 是 | DEBUG/INFO/WARNING/ERROR | MCP 日志级别 |
| `logging.format` | 是 | text/json | 日志格式 |

所有对象使用 `extra="forbid"`。配置拼写错误必须在启动时明确失败，不能静默忽略。

### 7.4 凭据安全

- `.gitignore` 必须包含精确规则 `/config/xiaozhi-mcp.json`。
- 模板只能包含明显无效的示例 endpoint。
- 真实配置文件建议权限为 `0600`。
- endpoint 日志只显示 `scheme://host/***`，不得显示 path、query 或 token。
- 配置校验异常不得回显完整原始 JSON。
- systemd unit 只传 `--config` 路径，不在 unit 中写 endpoint。

## 8. MCP 工具契约

### 8.1 命名规范

- 工具名只使用小写 ASCII、数字和下划线。
- 使用 `drumnext_` 前缀避免与其他 MCP Server 重名。
- 参数使用 `snake_case`。
- 时间参数对大模型使用秒；调用现有 API 时转换成毫秒。
- 工具描述必须说明副作用、单位和适用状态。

### 8.2 第一版工具

| 工具 | 参数 | REST 调用 | 说明 |
| --- | --- | --- | --- |
| `drumnext_get_status` | 无 | `GET /api/v1/playback` | 查询当前状态 |
| `drumnext_list_scores` | 无 | `GET /api/v1/scores` | 查询乐谱摘要 |
| `drumnext_play` | `score_id?: string` | 见下文 | 播放当前或指定乐谱 |
| `drumnext_pause` | 无 | `POST /api/v1/playback/pause` | 暂停 |
| `drumnext_resume` | 无 | `POST /api/v1/playback/resume` | 恢复 |
| `drumnext_stop` | 无 | `POST /api/v1/playback/stop` | 停止并回到开头 |
| `drumnext_seek` | `position_seconds: float` | `POST /api/v1/playback/seek` | 跳转到绝对秒数 |
| `drumnext_set_speed` | `speed: float` | `POST /api/v1/playback/speed` | 设置播放速度 |

第一版只暴露上述八个工具。增加工具必须先更新本文档和安全审查。

### 8.3 播放指定乐谱

不修改现有 FastAPI，因此 `drumnext_play(score_id="大鱼")` 在 MCP 服务内顺序执行：

1. `GET /api/v1/scores`，把精确标题匹配转换为真实 `id`；ID 本身也可直接使用。
2. `POST /api/v1/playback/score`，请求体为 `{"scoreId":"大鱼"}`。
3. `POST /api/v1/playback/play`。
4. 返回最后一次调用得到的 `PlaybackSnapshot`。

不做拼音、编辑距离或其他模糊匹配。无唯一匹配时返回候选，让模型询问用户。

由于现有 API 没有“切歌并播放”的原子命令，步骤 2 成功而步骤 3 失败时，实际状态
可能是“已切换乐谱但尚未播放”。MCP 错误必须包含步骤 2 返回的最新状态，不能声称
状态完全未改变，也不得自动重复步骤 3。这是保持服务解耦后的已知第一版限制。

未传 `score_id` 时只调用 `POST /api/v1/playback/play`。

### 8.4 参数规则

`score_id`

- 长度 `1..64`。
- 优先匹配乐谱 ID，然后匹配不区分大小写的完整标题。
- 不唯一或不存在时返回 `SCORE_NOT_FOUND` 和有限候选。

`position_seconds`

- 必须大于或等于 0，允许小数。
- 乘以 1000 后作为 `positionMs` 调用 seek API。
- 超过乐谱时长时沿用现有后端的上界收敛行为。

`speed`

- 范围 `0.25..4.0`，与现有 API 保持一致。

### 8.5 成功返回

播放类工具统一返回消息和最终状态：

```json
{
  "message": "已开始播放《大鱼》",
  "playback": {
    "status": "playing",
    "scoreId": "大鱼",
    "durationMs": 168154,
    "positionMs": 0,
    "anchorPositionMs": 0,
    "anchorClockMs": 12500.2,
    "speed": 1.0
  }
}
```

乐谱列表只返回 `id`、`title`、`durationMs` 和 `noteCount`，不返回完整音符数组。

### 8.6 错误模型

可预期错误转换成 MCP tool error，内容使用稳定错误码：

```json
{
  "code": "BACKEND_UNAVAILABLE",
  "message": "DrumNext 服务当前不可用",
  "retryable": true,
  "details": {}
}
```

| 错误码 | 含义 | 可重试 |
| --- | --- | --- |
| `INVALID_ARGUMENT` | 工具参数不合法 | 否 |
| `SCORE_NOT_FOUND` | 乐谱 ID/标题不存在或不唯一 | 否 |
| `BACKEND_UNAVAILABLE` | 连接失败或超时 | 是，但写命令不可盲目重放 |
| `BACKEND_REJECTED` | REST 返回 4xx | 视错误而定 |
| `BACKEND_FAILURE` | REST 返回 5xx 或无效 JSON | 是 |
| `PROTOCOL_ERROR` | MCP 消息或 stdio 输出无效 | 否，当前会话重建 |

不得把 HTML 错误页、Python 堆栈、文件路径或 endpoint 返回给小智服务。

## 9. 桥接协议与生命周期

### 9.1 消息转发

- 每个 WebSocket 文本帧视为一条 MCP JSON-RPC 消息。
- WSS → stdio：严格 UTF-8 文本后追加一个换行符并 flush。
- stdio → WSS：stdout 每一行发送为一个文本帧，仅去除行末换行。
- 不修改 JSON-RPC `id`、方法、参数或响应。
- 不添加 ESP32 设备协议的 `type: "mcp"` 外层。
- 二进制帧仅在严格 UTF-8 解码成功时接受，否则关闭当前会话。
- 帧大小超过 `limits.maxMessageBytes` 时关闭当前会话。
- stdout 出现非 JSON 内容视为协议污染，终止子进程并重连。

### 9.2 单次会话生命周期

1. 加载并校验配置。
2. 建立小智 WSS 连接。
3. 连接成功后启动新的 FastMCP stdio 子进程。
4. 并发运行 WSS→stdin、stdout→WSS、stderr→日志三个任务。
5. 任一协议方向结束时取消其余转发任务。
6. 先关闭 stdin，等待 `shutdownGraceSeconds`。
7. 未退出则 terminate，再等待 `terminateGraceSeconds`。
8. 仍未退出才 kill，并正确回收子进程。
9. 关闭 WebSocket，按配置退避后重新建立全新会话。

每次 WSS 重连必须创建新的 MCP 子进程，不能复用上一会话的初始化状态。

### 9.3 重连规则

- 使用配置中的 initial、max、multiplier 和 jitter。
- DNS、TCP、TLS、服务端 5xx 和异常断开可以重试。
- 配置缺失、JSON 无效、schemaVersion 不支持等问题立即退出。
- 明确认证失败可以继续低频重试，但不得在日志中输出 endpoint。
- 稳定连接达到 `stableResetSeconds` 后重置失败计数。
- 等待使用可取消的异步定时器，不使用阻塞 sleep。
- 连接断开后不得缓存和自动重放未完成的 `tools/call`。

## 10. 依赖与启动方式

### 10.1 依赖

预计增加以下运行时依赖，并在实现时锁定到 `pyproject.toml` 与 `uv.lock`：

- MCP/FastMCP：stdio MCP Server。
- `websockets`：小智 WSS 连接。
- `httpx`：调用现有 DrumNext API；需要从 dev 依赖移入运行时依赖。

不使用全局 pip 包，不在 `backend/drumnext_mcp` 内创建第二个虚拟环境。

### 10.2 命令入口

`pyproject.toml` 增加：

```toml
[project.scripts]
drumnext = "drumnext.main:run"
drumnext-mcp = "drumnext_mcp.bridge:run"
```

默认启动：

```bash
uv run drumnext-mcp
```

指定其他配置文件：

```bash
uv run drumnext-mcp --config /etc/drumnext/xiaozhi-mcp.json
```

原有服务仍独立启动：

```bash
uv run drumnext
```

两条命令不存在父子关系。启动 MCP 不应自动启动 FastAPI，启动 FastAPI 也不应自动
启动 MCP。

## 11. 日志与安全

### 11.1 应记录

- MCP 服务启动、配置文件路径和配置版本。
- WSS 连接成功、关闭类型、重连次数和等待秒数。
- MCP 子进程启动、退出码、terminate 和 kill。
- 工具名、耗时、成功或稳定错误码。
- 固定 REST 方法、固定路径、状态码和耗时。

### 11.2 禁止记录

- 完整 endpoint。
- WebSocket 原始消息正文。
- 配置文件原文。
- 环境变量全集。
- HTTP 响应中的堆栈或 HTML 正文。

### 11.3 最小权限

- MCP 工具参数不能控制 URL、HTTP 方法、请求头或文件路径。
- API client 只允许请求本文列出的路径。
- 不执行模型提供的 Shell、Python、表达式或模板。
- MCP 服务使用独立低权限系统用户运行。
- `xiaozhi-mcp.json` 权限为 `0600`。

## 12. 可靠性规则

- MCP 服务不缓存播放状态；查询和写操作都以 REST 最终响应为准。
- FastAPI 不可用时 MCP 进程继续连接小智，工具返回 `BACKEND_UNAVAILABLE`。
- FastAPI 恢复后下一次调用直接恢复，无需重启 MCP。
- MCP 崩溃或停用不影响手机 REST 控制和投影 WebSocket。
- `pause`、`resume`、`stop` 和相同速度设置应保持现有后端的幂等行为。
- API timeout 表示结果未知，不等于命令一定没有执行。
- 桥接层不得自动重发写工具调用。
- 多个 MCP 调用并发到达时，最终写顺序由现有 FastAPI `command_lock` 决定；MCP
  不增加跨进程业务锁。

## 13. 测试规范

### 13.1 配置测试

- 完整示例配置能够加载。
- 缺少 endpoint、非法 URL、未知字段和错误 schemaVersion 会失败。
- backoff、timeout、message size 的边界正确。
- 脱敏输出不包含 endpoint path、query 或 token。
- 默认路径相对项目根解析，不依赖当前工作目录。

### 13.2 API 客户端测试

- 每个方法只访问规定的 HTTP 方法和路径。
- 连接失败、timeout、404、422、500 和无效 JSON 正确映射错误。
- 响应 DTO 不依赖 `drumnext` 包。
- 工具参数无法改变目标主机或路径。

### 13.3 工具测试

- `tools/list` 恰好包含本文定义的八个工具。
- input schema 的 required、类型、长度和范围正确。
- 秒到毫秒转换覆盖整数、小数和零。
- 乐谱 ID、完整标题、无匹配和不唯一匹配行为正确。
- 指定乐谱播放按 score→play 顺序调用。
- 第二步失败时返回最新已知状态，不伪造原子性。
- 列表不返回完整 notes，且遵守 `maxScoresReturned`。
- REST 错误表现为 MCP tool error。
- stdout 没有日志污染。

### 13.4 桥接测试

使用假的 WebSocket 和子进程，不连接真实接入点：

- 文本帧正确写入 stdin 并 flush。
- stdout 每行正确发送为一个 WSS 文本帧。
- stderr 只进入日志。
- 非法 UTF-8、非 JSON stdout 和超限帧终止当前会话。
- 任一方向 EOF 都会取消其他任务并回收子进程。
- 清理顺序为 close stdin、wait、terminate、wait、kill。
- 重连退避有倍率、上限和抖动；测试使用假时钟，不真实等待。
- 进程信号不会遗留僵尸子进程。
- 未完成调用不会在新连接自动重放。

### 13.5 解耦测试

- `backend/drumnext_mcp` 不导入 `drumnext`。
- 现有 `create_app()` 不初始化、启动或引用 MCP。
- MCP 测试可以在不创建 FastAPI app 的情况下完成。
- 现有后端测试可以在缺少 MCP 配置文件时完整通过。
- 停止 MCP 进程后，现有 REST 和投影 WebSocket 行为不变。

### 13.6 验证命令

```bash
uv run ruff check .
uv run pytest
npm test
npm run typecheck
npm run build
```

本功能不改变投影视觉，不更新 Playwright 视觉截图基线。

## 14. 开发顺序

### 阶段 1：独立包与配置

- 创建 `backend/drumnext_mcp`。
- 添加配置模型、加载器、示例文件和 `.gitignore` 规则。
- 增加包构建配置和 `drumnext-mcp` 命令。
- 完成配置与解耦测试。

验收：缺少真实 endpoint 时明确报配置错误；现有服务测试不受影响。

### 阶段 2：REST 客户端与工具

- 定义独立响应 DTO 和稳定错误。
- 实现受限 API client。
- 实现八个工具及 schema 测试。
- 用假的 HTTP transport 完成全部工具测试。

验收：本地 MCP client 可以完成 initialize、tools/list 和 tools/call，不需要修改
现有 FastAPI 源码。

### 阶段 3：WSS 桥接

- 实现 WSS/stdin/stdout 转发。
- 实现子进程回收、信号处理、消息限制和重连。
- 完成桥接协议测试。

验收：假接入点反复断开时能重建会话，无调用重放、无僵尸进程。

### 阶段 4：真实接入点联调

- 复制 example 生成被忽略的真实配置。
- 填入现有 MCP endpoint。
- 启动原有服务和独立 MCP 服务。
- 在小智端验证状态、乐谱、播放、暂停、恢复、停止、跳转和调速。

验收：工具调用能改变现有 FastAPI 状态，投影通过原有 WebSocket 正常更新。

### 阶段 5：独立部署

- 添加 `drumnext-mcp.service`。
- 配置独立用户、配置文件权限、自动重启和日志轮转。
- 验证 MCP 和原有服务可以分别重启及停用。

验收：设备冷启动后两项服务分别启动；任一服务异常不会带崩另一项服务。

## 15. systemd 部署要求

现有服务和 MCP 服务使用两个 unit：

```text
drumnext.service
drumnext-mcp.service
```

`drumnext-mcp.service` 可以设置：

```ini
[Unit]
Description=DrumNext MCP Service
After=network-online.target drumnext.service
Wants=network-online.target

[Service]
Type=simple
User=drumnext-mcp
WorkingDirectory=/opt/drumnext
ExecStart=/opt/drumnext/.venv/bin/drumnext-mcp --config /etc/drumnext/xiaozhi-mcp.json
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

这里只使用 `After`，不使用 `Requires=drumnext.service`。后端停止时 MCP 应继续运行并
返回可恢复错误，而不是被 systemd 联动停止。

endpoint 只存在 `/etc/drumnext/xiaozhi-mcp.json` 中，不能写入 unit 或命令行。

## 16. 手工验收

| 用户表达 | 期望工具与参数 | 期望结果 |
| --- | --- | --- |
| “现在播放到哪里？” | `drumnext_get_status` | 返回当前乐谱、状态、进度和速度 |
| “有哪些乐谱？” | `drumnext_list_scores` | 返回乐谱摘要 |
| “播放大鱼” | `drumnext_play(score_id="大鱼")` | 依次切歌并开始播放 |
| “暂停” | `drumnext_pause` | 当前画面暂停 |
| “继续” | `drumnext_resume` | 从暂停位置恢复 |
| “停止” | `drumnext_stop` | 停止并回到开头 |
| “跳到一分钟” | `drumnext_seek(position_seconds=60)` | 最终位置约为 `60000ms` |
| “设置一点二五倍速” | `drumnext_set_speed(speed=1.25)` | 最终速度为 `1.25` |

还必须验证：

- 重复暂停、恢复和停止不会报异常。
- FastAPI 停止时小智收到明确的服务不可用提示。
- FastAPI 恢复后无需重启 MCP 即可继续调用。
- MCP 重启不改变当前播放状态。
- 停止 MCP 后，手机控制和投影仍正常。
- 接入点断开并恢复后工具列表仍完整。

## 17. 回滚

MCP 功能可以独立回滚：

1. 停止并禁用 `drumnext-mcp.service`。
2. 删除或移走真实 `xiaozhi-mcp.json`。
3. 保留现有 `drumnext.service` 正常运行。

回滚 MCP 不修改乐谱、布局、设置或播放状态，不需要回滚投影端。

## 18. 完成定义

- MCP 代码位于独立 `drumnext_mcp` 包，且不导入 `drumnext`。
- 现有 FastAPI 和投影代码不需要为 MCP 修改。
- 所有 MCP 参数都来自 JSON 配置文件；命令行只允许选择配置文件路径。
- 真实配置被 Git 忽略，endpoint 不出现在日志或进程命令行。
- 八个工具的名称、schema、结果和错误具有自动测试。
- 后端不可用时 MCP 进程继续运行，恢复后自动可用。
- WSS 断线能够退避重连，没有调用重放和僵尸子进程。
- MCP 与原有服务能够分别启动、停止、重启和部署。
- Ruff、pytest、Vitest、TypeScript 类型检查和生产构建通过。
- 使用真实接入点完成第 16 节验收。

## 19. 实现参考

- [78/mcp-calculator](https://github.com/78/mcp-calculator)：小智 MCP 接入点与 stdio/WebSocket 桥接参考。
- [Model Context Protocol](https://modelcontextprotocol.io/)：MCP 协议与 SDK 文档。

参考项目只用于核对接入点行为。DrumNext MCP 的代码、配置、依赖和测试必须完整保存
在当前仓库内，不能把外部脚本作为生产运行时依赖。
