"""FastAPI 接口层测试。"""
from __future__ import annotations

import os
import unittest

from fastapi.testclient import TestClient
from dotenv import load_dotenv

from api.main import app

load_dotenv()

client = TestClient(app)


def _has_real_key() -> bool:
    """只有配置了真实 DeepSeek Key 时才执行真实对话接口测试。"""
    key = os.getenv("DEEPSEEK_API_KEY", "")
    placeholders = {"your_deepseek_api_key", "sk-在这里填写你的DeepSeekKey"}
    return bool(key) and key not in placeholders


class BasicApiTests(unittest.TestCase):
    """无需外部模型即可执行的接口测试。"""

    def test_root(self):
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["code"], 0)

    def test_health(self):
        resp = client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["status"], "ok")

    def test_validation_error(self):
        resp = client.post("/api/v1/chat", json={"message": ""})
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["code"], 42200)

    def test_engine_validation_error(self):
        resp = client.post(
            "/api/v1/chat",
            json={"message": "你好", "engine": "not-exist"},
        )
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["code"], 42200)


class McpApiTests(unittest.TestCase):
    """验证 MCP 服务配置接口；测试结束后清理临时服务。"""

    TEST_NAME = "api-mcp-test"

    def test_mcp_crud(self):
        listed = client.get("/api/v1/mcp/servers")
        self.assertEqual(listed.status_code, 200)
        names = [server["name"] for server in listed.json()["data"]]
        self.assertIn("building", names)

        try:
            created = client.post(
                "/api/v1/mcp/servers",
                json={
                    "name": self.TEST_NAME,
                    "label": "接口测试服务",
                    "command": "python",
                    "args": ["-m", "test_mcp"],
                },
            )
            self.assertEqual(created.status_code, 200)
            self.assertEqual(created.json()["code"], 0)

            updated = client.put(
                f"/api/v1/mcp/servers/{self.TEST_NAME}",
                json={
                    "name": self.TEST_NAME,
                    "label": "接口测试服务-已更新",
                    "command": "node",
                },
            )
            self.assertEqual(updated.status_code, 200)
            self.assertEqual(updated.json()["data"]["command"], "node")
        finally:
            deleted = client.delete(f"/api/v1/mcp/servers/{self.TEST_NAME}")
            self.assertEqual(deleted.status_code, 200)


class SkillApiTests(unittest.TestCase):
    """验证技能管理接口；测试结束后清理自定义技能。"""

    TEST_NAME = "api-skill-test"

    def test_skill_crud(self):
        listed = client.get("/api/v1/skills")
        self.assertEqual(listed.status_code, 200)
        self.assertGreaterEqual(len(listed.json()["data"]), 1)

        try:
            created = client.post(
                "/api/v1/skills",
                json={
                    "name": self.TEST_NAME,
                    "description": "接口测试技能",
                    "when_to_use": "测试时",
                    "content": "按知识库结果回答。",
                },
            )
            self.assertEqual(created.status_code, 200)
            self.assertEqual(created.json()["code"], 0)

            updated = client.put(
                f"/api/v1/skills/{self.TEST_NAME}",
                json={
                    "name": self.TEST_NAME,
                    "description": "接口测试技能-已更新",
                    "when_to_use": "",
                    "content": "按更新后的规则回答。",
                },
            )
            self.assertEqual(updated.status_code, 200)
            self.assertEqual(updated.json()["data"]["description"], "接口测试技能-已更新")
        finally:
            deleted = client.delete(f"/api/v1/skills/{self.TEST_NAME}")
            self.assertEqual(deleted.status_code, 200)


@unittest.skipUnless(_has_real_key(), "未配置真实 DeepSeek Key，跳过对话接口测试")
class ChatApiTests(unittest.TestCase):
    """验证真实对话、会话查询与删除。"""

    def test_chat_roundtrip(self):
        resp = client.post(
            "/api/v1/chat",
            json={"message": "现在几点了？", "session_id": "api-test"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["code"], 0)
        self.assertTrue(resp.json()["data"]["reply"])

    def test_session_manage(self):
        client.post(
            "/api/v1/chat",
            json={"message": "你好", "session_id": "api-test"},
        )
        messages = client.get(
            "/api/v1/sessions/api-test/messages",
            params={"limit": 5},
        )
        self.assertEqual(messages.status_code, 200)
        self.assertGreater(len(messages.json()["data"]["messages"]), 0)

        deleted = client.delete("/api/v1/sessions/api-test")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()["message"], "会话已删除")


if __name__ == "__main__":
    unittest.main()
