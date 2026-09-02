# 建筑规范图集智能体

基于 **LangChain v1 + DeepSeek Agent Harness + DeepSeek** 的企业内部知识库智能体，可以回答规范标准与制度流程问题、计算工程用量，并生成建筑平面示意 CAD 图纸。

## 项目特点

- 使用 LangChain v1 最新的 `create_agent`，替代已弃用的 `langgraph.prebuilt.create_react_agent`
- 可选接入 DeepSeek 官方 Agent Harness：通过内置 MCP 客户端把知识库、用量计算、CAD 工具注册给 Harness
- MCP 服务可配置：网页可新增/修改/删除 stdio 或 streamable-http 外部 MCP 服务，配置实时写入 `.mcp_servers.json`
- Skills 技能能力：Agent Harness 可发现并加载 `SKILL.md` 技能，网页可新增/编辑/删除自定义技能
- Harness 模式关闭默认终端/编辑器，只暴露受控领域工具，会话持久化到项目 `.harness_home/`
- 多格式文档清洗流水线：支持 PDF、Word、PPT、Markdown、TXT，含表格与幻灯片文本解析
- 语义分块 + 轻量向量检索：TF-IDF 字符级 n-gram，适合中文文档
- 混合检索：关键词 BM25 得分 + 向量余弦相似度加权
- RAG 评测体系：Hit@1/3/5、MRR，输出评测报告
- 伪标签生成：用 DeepSeek 从文档自动生成问答对，供检索效果调优
- 建筑用量计算：混凝土、砖墙、涂料、钢筋
- CAD 图纸生成：按房间参数输出 DXF 文件，可用 AutoCAD / LibreCAD 打开
- SQLite 持久化多轮会话记忆
- Streamlit 中文网页 + 命令行 REPL
- 企业级 FastAPI 接口层：版本化路由、统一响应、异常处理、请求追踪、日志、会话管理

## 快速开始

要求 Python 3.10+，建议 3.12（Agent Harness Python SDK 要求 3.10+）。

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

创建环境变量文件并填入 DeepSeek Key：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，把 `DEEPSEEK_API_KEY` 替换成你的真实 Key。`.env` 已加入 `.gitignore`，不会上传到 GitHub。

## 添加规范知识库

把规范文件放入 `knowledge/` 目录即可：

```text
knowledge/
├── README.md
├── 民用建筑设计统一标准.pdf
├── 建筑设计防火规范.docx
└── 住宅设计规范.md
```

支持 `.pdf`、`.docx`、`.pptx`、`.md`、`.txt`。文件放入后无需重启，智能体会在下次检索时自动重建索引。规范原文只保存在本地，不会上传到 GitHub。

## 运行

最省事的方式：双击根目录的 `start_all.bat`，脚本会自动创建虚拟环境、安装依赖，并同时启动接口服务和网页服务。

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

命令行切换 Agent Harness 引擎：

```bash
python cli.py --engine harness --thread demo-2
```

企业级接口服务：

```bash
uvicorn api.main:app --reload --port 8000
```

接口文档：<http://localhost:8000/docs>

一键启动脚本（PowerShell）：

```powershell
.\scripts\run_api.ps1
.\scripts\run_web.ps1
```

网页侧栏还提供：接口服务状态、知识库文件数量、已生成 DXF 图纸下载。

网页侧栏顶部可选择运行引擎：

- `LangChain 智能体`：使用现有 `create_agent` 稳定链路
- `Agent Harness`：启动 DeepSeek 官方 Harness，工具名形如 `mcp__building__search_knowledge`

首次切换 Agent Harness 时需要初始化本地 Harness home 并连接 MCP 工具服务，几秒后即可对话。

## MCP 服务配置

侧栏选择 `MCP 服务配置`，可管理 Agent Harness 能调用的 MCP 服务：

- 内置 `building` 服务：企业知识库、用量计算、CAD 图纸与项目纪要，不可删除
- 自定义 `stdio` 服务：配置可执行程序、启动参数、工作目录与环境变量
- 自定义 `streamable-http` 服务：配置端点地址与请求头

