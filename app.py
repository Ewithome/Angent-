"""DeepSeek 智能体 Streamlit 聊天界面。"""
from __future__ import annotations

import time

import streamlit as st

from agent_core import build_agent, thread_config

st.set_page_config(page_title="DeepSeek 智能体", page_icon="🤖", layout="wide")


@st.cache_resource
def get_agent():
    return build_agent()


try:
    agent = get_agent()
except ValueError as exc:
    st.error(f"配置错误：{exc}")
    st.stop()

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "default"
if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("DeepSeek 工作助理")

with st.sidebar:
    st.header("会话")
    new_thread_id = st.text_input("会话 ID", value=st.session_state.thread_id)
    if new_thread_id != st.session_state.thread_id:
        st.session_state.thread_id = new_thread_id
        st.session_state.messages = []
        st.rerun()

    if st.button("新建会话", use_container_width=True):
        st.session_state.thread_id = f"thread-{int(time.time())}"
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption("内置工具")
    st.write("- 计算器：安全数学计算")
    st.write("- 当前时间：日期与时间")
    st.write("- 天气查询：Open-Meteo 实时天气")
    st.write("- 笔记管理：保存 / 列出 / 读取")

    st.divider()
    st.caption("接口文档")
    st.link_button("打开 FastAPI 接口文档", "http://localhost:8000/docs")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("例如：北京天气怎么样？帮我算一下预算，再记一条待办"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    config = thread_config(st.session_state.thread_id)
    inputs = {"messages": [{"role": "user", "content": prompt}]}

    with st.chat_message("assistant"):
        placeholder = st.empty()
        status = st.status("智能体运行中...", expanded=False)
        full_text = ""

        try:
            for event in agent.stream(inputs, config=config, stream_mode="messages"):
                chunk = event[0]
                text = chunk.content if isinstance(chunk.content, str) else ""
                if text:
                    full_text += text
                    placeholder.markdown(f"{full_text}▌")
        except Exception:  # noqa: BLE001
            result = agent.invoke(inputs, config=config)
            full_text = next(
                (
                    m.content
                    for m in reversed(result["messages"])
                    if m.content and not getattr(m, "tool_calls", None)
                ),
                "运行完成",
            )

        status.update(label="运行完成", state="complete", expanded=False)
        placeholder.markdown(full_text or "运行完成")

    st.session_state.messages.append({"role": "assistant", "content": full_text or "运行完成"})
