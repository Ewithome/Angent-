# 建筑规范图集智能体

基于 **LangChain v1 + LangGraph v1 + DeepSeek** 的建筑规范方向智能体，可以回答客户关于规范标准的问题、计算工程用量，并生成建筑平面示意 CAD 图纸。

## 项目特点

- 使用 LangChain v1 最新的 `create_agent`，替代已弃用的 `langgraph.prebuilt.create_react_agent`
- 本地规范知识库检索：支持 PDF、Word、Markdown、TXT，答案可溯源
- 建筑用量计算：混凝土、砖墙、涂料、钢筋
- CAD 图纸生成：按房间参数输出 DXF 文件，可用 AutoCAD / LibreCAD 打开
- SQLite 持久化多轮会话记忆
- Streamlit 中文网页 + 命令行 REPL
- 企业级 FastAPI 接口层：版本化路由、统一响应、异常处理、请求追踪、日志、会话管理

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

支持 `.pdf`、`.docx`、`.md`、`.txt`。文件放入后无需重启，智能体会在下次检索时自动重建索引。规范原文只保存在本地，不会上传到 GitHub。

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

接口文档：<http://localhost:8000/docs>

一键启动脚本（PowerShell）：

```powershell
.\scripts\run_api.ps1
.\scripts\run_web.ps1
```

## 测试

```bash
python -m unittest discover -s tests -v
```

测试覆盖安全计算器、混凝土/砖墙/涂料/钢筋计算、CAD 图纸生成、规范知识库检索、API 健康检查与参数校验；配置真实 DeepSeek Key 时还会自动执行对话和会话管理接口测试。

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
  "message": "住宅楼梯踏步高度有什么要求？再帮我算 10m×5m×0.2m 的混凝土用量",
  "session_id": "building-demo"
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
└── .env.example            # 环境变量模板
```

## 技术说明

`create_agent` 是 LangChain 1.0 构建智能体的标准方式，底层运行在 LangGraph 上，自动支持工具循环、多轮记忆、流式输出、持久化和人工介入。会话检查点存在 `agent_memory.db`，记忆按 `thread_id` 隔离。

规范检索采用本地关键词检索，不依赖外部 Embedding 服务；生成 CAD 图纸使用 `ezdxf` 输出标准 DXF 格式。

## 常见问题

- 报 `DEEPSEEK_API_KEY` 错误：检查 `.env` 是否已创建且填写正确。
- 检索不到规范内容：确认文件已放入 `knowledge/`，且格式为 PDF、Word、Markdown 或 TXT。
- 生成的 DXF 打不开：用 AutoCAD、LibreCAD 或支持 DXF 的看图软件打开 `outputs/cad/` 下的文件。
