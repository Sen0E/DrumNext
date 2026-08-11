# DrumNext 手机 App API 文档

状态：可供 App 开发使用
API 版本：`v1`
服务版本：`0.1.0`
最后核对：2026-08-09

## 1. 文档范围

本文档描述手机 App 控制和设置 DrumNext 空灵鼓投影时使用的公开接口，包括：

- 18 个 REST API；
- 1 个实时 WebSocket；
- 播放状态、乐谱、鼓面布局和投影视觉设置的数据结构；
- 错误处理、时间同步和多客户端协作约定。

手机 App 直接连接 DrumNext FastAPI，不连接小智 MCP 接入点，也不依赖
`drumnext_mcp` 进程。MCP 服务停止不会影响本文档中的接口。

## 2. 连接信息

### 2.1 Base URL

REST API 根地址：

```text
http://<DrumNext设备IP>:8000/api/v1
```

示例：

```text
http://192.168.1.50:8000/api/v1
```

WebSocket 地址：

```text
ws://<DrumNext设备IP>:8000/ws/v1/projection
```

如果前面部署了 HTTPS 反向代理，应分别使用 `https://` 和 `wss://`。

### 2.2 协议约定

| 项目              | 约定                                   |
| ----------------- | -------------------------------------- |
| 字符编码          | UTF-8                                  |
| REST Content-Type | `application/json`                   |
| JSON 字段命名     | `camelCase`                          |
| 时间位置和时长    | 毫秒，字段后缀为`Ms`                 |
| 播放速度          | 倍率，例如`1.25` 表示 1.25 倍速      |
| 坐标              | 相对投影画面的归一化坐标，范围`0..1` |
| 颜色              | `#RRGGBB` 或 `#RRGGBBAA`           |

### 2.3 认证与网络安全

当前 API **没有认证和授权机制**，也没有内置 HTTPS。任何能够访问服务端口的客户端都
可以控制投影或修改设置。

因此 App 第一版应仅在可信局域网、受控 Wi-Fi 或 VPN 内使用，不应把端口直接暴露到
公网。原生 App 可以直接请求局域网地址；浏览器或混合 WebView 还需要考虑同源策略，
当前后端没有配置通用 CORS 中间件。

### 2.4 OpenAPI

服务运行后可查看自动生成的接口定义：

```text
GET /openapi.json
GET /docs
```

自动生成的 OpenAPI 适合生成基础客户端；本文档中的状态语义、重试规则和 WebSocket
约定仍需单独实现。

## 3. 推荐的 App 启动流程

1. 调用 `GET /api/v1/health` 检查连接。
2. 并发读取：
   - `GET /api/v1/playback`
   - `GET /api/v1/scores`
   - `GET /api/v1/layout`
   - `GET /api/v1/settings/ending-animation`
   - `GET /api/v1/settings/projection-visuals`
3. 建立 `/ws/v1/projection` WebSocket，接收后续状态变化。
4. 通过 REST 发送控制命令，并始终使用 REST 响应更新 App 本地状态。
5. WebSocket 断开时退避重连；重连后重新接受初始 `playback.snapshot`。

REST 命令响应是该命令完成后的最终服务端状态。不要先假设命令一定成功再更新 UI。

## 4. API 总览

### 4.1 系统

| 方法    | 路径               | 用途               |
| ------- | ------------------ | ------------------ |
| `GET` | `/api/v1/health` | 健康检查和版本查询 |

### 4.2 播放控制

| 方法     | 路径                        | 用途             |
| -------- | --------------------------- | ---------------- |
| `GET`  | `/api/v1/playback`        | 查询当前播放状态 |
| `POST` | `/api/v1/playback/play`   | 开始播放         |
| `POST` | `/api/v1/playback/pause`  | 暂停             |
| `POST` | `/api/v1/playback/resume` | 从暂停位置恢复   |
| `POST` | `/api/v1/playback/stop`   | 停止并回到开头   |
| `POST` | `/api/v1/playback/seek`   | 跳转时间轴       |
| `POST` | `/api/v1/playback/speed`  | 设置播放速度     |
| `POST` | `/api/v1/playback/score`  | 切换当前乐谱     |

