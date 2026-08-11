#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PI_TARGET="${DRUMNEXT_PI_TARGET:-}"
REMOTE_DIR="${DRUMNEXT_PI_PATH:-/home/pi/DrumNext}"
BUILD_FRONTEND=true
SYNC_DEPENDENCIES=true
SYNC_RUNTIME_CONFIG=true
SYNC_MCP_CONFIG=true

usage() {
  cat <<'EOF'
用法：scripts/sync-to-pi.sh [SSH目标] [选项]

示例：
  scripts/sync-to-pi.sh pi@192.168.1.100
  scripts/sync-to-pi.sh drum-pi --path /opt/drumnext
  scripts/sync-to-pi.sh pi@192.168.1.100 --no-runtime-config

选项：
  --path PATH         树莓派上的项目目录，默认 /home/pi/DrumNext
  --no-build          不运行 npm run build，直接同步现有 dist
  --no-deps           同步后不在树莓派执行 uv sync
  --no-runtime-config 不同步布局、结束动画和投影视觉运行配置
  --no-mcp-config     不同步 config/xiaozhi-mcp.json
  -h, --help          显示帮助

也可使用环境变量：
  DRUMNEXT_PI_TARGET  SSH 目标，例如 pi@192.168.1.100 或 SSH config 别名
  DRUMNEXT_PI_PATH    远端项目目录
EOF
}

log() {
  printf '[DrumNext Sync] %s\n' "$*"
}

fail() {
  printf '[DrumNext Sync] 错误：%s\n' "$*" >&2
  exit 1
}

while (( $# > 0 )); do
  case "$1" in
    --path)
      (( $# >= 2 )) || fail "--path 缺少路径"
      REMOTE_DIR="$2"
      shift
      ;;
    --no-build)
      BUILD_FRONTEND=false
      ;;
    --no-deps)
      SYNC_DEPENDENCIES=false
      ;;
    --no-runtime-config)
      SYNC_RUNTIME_CONFIG=false
      ;;
    --no-mcp-config)
      SYNC_MCP_CONFIG=false
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --*)
      usage >&2
      fail "未知参数：$1"
      ;;
    *)
      [[ -z "${PI_TARGET}" ]] || fail "只能指定一个 SSH 目标"
      PI_TARGET="$1"
      ;;
  esac
  shift
done

[[ -n "${PI_TARGET}" ]] || {
  usage >&2
  fail "请指定 SSH 目标，例如 pi@192.168.1.100"
}
[[ "${PI_TARGET}" != -* && ! "${PI_TARGET}" =~ [[:space:]] ]] \
  || fail "SSH 目标格式无效"
[[ "${REMOTE_DIR}" == /* ]] || fail "远端项目目录必须是绝对路径"
[[ "${REMOTE_DIR}" =~ ^/[A-Za-z0-9._/-]+$ ]] \
  || fail "远端项目目录只能包含字母、数字、点、下划线、横线和斜杠"

command -v ssh >/dev/null 2>&1 || fail "未安装 ssh"
command -v rsync >/dev/null 2>&1 || fail "未安装 rsync"
if [[ "${BUILD_FRONTEND}" == true ]]; then
  command -v npm >/dev/null 2>&1 || fail "未安装 npm"
fi

cd "${PROJECT_ROOT}"

if [[ "${BUILD_FRONTEND}" == true ]]; then
  log "编译投影网页……"
  npm run build
fi
[[ -f "${PROJECT_ROOT}/dist/index.html" ]] \
  || fail "缺少 dist/index.html，请取消 --no-build 或先运行 npm run build"

if [[ "${SYNC_MCP_CONFIG}" == true \
  && ! -f "${PROJECT_ROOT}/config/xiaozhi-mcp.json" ]]; then
  fail "缺少 config/xiaozhi-mcp.json；如暂不需要同步可使用 --no-mcp-config"
fi

log "准备远端目录 ${PI_TARGET}:${REMOTE_DIR}"
ssh "${PI_TARGET}" \
  "mkdir -p -- '${REMOTE_DIR}/backend/drumnext' '${REMOTE_DIR}/backend/drumnext_mcp' '${REMOTE_DIR}/resources/scores' '${REMOTE_DIR}/config' '${REMOTE_DIR}/dist'"

log "同步项目入口和部署脚本……"
ROOT_FILES=(
  "./pyproject.toml"
  "./uv.lock"
  "./README.md"
  "./config/default-layout.json"
  "./config/xiaozhi-mcp.example.json"
  "./scripts/"
)
rsync -azR --info=progress2 \
  --exclude '__pycache__/' --exclude '*.py[cod]' \
  "${ROOT_FILES[@]}" "${PI_TARGET}:${REMOTE_DIR}/"

log "同步 FastAPI 和 MCP Python 代码……"
rsync -az --delete --info=progress2 \
  --exclude '__pycache__/' --exclude '*.py[cod]' \
  "${PROJECT_ROOT}/backend/drumnext/" \
  "${PI_TARGET}:${REMOTE_DIR}/backend/drumnext/"
rsync -az --delete --info=progress2 \
  --exclude '__pycache__/' --exclude '*.py[cod]' \
  "${PROJECT_ROOT}/backend/drumnext_mcp/" \
  "${PI_TARGET}:${REMOTE_DIR}/backend/drumnext_mcp/"

log "同步乐谱和生产网页……"
rsync -az --info=progress2 \
  "${PROJECT_ROOT}/resources/scores/" \
  "${PI_TARGET}:${REMOTE_DIR}/resources/scores/"
rsync -az --delete --info=progress2 \
  "${PROJECT_ROOT}/dist/" \
  "${PI_TARGET}:${REMOTE_DIR}/dist/"

if [[ "${SYNC_RUNTIME_CONFIG}" == true ]]; then
  RUNTIME_CONFIG_FILES=()
  for relative_path in \
    config/user-layout.json \
    config/ending-animation.json \
    config/projection-visuals.json; do
    if [[ -f "${PROJECT_ROOT}/${relative_path}" ]]; then
      RUNTIME_CONFIG_FILES+=("./${relative_path}")
    fi
  done
  if (( ${#RUNTIME_CONFIG_FILES[@]} > 0 )); then
    log "同步运行配置……"
    rsync -azR --info=progress2 \
      "${RUNTIME_CONFIG_FILES[@]}" "${PI_TARGET}:${REMOTE_DIR}/"
  fi
fi

if [[ "${SYNC_MCP_CONFIG}" == true ]]; then
  log "同步 MCP 私有配置……"
  rsync -azR --info=progress2 \
    "./config/xiaozhi-mcp.json" "${PI_TARGET}:${REMOTE_DIR}/"
  ssh "${PI_TARGET}" "chmod 600 -- '${REMOTE_DIR}/config/xiaozhi-mcp.json'"
fi

if [[ "${SYNC_DEPENDENCIES}" == true ]]; then
  log "在树莓派同步 Python 依赖……"
  ssh "${PI_TARGET}" "cd -- '${REMOTE_DIR}' && if command -v uv >/dev/null 2>&1; then uv sync --frozen --no-dev; elif [ -x \"\$HOME/.local/bin/uv\" ]; then \"\$HOME/.local/bin/uv\" sync --frozen --no-dev; else echo '远端未找到 uv' >&2; exit 127; fi"
fi

log "同步完成"
printf '\n远端启动命令：\n  ssh -t %q "cd -- %q && ./scripts/start-all.sh"\n' \
  "${PI_TARGET}" "${REMOTE_DIR}"
