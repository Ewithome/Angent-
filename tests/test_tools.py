"""建筑领域工具层单元测试。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import agent_core
import building_tools
import knowledge_base


class CalculatorTests(unittest.TestCase):
    """验证安全计算器只允许数学表达式，并拒绝危险输入。"""

    def test_basic_arithmetic(self):
        result = agent_core.calculator.invoke({"expression": "(1 + 2) * 3"})
        self.assertEqual(result, "9")

    def test_power_and_mod(self):
        result = agent_core.calculator.invoke({"expression": "2 ** 10 % 7"})
        self.assertEqual(result, "2")

    def test_unsafe_expression_rejected(self):
        result = agent_core.calculator.invoke({"expression": "__import__('os')"})
        self.assertTrue(result.startswith("计算出错"))


class BuildingCalculationTests(unittest.TestCase):
    """验证混凝土、砖墙、涂料、钢筋用量计算。"""

    def test_concrete_volume(self):
        result = building_tools.calculate_concrete_volume.invoke(
            {"length_m": 10, "width_m": 5, "thickness_m": 0.2}
        )
        self.assertIn("10.00 立方米", result)

    def test_brick_wall_quantity(self):
        result = building_tools.calculate_brick_wall_quantity.invoke(
            {"length_m": 10, "height_m": 3, "thickness_m": 0.24}
        )
        self.assertIn("约 3686 块", result)

    def test_paint_area(self):
        result = building_tools.calculate_paint_area.invoke(
            {
                "length_m": 4,
                "width_m": 3,
                "height_m": 2.8,
                "windows_area": 2,
                "doors_area": 1.5,
            }
        )
        self.assertIn("35.70 平方米", result)

    def test_rebar_weight(self):
        result = building_tools.calculate_rebar_weight.invoke(
            {"diameter_mm": 20, "length_m": 6, "quantity": 1}
        )
        self.assertIn("14.80 千克", result)


class CadDrawingTests(unittest.TestCase):
    """验证 CAD 图纸生成并检查 DXF 文件落盘。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_dir = building_tools.OUTPUT_DIR
        building_tools.OUTPUT_DIR = Path(self._tmp.name)

    def tearDown(self):
        building_tools.OUTPUT_DIR = self._old_dir
        self._tmp.cleanup()

    def test_generate_dxf(self):
        result = building_tools.generate_cad_drawing.invoke(
            {
                "length_m": 6,
                "width_m": 4,
                "output_name": "test_plan",
            }
        )
        self.assertTrue(result.startswith("已生成 CAD 图纸"))
        output = building_tools.OUTPUT_DIR / "test_plan.dxf"
        self.assertTrue(output.exists())
        self.assertGreater(output.stat().st_size, 0)


class KnowledgeBaseTests(unittest.TestCase):
    """验证本地规范知识库检索。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_dir = knowledge_base.KNOWLEDGE_DIR
        knowledge_base.KNOWLEDGE_DIR = Path(self._tmp.name)
        knowledge_base._index_cache = {"key": None, "chunks": []}
        sample = knowledge_base.KNOWLEDGE_DIR / "住宅设计规范.txt"
        sample.write_text(
            "楼梯踏步高度不应大于 0.175m，楼梯踏步宽度不应小于 0.26m。",
            encoding="utf-8",
        )

    def tearDown(self):
        knowledge_base.KNOWLEDGE_DIR = self._old_dir
        knowledge_base._index_cache = {"key": None, "chunks": []}
        self._tmp.cleanup()

    def test_search_building_code(self):
        result = knowledge_base.search_building_code.invoke(
            {"query": "楼梯踏步高度"}
        )
        self.assertIn("住宅设计规范.txt", result)
        self.assertIn("0.175m", result)


class NoteTests(unittest.TestCase):
    """验证笔记工具的保存、列出、读取闭环。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_dir = agent_core.NOTES_DIR
        agent_core.NOTES_DIR = Path(self._tmp.name)

    def tearDown(self):
        agent_core.NOTES_DIR = self._old_dir
        self._tmp.cleanup()

    def test_note_roundtrip(self):
        agent_core.save_note.invoke({"title": "项目纪要", "content": "明天审查图纸"})
        titles = agent_core.list_notes.invoke({})
        self.assertIn("项目纪要", titles)
        content = agent_core.read_note.invoke({"title": "项目纪要"})
        self.assertIn("明天审查图纸", content)


if __name__ == "__main__":
    unittest.main()
