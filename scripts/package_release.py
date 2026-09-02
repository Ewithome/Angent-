"""一键打包与发布：生成 release zip，并可选发布 GitHub Release。"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
_VERSION_PATTERN = re.compile(r'app_version:\s*str\s*=\s*"([^"]+)"')


def _current_version() -> str:
    config_path = PROJECT_ROOT / "api" / "config.py"
    match = _VERSION_PATTERN.search(config_path.read_text(encoding="utf-8"))
    return match.group(1) if match else "1.0.0"


def _tracked_files() -> list[str]:
    """只打包 git 已跟踪文件，避免把 .env、本地知识库等敏感内容带进产物。"""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def _should_skip(relative: str) -> bool:
    parts = relative.split("/")
    if parts[0] in {"legacy", "tests", ".github", "notes"}:
        return True
    if relative.endswith((".pyc", ".pyo", ".log")):
        return True
    if any(part in {"__pycache__", ".venv", ".harness_home", ".harness_workspace"} for part in parts):
        return True
    return False


def _release_notes(version: str) -> str:
    return f"""企业知识库智能体 v{version}

功能：
- LangChain 与 DeepSeek Agent Harness 双引擎
- 知识库混合检索与 RAG 评测
- 建筑规范、用量计算、CAD DXF 图纸生成
- MCP 服务配置与 Skills 技能管理
- FastAPI 企业级接口与统一响应

