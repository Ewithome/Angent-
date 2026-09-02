"""Skills 技能管理：读取、新增、编辑与删除本地 SKILL.md。"""
from __future__ import annotations

import re
import time
import os
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)

# 随仓库提供的示例技能；自定义技能统一保存到 .skills，避免内部内容被误提交
EXAMPLE_SKILLS_DIR = PROJECT_ROOT / "skills"
USER_SKILLS_DIR = PROJECT_ROOT / ".skills"
# 官方本地发现默认包含的已有技能根目录
PROJECT_DSH_SKILLS_DIR = PROJECT_ROOT / ".dsh" / "skills"
_HARNESS_HOME = Path(os.getenv("HARNESS_HOME") or PROJECT_ROOT / ".harness_home")
DSH_HOME_SKILLS_DIR = _HARNESS_HOME / "skills"
AGENTS_HOME_SKILLS_DIR = (
    Path(os.getenv("DSH_AGENTS_HOME") or Path.home() / ".agents") / "skills"
)
EXTERNAL_SKILL_DIRS: list[Path] = [
    PROJECT_DSH_SKILLS_DIR,
    DSH_HOME_SKILLS_DIR,
    AGENTS_HOME_SKILLS_DIR,
]

_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_FRONTMATTER_PATTERN = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n?(.*)$",
    re.DOTALL,
)


class SkillInfo(BaseModel):
    """一个技能目录项：frontmatter 摘要与完整 Markdown 指令正文。"""

    name: str = Field(description="kebab-case 技能名称，例如 spec-consultant")
    description: str = Field(description="给模型看的简短用途说明")
    when_to_use: str = Field(default="", description="可选的路由提示")
    source: Literal["example", "custom", "external"] = Field(
        description="example 为仓库示例，custom 为项目用户技能，external 为已有全局技能"
    )
    path: str = Field(description="SKILL.md 或 .md 文件绝对路径")
    content: str = Field(description="frontmatter 之后的完整指令正文")
    readonly: bool = Field(default=False, description="示例技能是否只读")


def _skill_name_from_path(path: Path) -> str:
    """目录 bundle 用父目录名，平铺文件用文件名。"""
    if path.name == "SKILL.md":
        return path.parent.name
    return path.stem


def parse_skill_file(path: Path) -> SkillInfo:
    """解析一个本地技能文件，返回校验后的技能信息。"""
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_PATTERN.match(text)
    if not match:
        raise ValueError(f"技能文件缺少 YAML frontmatter：{path}")
    try:
        metadata = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"技能 frontmatter 解析失败：{path}：{exc}") from exc

    if not isinstance(metadata, dict):
        raise ValueError(f"技能 frontmatter 必须是键值对象：{path}")
    name = metadata.get("name") or _skill_name_from_path(path)
    description = metadata.get("description")
    if not isinstance(name, str) or not _NAME_PATTERN.match(name):
        raise ValueError(f"技能名称必须是 kebab-case：{path}")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"技能缺少 description：{path}")

    if path.is_relative_to(USER_SKILLS_DIR):
        source = "custom"
    elif path.is_relative_to(EXAMPLE_SKILLS_DIR):
        source = "example"
    else:
        source = "external"
    return SkillInfo(
        name=name,
        description=description.strip(),
        when_to_use=str(metadata.get("whenToUse") or ""),
        source=source,
        path=str(path.resolve()),
        content=match.group(2).strip(),
        readonly=source != "custom",
    )


def _scan_root(root: Path) -> list[SkillInfo]:
    """扫描一个技能根目录下的目录 bundle 与平铺 Markdown。"""
    if not root.exists():
        return []
    skills: list[SkillInfo] = []
    for child in sorted(root.iterdir()):
        if child.is_dir():
            candidate = child / "SKILL.md"
        elif child.suffix.lower() == ".md":
            candidate = child
        else:
            continue
        if candidate.is_file():
            try:
                skills.append(parse_skill_file(candidate))
            except ValueError:
                # 无效文件按官方规则静默跳过，避免一个坏文件破坏整个目录
                continue
    return skills


def list_skills() -> list[SkillInfo]:
    """返回示例技能与用户自定义技能的合集。"""
    skills = [
        *_scan_root(EXAMPLE_SKILLS_DIR),
        *_scan_root(USER_SKILLS_DIR),
        *[
            skill
            for root in EXTERNAL_SKILL_DIRS
            for skill in _scan_root(root)
        ],
    ]
    return sorted(skills, key=lambda skill: skill.name)


def get_skill(name: str) -> SkillInfo | None:
    return next((skill for skill in list_skills() if skill.name == name), None)


def _skill_file_path(name: str) -> Path:
    """自定义技能统一写入 .skills/<name>.md。"""
    USER_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    return USER_SKILLS_DIR / f"{name}.md"


def _skill_markdown(name: str, description: str, when_to_use: str, content: str) -> str:
    metadata = {"name": name, "description": description}
    if when_to_use:
        metadata["whenToUse"] = when_to_use
    frontmatter = yaml.safe_dump(
        metadata,
        allow_unicode=True,
        sort_keys=False,
    ).strip()
    return f"---\n{frontmatter}\n---\n\n{content.strip()}\n"


def upsert_skill(
    name: str,
    description: str,
    content: str,
    when_to_use: str = "",
) -> SkillInfo:
    """新增或覆盖一个用户自定义技能。"""
    if not _NAME_PATTERN.match(name):
        raise ValueError("技能名称仅支持小写字母、数字与中划线，例如 spec-consultant")
    if not description.strip():
        raise ValueError("请填写技能说明 description")
    if not content.strip():
        raise ValueError("请填写技能指令正文")

    existing = get_skill(name)
    if existing and existing.source == "example":
        raise ValueError(f"{name} 是仓库示例技能，不能修改；请换一个名称")

    path = _skill_file_path(name)
    path.write_text(
        _skill_markdown(name, description.strip(), when_to_use.strip(), content),
        encoding="utf-8",
    )
    return parse_skill_file(path)


def delete_skill(name: str) -> bool:
    """删除用户自定义技能；示例技能不允许删除。"""
    existing = get_skill(name)
    if not existing or existing.source == "example":
        return False
    path = Path(existing.path)
    last_error: OSError | None = None
    for _ in range(5):
        try:
            path.unlink(missing_ok=True)
            return True
        except OSError as exc:
            # Harness 文件监视器可能短暂占用文件，稍后重试
            last_error = exc
            time.sleep(0.2)
    raise ValueError(f"删除技能文件失败：{last_error}")