### 4.3 乐谱与布局

| 方法     | 路径                          | 用途               |
| -------- | ----------------------------- | ------------------ |
| `GET`  | `/api/v1/scores`            | 查询乐谱摘要列表   |
| `GET`  | `/api/v1/scores/{score_id}` | 查询完整乐谱       |
| `GET`  | `/api/v1/layout`            | 查询当前鼓面布局   |
| `PUT`  | `/api/v1/layout`            | 保存自定义鼓面布局 |
| `POST` | `/api/v1/layout/reset`      | 恢复默认鼓面布局   |

### 4.4 投影设置

| 方法    | 路径                                    | 用途             |
| ------- | --------------------------------------- | ---------------- |
| `GET` | `/api/v1/settings/ending-animation`   | 查询结束动画风格 |
| `PUT` | `/api/v1/settings/ending-animation`   | 修改结束动画风格 |
| `GET` | `/api/v1/settings/projection-visuals` | 查询投影视觉参数 |
| `PUT` | `/api/v1/settings/projection-visuals` | 修改投影视觉参数 |

## 5. 通用数据模型

### 5.1 PlaybackSnapshot

所有播放命令都返回同一个 `PlaybackSnapshot`：

```json
{
  "status": "playing",
  "scoreId": "demo-score",
  "durationMs": 16000,
  "positionMs": 2500.0,
  "anchorPositionMs": 2000.0,
  "anchorClockMs": 12000.0,
  "speed": 1.0
}
```

| 字段                 | 类型                                 | 说明                         |
| -------------------- | ------------------------------------ | ---------------------------- |
| `status`           | `"stopped" \| "playing" \| "paused"` | 当前状态                     |
| `scoreId`          | `string`                           | 当前乐谱 ID                  |
| `durationMs`       | `integer > 0`                      | 当前乐谱总时长               |
| `positionMs`       | `number >= 0`                      | 生成响应时的播放位置         |
| `anchorPositionMs` | `number >= 0`                      | 服务端计算动态进度的锚点位置 |
| `anchorClockMs`    | `number >= 0`                      | 锚点对应的服务端单调时钟     |
| `speed`            | `number > 0`                       | 当前速度倍率                 |

`anchorClockMs` 不是 Unix 时间戳，不能直接与手机的系统时间比较。只展示进度时可直接使用
`positionMs`；需要在两次消息之间平滑推进进度时，应采用第 12 节的 WebSocket 时钟同步。

当播放位置到达 `durationMs` 时，位置会收敛到时长上限，但当前版本不会自动把
`status` 从 `playing` 改成 `stopped`。

### 5.2 ScoreSummary

```json
{
  "id": "demo-score",
  "title": "DrumNext 演示乐谱",
  "durationMs": 16000,
  "noteCount": 15
}
```

| 字段           | 类型        | 说明                          |
| -------------- | ----------- | ----------------------------- |
| `id`         | `string`  | 稳定乐谱 ID，控制接口使用此值 |
| `title`      | `string`  | 展示标题                      |
| `durationMs` | `integer` | 乐谱时长                      |
| `noteCount`  | `integer` | 音符数量                      |

### 5.3 ScoreNote

```json
{
  "id": "demo-03",
  "timeMs": 2800,
  "noteKey": "low_3",
  "velocity": 0.88
}
```

| 字段         | 类型        | 约束                                   |
| ------------ | ----------- | -------------------------------------- |
| `id`       | `string`  | 长度`1..64`，同一乐谱内唯一          |
| `timeMs`   | `integer` | `>= 0`，不超过乐谱时长               |
| `noteKey`  | `string`  | 匹配`(low\|mid\|high)_[1-7](_center)?` |
| `velocity` | `number`  | `0..1`                               |

### 5.4 Score

