"""MCP 服务配置存储与校验测试。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from harness.mcp_config import McpConfigStore, McpServerConfig, builtin_server


class McpConfigStoreTests(unittest.TestCase):
    """验证自定义 MCP 服务的保存、加载、覆盖与删除。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = McpConfigStore(Path(self._tmp.name) / "mcp.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_custom_server_roundtrip(self):
        server = McpServerConfig(
            name="filesystem",
            command="python",
            args=["-m", "mcp_server_filesystem"],
        )
        self.store.upsert(server)
        loaded = self.store.get_custom("filesystem")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.command, "python")
        self.assertFalse(loaded.builtin)

    def test_upsert_overwrites_same_name(self):
        first = McpServerConfig(name="memory", command="npx")
        second = McpServerConfig(name="memory", command="node", label="new")
        self.store.upsert(first)
        self.store.upsert(second)
        servers = self.store.list_custom()
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].command, "node")

    def test_delete_custom(self):
        self.store.upsert(McpServerConfig(name="db", command="db-mcp"))
        self.assertTrue(self.store.delete("db"))
        self.assertFalse(self.store.delete("db"))

    def test_reserved_name_rejected(self):
        with self.assertRaises(ValueError):
            self.store.upsert(McpServerConfig(name="building", command="x"))

    def test_transport_validation(self):
        with self.assertRaises(ValidationError):
            McpServerConfig(name="bad", transport="stdio", command=None)
        with self.assertRaises(ValidationError):
            McpServerConfig(
                name="bad-http",
                transport="streamable-http",
                url=None,
            )

    def test_builtin_server_always_present(self):
        servers = self.store.list_all()
        names = [server.name for server in servers]
        self.assertEqual(builtin_server().name, "building")
        self.assertIn("building", names)


if __name__ == "__main__":
    unittest.main()
