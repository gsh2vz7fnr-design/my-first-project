import streamlit as st
import time

# 页面配置
st.set_page_config(
    page_title="AI育儿助手",
    page_icon="👶",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 自定义CSS
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .block-container {
        padding-top: 2rem;
        padding-bottom: 5rem;
    }
    
    .stChatInput {
        border-radius: 20px;
    }
    
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #eee;
    }
</style>
""", unsafe_allow_html=True)

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant", 
            "content": "👋 您好！我是您的AI育儿助手（界面预览版）。\n\n我可以帮您判断宝宝的健康状况，或者回答关于喂养、护理的问题。\n\n请告诉我宝宝怎么了？"
        }
    ]

# 侧边栏
with st.sidebar:
    st.title("👶 育儿助手")
    st.caption("您的全天候育儿顾问")
    
    st.markdown("---")
    
    if st.button("🗑️ 开启新对话", use_container_width=True, type="primary"):
        st.session_state.messages = [
            {
                "role": "assistant", 
                "content": "👋 您好！我是您的AI育儿助手。请告诉我宝宝怎么了？"
            }
        ]
        st.rerun()
        
    st.markdown("---")
    st.warning("⚠️ **这是预览模式**")
    st.info("完整功能需要连接后端服务。")
    st.caption("请运行 `python3 app/main.py` 启动后端。")

# 主聊天区域
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="👶" if message["role"] == "assistant" else "👤"):
        st.markdown(message["content"])

# 用户输入处理
if prompt := st.chat_input("输入您的问题..."):
    # 显示用户消息
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)
    
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 模拟AI回复
    with st.chat_message("assistant", avatar="👶"):
        with st.spinner("Thinking..."):
            time.sleep(1) # 模拟延迟
            response_text = f"收到您的问题：“{prompt}”\n\n这是一个演示回复。在真实环境中，我会根据您的描述提供专业的育儿建议。\n\n💡 **提示**：目前处于预览模式，未连接真实的大模型。"
            st.markdown(response_text)
            
        st.session_state.messages.append({
            "role": "assistant",
            "content": response_text
        })
