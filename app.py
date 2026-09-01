"""DeepSeek 智能体 Streamlit 聊天界面。"""
from __future__ import annotations

import time

import streamlit as st

from agent_core import build_agent, get_final_answer, thread_config

st.set_page_config(page_title="建筑规范图集智能体", page_icon="🏗️", layout="wide")


@st.cache_resource
def get_agent():
    # 整个应用复用同一个 Agent 实例，避免重复加载模型和数据库连接
    return build_agent()


def clear_session(agent, thread_id: str) -> None:
    """删除持久化记忆并清空界面消息。"""
    try:
        agent.checkpointer.delete_thread(thread_id)
    except Exception:  # noqa: BLE001
        # 即使删除失败也先清空界面，方便用户继续使用
        pass
    st.session_state.messages = []


try:
    agent = get_agent()
except ValueError as exc:
    st.error(f"配置错误：{exc}")
    st.stop()

# 初始化会话状态
if "thread_id" not in st.session_state:
    st.session_state.thread_id = "default"
if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("建筑规范图集智能体")

with st.sidebar:
    st.header("设置")

    st.caption("会话")
    new_thread_id = st.text_input("会话 ID", value=st.session_state.thread_id)
    if new_thread_id != st.session_state.thread_id:
        st.session_state.thread_id = new_thread_id
        st.session_state.messages = []
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("新建会话", use_container_width=True):
            st.session_state.thread_id = f"thread-{int(time.time())}"
            st.session_state.messages = []
            st.rerun()

    with col2:
        if st.button("清空当前会话", use_container_width=True):
            clear_session(agent, st.session_state.thread_id)
            st.rerun()

    st.divider()
    st.caption("能力")
    st.write("- 规范检索：knowledge/ 知识库")
    st.write("- 用量计算：混凝土 / 砖墙 / 涂料 / 钢筋")
    st.write("- CAD 图纸：生成 DXF 平面图")
    st.write("- 计算器：安全数学计算")
    st.write("- 笔记管理：保存 / 列出 / 读取")

    st.divider()
    st.caption("开发")
    st.link_button("打开 FastAPI 接口文档", "http://localhost:8000/docs")

# 展示历史消息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("例如：住宅楼梯踏步高度有什么要求？帮我算 10m×5m×0.2m 混凝土用量，再生成一张平面图"):
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
            # 同时订阅 token 流和节点更新，节点更新用于展示工具调用过程
            for event in agent.stream(
                inputs,
                config=config,
                stream_mode=["messages", "updates"],
            ):
                mode, payload = event
                if mode == "messages":
                    chunk, _metadata = payload
                    text = chunk.content if isinstance(chunk.content, str) else ""
                    if text:
                        full_text += text
                        placeholder.markdown(f"{full_text}▌")
                elif mode == "updates":
                    for node_name, update in payload.items():
                        if node_name == "tools":
                            for tool_message in update.get("messages", []):
                                tool_name = getattr(tool_message, "name", "")
                                if tool_name:
                                    status.write(f"正在调用工具：{tool_name}")
        except Exception as exc:  # noqa: BLE001
            # 流式接口异常时退回一次性调用，保证用户仍然拿到回答
            try:
                result = agent.invoke(inputs, config=config)
                full_text = get_final_answer(result)
                status.update(label="运行完成", state="complete", expanded=False)
            except Exception as invoke_exc:  # noqa: BLE001
                status.update(label="运行失败", state="error", expanded=True)
                st.error(f"智能体调用失败：{invoke_exc}")
                full_text = ""

        if full_text:
            status.update(label="运行完成", state="complete", expanded=False)
            placeholder.markdown(full_text)
            st.session_state.messages.append(
                {"role": "assistant", "content": full_text}
            )
