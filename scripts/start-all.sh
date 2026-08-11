#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${PROJECT_ROOT}/.runtime"
LOG_DIR="${PROJECT_ROOT}/logs"
MCP_CONFIG="${DRUMNEXT_MCP_CONFIG:-${PROJECT_ROOT}/config/xiaozhi-mcp.json}"
PROJECTION_URL="${DRUMNEXT_PROJECTION_URL:-http://127.0.0.1:8000}"
HEALTH_URL="${DRUMNEXT_HEALTH_URL:-${PROJECTION_URL}/api/v1/health}"
STARTUP_TIMEOUT_SECONDS="${DRUMNEXT_STARTUP_TIMEOUT_SECONDS:-60}"
BROWSER_MODE="kiosk"
BROWSER_ENABLED=true
BACKEND_PID=""
MCP_PID=""
BROWSER_PID=""

usage() {
  cat <<'EOF'
用法：scripts/start-all.sh [选项]

一键启动 DrumNext FastAPI、MCP 服务和投影网页。

选项：
  --windowed    使用普通浏览器窗口，不进入 kiosk 全屏
  --no-browser  只启动 FastAPI 和 MCP，不打开浏览器
  -h, --help    显示帮助

环境变量：
  DRUMNEXT_MCP_CONFIG               MCP 配置文件路径
  DRUMNEXT_PROJECTION_URL           投影页面地址
  DRUMNEXT_HEALTH_URL               FastAPI 健康检查地址
  DRUMNEXT_STARTUP_TIMEOUT_SECONDS  后端启动超时秒数，默认 60
  DRUMNEXT_BROWSER                  Chromium 可执行文件路径
EOF
}

log() {
  printf '[DrumNext] %s\n' "$*"
}

fail() {
  printf '[DrumNext] 错误：%s\n' "$*" >&2
  exit 1
}

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  log "正在停止服务……"
  for pid in "${BROWSER_PID}" "${MCP_PID}" "${BACKEND_PID}"; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
    fi
  done
  for pid in "${BROWSER_PID}" "${MCP_PID}" "${BACKEND_PID}"; do
    if [[ -n "${pid}" ]]; then
      wait "${pid}" 2>/dev/null || true
    fi
  done
  exit "${exit_code}"
}

find_uv() {
  if [[ -n "${UV_BIN:-}" && -x "${UV_BIN}" ]]; then
    printf '%s\n' "${UV_BIN}"
  elif command -v uv >/dev/null 2>&1; then
    command -v uv
  elif [[ -x "${HOME}/.local/bin/uv" ]]; then
    printf '%s\n' "${HOME}/.local/bin/uv"
  else
    return 1
  fi
}

find_browser() {
  local candidate
  if [[ -n "${DRUMNEXT_BROWSER:-}" ]]; then
    [[ -x "${DRUMNEXT_BROWSER}" ]] || return 1
    printf '%s\n' "${DRUMNEXT_BROWSER}"
    return
  fi
  for candidate in chromium chromium-browser google-chrome; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      command -v "${candidate}"
      return
    fi
  done
  return 1
}

