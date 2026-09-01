# DeepSeek 智能体实战项目

基于 **LangChain v1 + LangGraph v1** 构建的 DeepSeek 个人助理智能体，支持工具调用、SQLite 会话记忆、Streamlit 网页聊天和命令行交互。

## 项目特点

- 使用 LangChain v1 最新的 `create_agent`，替代已弃用的 `langgraph.prebuilt.create_react_agent`
- DeepSeek 通过 OpenAI 兼容接口接入，无需额外框架
- SQLite checkpointer 持久化多轮会话记忆
- 内置 6 个工具：数学计算、当前时间、真实天气、保存/列出/读取本地笔记
- Streamlit 流式输出界面 + 命令行 REPL 两种使用方式
- 企业级 FastAPI 接口层：版本化路由、统一响应、异常处理、请求追踪、日志、会话管理
- 旧版 LangChain 0.2 demo 保留在 `legacy/`，方便对比学习

## 快速开始

要求 Python 3.9+，建议 3.12。

```bash
git clone https://github.com/Ewithome/Angent-.git
cd Agent-
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

国内网络如果安装慢，可以加清华镜像参数：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

Windows PowerShell 激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

然后创建环境变量文件并填入 DeepSeek Key：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，把 `DEEPSEEK_API_KEY` 替换成你的真实 Key。

`.env` 已加入 `.gitignore`，不会上传到 GitHub。

## 运行

网页聊天界面：

```bash
streamlit run app.py
```

命令行：

```bash
python cli.py
```

命令行指定独立会话：

```bash
python cli.py --thread demo-1
```

企业级接口服务：

```bash
uvicorn api.main:app --reload --port 8000
```

启动后访问接口文档：<http://localhost:8000/docs>

一键启动脚本（PowerShell）：

```powershell
.\scripts\run_api.ps1
.\scripts\run_web.ps1
```

## 测试

运行全部测试：

```bash
python -m unittest discover -s tests -v
```

测试覆盖安全计算器、笔记工具、API 健康检查、参数校验；配置了真实 DeepSeek Key 时还会自动执行对话和会话管理接口测试。

## 接口说明

所有接口都返回统一响应格式：

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "request_id": "生成的请求追踪ID"
}
```

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/health` | 健康检查 |
| POST | `/api/v1/chat` | 发送消息给智能体 |
| GET | `/api/v1/sessions/{session_id}/messages` | 获取会话消息 |
| DELETE | `/api/v1/sessions/{session_id}` | 删除会话 |

对话接口请求示例：

```json
{
  "message": "北京今天天气怎么样？",
  "session_id": "demo-1"
}
```

## 试试这些问题

- 帮我算一下 `(123 + 456) * 7 - 20 / 4`
- 现在几点？
- 北京今天天气怎么样？
- 记一条待办：明天上午 9 点给客户回邮件
- 我有哪些笔记？把待办笔记读出来
- 帮我计算 2 的 16 次方，然后保存成一条笔记

## 项目结构

```text
.
├── agent_core.py           # 工具、模型、记忆、create_agent 组装
├── app.py                  # Streamlit 网页界面
├── cli.py                  # 命令行入口
├── api/                    # 企业级 FastAPI 接口层
│   ├── main.py             # 应用入口与统一异常处理
│   ├── config.py           # 环境配置
│   ├── schemas.py          # 请求与响应模型
│   └── routers/            # 健康检查、对话、会话路由
├── tests/                  # 工具与接口自动化测试
├── scripts/                # 一键启动脚本
├── requirements.txt        # 新版依赖
├── requirements-legacy.txt # 旧版 demo 依赖
├── legacy/
│   └── agent_demo.py       # LangChain 0.2 旧 demo
├── notes/                  # 智能体保存的本地笔记
└── .env.example            # 环境变量模板
```

## 技术说明

`create_agent` 是 LangChain 1.0 构建智能体的标准方式，底层运行在 LangGraph 上，自动支持工具循环、多轮记忆、流式输出、持久化和人工介入。项目把检查点存在 `agent_memory.db`，会话记忆按 `thread_id` 隔离。

## 常见问题

- 报 `DEEPSEEK_API_KEY` 错误：检查 `.env` 是否已创建且填写正确。
- 天气查询失败：Open-Meteo 请求失败时工具会返回演示兜底数据，不影响其他功能。
- 想运行旧版 demo：先安装 `requirements-legacy.txt`，再运行 `legacy/agent_demo.py`；新版项目不需要旧依赖。