```json
{
  "schemaVersion": 1,
  "id": "demo-score",
  "title": "DrumNext 演示乐谱",
  "durationMs": 16000,
  "notes": [
    {
      "id": "demo-03",
      "timeMs": 2800,
      "noteKey": "low_3",
      "velocity": 0.88
    }
  ]
}
```

音符按 `timeMs` 升序返回。当前 API 只支持读取乐谱，没有上传、修改或删除乐谱的接口。

### 5.5 LayoutPad

```json
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
```

| 字段            | 类型       | 约束或说明                                         |
| --------------- | ---------- | -------------------------------------------------- |
| `noteKey`     | `string` | 匹配`(low\|mid\|high)_[1-7](_center)?`，布局内唯一 |
| `x`           | `number` | `0..1`，鼓面中心横坐标                           |
| `y`           | `number` | `0..1`，鼓面中心纵坐标                           |
| `radius`      | `number` | `> 0` 且 `<= 0.25`                             |
| `color`       | `string` | `#RRGGBB` 或 `#RRGGBBAA`                       |
| `label`       | `string` | 长度`1..16`                                      |
| `octaveLabel` | `string` | 长度`1..8`                                       |
| `audioAsset`  | `string` | 长度`1..128`，投影端资源名                       |

### 5.6 Layout

```json
{
  "schemaVersion": 1,
  "revision": 5,
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

| 字段              | 类型            | 约束                               |
| ----------------- | --------------- | ---------------------------------- |
| `schemaVersion` | `integer`     | 当前必须为`1`                    |
| `revision`      | `integer`     | `>= 1`                           |
| `pads`          | `LayoutPad[]` | `1..64` 项，`noteKey` 不得重复 |

## 6. 系统 API

### 6.1 健康检查

```http
GET /api/v1/health
```

成功响应：`200 OK`

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

App 可用此接口判断设备是否可达。它只表示 HTTP 服务正常，不表示投影浏览器或 MCP 服务
已经连接。

## 7. 播放控制 API

### 7.1 查询播放状态

```http
GET /api/v1/playback
```

请求体：无
成功响应：`200 OK`，返回 `PlaybackSnapshot`。

### 7.2 开始播放

```http
POST /api/v1/playback/play
```

请求体：无
成功响应：`200 OK`，返回 `PlaybackSnapshot`。

行为：

- 当前为 `stopped`：从 `0ms` 开始播放；
- 当前为 `paused`：从暂停位置开始播放；
- 当前为 `playing`：保持当前位置并重新建立时间锚点。

### 7.3 暂停

```http
POST /api/v1/playback/pause
```

请求体：无
成功响应：`200 OK`，返回 `PlaybackSnapshot`。

只有当前为 `playing` 时才改变状态；重复暂停不会报错。

### 7.4 恢复

```http
POST /api/v1/playback/resume
```

请求体：无
成功响应：`200 OK`，返回 `PlaybackSnapshot`。

只有当前为 `paused` 时才恢复；其他状态调用不会报错。

### 7.5 停止

```http
POST /api/v1/playback/stop
```

请求体：无
成功响应：`200 OK`，返回 `PlaybackSnapshot`。

结果始终为：

```json
{
  "status": "stopped",
  "positionMs": 0
}
```

实际响应还包含 `PlaybackSnapshot` 的其他字段。重复停止是幂等操作。

### 7.6 跳转播放位置

```http
POST /api/v1/playback/seek
Content-Type: application/json

{
  "positionMs": 60000
}
```

| 字段           | 类型       | 必填 | 约束     |
| -------------- | ---------- | ---- | -------- |
| `positionMs` | `number` | 是   | `>= 0` |

成功响应：`200 OK`，返回更新后的 `PlaybackSnapshot`。

行为：

- 跳转后保留原来的 `playing`、`paused` 或 `stopped` 状态；
- 超过乐谱时长时自动收敛到 `durationMs`；
- 负数返回 `422`。

### 7.7 设置播放速度

```http
POST /api/v1/playback/speed
Content-Type: application/json

