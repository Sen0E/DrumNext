# DrumNext

DrumNext 是运行在 Raspberry Pi 5 上的空灵鼓乐谱投影与远程控制系统。投影端使用 PixiJS/WebGL2 绘制鼓面、缩圈、命中高亮和粒子；FastAPI 后端负责乐谱、布局、播放状态、命令串行化以及 WebSocket 实时同步。

本仓库是独立重构项目，不依赖父目录中的旧项目代码、资源或运行环境。修改代码前必须阅读 [DEVELOPMENT.md](DEVELOPMENT.md)，该文档定义了架构边界、时间模型、性能预算、测试策略和 AI 开发规范。

## 当前状态

目前已经实现：

- 15 个可配置鼓面和 1920×1080 设计坐标系。
- 纯黑投影背景、缩圈、命中高亮和基础粒子。
- 基于绝对单调时间锚点的播放、暂停、恢复、停止、跳转和调速。
- FastAPI REST 控制接口。
- WebSocket 完整快照、增量事件、全局序号、重连和时钟偏移估算。
- 4 秒音符前瞻窗口和投影端音符 ID 去重。
- 乐谱查询、切换、旧格式适配和布局持久化更新。
- FastAPI API 调试页面及 OpenAPI 文档。
- Vitest、pytest 和 Playwright 自动测试。
- Vite 生产构建和 FastAPI 静态文件托管。

当前明确不包含：

- 音频播放与 Web Audio 调度。
- systemd、Chromium kiosk 和设备自动恢复配置。
- 生产设备的升级、回滚和日志轮转。

当前视觉性能验收下限为目标设备稳定不低于 30 FPS。最终性能结论必须在 Raspberry Pi 5、1920×1080、生产构建和 Chromium kiosk 条件下确认。

## 技术栈

| 组件           | 技术                            |
| -------------- | ------------------------------- |
| 投影渲染       | TypeScript、PixiJS 8、WebGL2    |
| 前端构建       | Vite                            |
| 前端测试       | Vitest、Playwright              |
| 后端           | Python 3.11+、FastAPI、Pydantic |
| Python 管理    | uv                              |
| 后端测试与检查 | pytest、Ruff                    |
| 实时通信       | WebSocket                       |

投影端不使用 React 或 Vue；业务状态的唯一事实来源是 FastAPI 后端。

## 系统架构

```text
手机 App / FastAPI 调试页
          │
          │ REST /api/v1/*
          ▼
┌─────────────────────────────┐
│ FastAPI                     │
│                             │
│ 乐谱、布局、播放状态机      │
│ 命令串行化、事件序号        │
│ 静态资源与生产页面托管      │
└──────────────┬──────────────┘
               │ WebSocket /ws/v1/projection
               │ 快照、事件、时钟同步、音符窗口
               ▼
┌─────────────────────────────┐
│ PixiJS 投影端               │
│                             │
│ 只读状态镜像、绝对时间求值  │
│ 鼓面、缩圈、高亮、粒子      │
└─────────────────────────────┘
```

后端处理所有写命令。投影端只读取后端快照和事件，不反向修改业务状态。

## 目录结构

```text
DrumNext/
├── DEVELOPMENT.md                 # 架构、约束与开发规范
├── README.md                      # 项目入口文档
├── package.json                   # Node 依赖与稳定命令
├── package-lock.json
├── pyproject.toml                 # Python 依赖、命令和工具配置
├── uv.lock
├── backend/
│   ├── drumnext/
│   │   ├── api/                   # REST 路由
│   │   ├── domain/                # Pydantic 领域与协议模型
│   │   ├── playback/              # 时钟、状态机和音符窗口
│   │   ├── storage/               # 乐谱与布局文件访问
│   │   ├── transport/             # WebSocket 事件广播
│   │   ├── config.py              # 集中配置入口
│   │   └── main.py                # FastAPI 应用工厂和启动入口
│   └── tests/
├── projection/
│   ├── src/
│   │   ├── app/                   # 浏览器能力检测
│   │   ├── config/                # 投影端配置类型和测试数据
│   │   ├── debug/                 # FPS 等诊断信息
│   │   ├── network/               # API、协议、WebSocket、时钟同步
│   │   ├── playback/              # 时间轴和已调度音符镜像
│   │   └── scene/                 # PixiJS 场景与稳定图层
│   ├── tests/                     # Vitest 纯逻辑测试
│   ├── e2e/                       # Playwright 浏览器测试
│   └── snapshots/                 # 确定性视觉基线
├── shared/
│   ├── fixtures/                  # 前后端共同读取的协议样例
│   └── schemas/                   # JSON Schema
├── resources/
│   ├── scores/                    # 乐谱 JSON
│   └── drum_notes_config.json     # 原始 1920×1080 鼓面坐标参考
└── config/
    └── default-layout.json        # 当前运行时归一化布局
```

