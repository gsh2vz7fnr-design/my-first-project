import streamlit as st
import requests
import json

# 页面配置 - 设置为居中布局，更像聊天APP
st.set_page_config(
    page_title="AI育儿助手",
    page_icon="👶",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 自定义CSS - 美化界面并隐藏不必要的元素
st.markdown("""
<style>
    /* 隐藏 Streamlit 默认的汉堡菜单、Header 和 Footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 调整顶部空白，让内容更紧凑 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 5rem;
    }
    
    /* 美化聊天输入框 */
    .stChatInput {
        border-radius: 20px;
    }
    
    /* 侧边栏样式微调 */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #eee;
    }
</style>
""", unsafe_allow_html=True)

# API配置
API_URL = "http://localhost:8000/chat"
HEALTH_URL = "http://localhost:8000/health"

# 初始化会话状态 - 添加默认欢迎语
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant", 
            "content": "👋 您好！我是您的AI育儿助手。\n\n我可以帮您判断宝宝的健康状况，或者回答关于喂养、护理的问题。\n\n请告诉我宝宝怎么了？"
        }
    ]

# 侧边栏 - 极简设计
with st.sidebar:
    st.title("👶 育儿助手")
    st.caption("您的全天候育儿顾问")
    
    st.markdown("---")
    
    # 功能按钮
    if st.button("🗑️ 开启新对话", use_container_width=True, type="primary"):
        st.session_state.messages = [
            {
                "role": "assistant", 
                "content": "👋 您好！我是您的AI育儿助手。请告诉我宝宝怎么了？"
            }
        ]
        st.rerun()
    
    st.markdown("---")
    
    # 系统状态检测 (静默检测，只在出错时显示)
    try:
        requests.get(HEALTH_URL, timeout=1)
        st.success("🟢 服务在线")
    except:
        st.error("🔴 服务未连接")
        st.caption("请确保后端服务已启动")
        
    st.markdown("---")
    st.caption("⚠️ **免责声明**")
    st.caption("本服务仅供参考，不构成医疗诊断建议。**如遇紧急情况（如高烧不退、呼吸困难等），请立即前往医院就诊。**")

# 主聊天区域
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="👶" if message["role"] == "assistant" else "👤"):
        st.markdown(message["content"])

# 用户输入处理
if prompt := st.chat_input("输入您的问题..."):
    # 1. 显示用户消息
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)
    
    # 添加到历史
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2. 获取AI回复
    with st.chat_message("assistant", avatar="👶"):
        message_placeholder = st.empty()
        message_placeholder.markdown("Thinking...")
        
        try:
            response = requests.post(
                API_URL,
                json={"message": prompt},
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                response_text = result["response"]
                
                # 纯净展示，不显示任何技术元数据
                message_placeholder.markdown(response_text)
                
                # 添加到历史
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text
                })
            else:
                error_msg = "抱歉，我现在有点累，请稍后再试。"
                message_placeholder.markdown(error_msg)
                # 只有在开发模式下才打印具体错误，C端模式下保持安静
                print(f"API Error: {response.status_code}")

        except requests.exceptions.ConnectionError:
            error_msg = "⚠️ 无法连接到服务。请检查网络或联系管理员。"
            message_placeholder.markdown(error_msg)
        except Exception as e:
            error_msg = "抱歉，遇到了一点小问题，请重试。"
            message_placeholder.markdown(error_msg)
            print(f"Error: {str(e)}")
