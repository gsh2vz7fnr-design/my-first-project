#!/usr/bin/env python3
"""
测试硅基流动Embedding API

用法:
    python scripts/test_siliconflow_api.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 加载环境变量
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"已加载环境变量: {env_file}")
else:
    print(f"警告: 未找到.env文件: {env_file}")
    sys.exit(1)

# 获取配置
api_key = os.getenv("SILICONFLOW_API_KEY")
api_base = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
model = os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")

print(f"\n配置信息:")
print(f"  API Base: {api_base}")
print(f"  Model: {model}")
print(f"  API Key: {api_key[:20]}...{api_key[-4:] if api_key else 'None'}")

# 测试API
print(f"\n正在测试Embedding API...")

try:
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=api_base
    )

    # 测试embedding
    response = client.embeddings.create(
        model=model,
        input=["这是一个测试文本。"]
    )

    embedding = response.data[0].embedding
    print(f"\n成功!")
    print(f"  Embedding维度: {len(embedding)}")
    print(f"  前5个值: {embedding[:5]}")

except ImportError:
    print("\n错误: 需要安装openai库")
    print("运行: pip install openai")
    sys.exit(1)
except Exception as e:
    print(f"\n错误: {e}")
    print("\n请检查:")
    print("  1. SILICONFLOW_API_KEY是否正确")
    print("  2. SILICONFLOW_BASE_URL是否正确")
    print("  3. 模型名称是否正确")
    sys.exit(1)