不要从父目录复制或读取运行时数据。新增依赖、资源、配置和脚本必须位于本项目根目录内。

## 环境要求

- Node.js 20 或更高版本。
- npm。
- Python 3.11 或更高版本。
- uv。
- 支持 WebGL2 的 Chromium/Chrome。

安装依赖：

```bash
npm install
uv sync
```

如首次运行浏览器测试，需要安装 Playwright Chromium：

```bash
npm exec playwright install chromium
```

## 本地开发

开发时需要同时启动后端和 Vite。建议打开两个终端，并确保命令都在 DrumNext 根目录执行。

终端一：

```bash
uv run drumnext
```

后端默认地址：

```text
http://localhost:8000
```

终端二：

```bash
npm run dev
```

投影开发页面：

```text
http://localhost:5173
```

Vite 会将 `/api` 和 `/ws` 代理到 `http://127.0.0.1:8000`。修改 Python 代码后需要重启后端；修改投影端代码通常会由 Vite 热更新。

## 调试入口

| 地址                                    | 用途                                 |
| --------------------------------------- | ------------------------------------ |
| `http://localhost:8000/api/v1/health` | 后端健康检查                         |
| `http://localhost:8000/debug/api`     | FastAPI 托管的人工控制与响应查看页面 |
| `http://localhost:8000/docs`          | Swagger/OpenAPI 交互文档             |
| `http://localhost:8000/redoc`         | ReDoc 接口文档                       |
| `http://localhost:5173`               | Vite 投影开发页面                    |

`/debug/api` 只是 REST API 调用器，不保存播放状态，也不属于投影前端。业务状态始终由后端维护。

## REST API

所有业务 API 使用 `/api/v1` 前缀。

### 播放控制

| 方法     | 路径                        | 请求体                    | 说明                     |
| -------- | --------------------------- | ------------------------- | ------------------------ |
| `GET`  | `/api/v1/playback`        | 无                        | 获取当前播放快照         |
| `POST` | `/api/v1/playback/play`   | 无                        | 从停止位置或当前位置播放 |
| `POST` | `/api/v1/playback/pause`  | 无                        | 暂停并固定当前位置       |
| `POST` | `/api/v1/playback/resume` | 无                        | 从暂停位置恢复           |
| `POST` | `/api/v1/playback/stop`   | 无                        | 停止并回到 0ms           |
| `POST` | `/api/v1/playback/seek`   | `{"positionMs": 30000}` | 跳转播放位置             |
| `POST` | `/api/v1/playback/speed`  | `{"speed": 1.25}`       | 设置 0.25–4 倍速度      |
| `POST` | `/api/v1/playback/score`  | `{"scoreId": "大鱼"}`   | 切换乐谱并停止到 0ms     |

示例：

```bash
curl -X POST http://localhost:8000/api/v1/playback/play
curl -X POST http://localhost:8000/api/v1/playback/pause
curl -X POST http://localhost:8000/api/v1/playback/seek \
  -H 'Content-Type: application/json' \
  -d '{"positionMs":30000}'
curl -X POST http://localhost:8000/api/v1/playback/speed \
  -H 'Content-Type: application/json' \
  -d '{"speed":1.25}'
```

播放快照示例：

```json
{
  "status": "playing",
  "scoreId": "大鱼",
  "durationMs": 168154,
  "positionMs": 4200.5,
  "anchorPositionMs": 3692,
  "anchorClockMs": 12500.2,
  "speed": 1.0
}
```

### 乐谱与布局

