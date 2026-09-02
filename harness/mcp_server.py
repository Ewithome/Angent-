"""把本项目能力暴露为标准 MCP 工具，供 DeepSeek Harness 调用。

Agent Harness 通过内置 MCP 客户端按 stdio 协议拉起本模块，工具名会以
``mcp__building__*`` 的形式出现在模型工具列表中，例如
``mcp__building__search_knowledge``。
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

import agent_core
import building_tools
import knowledge_base


def _invoke(tool, arguments: dict) -> str:
    """统一执行 LangChain 装饰过的领域工具，返回模型可直接阅读的文本。"""
    try:
        result = tool.invoke(arguments)
        return str(result)
    except Exception as exc:  # noqa: BLE001
        return f"工具调用失败：{exc}"


# MCP 服务端名称会出现在日志与客户端诊断信息中
server = MCPServer(
    name="building-knowledge-mcp",
    title="建筑规范与企业知识库 MCP",
    version="1.0.0",
)


@server.tool(
    name="search_knowledge",
    title="检索企业知识库",
    description="从企业知识库检索规范、制度、产品手册或业务流程，返回来源与原文片段。",
)
def search_knowledge(query: str) -> str:
    """检索 knowledge/ 目录中的规范与制度文档，query 为关键词或问题。"""
    return _invoke(knowledge_base.search_building_code, {"query": query})


@server.tool(
    name="list_knowledge_files",
    title="查看知识库文档",
    description="返回当前知识库中的文档数量，帮助确认知识库是否已收录相关规范。",
)
def list_knowledge_files() -> str:
    """返回知识库文件数量；新增文档会自动进入后续检索索引。"""
    count = knowledge_base.get_knowledge_file_count()
    return f"当前知识库共 {count} 个文档，文件放在项目 knowledge/ 目录。"


@server.tool(
    name="calculate_concrete_volume",
    title="计算混凝土用量",
    description="按长宽厚计算混凝土体积，参数单位均为米。",
)
def calculate_concrete_volume(length_m: float, width_m: float, thickness_m: float) -> str:
    """计算混凝土体积，单位为立方米。"""
    return _invoke(
        building_tools.calculate_concrete_volume,
        {"length_m": length_m, "width_m": width_m, "thickness_m": thickness_m},
    )


@server.tool(
    name="calculate_brick_wall_quantity",
    title="计算砖墙用砖量",
    description="按墙长、墙高、墙厚估算标准砖数量，单位均为米。",
)
def calculate_brick_wall_quantity(
    length_m: float,
    height_m: float,
    thickness_m: float,
) -> str:
    """估算砖墙用砖量，厚度常用 0.24 米。"""
    return _invoke(
        building_tools.calculate_brick_wall_quantity,
        {
            "length_m": length_m,
            "height_m": height_m,
            "thickness_m": thickness_m,
        },
    )


@server.tool(
    name="calculate_paint_area",
    title="计算墙面刷漆面积",
    description="计算房间内墙刷漆面积，长度宽度高度单位米，门窗面积单位平方米。",
)
def calculate_paint_area(
    length_m: float,
    width_m: float,
    height_m: float,
    windows_area: float = 0.0,
    doors_area: float = 0.0,
) -> str:
    """按四墙展开面积扣除门窗洞口后返回刷漆面积与涂料估算。"""
    return _invoke(
        building_tools.calculate_paint_area,
        {
            "length_m": length_m,
            "width_m": width_m,
            "height_m": height_m,
            "windows_area": windows_area,
            "doors_area": doors_area,
        },
    )


@server.tool(
    name="calculate_rebar_weight",
    title="计算钢筋重量",
    description="按直径毫米、单根长度米和根数计算钢筋总重量。",
)
def calculate_rebar_weight(
    diameter_mm: float,
    length_m: float,
    quantity: float = 1.0,
) -> str:
    """计算钢筋重量，单位为千克。"""
    return _invoke(
        building_tools.calculate_rebar_weight,
        {
            "diameter_mm": diameter_mm,
            "length_m": length_m,
            "quantity": quantity,
        },
    )


@server.tool(
    name="generate_cad_drawing",
    title="生成 CAD 平面图纸",
    description="按房间长宽生成 DXF 建筑平面示意图纸，输出到项目 outputs/cad/。",
)
def generate_cad_drawing(
    length_m: float,
    width_m: float,
    wall_thickness_m: float = 0.24,
    door_width_m: float = 0.9,
    window_width_m: float = 1.5,
    output_name: str = "building_plan",
) -> str:
    """生成 DXF 图纸并返回文件绝对路径与生成参数。"""
    return _invoke(
        building_tools.generate_cad_drawing,
        {
            "length_m": length_m,
            "width_m": width_m,
            "wall_thickness_m": wall_thickness_m,
            "door_width_m": door_width_m,
            "window_width_m": window_width_m,
            "output_name": output_name,
        },
    )


@server.tool(
    name="list_cad_drawings",
    title="查看已生成 CAD 图纸",
    description="列出项目已生成的 DXF 文件，用户可据此下载图纸。",
)
def list_cad_drawings() -> str:
    """返回 outputs/cad/ 下的已有图纸列表。"""
    files = building_tools.list_cad_files()
    if not files:
        return "暂无已生成的 CAD 图纸，可先调用 generate_cad_drawing 生成。"
    return "已生成图纸：\n" + "\n".join(f"- {path}" for path in files)


@server.tool(
    name="save_project_note",
    title="保存项目纪要",
    description="把项目纪要、客户要求或待办事项保存为本地 Markdown 笔记。",
)
def save_project_note(title: str, content: str) -> str:
    """保存一条笔记到 notes/，title 为标题，content 为正文。"""
    return _invoke(agent_core.save_note, {"title": title, "content": content})


@server.tool(
    name="list_project_notes",
    title="列出项目纪要",
    description="列出本地已保存的项目纪要标题。",
)
def list_project_notes() -> str:
    """返回全部已有笔记标题。"""
    return _invoke(agent_core.list_notes, {})


@server.tool(
    name="read_project_note",
    title="读取项目纪要",
    description="按标题读取一条本地项目纪要内容。",
)
def read_project_note(title: str) -> str:
    """读取指定标题的笔记正文。"""
    return _invoke(agent_core.read_note, {"title": title})


def main() -> None:
    """以 stdio 模式启动 MCP 服务，供 Agent Harness 内部客户端连接。"""
    server.run()


if __name__ == "__main__":
    main()