{
  "speed": 1.25
}
```

| 字段      | 类型       | 必填 | 约束          |
| --------- | ---------- | ---- | ------------- |
| `speed` | `number` | 是   | `0.25..4.0` |

成功响应：`200 OK`，返回更新后的 `PlaybackSnapshot`。

修改速度时会先固定当前准确位置，再应用新速度，因此不会造成进度跳变。

### 7.8 切换乐谱

```http
POST /api/v1/playback/score
Content-Type: application/json

{
  "scoreId": "demo-score"
}
```

| 字段        | 类型       | 必填 | 约束                                     |
| ----------- | ---------- | ---- | ---------------------------------------- |
| `scoreId` | `string` | 是   | 长度`1..64`，必须是已存在的精确乐谱 ID |

成功响应：`200 OK`，返回更新后的 `PlaybackSnapshot`。

切换成功后状态变为 `stopped`，位置变为 `0ms`。此接口只切换乐谱，不自动播放；App 如需
“切歌并播放”，应按顺序调用：

1. `POST /api/v1/playback/score`
2. `POST /api/v1/playback/play`

这两个请求不是原子操作。如果第一步成功而第二步失败，乐谱已经切换但仍处于停止状态。

乐谱不存在时返回 `404 SCORE_NOT_FOUND`。

## 8. 乐谱 API

### 8.1 查询乐谱列表

```http
GET /api/v1/scores
```

成功响应：`200 OK`

```json
[
  {
    "id": "demo-score",
    "title": "DrumNext 演示乐谱",
    "durationMs": 16000,
    "noteCount": 15
  }
]
```

当前接口不分页。返回顺序来自服务端乐谱文件排序，App 不应把数组下标当作乐谱标识。

### 8.2 查询完整乐谱

```http
GET /api/v1/scores/{score_id}
```

路径参数：

| 参数         | 类型       | 说明                                          |
| ------------ | ---------- | --------------------------------------------- |
| `score_id` | `string` | 乐谱 ID；构造 URL 时必须进行 percent-encoding |

成功响应：`200 OK`，返回 `Score`。
乐谱不存在：`404 SCORE_NOT_FOUND`。

## 9. 鼓面布局 API

### 9.1 查询当前布局

```http
GET /api/v1/layout
```

成功响应：`200 OK`，返回 `Layout`。

如果存在用户自定义布局则返回自定义布局，否则返回内置默认布局。

### 9.2 保存自定义布局

```http
PUT /api/v1/layout
Content-Type: application/json
```

请求体：完整 `Layout`，不是局部 PATCH。
成功响应：`200 OK`，返回服务端保存后的完整 `Layout`。

服务端会忽略请求中 `revision` 的递增意图，以当前服务端 revision 为基础自动加 `1`。
当前没有基于 revision 的冲突检测；两个 App 同时保存时，后完成的请求覆盖前一个结果。

推荐编辑流程：

1. `GET /api/v1/layout`
2. 在返回对象上修改需要的字段
3. `PUT /api/v1/layout`
4. 用 PUT 响应整体替换 App 本地布局

保存成功会通过 WebSocket 广播 `layout.changed`。

### 9.3 恢复默认布局

```http
POST /api/v1/layout/reset
```

请求体：无
成功响应：`200 OK`，返回恢复后的默认 `Layout`。

此操作会删除服务端持久化的用户布局，并广播 `layout.changed`。

## 10. 投影设置 API

### 10.1 查询结束动画

```http
GET /api/v1/settings/ending-animation
```

成功响应：`200 OK`

```json
{
  "style": "calm"
}
```

`style` 可选值：

| 值              | 说明                     |
| --------------- | ------------------------ |
| `calm`        | 平静结束效果，也是默认值 |
| `spectacular` | 壮观结束效果             |

### 10.2 修改结束动画

```http
PUT /api/v1/settings/ending-animation
Content-Type: application/json