| 方法    | 路径                         | 说明                            |
| ------- | ---------------------------- | ------------------------------- |
| `GET` | `/api/v1/scores`           | 列出乐谱摘要                    |
| `GET` | `/api/v1/scores/{scoreId}` | 获取完整乐谱                    |
| `GET` | `/api/v1/layout`           | 获取当前布局                    |
| `PUT` | `/api/v1/layout`           | 校验、保存用户布局并增加 revision |
| `POST` | `/api/v1/layout/reset`   | 删除用户布局并恢复默认布局   |

不存在的乐谱使用稳定错误结构：

```json
{
  "error": {
    "code": "SCORE_NOT_FOUND",
    "message": "未找到指定乐谱",
    "details": {"scoreId": "missing"}
  }
}
```

## WebSocket 协议

投影端连接：

```text
/ws/v1/projection
```

每条服务端消息都包含：

```json
{
  "protocolVersion": 1,
  "type": "playback.snapshot",
  "sequence": 1,
  "serverTimeMs": 12500.0,
  "payload": {}
}
```

- `sequence` 是服务端进程内全局单调递增序号。
- `serverTimeMs` 来自服务端单调时钟，不是墙上时间。
- 新连接和重连的第一条消息必须是 `playback.snapshot`。
- 第二条消息是 `notes.scheduled` 前瞻窗口。
- 投影端按序号拒绝乱序消息，并按音符 ID 去重。
- 浏览器发送 `clock.ping`，服务端返回 `clock.pong`；投影端使用低延迟样本估计时钟偏移。

当前使用的事件包括：

```text
playback.snapshot
playback.started
playback.paused
playback.resumed
playback.stopped
playback.seeked
playback.speed_changed
score.changed
layout.changed
notes.scheduled
clock.pong
```

跨端协议变更必须同步更新：

1. `backend/drumnext/domain/` 中的 Pydantic 模型。
2. `projection/src/network/` 中的 TypeScript 解析器。
3. `shared/schemas/` 中的 JSON Schema。
4. `shared/fixtures/` 中至少一个 fixture。
5. Python 和 TypeScript 契约测试。

## 播放时间模型

播放位置禁止逐帧累加，统一使用绝对锚点公式：

```text
positionMs = anchorPositionMs + (nowMs - anchorClockMs) × speed
```

- 后端使用 `time.monotonic_ns()`。
- 投影端使用 `performance.now()`。
- 暂停、恢复、调速和跳转都会重建锚点。
- 位置不会依赖系统日期、时区或墙上时钟。
- 测试使用虚拟时钟，不通过真实等待验证状态机。

修改播放逻辑时，必须优先更新状态机和时钟测试。

## 乐谱格式

### 标准格式

新增乐谱优先使用具名字段格式：

```json
{
  "schemaVersion": 1,
  "id": "example-score",
  "title": "示例乐谱",
  "durationMs": 120000,
  "notes": [
    {
      "id": "n-000001",
      "timeMs": 3692,
      "noteKey": "low_4",
      "velocity": 0.8
    }
  ]
}
```

约束：

- 音符必须按 `timeMs` 升序排列。
- 同一乐谱中的音符 ID 必须唯一。
- `velocity` 范围是 0–1。
- 音符时间不能超过 `durationMs`。
- `noteKey` 必须存在于当前布局。
- 音符数量和字符串长度由 Pydantic 模型限制；接收外部上传功能时还必须在传输层限制文件及请求体大小。

### 大鱼旧格式

`resources/scores/大鱼.json` 保留原始二维数组：

```json
[
  [3692, "low_4"],
  [3923, "low_6"]
]
```

`ScoreStore` 在读取时将其转换成标准内部模型，并生成稳定音符 ID。源文件不会被修改。目前导入结果为 365 个音符，乐谱时长为 168154ms。

## 音位与布局

常规音位格式：

```text
low_1 ... low_7
mid_1 ... mid_7
high_1 ... high_7
```

中心音位使用独立键：

```text
low_3_center
```

当前布局来源于 `resources/drum_notes_config.json` 中的 1920×1080 像素坐标。运行时使用的 `config/default-layout.json` 已转换为归一化坐标，并将原配置的中心 `low_3` 显式映射为 `low_3_center`。

标准布局结构：

