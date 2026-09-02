"""Agent Harness 接入层测试：MCP 工具清单与真实模型冒烟测试。"""
from __future__ import annotations

import asyncio
import os
import unittest

from dotenv import load_dotenv
from harness.mcp_server import (
    calculate_concrete_volume,
    calculate_rebar_weight,
    server,
)

load_dotenv()


class MCPToolTests(unittest.TestCase):
    """验证 MCP 服务注册的领域工具可被 Harness 客户端发现。"""

    @staticmethod
    def _tool_names() -> list[str]:
        result = asyncio.run(server.list_tools())
        return [tool.name for tool in result]

    def test_tool_list_contains_business_tools(self):
        names = self._tool_names()
        for expected in (
            "search_knowledge",
            "calculate_concrete_volume",
            "generate_cad_drawing",
            "list_project_notes",
        ):
            self.assertIn(expected, names)

    def test_direct_tool_call(self):
        self.assertIn("10.00 立方米", calculate_concrete_volume(10, 5, 0.2))
        self.assertIn("14.80 千克", calculate_rebar_weight(20, 6, 1))


def _has_real_key() -> bool:
    """与 API 测试保持一致：配置真实 Key 时才执行真实模型调用。"""
    key = os.getenv("DEEPSEEK_API_KEY", "")
    placeholders = {"your_deepseek_api_key", "sk-在这里填写你的DeepSeekKey"}
    return bool(key) and key not in placeholders


@unittest.skipUnless(_has_real_key(), "未配置真实 DeepSeek Key，跳过 Agent Harness 冒烟测试")
class HarnessLiveTests(unittest.TestCase):
    """真实启动 Agent Harness，验证 MCP 工具桥与 DeepSeek 调用可用。"""

    def test_harness_chat(self):
        from harness.agent import run_harness_chat

        reply = run_harness_chat(
            "只回复两个中文字：正常，不要调用任何工具。",
            session_id="harness-test",
        )
        self.assertTrue(reply)
        self.assertIn("正常", reply)


if __name__ == "__main__":
    unittest.main()
