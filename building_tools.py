"""建筑领域工具：用量计算与 CAD 平面图生成。"""
from __future__ import annotations

import math
import os
import re
from pathlib import Path

import ezdxf
from langchain.tools import tool

OUTPUT_DIR = Path(os.getenv("CAD_OUTPUT_DIR", "outputs/cad"))
_STEEL_DENSITY = 7850  # 钢材密度 kg/m3
_BRICKS_PER_CUBIC_METER = 512  # 标准砖含灰缝估算值


def list_cad_files() -> list[Path]:
    """返回已生成的 DXF 文件列表，供页面展示和下载。"""
    if not OUTPUT_DIR.exists():
        return []
    return sorted(OUTPUT_DIR.glob("*.dxf"))


@tool
def calculate_concrete_volume(length_m: float, width_m: float, thickness_m: float) -> str:
    """计算混凝土用量。参数单位均为米，例如长10米、宽5米、厚0.2米。"""
    volume = length_m * width_m * thickness_m
    return (
        f"混凝土体积：{volume:.2f} 立方米"
        f"（长 {length_m}m × 宽 {width_m}m × 厚 {thickness_m}m）"
    )


@tool
def calculate_brick_wall_quantity(
    length_m: float,
    height_m: float,
    thickness_m: float,
) -> str:
    """估算砖墙用砖量。厚度常用 0.115（半砖墙）或 0.24（一砖墙），单位均为米。"""
    wall_volume = length_m * height_m * thickness_m
    bricks = wall_volume * _BRICKS_PER_CUBIC_METER
    return (
        f"砖墙体积：{wall_volume:.2f} 立方米；"
        f"估算用砖：约 {bricks:.0f} 块"
        f"（按标准砖 240×115×53mm 含灰缝 512 块/立方米估算）"
    )


@tool
def calculate_paint_area(
    length_m: float,
    width_m: float,
    height_m: float,
    windows_area: float = 0.0,
    doors_area: float = 0.0,
) -> str:
    """计算房间墙面刷漆面积。长度、宽度、高度单位米，门窗面积单位平方米。"""
    wall_area = 2 * (length_m + width_m) * height_m - windows_area - doors_area
    paint_liters = wall_area / 10  # 按每升涂料刷 10 平方米一遍估算
    return (
        f"墙面面积：{wall_area:.2f} 平方米；"
        f"按每升刷 10 平方米一遍估算，约需 {paint_liters:.2f} 升涂料"
    )


@tool
def calculate_rebar_weight(
    diameter_mm: float,
    length_m: float,
    quantity: float = 1.0,
) -> str:
    """计算钢筋重量。直径单位毫米，长度单位米，quantity 为根数。"""
    radius_m = diameter_mm / 2000
    area_m2 = math.pi * radius_m * radius_m
    weight = area_m2 * length_m * _STEEL_DENSITY * quantity
    return (
        f"钢筋重量：约 {weight:.2f} 千克"
        f"（直径 {diameter_mm}mm，单根长 {length_m}m，共 {quantity} 根）"
    )


@tool
def generate_cad_drawing(
    length_m: float,
    width_m: float,
    wall_thickness_m: float = 0.24,
    door_width_m: float = 0.9,
    window_width_m: float = 1.5,
    output_name: str = "building_plan",
) -> str:
    """生成建筑平面示意 DXF 图纸。参数为房间长宽、墙厚、门宽、窗宽，output_name 为文件名（不含扩展名）。"""
    safe_name = re.sub(r'[\\/:*?"<>|]+', "_", output_name.strip()) or "building_plan"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{safe_name}.dxf"

    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()

    # 按功能分层，方便 CAD 软件中单独控制显示
    layer_colors = {
        "WALL": 7,
        "DOOR": 3,
        "WINDOW": 4,
        "DIMENSION": 2,
        "TEXT": 1,
    }
    for name, color in layer_colors.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)

    length = length_m * 1000  # 米转毫米
    width = width_m * 1000
    thickness = wall_thickness_m * 1000

    # 外墙与内墙线
    msp.add_lwpolyline(
        [(0, 0), (length, 0), (length, width), (0, width)],
        close=True,
        dxfattribs={"layer": "WALL"},
    )
    if length > 2 * thickness and width > 2 * thickness:
        msp.add_lwpolyline(
            [
                (thickness, thickness),
                (length - thickness, thickness),
                (length - thickness, width - thickness),
                (thickness, width - thickness),
            ],
            close=True,
            dxfattribs={"layer": "WALL"},
        )

    # 门：底边中间留门洞并画出两侧门垛
    door = min(door_width_m * 1000, length - 2 * thickness)
    door_start = (length - door) / 2
    msp.add_line(
        (door_start, 0),
        (door_start + door, 0),
        dxfattribs={"layer": "DOOR"},
    )
    msp.add_line(
        (door_start, 0),
        (door_start, thickness),
        dxfattribs={"layer": "DOOR"},
    )
    msp.add_line(
        (door_start + door, 0),
        (door_start + door, thickness),
        dxfattribs={"layer": "DOOR"},
    )

    # 窗：顶边、左边、右边各画一扇示意窗线
    window = min(window_width_m * 1000, length - 2 * thickness, width - 2 * thickness)
    msp.add_line(
        ((length - window) / 2, width),
        ((length + window) / 2, width),
        dxfattribs={"layer": "WINDOW"},
    )
    msp.add_line(
        (0, (width - window) / 2),
        (0, (width + window) / 2),
        dxfattribs={"layer": "WINDOW"},
    )
    msp.add_line(
        (length, (width - window) / 2),
        (length, (width + window) / 2),
        dxfattribs={"layer": "WINDOW"},
    )

    # 尺寸标注
    dim_h = msp.add_linear_dim(
        base=(0, -400),
        p1=(0, 0),
        p2=(length, 0),
        angle=0,
        dimstyle="EZDXF",
        override={"dimtxt": 100, "dimasz": 100},
    )
    dim_h.render()
    dim_v = msp.add_linear_dim(
        base=(-400, 0),
        p1=(0, 0),
        p2=(0, width),
        angle=90,
        dimstyle="EZDXF",
        override={"dimtxt": 100, "dimasz": 100},
    )
    dim_v.render()

    # 图纸标题
    msp.add_text(
        f"建筑平面示意 {length_m:.1f} x {width_m:.1f} m",
        height=120,
        dxfattribs={"layer": "TEXT"},
    ).set_placement((length / 2 - 500, width / 2))

    doc.saveas(path)
    return (
        f"已生成 CAD 图纸：{path}\n"
        f"参数：长 {length_m}m，宽 {width_m}m，墙厚 {wall_thickness_m}m，"
        f"门宽 {door_width_m}m，窗宽 {window_width_m}m。"
    )
