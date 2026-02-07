#!/bin/bash
# 智能儿科分诊与护理助手 - 启动脚本

echo "======================================"
echo "  智能儿科分诊与护理助手"
echo "======================================"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装"
    exit 1
fi

echo "✓ Python3: $(python3 --version)"
echo ""

# 检查后端依赖
echo "📦 检查后端依赖..."
cd backend

# 安装依赖（如果需要）
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "正在安装后端依赖..."
    pip3 install -r requirements.txt
fi

# 检查环境变量
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件"
    echo "正在创建 .env 文件..."
    cat > .env << 'EOF'
# DeepSeek API配置
DEEPSEEK_API_KEY=your-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# 调试模式
DEBUG=True
EOF
    echo "⚠️  请编辑 .env 文件填入正确的 API Key"
fi

echo ""
echo "======================================"
echo "  启动选项"
echo "======================================"
echo "1. 启动后端服务"
echo "2. 运行评估测试"
echo "3. 检查系统状态"
echo "4. 退出"
echo ""
read -p "请选择 [1-4]: " choice

case $choice in
    1)
        echo ""
        echo "🚀 启动后端服务..."
        echo "服务地址: http://localhost:8000"
        echo "API文档: http://localhost:8000/docs"
        echo ""
        echo "按 Ctrl+C 停止服务"
        echo ""
        python3 app/main.py
        ;;
    2)
        echo ""
        echo "🧪 运行评估测试..."
        echo ""
        python3 evaluation/run_evaluation.py \
            --test-file app/data/test_cases.json \
            --output-file evaluation_report.json
        ;;
    3)
        echo ""
        echo "🔍 检查系统状态..."
        echo ""

        # 检查Python模块
        echo "Python模块:"
        python3 -c "import fastapi" && echo "  ✓ fastapi" || echo "  ✗ fastapi"
        python3 -c "import uvicorn" && echo "  ✓ uvicorn" || echo "  ✗ uvicorn"
        python3 -c "import openai" && echo "  ✓ openai" || echo "  ✗ openai"
        echo ""

        # 检查数据文件
        echo "数据文件:"
        ls -1 app/data/knowledge_base/*.json 2>/dev/null | wc -l | xargs echo "  知识库文件:"
        ls -1 app/data/blacklist/*.txt 2>/dev/null | wc -l | xargs echo "  黑名单文件:"
        ls -1 app/data/triage_rules/*.json 2>/dev/null | wc -l | xargs echo "  分诊规则文件:"
        echo ""

        # 语法检查
        echo "语法检查:"
        python3 -m py_compile app/main.py && echo "  ✓ main.py" || echo "  ✗ main.py"
        python3 -m py_compile app/routers/chat.py && echo "  ✓ chat.py" || echo "  ✗ chat.py"
        python3 -m py_compile services/stream_filter.py && echo "  ✓ stream_filter.py" || echo "  ✗ stream_filter.py"
        ;;
    4)
        echo "退出"
        exit 0
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac
