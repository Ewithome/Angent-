"""DeepSeek 智能体 Streamlit 聊天界面。"""
from __future__ import annotations

import time

import requests
import streamlit as st

from agent_core import build_agent, get_final_answer, thread_config
import building_tools
import knowledge_base

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


def clear_harness_session(thread_id: str) -> None:
    """删除 Agent Harness 本地会话并清空界面消息。"""
    try:
        from harness.agent import get_gateway

        get_gateway().delete_session(thread_id)
    except Exception:  # noqa: BLE001
        pass
    st.session_state.messages = []


def check_api_status() -> str:
    """检测本地 FastAPI 服务是否可用。"""
    try:
        resp = requests.get(
            "http://127.0.0.1:8000/api/v1/health",
            timeout=2,
        )
        return "正常" if resp.status_code == 200 else f"异常（{resp.status_code}）"
    except requests.RequestException:
        return "未启动"


def _parse_key_value_lines(lines: list[str], field_name: str) -> dict[str, str]:
    """把每行 KEY=VALUE 的界面输入解析成配置字典。"""
    result: dict[str, str] = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "=" not in line:
            raise ValueError(f"{field_name} 中的 {line!r} 缺少 = 分隔符")
        key, _, value = line.partition("=")
        if not key.strip():
            raise ValueError(f"{field_name} 中的 KEY 不能为空")
        result[key.strip()] = value.strip()
    return result


