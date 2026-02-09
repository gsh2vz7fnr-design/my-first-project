#!/usr/bin/env python3
"""
RAG数据管道环境验证脚本

检查所有依赖是否正确安装
"""

import sys

def check_import(module_name, display_name=None):
    """检查模块是否可导入"""
    if display_name is None:
        display_name = module_name

    try:
        __import__(module_name)
        print(f"  [OK] {display_name}")
        return True
    except ImportError as e:
        print(f"  [FAIL] {display_name} - {e}")
        return False


def check_file(file_path, display_name=None):
    """检查文件是否存在"""
    from pathlib import Path

    if display_name is None:
        display_name = file_path

    if Path(file_path).exists():
        print(f"  [OK] {display_name}")
        return True
    else:
        print(f"  [FAIL] {display_name} - 文件不存在")
        return False


def main():
    print("="*60)
    print("RAG数据管道环境验证")
    print("="*60)
    print()

    # 检查Python版本
    print(f"Python版本: {sys.version}")
    print()

    # 检查依赖
    print("检查依赖包:")
    all_ok = True

    all_ok &= check_import("langchain", "langchain")
    all_ok &= check_import("langchain_openai", "langchain-openai")
    all_ok &= check_import("langchain_community", "langchain-community")
    all_ok &= check_import("langchain_text_splitters", "langchain-text-splitters")
    all_ok &= check_import("langchain_core", "langchain-core")
    all_ok &= check_import("chromadb", "chromadb")
    all_ok &= check_import("tiktoken", "tiktoken")
    all_ok &= check_import("tqdm", "tqdm")
    all_ok &= check_import("dotenv", "python-dotenv")

    print()

    # 检查文件
    print("检查文件:")
    from pathlib import Path
    SCRIPT_DIR = Path(__file__).parent
    PROJECT_ROOT = SCRIPT_DIR.parent

    all_ok &= check_file(SCRIPT_DIR / "ingest_md_to_vector.py", "ingest_md_to_vector.py")
    all_ok &= check_file(SCRIPT_DIR / "test_ingest_preview.py", "test_ingest_preview.py")

    # 检查数据文件
    all_ok &= check_file("/Users/zhang/Desktop/Claude/《美国儿科学会育儿百科》1-600.md", "数据文件 part1")
    all_ok &= check_file("/Users/zhang/Desktop/Claude/《美国儿科学会育儿百科》601-1054.md", "数据文件 part2")

    print()

    # 检查环境变量
    print("检查环境配置:")
    import os
    from dotenv import load_dotenv

    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"  [OK] .env文件已加载")

        if os.getenv("OPENAI_API_KEY"):
            print(f"  [OK] OPENAI_API_KEY已配置")
        else:
            print(f"  [WARN] OPENAI_API_KEY未配置（运行完整脚本需要）")
    else:
        print(f"  [WARN] .env文件不存在")

    print()
    print("="*60)

    if all_ok:
        print("验证通过！可以运行脚本了。")
        print()
        print("下一步:")
        print("  1. 运行测试预览: python scripts/test_ingest_preview.py")
        print("  2. 配置API密钥后运行: python scripts/ingest_md_to_vector.py")
    else:
        print("验证失败！请安装缺失的依赖。")
        print()
        print("运行: pip install -r requirements.txt")

    print("="*60)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