使用：
1. 解压后复制 .env.example 为 .env，填写 DEEPSEEK_API_KEY
2. 双击 start_all.bat
3. 打开 http://localhost:8501
"""


def _copy_tracked_files(build_dir: Path, version: str) -> Path:
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    for relative in _tracked_files():
        if _should_skip(relative):
            continue
        source = PROJECT_ROOT / relative
        if not source.is_file():
            continue
        target = build_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    guide = build_dir / "发布说明.txt"
    guide.write_text(
        "一、安装\n"
        "1. 复制 .env.example 为 .env，并填写 DEEPSEEK_API_KEY。\n"
        "2. 双击 start_all.bat，脚本会自动创建虚拟环境并安装依赖。\n"
        "3. 国内网络慢时脚本已默认使用清华 PyPI 镜像。\n\n"
        "二、访问\n"
        "网页界面：http://localhost:8501\n"
        "接口文档：http://localhost:8000/docs\n\n"
        "三、说明\n"
        "正式规范文档请放到 knowledge/ 目录，自定义技能会保存到 .skills/。\n",
        encoding="utf-8",
    )
    return build_dir


def _make_zip(build_dir: Path, version: str) -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DIST_DIR / f"enterprise-knowledge-agent-{version}.zip"
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(build_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(DIST_DIR).as_posix())
    return zip_path


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *_proxy_args(), *args],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Git 操作超时：git {' '.join(args)}") from exc


def _git_quiet(*args: str) -> bool:
    result = subprocess.run(
        ["git", *_proxy_args(), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        timeout=90,
    )
    return result.returncode == 0


def _proxy_args() -> list[str]:
    """读取 Windows 系统代理，避免 Git 绕过本地网络代理导致超时。"""
    if os.name != "nt":
        return []
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        ) as key:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
    except OSError:
        return []
    if not enabled or not server:
        return []
    if not server.startswith(("http://", "https://")):
        server = f"http://{server}"
    return ["-c", f"http.proxy={server}", "-c", f"https.proxy={server}"]


def _github_repo() -> str:
    remote = _git("config", "--get", "remote.origin.url").stdout.strip()
    match = re.search(r"github\.com[:/]([^/]+)/([^/\s]+?)(?:\.git)?$", remote)
    if not match:
        raise RuntimeError(f"无法识别 GitHub 仓库地址：{remote}")
    return f"{match.group(1)}/{match.group(2).removesuffix('.git')}"


def _github_token() -> str:
    """从 Git 凭据管理器读取 GitHub token，不在命令行和日志中输出。"""
    result = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n",
        text=True,
        capture_output=True,
        check=True,
    )
    fields = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            fields[key.strip()] = value.strip()
    token = fields.get("password", "")
    if not token:
        raise RuntimeError("Git 凭据管理器未返回 GitHub token，无法发布 Release")
    return token


def _github_request(
    method: str,
    url: str,
    token: str,
    payload: dict | None = None,
    raw: bytes | None = None,
    content_type: str | None = None,
) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif raw is not None:
        data = raw
        headers["Content-Type"] = content_type or "application/zip"
    else:
        data = None

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GitHub API 失败 {exc.code}：{detail[:800]}") from exc


def _find_existing_release(repo: str, tag: str, token: str) -> dict | None:
    try:
        return _github_request(
            "GET",
            f"https://api.github.com/repos/{repo}/releases/tags/{tag}",
            token,
        )
    except RuntimeError as exc:
        if "GitHub API 失败 404" in str(exc):
            return None
        raise


def _publish_github(zip_path: Path, version: str) -> str:
    print("正在推送代码和版本标签...", flush=True)
    repo = _github_repo()
    token = _github_token()
    tag = f"v{version}"

    _git("push", "origin", "HEAD:main")
    if not _git_quiet("rev-parse", "-q", "--verify", f"refs/tags/{tag}"):
        _git("tag", tag)
    if not _git_quiet("ls-remote", "--tags", "origin", f"refs/tags/{tag}"):
        _git("push", "origin", tag)

    print("正在创建 GitHub Release...", flush=True)
    release_payload = {
        "tag_name": tag,
        "name": f"企业知识库智能体 v{version}",
        "body": _release_notes(version),
        "target_commitish": "main",
        "prerelease": False,
    }
    release = _find_existing_release(repo, tag, token)
    if release is None:
        release = _github_request(
            "POST",
            f"https://api.github.com/repos/{repo}/releases",
            token,
            payload=release_payload,
        )
    else:
        release = _github_request(
            "PATCH",
            release["url"],
            token,
            payload={
                "name": release_payload["name"],
                "body": release_payload["body"],
            },
        )
    upload_url = release["upload_url"].split("{", 1)[0]
    asset_name = urllib.parse.quote(zip_path.name)
    upload_url = f"{upload_url}?name={asset_name}"
    for asset in release.get("assets", []):
        if asset["name"] == zip_path.name:
            _github_request("DELETE", asset["url"], token)
    with zip_path.open("rb") as handle:
        _github_request(
            "POST",
            upload_url,
            token,
            raw=handle.read(),
            content_type="application/zip",
        )
    return release["html_url"]


def main() -> None:
    parser = argparse.ArgumentParser(description="一键打包发布")
    parser.add_argument("--version", default=None, help="覆盖发布版本，默认读取 api/config.py")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="打包后创建并发布 GitHub Release",
    )
    parser.add_argument(
        "--auto-commit",
        action="store_true",
        help="发布前自动提交当前工作区改动，实现真正的一键发布",
    )
    args = parser.parse_args()

    version = args.version or _current_version()
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        raise SystemExit(f"版本号格式不正确：{version}")

    if args.publish:
        if args.auto_commit:
            _auto_commit(version)
        elif _git("status", "--porcelain").stdout.strip():
            raise SystemExit("工作区还有未提交改动，请先提交代码再执行一键发布")

    print(f"开始打包 v{version}...", flush=True)
    build_dir = _copy_tracked_files(DIST_DIR / f"enterprise-knowledge-agent-{version}", version)
    zip_path = _make_zip(build_dir, version)
    print(f"打包完成：{zip_path}", flush=True)

    if args.publish:
        print("准备发布 GitHub Release...", flush=True)
        url = _publish_github(zip_path, version)
        print(f"GitHub Release 已发布：{url}", flush=True)


def _auto_commit(version: str) -> None:
    """自动提交工作区改动，保证发布的 zip 与 GitHub 代码完全一致。"""
    status = _git("status", "--porcelain").stdout.strip()
    if not status:
        return
    print(f"检测到未提交改动，正在自动提交 v{version} 发布内容...", flush=True)
    _git("add", "-A")
    _git("commit", "-m", f"chore: prepare release v{version}")


if __name__ == "__main__":
    main()