def render_mcp_settings() -> None:
    """网页端 MCP 服务管理：查看、新增、编辑、删除与重新加载。"""
    from harness.agent import get_gateway
    from harness.mcp_config import McpServerConfig, get_mcp_store

    store = get_mcp_store()
    saved_message = st.session_state.pop("mcp_saved_message", "")
    if saved_message:
        st.success(saved_message)

    st.subheader("MCP 服务配置")
    st.caption("配置保存在本地 .mcp_servers.json，不会上传到 GitHub")

    servers = store.list_all()
    rows = [
        {
            "服务名称": server.name,
            "说明": server.label or server.description,
            "传输方式": server.transport,
            "状态": "内置" if server.builtin else ("启用" if server.enabled else "停用"),
            "命令/地址": server.command or server.url or "",
        }
        for server in servers
    ]
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)

    custom_servers = store.list_custom()
    st.markdown("#### 自定义服务")
    for server in custom_servers:
        col1, col2 = st.columns([5, 1])
        col1.write(f"**{server.name}** - {server.label or server.description or server.transport}")
        if col2.button("删除", key=f"delete-mcp-{server.name}", use_container_width=True):
            try:
                store.delete(server.name)
                get_gateway().reload_mcp_servers()
                st.session_state["mcp_saved_message"] = (
                    f"MCP 服务 {server.name} 已删除"
                )
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"删除失败：{exc}")
    if not custom_servers:
        st.write("暂无自定义 MCP 服务，可在下方添加。")

    st.markdown("#### 新增 / 编辑")
    target = st.selectbox(
        "编辑目标",
        ["新建 MCP 服务", *[server.name for server in custom_servers]],
    )
    current = store.get_custom(target) if target != "新建 MCP 服务" else None

    with st.form("mcp_server_form", clear_on_submit=current is None):
        col1, col2 = st.columns(2)
        with col1:
            server_name = st.text_input(
                "服务名称",
                value=current.name if current else "",
                disabled=current is not None,
                help="字母、数字、下划线、中划线，最长 32 位",
            )
            label = st.text_input("展示名称", value=current.label if current else "")
            description = st.text_input(
                "用途说明",
                value=current.description if current else "",
            )
            transport = st.selectbox(
                "传输方式",
                ["stdio", "streamable-http"],
                index=0 if current is None or current.transport == "stdio" else 1,
            )
            enabled = st.checkbox(
                "启用服务",
                value=True if current is None else current.enabled,
            )
            tool_call_timeout_ms = st.number_input(
                "工具超时（毫秒）",
                min_value=1000,
                max_value=600000,
                value=120000 if current is None else current.tool_call_timeout_ms,
                step=1000,
            )
            fail_on_startup_error = st.checkbox(
                "连接失败时中止 Harness",
                value=False if current is None else current.fail_on_startup_error,
            )
        with col2:
            command = st.text_input(
                "可执行程序（stdio）",
                value=current.command if current and current.command else "",
                placeholder=r"C:\路径\python.exe 或 npx",
            )
            args_text = st.text_area(
                "启动参数（每行一个）",
                value="\n".join(current.args) if current and current.args else "",
                height=90,
            )
            env_text = st.text_area(
                "环境变量（KEY=VALUE，每行一个）",
                value="\n".join(
                    f"{key}={value}"
                    for key, value in (current.env if current else {}).items()
                ),
                height=80,
            )
            cwd = st.text_input(
                "工作目录（stdio）",
                value=current.cwd if current and current.cwd else "",
            )
            url = st.text_input(
                "HTTP 端点地址",
                value=current.url if current and current.url else "",
                placeholder="http://localhost:3000/mcp",
            )
            headers_text = st.text_area(
                "HTTP 请求头（KEY=VALUE，每行一个）",
                value="\n".join(
                    f"{key}={value}"
                    for key, value in (current.headers if current else {}).items()
                ),
                height=80,
            )

        submitted = st.form_submit_button("保存 MCP 服务", use_container_width=True)
        if submitted:
            try:
                if not server_name:
                    raise ValueError("请填写服务名称")
                args = [line.strip() for line in args_text.splitlines() if line.strip()]
                config = McpServerConfig(
                    name=server_name,
                    label=label,
                    description=description,
                    transport=transport,
                    command=command.strip() or None,
                    args=args,
                    env=_parse_key_value_lines(env_text.splitlines(), "环境变量"),
                    cwd=cwd.strip() or None,
                    url=url.strip() or None,
                    headers=_parse_key_value_lines(headers_text.splitlines(), "HTTP 请求头"),
                    tool_call_timeout_ms=int(tool_call_timeout_ms),
                    fail_on_startup_error=fail_on_startup_error,
                    enabled=enabled,
                )
                store.upsert(config)
                get_gateway().reload_mcp_servers()
                st.session_state["mcp_saved_message"] = (
                    f"MCP 服务 {config.name} 已保存，Agent Harness 将在下次对话重新加载"
                )
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"保存失败：{exc}")


def render_skills_settings() -> None:
    """网页端技能管理：查看示例技能、新增和编辑 Agent Harness 技能。"""
    from harness.skills_store import delete_skill, list_skills, upsert_skill

    saved_message = st.session_state.pop("skill_saved_message", "")
    if saved_message:
        st.success(saved_message)

    st.subheader("Agent Harness 技能管理")
    st.caption("示例技能位于 skills/；新增技能写入本地 .skills/，不会上传 GitHub")

    skills = list_skills()
    rows = [
        {
            "技能名称": skill.name,
            "来源": "示例" if skill.source == "example" else "自定义",
            "用途": skill.description,
        }
        for skill in skills
    ]
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.write("暂无可用技能。")

    custom_skills = [skill for skill in skills if skill.source == "custom"]
    st.markdown("#### 自定义技能")
    for skill in custom_skills:
        col1, col2 = st.columns([5, 1])
        col1.write(f"**{skill.name}** - {skill.description}")
        if col2.button("删除", key=f"delete-skill-{skill.name}", use_container_width=True):
            try:
                delete_skill(skill.name)
                st.session_state["skill_saved_message"] = f"技能 {skill.name} 已删除"
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"删除失败：{exc}")
    if not custom_skills:
        st.write("暂无自定义技能，可在下方新增。")

    st.markdown("#### 新增 / 编辑")
    target = st.selectbox(
        "编辑目标",
        ["新建技能", *[skill.name for skill in custom_skills]],
    )
    current = next((skill for skill in custom_skills if skill.name == target), None)

    with st.form("skill_form", clear_on_submit=current is None):
        name = st.text_input(
            "技能名称",
            value=current.name if current else "",
            disabled=current is not None,
            placeholder="kebab-case，例如 spec-consultant",
        )
        description = st.text_input(
            "用途说明",
            value=current.description if current else "",
            max_chars=500,
        )
        when_to_use = st.text_input(
            "使用时机",
            value=current.when_to_use if current else "",
            max_chars=500,
        )
        content = st.text_area(
            "指令正文",
            value=current.content if current else "",
            height=260,
            help="只需填写 Markdown 正文，系统会自动生成 frontmatter",
        )

        submitted = st.form_submit_button("保存技能", use_container_width=True)
        if submitted:
            try:
                saved = upsert_skill(
                    name=name,
                    description=description,
                    when_to_use=when_to_use,
                    content=content,
                )
                st.session_state["skill_saved_message"] = (
                    f"技能 {saved.name} 已保存，Agent Harness 会自动发现"
                )
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"保存失败：{exc}")


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