{
  "style": "spectacular"
}
```

成功响应：`200 OK`，返回保存后的完整设置。
未知值或未知字段：`422 Unprocessable Entity`。

保存成功会持久化设置并广播 `ending_animation.changed`。

### 10.3 查询投影视觉参数

```http
GET /api/v1/settings/projection-visuals
```

成功响应：`200 OK`

```json
{
  "showPerformanceInfo": false,
  "approachRingWidth": 14,
  "approachRingOpacity": 0.22,
  "lowPadScale": 1,
  "midPadScale": 1,
  "highPadScale": 1,
  "centerPadScale": 1
}
```

### 10.4 修改投影视觉参数

```http
PUT /api/v1/settings/projection-visuals
Content-Type: application/json

{
  "showPerformanceInfo": true,
  "approachRingWidth": 18,
  "approachRingOpacity": 0.65,
  "lowPadScale": 1.1,
  "midPadScale": 0.95,
  "highPadScale": 1.2,
  "centerPadScale": 1.3
}
```

| 字段                    | 类型       | 范围        | 默认值   | 说明             |
| ----------------------- | ---------- | ----------- | -------- | ---------------- |
| `showPerformanceInfo` | `boolean` | `true/false` | `false` | 显示左上角 FPS 信息 |
| `approachRingWidth`   | `number` | `2..40`   | `14`   | 接近提示环线宽   |
| `approachRingOpacity` | `number` | `0.05..1` | `0.22` | 接近提示环透明度 |
| `lowPadScale`         | `number` | `0.5..2`  | `1`    | 低音鼓面尺寸倍率 |
| `midPadScale`         | `number` | `0.5..2`  | `1`    | 中音鼓面尺寸倍率 |
| `highPadScale`        | `number` | `0.5..2`  | `1`    | 高音鼓面尺寸倍率 |
| `centerPadScale`      | `number` | `0.5..2`  | `1`    | 中心鼓面尺寸倍率 |

成功响应：`200 OK`，返回保存后的完整设置。
越界值或未知字段：`422 Unprocessable Entity`。

这是 PUT 接口，不是 PATCH。虽然当前服务端会为缺少的字段填入模型默认值，App 仍应先
GET 并提交完整对象，否则缺少的字段可能恢复为默认值，而不是保留原设置。

保存成功会持久化设置并广播 `projection_visuals.changed`。

## 11. 错误响应

### 11.1 乐谱不存在

适用于：

- `GET /api/v1/scores/{score_id}`
- `POST /api/v1/playback/score`

响应：`404 Not Found`

```json
{
  "error": {
    "code": "SCORE_NOT_FOUND",
    "message": "未找到指定乐谱",
    "details": {
      "scoreId": "missing"
    }
  }
}
```

App 应优先判断 `error.code`，不要依赖中文 `message` 文案。

### 11.2 参数校验失败

响应：`422 Unprocessable Entity`

```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": ["body", "speed"],
      "msg": "Input should be less than or equal to 4",
      "input": 10,
      "ctx": {
        "le": 4
      }
    }
  ]
}
```

`detail` 中具体的英文 `type` 和 `msg` 可能随服务端验证库升级而变化。App 应利用 `loc`
定位字段，并向用户显示自己的本地化提示，不要直接展示服务端英文文案。

### 11.3 其他错误

| 状态     | 含义                        | App 建议                                |
| -------- | --------------------------- | --------------------------------------- |
| `400`  | 请求格式或协议错误          | 检查客户端实现，不自动重试              |
| `404`  | 路径或资源不存在            | 区分`SCORE_NOT_FOUND` 与错误 URL      |
| `422`  | JSON 字段、类型或范围不合法 | 标记对应表单字段                        |
| `500`  | 服务端内部错误              | 显示通用错误，可稍后查询状态            |
| 网络超时 | 命令结果未知                | 不要直接假定命令未执行，先 GET 当前状态 |

当前服务端没有统一定义除 `SCORE_NOT_FOUND` 外的业务错误体。对未知错误体应容错处理。

## 12. 实时 WebSocket

### 12.1 连接

```text
ws://<DrumNext设备IP>:8000/ws/v1/projection
```

WebSocket 用于状态广播和时钟同步，不用于发送播放控制命令。播放、布局和设置修改仍通过
REST API 完成。

连接建立后，服务端首先发送：

1. `playback.snapshot`
2. `notes.scheduled`

App 应在每次重新连接后清空旧的 sequence 判断和旧的临时调度数据，以新快照为准。

### 12.2 服务端事件信封

所有服务端消息均为文本 JSON：

```json
{
  "protocolVersion": 1,
  "type": "playback.snapshot",
  "sequence": 1,
  "serverTimeMs": 12500.0,
  "payload": {}
}
```

| 字段                | 类型             | 说明                       |
| ------------------- | ---------------- | -------------------------- |
| `protocolVersion` | `1`            | WebSocket 协议版本         |
| `type`            | `string`       | 事件类型                   |
| `sequence`        | `integer >= 1` | 服务进程内全局递增序号     |
| `serverTimeMs`    | `number >= 0`  | 生成消息时的服务端单调时钟 |
| `payload`         | `object`       | 与事件类型对应的数据       |

`sequence` 会在服务重启后重新开始。App 只应在同一条 WebSocket 连接内用它丢弃重复或
乱序消息。

### 12.3 客户端时钟 Ping

客户端发送：

```json
{
  "type": "clock.ping",
  "clientTimeMs": 8200.5
}
```

| 字段             | 类型             | 约束                             |
| ---------------- | ---------------- | -------------------------------- |
| `type`         | `"clock.ping"` | 固定值                           |
| `clientTimeMs` | `number`       | `>= 0`，建议使用客户端单调时钟 |

服务端回复：

```json
{
  "protocolVersion": 1,
  "type": "clock.pong",
  "sequence": 12,
  "serverTimeMs": 12600.0,
  "payload": {
    "clientTimeMs": 8200.5
  }
}
```

每次收到合法 ping 后，服务端还会发送新的 `notes.scheduled` 窗口。建议 App 每 2 秒发送
一次 ping；进入后台时可以停止，回到前台后重新连接或立即补发一次。

### 12.4 时钟偏移估算

设：

- `sent`：发送 ping 时的客户端单调时钟；
- `received`：收到 pong 时的客户端单调时钟；
- `server`：pong 的 `serverTimeMs`。

则：

```text
roundTripMs = received - sent
offsetMs = server - (sent + roundTripMs / 2)
estimatedServerNow = clientMonotonicNow + offsetMs
```

播放中可估算：

```text
estimatedPositionMs = min(
  durationMs,
  anchorPositionMs + (estimatedServerNow - anchorClockMs) * speed
)
```

当状态不是 `playing` 时，直接使用 `positionMs` 或 `anchorPositionMs`。建议保留多个低延迟
样本并取中值，避免网络抖动导致 UI 进度跳跃。

### 12.5 事件类型

| `type`                       | `payload`                    | 触发时机                 |
| ------------------------------ | ------------------------------ | ------------------------ |
| `playback.snapshot`          | `PlaybackSnapshot`           | WebSocket 初次连接       |
| `playback.started`           | `PlaybackSnapshot`           | REST play 成功           |
| `playback.paused`            | `PlaybackSnapshot`           | REST pause 成功          |
| `playback.resumed`           | `PlaybackSnapshot`           | REST resume 成功         |
| `playback.stopped`           | `PlaybackSnapshot`           | REST stop 成功           |
| `playback.seeked`            | `PlaybackSnapshot`           | REST seek 成功           |
| `playback.speed_changed`     | `PlaybackSnapshot`           | REST speed 成功          |
| `score.changed`              | `PlaybackSnapshot`           | REST score 成功          |
| `layout.changed`             | `Layout`                     | 布局更新或重置成功       |
| `ending_animation.changed`   | `EndingAnimationSettings`    | 结束动画更新成功         |
| `projection_visuals.changed` | `ProjectionVisualSettings`   | 投影视觉参数更新成功     |
| `clock.pong`                 | `{ "clientTimeMs": number }` | 收到客户端 ping          |
| `notes.scheduled`            | `NotesScheduledPayload`      | 初次连接以及每次 ping 后 |

### 12.6 NotesScheduledPayload

```json
{
  "scoreId": "demo-score",
  "windowStartMs": 2500.0,
  "windowEndMs": 6500.0,
  "notes": [
    {
      "id": "demo-03",
      "timeMs": 2800,
      "noteKey": "low_3",
      "velocity": 0.88
    }
  ]
}
```

| 字段              | 类型            | 说明                              |
| ----------------- | --------------- | --------------------------------- |
| `scoreId`       | `string`      | 调度窗口所属乐谱                  |
| `windowStartMs` | `number`      | 窗口起点                          |
| `windowEndMs`   | `number`      | 窗口终点，不超过乐谱时长          |
| `notes`         | `ScoreNote[]` | 窗口内的音符，当前前瞻窗口为 4 秒 |

## 13. 并发、幂等与重试

- 所有写操作由服务端命令锁串行处理；多个手机、MCP 和投影可以同时连接。
- `pause`、`resume`、`stop` 和设置相同速度可安全重复调用。
- `score`、`seek` 和设置接口使用相同参数重复调用通常得到相同业务状态，但仍会产生新的
  WebSocket 事件。
- 网络超时不代表写操作一定没有执行。写请求超时后，先调用对应 GET 接口确认状态，避免
  盲目重放。
- 多客户端同时编辑布局或设置时没有 ETag、`If-Match` 或 revision 冲突保护，最后完成的
  写入生效。
- App 不应长期缓存服务端权威状态；恢复前台或 WebSocket 重连后应重新 GET。

## 14. TypeScript 参考类型

```ts
export type PlaybackStatus = "stopped" | "playing" | "paused";