```json
{
  "schemaVersion": 1,
  "revision": 1,
  "pads": [
    {
      "noteKey": "low_3_center",
      "x": 0.5,
      "y": 0.5,
      "radius": 0.07,
      "color": "#45A3FF",
      "label": "3",
      "octaveLabel": "L",
      "audioAsset": "low_3.wav"
    }
  ]
}
```

布局要求：

- `x`、`y` 和 `radius` 使用归一化坐标。
- 画面按 1920×1080 contain 方式等比缩放并居中。
- `noteKey` 不得重复。
- 颜色使用 `#RRGGBB` 或 `#RRGGBBAA`。
- `PUT /api/v1/layout` 会忽略请求中的旧 revision，并基于当前 revision 加一。
- 用户布局只写入 `config/user-layout.json`，不会修改默认布局文件。
- `POST /api/v1/layout/reset` 会删除用户布局文件并返回默认布局。
- 布局更新成功后广播 `layout.changed`，投影端销毁旧场景并重建全部图层。

## 配置

配置集中定义于 `backend/drumnext/config.py`，环境变量统一使用 `DRUMNEXT_` 前缀。

| 环境变量                      | 默认值                                | 说明               |
| ----------------------------- | ------------------------------------- | ------------------ |
| `DRUMNEXT_HOST`             | `0.0.0.0`                           | FastAPI 监听地址   |
| `DRUMNEXT_PORT`             | `8000`                              | FastAPI 端口       |
| `DRUMNEXT_PROJECTION_DIST`  | `<root>/dist`                       | 投影生产构建目录   |
| `DRUMNEXT_SCORE_DIRECTORY`  | `<root>/resources/scores`           | 乐谱目录           |
| `DRUMNEXT_LAYOUT_FILE`      | `<root>/config/default-layout.json` | 默认布局文件       |
| `DRUMNEXT_USER_LAYOUT_FILE` | `<root>/config/user-layout.json`   | 用户布局文件       |
| `DRUMNEXT_DEFAULT_SCORE_ID` | `大鱼`                              | 后端启动时默认乐谱 |

所有默认路径都根据代码文件位置解析，不依赖进程启动时的当前目录。

Vite 可通过 `DRUMNEXT_BACKEND_URL` 覆盖开发代理目标；未设置时使用 `http://127.0.0.1:8000`。该变量主要用于隔离的端到端测试。

## 稳定命令

| 命令                    | 用途                                         |
| ----------------------- | -------------------------------------------- |
| `npm run dev`         | 启动 Vite 投影开发服务器                     |
| `uv run drumnext`     | 启动 FastAPI 后端                            |
| `npm run typecheck`   | TypeScript 严格类型检查                      |
| `npm run lint`        | ESLint 检查                                  |
| `npm test`            | Vitest 纯逻辑与协议测试                      |
| `npm run test:e2e`    | Playwright 浏览器、API、WebSocket 和截图测试 |
| `uv run ruff check .` | Python 静态检查                              |
| `uv run pytest`       | 后端单元、API、存储和契约测试                |
| `npm run build`       | TypeScript 检查并生成生产构建                |

一次完整验证：

```bash
npm run typecheck
npm run lint
npm test
uv run ruff check .
uv run pytest
npm run build
npm run test:e2e
```

Playwright 会在隔离端口启动测试服务：

- FastAPI：`127.0.0.1:18000`
- Vite preview：`127.0.0.1:4173`

不要让其他程序占用这些端口。视觉测试固定为 1920×1080、device scale factor 1，并使用确定的乐谱时间。

## 生产构建与运行

构建投影页面：

```bash
npm run build
```

产物生成到根目录 `dist/`。然后启动 FastAPI：

```bash
uv run drumnext
```

访问：

```text
http://localhost:8000
```

此时页面由 FastAPI 托管，不应使用 Vite 开发服务器作为生产服务。若尚未构建，FastAPI 根页面会返回明确的 503 诊断页面。

当前仓库尚未包含 Raspberry Pi systemd 和 Chromium kiosk 部署单元；设备化部署前必须补齐并进行真机验证。

## 开发工作流

开始修改前：

