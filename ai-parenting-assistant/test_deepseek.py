"""
测试DeepSeek API连接
快速验证API密钥是否配置正确
"""
import sys
import os
sys.path.append('./app')

from dotenv import load_dotenv
from llm_service import LLMService

# 加载环境变量
load_dotenv()

print("=" * 60)
print("DeepSeek API 连接测试")
print("=" * 60)

# 检查环境变量
print("\n【步骤1：检查环境变量】")
deepseek_key = os.getenv("DEEPSEEK_API_KEY")
openai_key = os.getenv("OPENAI_API_KEY")

if deepseek_key:
    print(f"✅ 检测到 DEEPSEEK_API_KEY: {deepseek_key[:10]}...")
elif openai_key:
    print(f"✅ 检测到 OPENAI_API_KEY: {openai_key[:10]}...")
else:
    print("❌ 未检测到API密钥")
    print("\n请创建 .env 文件并配置API密钥：")
    print("  DEEPSEEK_API_KEY=sk-your-key-here")
    print("\n或者：")
    print("  OPENAI_API_KEY=sk-your-key-here")
    sys.exit(1)

# 初始化LLM服务
print("\n【步骤2：初始化LLM服务】")
try:
    service = LLMService()
    print("✅ LLM服务初始化成功")
except Exception as e:
    print(f"❌ 初始化失败: {e}")
    sys.exit(1)

# 测试API调用
print("\n【步骤3：测试API调用】")
print("正在发送测试请求...")

test_query = "宝宝发烧了怎么办？"
test_context = "婴儿发烧的处理：当体温超过38.5度时，可以考虑使用退烧药。"

try:
    response = service.generate_response(
        user_query=test_query,
        context=test_context,
        intent="daily_care"
    )

    print("\n✅ API调用成功！")
    print("\n" + "=" * 60)
    print("测试问题：", test_query)
    print("=" * 60)
    print("\nAI回复：")
    print(response)
    print("\n" + "=" * 60)

    # 检查回复质量
    print("\n【步骤4：检查回复质量】")
    checks = {
        "包含安抚语言": any(word in response for word in ["理解", "担心", "别着急"]),
        "包含具体建议": len(response) > 100,
        "包含免责声明": "AI助手" in response or "仅供参考" in response,
        "没有诊断性语言": not any(word in response for word in ["诊断为", "确诊", "得了"])
    }

    for check, passed in checks.items():
        status = "✅" if passed else "⚠️"
        print(f"{status} {check}")

    all_passed = all(checks.values())

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！DeepSeek API配置成功！")
    else:
        print("⚠️ 部分测试未通过，但API连接正常")
    print("=" * 60)

    print("\n💡 下一步：")
    print("1. 运行 'python3 scripts/init_knowledge_base.py' 初始化知识库")
    print("2. 运行 'python3 app/main.py' 启动后端服务")
    print("3. 运行 'streamlit run frontend/streamlit_app.py' 启动前端界面")

except Exception as e:
    print(f"\n❌ API调用失败: {e}")
    print("\n可能的原因：")
    print("1. API密钥无效或已过期")
    print("2. 账户余额不足")
    print("3. 网络连接问题")
    print("4. API服务暂时不可用")
    print("\n请检查后重试")
    sys.exit(1)