export interface PlaybackSnapshot {
  status: PlaybackStatus;
  scoreId: string;
  durationMs: number;
  positionMs: number;
  anchorPositionMs: number;
  anchorClockMs: number;
  speed: number;
}

export interface ScoreSummary {
  id: string;
  title: string;
  durationMs: number;
  noteCount: number;
}

export interface ScoreNote {
  id: string;
  timeMs: number;
  noteKey: string;
  velocity: number;
}

export interface Score {
  schemaVersion: 1;
  id: string;
  title: string;
  durationMs: number;
  notes: ScoreNote[];
}

export interface LayoutPad {
  noteKey: string;
  x: number;
  y: number;
  radius: number;
  color: string;
  label: string;
  octaveLabel: string;
  audioAsset: string;
}

export interface Layout {
  schemaVersion: 1;
  revision: number;
  pads: LayoutPad[];
}

export interface EndingAnimationSettings {
  style: "calm" | "spectacular";
}

export interface ProjectionVisualSettings {
  showPerformanceInfo: boolean;
  approachRingWidth: number;
  approachRingOpacity: number;
  lowPadScale: number;
  midPadScale: number;
  highPadScale: number;
  centerPadScale: number;
}

export interface EventEnvelope<T extends Record<string, unknown>> {
  protocolVersion: 1;
  type: string;
  sequence: number;
  serverTimeMs: number;
  payload: T;
}
```

## 15. 当前未提供的能力

以下功能不在当前手机 API 中：

- 用户登录、令牌认证和权限管理；
- 设备发现和配网；
- 乐谱上传、编辑、删除；
- 音频流、录音、ASR 或 TTS；
- 文件管理、系统命令、重启或升级；
- 多设备云端同步；
- 分页、搜索和模糊乐谱匹配；
- 布局编辑冲突检测。

如 App 需要这些能力，应先扩展并版本化后端 API，不应通过 MCP、静态文件路径或未公开
内部接口绕过当前契约。