prepare_desktop_environment() {
  local user_id
  user_id="$(id -u)"
  if [[ -z "${XDG_RUNTIME_DIR:-}" && -d "/run/user/${user_id}" ]]; then
    export XDG_RUNTIME_DIR="/run/user/${user_id}"
  fi
  if [[ -z "${WAYLAND_DISPLAY:-}" && -n "${XDG_RUNTIME_DIR:-}" \
    && -S "${XDG_RUNTIME_DIR}/wayland-0" ]]; then
    export WAYLAND_DISPLAY="wayland-0"
  fi
  if [[ -z "${DISPLAY:-}" && -S /tmp/.X11-unix/X0 ]]; then
    export DISPLAY=":0"
  fi
  if [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" && -n "${XDG_RUNTIME_DIR:-}" \
    && -S "${XDG_RUNTIME_DIR}/bus" ]]; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
  fi
}

wait_for_backend() {
  local deadline=$((SECONDS + STARTUP_TIMEOUT_SECONDS))
  while (( SECONDS < deadline )); do
    if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
      tail -n 30 "${LOG_DIR}/backend.log" >&2 || true
      fail "FastAPI 启动失败，请查看 ${LOG_DIR}/backend.log"
    fi
    if curl --silent --fail --max-time 2 "${HEALTH_URL}" >/dev/null; then
      return
    fi
    sleep 1
  done
  tail -n 30 "${LOG_DIR}/backend.log" >&2 || true
  fail "等待 FastAPI 超时：${HEALTH_URL}"
}

while (( $# > 0 )); do
  case "$1" in
    --windowed)
      BROWSER_MODE="windowed"
      ;;
    --no-browser)
      BROWSER_ENABLED=false
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      fail "未知参数：$1"
      ;;
  esac
  shift
done

[[ "${STARTUP_TIMEOUT_SECONDS}" =~ ^[1-9][0-9]*$ ]] \
  || fail "DRUMNEXT_STARTUP_TIMEOUT_SECONDS 必须是正整数"
command -v curl >/dev/null 2>&1 || fail "未安装 curl"
UV_COMMAND="$(find_uv)" || fail "未找到 uv，请先安装：https://docs.astral.sh/uv/"
[[ -f "${PROJECT_ROOT}/pyproject.toml" ]] || fail "缺少 pyproject.toml"
[[ -f "${PROJECT_ROOT}/uv.lock" ]] || fail "缺少 uv.lock"
[[ -f "${PROJECT_ROOT}/dist/index.html" ]] \
  || fail "缺少 dist/index.html，请先在开发机执行 npm run build 并同步 dist"
[[ -f "${MCP_CONFIG}" ]] \
  || fail "缺少 MCP 配置：${MCP_CONFIG}；可从 config/xiaozhi-mcp.example.json 复制"

mkdir -p "${RUNTIME_DIR}" "${LOG_DIR}"
if command -v flock >/dev/null 2>&1; then
  exec 9>"${RUNTIME_DIR}/start-all.lock"
  flock -n 9 || fail "启动脚本已在运行"
fi

trap cleanup EXIT INT TERM
cd "${PROJECT_ROOT}"

log "启动 FastAPI……"
"${UV_COMMAND}" run --frozen --no-dev drumnext \
  >>"${LOG_DIR}/backend.log" 2>&1 &
BACKEND_PID=$!
wait_for_backend
log "FastAPI 已就绪：${PROJECTION_URL}"

log "启动 MCP 服务……"
"${UV_COMMAND}" run --frozen --no-dev drumnext-mcp --config "${MCP_CONFIG}" \
  >>"${LOG_DIR}/mcp.log" 2>&1 &
MCP_PID=$!
sleep 1
if ! kill -0 "${MCP_PID}" 2>/dev/null; then
  tail -n 30 "${LOG_DIR}/mcp.log" >&2 || true
  fail "MCP 服务启动失败，请查看 ${LOG_DIR}/mcp.log"
fi
log "MCP 服务已启动"

if [[ "${BROWSER_ENABLED}" == true ]]; then
  BROWSER_COMMAND="$(find_browser)" \
    || fail "未找到 Chromium；可通过 DRUMNEXT_BROWSER 指定浏览器路径"
  prepare_desktop_environment
  BROWSER_ARGUMENTS=(
    "--noerrdialogs"
    "--disable-infobars"
    "--disable-session-crashed-bubble"
    "--autoplay-policy=no-user-gesture-required"
    "--user-data-dir=${RUNTIME_DIR}/chromium-profile"
  )
  if [[ "${BROWSER_MODE}" == "kiosk" ]]; then
    BROWSER_ARGUMENTS+=("--kiosk")
  fi
  log "打开投影页面：${PROJECTION_URL}"
  "${BROWSER_COMMAND}" "${BROWSER_ARGUMENTS[@]}" "${PROJECTION_URL}" \
    >>"${LOG_DIR}/browser.log" 2>&1 &
  BROWSER_PID=$!
fi

log "全部启动完成；按 Ctrl+C 停止。日志目录：${LOG_DIR}"
if [[ "${BROWSER_ENABLED}" == true ]]; then
  wait -n "${BACKEND_PID}" "${MCP_PID}" "${BROWSER_PID}" || true
else
  wait -n "${BACKEND_PID}" "${MCP_PID}" || true
fi
fail "有进程意外退出，请检查 ${LOG_DIR}"
