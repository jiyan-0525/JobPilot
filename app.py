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

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask me about weather or math..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate AI response
    with st.chat_message("assistant"):
        with st.spinner("AI is thinking..."):
            response = chat_with_tools(prompt)
        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

# Sidebar: Available tools
with st.sidebar:
    st.header("🛠️ Available Tools")
    st.info("**Calculator** - Math calculations (+, -, *, /, **)")
    st.info("**Weather** - Real-time weather worldwide")
    st.caption("Supports Beijing, Shanghai, Berlin, and more")