1. 阅读 [DEVELOPMENT.md](DEVELOPMENT.md)。
2. 检查工作区状态，保留其他开发者未提交的修改。
3. 定位相关领域模型、协议 fixture 和测试。
4. 确认改动是否跨越 Python/TypeScript 边界。

实现过程中：

- 领域层不得导入 FastAPI。
- 路由只负责输入输出转换，不放置复杂播放逻辑。
- 所有写命令必须串行化。
- 播放位置必须由绝对时间锚点计算。
- 渲染循环中不得发起网络请求或创建大量对象。
- 高频 PixiJS 对象应初始化后复用。
- 外部输入只能提供资源 ID，不能提供任意文件路径。
- 协议修改必须同时更新模型、类型、Schema、fixture 和两端测试。
- 不得通过 `any`、关闭严格检查或宽泛异常捕获掩盖问题。

提交前：

1. 运行与改动范围对应的单元测试和静态检查。
2. 涉及投影行为时运行生产构建。
3. 涉及页面、API 或 WebSocket 时运行 Playwright。
4. 涉及视觉变化时检查并有意识地更新截图基线。
5. 涉及公开行为、命令或格式时更新 README 和 DEVELOPMENT。

## 常见开发任务

### 添加标准乐谱

1. 在 `resources/scores/` 创建标准 JSON 文件。
2. 确保文件中的 `id` 唯一，且所有 `noteKey` 存在于布局。
3. 启动后端并访问 `GET /api/v1/scores`。
4. 使用 `POST /api/v1/playback/score` 切换乐谱。
5. 添加存储校验测试；若会改变视觉基线，再更新 Playwright 测试。

### 修改鼓面布局

优先通过 `PUT /api/v1/layout` 修改并让后端递增 revision，修改只会写入 `config/user-layout.json`。调用 `POST /api/v1/layout/reset` 可删除用户布局并恢复 `config/default-layout.json`。

不要在效果代码中写死屏幕坐标；布局计算只能使用归一化数据和统一的 1920×1080 设计视口。

### 修改播放协议

先修改共享 fixture 和契约测试，再修改 Python 模型、后端广播、TypeScript 解析器和投影镜像。连接后的第一条消息仍必须保持为完整快照。

### 修改视觉效果

效果应当是播放时间的确定函数。避免使用回调链推进缩圈或命中状态。为纯时间函数添加 Vitest 测试，并为关键时间点添加或更新 Playwright 截图。缩圈半径当前使用线性进度，确保圆环持续收缩到命中帧，避免提前进入肉眼不可分辨的最终尺寸。

## 故障排查

### 投影页面一直停在初始化状态

- 确认 `uv run drumnext` 正在运行。
- 检查 `http://localhost:8000/api/v1/health`。
- 查看浏览器控制台是否有资源校验或 WebGL2 错误。
- 确认当前乐谱的所有 `noteKey` 都存在于布局。

### API 修改后行为没有变化

Python 后端当前未启用自动重载。停止旧进程并重新运行：

```bash
uv run drumnext
```

### WebSocket 反复重连

- 确认 Vite 代理目标与后端端口一致。
- 直接检查 `/api/v1/health`。
- 检查浏览器控制台中的 `projection.protocol_error`。
- 确认消息 `protocolVersion` 为 1。

### Playwright 报浏览器不存在

```bash
npm exec playwright install chromium
```

### `uv run` 提示外部 `VIRTUAL_ENV` 不匹配

uv 会忽略父目录或当前 shell 中不属于 DrumNext 的虚拟环境，并使用根目录 `.venv`。这符合项目独立性要求；必要时退出外部虚拟环境后重新执行 `uv sync`。

### 生产根页面返回 503

先生成投影构建：

```bash
npm run build
```

## 完成定义

一项修改只有在以下条件同时满足时才可交付：

- 行为符合需求和 `DEVELOPMENT.md`。
- 类型检查、Lint 和相关测试通过。
- 生产构建成功。
- 新增公共行为具有测试。
- 跨端协议同步更新两端和共享 fixture。
- 不引用父目录代码、资源或环境。
- 没有已知资源泄漏或每帧不必要分配。
- 文档与实际命令、接口和数据格式一致。

更详细的性能预算、场景图层、时间同步、资源管理和架构决策要求，请以 [DEVELOPMENT.md](DEVELOPMENT.md) 为准。
