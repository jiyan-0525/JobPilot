import streamlit as st
import sys
import os
from dotenv import load_dotenv

sys.path.append(".")
from agent import chat_with_tools

load_dotenv()

st.set_page_config(
    page_title="AI Agent Chat",
    page_icon="🤖",
    layout="wide"
)

st.title("🚀 AI Agent Chat - Week2")
st.markdown("**Calculator + Weather Tools** | Groq + Llama 3.1")

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# 显示聊天历史
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 聊天输入
if prompt := st.chat_input("问我天气或计算题..."):
    # 添加用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 生成AI回复
    with st.chat_message("assistant"):
        with st.spinner("AI正在思考..."):
            response = chat_with_tools(prompt)
        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

# 侧边栏：工具展示
with st.sidebar:
    st.header("🛠️ Available Tools")
    st.info("**Calculator** - 数学计算")
    st.info("**Weather** - 城市天气")
    st.caption("支持北京、上海、Berlin等")