配置保存在项目根目录 `.mcp_servers.json`，该文件已加入 `.gitignore`，不会把第三方密钥上传到 GitHub。可直接复制 `mcp_servers.example.json` 查看 JSON 字段格式。

保存或删除服务后，当前进程内的 Agent Harness 会自动标记为需要重新加载，下一次对话使用新工具列表。也可以通过接口立即刷新：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/mcp/servers/reload
```

## Skills 技能

侧栏选择 `技能管理` 可查看和管理技能。技能是给 Agent 的可复用任务指令，Agent Harness 会在会话中自动展示技能目录，并在任务匹配时调用 `skill` 工具加载完整指令。

仓库示例技能位于 `skills/`：

```text
skills/
├── spec-consultant/SKILL.md   # 建筑规范条文核查与合规审图
└── quantity-review/SKILL.md   # 工程用量复核与计算
```

用户通过网页新增的自定义技能保存在项目本地 `.skills/`，该目录已加入 `.gitignore`。技能文件使用 YAML frontmatter：

```markdown
---
name: spec-consultant
description: 建筑规范条文核查技能，用于回答规范要求并给出来源。
whenToUse: 用户咨询规范要求或需要审图结论时使用。
---

先调用 mcp__building__search_knowledge 检索知识库，再引用来源作答。
```

技能名称必须是小写 kebab-case，例如 `fire-review`。保存后无需重启，Agent Harness 文件监视器会自动把新技能加入下次目录；用户也可以在对话中输入 `/技能名` 主动调用。

## Agent Harness 接入说明

Agent Harness 采用“一切皆插件”架构。本项目保留 LangChain 作为默认业务链路，并新增 `harness/` 接入层：

```text
harness/
├── agent.py       # Harness 配置、patch 生成、进程级复用、对话执行
├── mcp_config.py  # MCP 服务配置模型与本地 JSON 存储
├── mcp_server.py  # 内置知识库与建筑工具 MCP 服务
├── skills_store.py # Skills 目录解析与本地技能存储
└── __init__.py
```

自定义 MCP 配置示例见 `mcp_servers.example.json`。
示例技能见 `skills/`，自定义技能保存在本地 `.skills/`。

运行逻辑：

1. `run_harness_chat()` 首次调用时创建隔离的 `HARNESS_HOME` 与 `HARNESS_WORKSPACE`。
2. 自动生成一次启动专用 patch，使用当前 Python 解释器启动 `harness.mcp_server`。
3. Harness 内置 MCP 客户端发现工具后，模型可直接调用 `mcp__building__search_knowledge`、`mcp__building__generate_cad_drawing` 等工具。
4. 为降低任意命令执行风险，企业模式会禁用 `sdk-minimal` 自带的持久终端与文件编辑器。

可在 `.env` 中调整 Harness 参数：

```dotenv
HARNESS_MODEL=deepseek-chat
HARNESS_MAX_TOKENS=16384
HARNESS_HOME=.harness_home
HARNESS_WORKSPACE=.harness_workspace
MCP_CONFIG_FILE=.mcp_servers.json
```

真实 `DEEPSEEK_API_KEY` 仍只保存在本地 `.env`，不会上传到 GitHub。

## 检索与评测

构建知识库索引并查看分块统计：

```bash
python scripts/build_knowledge_index.py
```

运行 RAG 检索效果评测：

```bash
python scripts/evaluate_rag.py
```

评测报告保存到 `outputs/eval_report.json`，评测问题集在 `eval/questions.json`，可按业务替换。

使用 DeepSeek 从知识库文档生成伪标签问答对：

```bash
python scripts/generate_pseudo_labels.py --limit 5
```

生成的问答对保存到 `eval/pseudo_labels.jsonl`，可用于后续检索权重调优和嵌入模型领域适配。

## 测试

```bash
python -m unittest discover -s tests -v
```

测试覆盖安全计算器、混凝土/砖墙/涂料/钢筋计算、CAD 图纸生成、规范知识库检索、PPT 解析、混合检索、API 健康检查与参数校验；配置真实 DeepSeek Key 时还会自动执行对话和会话管理接口测试。

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
| POST | `/api/v1/chat` | 发送消息给智能体（body 可选 `engine`：`langchain` / `harness`） |
| GET | `/api/v1/sessions/{session_id}/messages` | 获取会话消息 |
| DELETE | `/api/v1/sessions/{session_id}` | 删除会话 |
| GET | `/api/v1/mcp/servers` | 获取 MCP 服务列表 |
| POST | `/api/v1/mcp/servers` | 新增 MCP 服务 |
| PUT | `/api/v1/mcp/servers/{name}` | 修改 MCP 服务 |
| DELETE | `/api/v1/mcp/servers/{name}` | 删除 MCP 服务 |
| POST | `/api/v1/mcp/servers/reload` | 让 Agent Harness 下次对话重新加载 MCP 服务 |
| GET | `/api/v1/skills` | 获取技能列表 |
| POST | `/api/v1/skills` | 新增技能 |
| PUT | `/api/v1/skills/{name}` | 更新技能 |
| DELETE | `/api/v1/skills/{name}` | 删除自定义技能 |

对话接口请求示例：

```json
{
  "message": "住宅楼梯踏步高度有什么要求？再帮我算 10m×5m×0.2m 的混凝土用量",
  "session_id": "building-demo",
  "engine": "harness"
}
```

## 试试这些问题

- 住宅楼梯踏步高度有什么规范要求？
- 帮我算 10m×5m×0.2m 的混凝土用量
- 帮我估算一堵 12m 长、3m 高、0.24m 厚的砖墙需要多少块砖
- 一个 4m×3m×2.8m 的房间刷漆，门窗共扣 3.5 平方米，需要多少涂料？
- 帮我生成一张 6m×4m 的建筑平面示意 CAD 图
- 记一条项目纪要：明天上午审查消防图纸

## 项目结构

```text
.
├── agent_core.py           # 工具、模型、记忆、create_agent 组装
├── building_tools.py       # 建筑用量计算与 CAD 图纸生成
├── knowledge_base.py       # 规范知识库检索
├── knowledge/              # 规范文件目录（只保存在本地）
├── outputs/cad/            # 生成的 DXF 图纸目录
├── eval/                   # RAG 评测问题集与伪标签
├── scripts/
│   ├── build_knowledge_index.py
│   ├── evaluate_rag.py
│   └── generate_pseudo_labels.py
├── app.py                  # Streamlit 网页界面
├── cli.py                  # 命令行入口
├── api/                    # 企业级 FastAPI 接口层
│   ├── main.py             # 应用入口与统一异常处理
│   ├── config.py           # 环境配置
│   ├── schemas.py          # 请求与响应模型
│   └── routers/            # 健康检查、对话、会话路由
├── tests/                  # 工具与接口自动化测试
├── harness/                # Agent Harness 接入与 MCP 工具服务
├── scripts/                # 一键启动脚本
├── requirements.txt        # 新版依赖
└── .env.example            # 环境变量模板
```

## 技术说明

`create_agent` 是 LangChain 1.0 构建智能体的标准方式，底层运行在 LangGraph 上，自动支持工具循环、多轮记忆、流式输出、持久化和人工介入。会话检查点存在 `agent_memory.db`，记忆按 `thread_id` 隔离。

规范检索采用本地关键词检索，不依赖外部 Embedding 服务；生成 CAD 图纸使用 `ezdxf` 输出标准 DXF 格式。

## 常见问题

- 报 `DEEPSEEK_API_KEY` 错误：检查 `.env` 是否已创建且填写正确。
- 检索不到规范内容：确认文件已放入 `knowledge/`，且格式为 PDF、Word、Markdown 或 TXT。
- 生成的 DXF 打不开：用 AutoCAD、LibreCAD 或支持 DXF 的看图软件打开 `outputs/cad/` 下的文件。
- Agent Harness 报插件加载失败：确认已重新执行 `pip install -r requirements.txt`，且启动目录是项目根目录；首次运行会自动生成 `.harness_home/`。
- 提示 Key 配置错误：检查 `.env` 是否存在且 `DEEPSEEK_API_KEY` 已填写真实值；Harness 与 LangChain 共用同一个 Key。
