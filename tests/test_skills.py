"""技能目录解析与自定义技能存储测试。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import harness.skills_store as store_module


class SkillStoreTests(unittest.TestCase):
    """验证 SKILL.md 解析、新增、覆盖与删除。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._root = Path(self._tmp.name)
        self._old_example = store_module.EXAMPLE_SKILLS_DIR
        self._old_user = store_module.USER_SKILLS_DIR
        self._old_external = store_module.EXTERNAL_SKILL_DIRS
        store_module.EXAMPLE_SKILLS_DIR = self._root / "skills"
        store_module.USER_SKILLS_DIR = self._root / ".skills"
        store_module.EXTERNAL_SKILL_DIRS = []
        example = store_module.EXAMPLE_SKILLS_DIR / "spec-consultant"
        example.mkdir(parents=True)
        (example / "SKILL.md").write_text(
            """---
name: spec-consultant
description: 规范条文核查
---
检索知识库并引用来源。""",
            encoding="utf-8",
        )

    def tearDown(self):
        store_module.EXAMPLE_SKILLS_DIR = self._old_example
        store_module.USER_SKILLS_DIR = self._old_user
        store_module.EXTERNAL_SKILL_DIRS = self._old_external
        self._tmp.cleanup()

    def test_list_example_skill(self):
        skills = store_module.list_skills()
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0].name, "spec-consultant")
        self.assertEqual(skills[0].source, "example")
        self.assertTrue(skills[0].readonly)

    def test_upsert_custom_skill(self):
        saved = store_module.upsert_skill(
            name="fire-review",
            description="消防审查",
            when_to_use="消防图纸审查时",
            content="检查防火间距并调用知识库。",
        )
        self.assertEqual(saved.source, "custom")
        loaded = store_module.get_skill("fire-review")
        self.assertEqual(loaded.description, "消防审查")
        self.assertIn("防火间距", loaded.content)

    def test_example_skill_is_readonly(self):
        with self.assertRaises(ValueError):
            store_module.upsert_skill(
                name="spec-consultant",
                description="覆盖示例",
                content="不允许覆盖",
            )

    def test_delete_custom_skill(self):
        store_module.upsert_skill(name="temp-skill", description="临时", content="正文")
        self.assertTrue(store_module.delete_skill("temp-skill"))
        self.assertIsNone(store_module.get_skill("temp-skill"))

    def test_list_existing_external_skill(self):
        external = self._root / "external"
        external.mkdir()
        store_module.EXTERNAL_SKILL_DIRS = [external]
        skill_dir = external / "existing-tool"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            """---
name: existing-tool
description: 已有的外部技能
---
复用已有指令。""",
            encoding="utf-8",
        )
        loaded = store_module.get_skill("existing-tool")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.source, "external")
        self.assertTrue(loaded.readonly)


if __name__ == "__main__":
    unittest.main()
