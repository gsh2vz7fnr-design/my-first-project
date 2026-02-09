#!/bin/bash
# RAG数据管道环境设置脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "========================================="
echo "RAG数据管道环境设置"
echo "========================================="
echo ""

# 检查Python3
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到python3命令"
    exit 1
fi

echo "Python版本: $(python3 --version)"
echo ""

# 创建虚拟环境
VENV_DIR="$PROJECT_ROOT/venv"

if [ -d "$VENV_DIR" ]; then
    echo "虚拟环境已存在: $VENV_DIR"
else
    echo "创建虚拟环境: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source "$VENV_DIR/bin/activate"

# 升级pip
echo "升级pip..."
pip install --upgrade pip -q

# 安装依赖
echo "安装依赖..."
pip install -r "$PROJECT_ROOT/requirements.txt"

echo ""
echo "========================================="
echo "设置完成！"
echo "========================================="
echo ""
echo "使用方法："
echo ""
echo "  1. 激活虚拟环境:"
echo "     source $VENV_DIR/bin/activate"
echo ""
echo "  2. 运行测试预览:"
echo "     python scripts/test_ingest_preview.py"
echo ""
echo "  3. 配置API密钥后运行完整脚本:"
echo "     python scripts/ingest_md_to_vector.py"
echo ""
