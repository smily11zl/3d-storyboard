#!/bin/bash
# 一键安装所有依赖
# Usage: ./install.sh
# 幂等：重复运行只补装缺失的依赖，不会破坏已有环境。
#
# 依赖清单：
#   1. Python 3.11（后端运行环境）
#   2. Node.js + npm（前端构建）
#   3. Blender 4.4.x（.blend 转 glTF + AI 生成，可选但强烈建议）
#   4. 后端 Python 包（.venv + requirements.txt，含 hermes-agent）
#   5. 前端 npm 包（frontend/package.json）

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

echo "========================================="
echo "  Storyboard 3D Pipeline — 安装依赖"
echo "========================================="
echo ""

# ── [1/5] Python 3.11 ──────────────────────────────────────────────
echo "[1/5] 检查 Python 3.11 ..."
PYTHON_BIN=""
for candidate in python3.11 python3; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
        if [ "$version" = "3.11" ]; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    echo -e "${RED}  [FAIL] 未找到 Python 3.11。安装: brew install python@3.11${NC}"
    exit 1
fi
echo -e "${GREEN}  [OK] Python 3.11 ($PYTHON_BIN)${NC}"

# ── [2/5] Node.js ─────────────────────────────────────────────────
echo "[2/5] 检查 Node.js + npm ..."
if ! command -v node &>/dev/null || ! command -v npm &>/dev/null; then
    echo -e "${RED}  [FAIL] 未找到 Node.js/npm。安装: brew install node${NC}"
    exit 1
fi
echo -e "${GREEN}  [OK] Node.js $(node --version) / npm $(npm --version)${NC}"

# ── [3/5] Blender ─────────────────────────────────────────────────
echo "[3/5] 检查 Blender ..."
if command -v blender &>/dev/null; then
    echo -e "${GREEN}  [OK] Blender $(blender --version 2>/dev/null | head -1)${NC}"
else
    echo -e "${YELLOW}  [WARN] 未找到 Blender —— .blend 转换和 AI 生成将不可用。${NC}"
    echo -e "${YELLOW}         安装: brew install --cask blender  （需 4.4.x）${NC}"
fi

# ── [4/5] 后端依赖 ────────────────────────────────────────────────
echo "[4/5] 安装后端依赖（Python venv + pip）..."
if [ ! -d ".venv" ]; then
    echo "  创建虚拟环境 .venv ..."
    "$PYTHON_BIN" -m venv .venv
else
    echo "  .venv 已存在，跳过创建"
fi
echo "  升级 pip ..."
.venv/bin/pip install --upgrade pip -q
echo "  安装 requirements.txt（含 hermes-agent，可能需要几分钟）..."
.venv/bin/pip install -r requirements.txt
echo -e "${GREEN}  [OK] 后端依赖安装完成${NC}"

# ── [5/5] 前端依赖 ────────────────────────────────────────────────
echo "[5/5] 安装前端依赖（npm install）..."
cd frontend
npm install
cd "$SCRIPT_DIR"
echo -e "${GREEN}  [OK] 前端依赖安装完成${NC}"

echo ""
echo "========================================="
echo -e "  ${GREEN}${BOLD}安装完成！${NC}"
echo ""
echo "  下一步:"
echo "    1. 启动服务:   ./start.sh"
echo "    2. 打开页面:   http://localhost:5173"
echo "    3. 点 ⚙（右上）配置 DeepSeek API key"
echo ""
echo "  （若上面 Blender 显示 [WARN]，请先安装 Blender 再启动）"
echo "========================================="
