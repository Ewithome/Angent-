"""工具层单元测试。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import agent_core


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


class TimeTests(unittest.TestCase):
    """验证时间工具返回标准格式。"""

    def test_current_time_format(self):
        value = agent_core.get_current_time.invoke({})
        self.assertRegex(value, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


class NoteTests(unittest.TestCase):
    """验证笔记工具的保存、列出、读取闭环。"""

    def setUp(self):
        # 使用临时目录，避免测试污染真实 notes 目录
        self._tmp = tempfile.TemporaryDirectory()
        self._old_dir = agent_core.NOTES_DIR
        agent_core.NOTES_DIR = Path(self._tmp.name)

    def tearDown(self):
        agent_core.NOTES_DIR = self._old_dir
        self._tmp.cleanup()

    def test_note_roundtrip(self):
        agent_core.save_note.invoke({"title": "待办", "content": "明天开会"})
        titles = agent_core.list_notes.invoke({})
        self.assertIn("待办", titles)
        content = agent_core.read_note.invoke({"title": "待办"})
        self.assertIn("明天开会", content)


if __name__ == "__main__":
    unittest.main()