page = st.sidebar.radio(
    "功能",
    ["智能体对话", "技能管理", "MCP 服务配置"],
    index=0,
)
if page == "技能管理":
    render_skills_settings()
    st.stop()
if page == "MCP 服务配置":
    render_mcp_settings()
    st.stop()

with st.sidebar:
    st.header("设置")

    engine = st.radio(
        "运行引擎",
        ["LangChain 智能体", "Agent Harness"],
        index=0,
        help="LangChain 为稳定默认引擎；Agent Harness 使用 DeepSeek 官方 Agent 运行时",
    )

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
            if engine == "Agent Harness":
                clear_harness_session(st.session_state.thread_id)
                # Harness 内存会话无法直接截断，清空后换新会话 ID 保证完全隔离
                st.session_state.thread_id = f"thread-{int(time.time())}"
            else:
                clear_session(agent, st.session_state.thread_id)
            st.rerun()

    st.divider()
    st.caption("能力")
    st.write(f"当前引擎：{engine}")
    st.write("- 规范检索：knowledge/ 知识库")
    st.write("- 用量计算：混凝土 / 砖墙 / 涂料 / 钢筋")
    st.write("- CAD 图纸：生成 DXF 平面图")
    st.write("- 计算器：安全数学计算")
    st.write("- 笔记管理：保存 / 列出 / 读取")

    st.divider()
    st.caption("开发")
    st.link_button("打开 FastAPI 接口文档", "http://localhost:8000/docs")

    st.divider()
    st.caption("系统状态")
    st.write(f"接口服务：{check_api_status()}")
    st.write(f"知识库文件：{knowledge_base.get_knowledge_file_count()} 个")

    st.divider()
    st.caption("图纸输出")
    cad_files = building_tools.list_cad_files()
    if cad_files:
        selected = st.selectbox("已生成图纸", [path.name for path in cad_files])
        st.download_button(
            "下载 DXF 图纸",
            data=(building_tools.OUTPUT_DIR / selected).read_bytes(),
            file_name=selected,
            mime="application/dxf",
        )
    else:
        st.write("暂无图纸，向智能体提问即可生成")

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
            if engine == "Agent Harness":
                # Harness 返回最终结果后统一展示；首次调用需要启动本地运行时
                from harness.agent import run_harness_chat

                status.write("正在启动 Agent Harness 运行时并调用领域工具...")
                full_text = run_harness_chat(prompt, st.session_state.thread_id)
            else:
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
            if engine == "Agent Harness":
                status.update(label="运行失败", state="error", expanded=True)
                st.error(f"Agent Harness 调用失败：{exc}")
                full_text = ""
            else:
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
