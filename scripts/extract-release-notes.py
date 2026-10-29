#!/usr/bin/env python3
"""从 docs/project/changelog.md 中提取指定版本的发布说明，并生成包含多渠道安装指引的 Release Notes。

用法:
    python3 scripts/extract-release-notes.py --tag v0.2.0 --output RELEASE_NOTES.md
    python3 scripts/extract-release-notes.py --version 0.2.0
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def extract_notes_from_changelog(changelog_path: Path, version: str) -> str:
    """从 changelog 文件中解析出指定版本的条目内容。"""
    if not changelog_path.exists():
        return ""

    content = changelog_path.read_text(encoding="utf-8")

    # 清理 version 前缀 v
    raw_ver = version.lstrip("v").strip()
    escaped_ver = re.escape(raw_ver)

    # 匹配 ## [0.2.0] ... 或 ## v0.2.0 ... 或 ## 0.2.0 ...
    pattern = rf"^##\s+\[?(?:v)?{escaped_ver}\]?[^\n]*\n(.*?)(?=^##\s+|\Z)"
    match = re.search(pattern, content, flags=re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1).strip()

    # 如果没有精确匹配到版本标题，尝试匹配带有该版本号的行
    alt_pattern = rf"^##\s+.*?{escaped_ver}.*?\n(.*?)(?=^##\s+|\Z)"
    match_alt = re.search(alt_pattern, content, flags=re.MULTILINE | re.DOTALL)
    if match_alt:
        return match_alt.group(1).strip()

    return ""


def build_release_body(version: str, notes: str) -> str:
    """构建包含多平台安装指引与详细变更说明的 Markdown 正文。"""
    ver_clean = version.lstrip("v").strip()
    tag_clean = f"v{ver_clean}"

    header = f"""# 🚀 bdpan-cli {tag_clean} 发布说明

百度网盘工程化 CLI 管理工具。基于官方开放平台协议构建，支持多平台免安装独立二进制运行、多账号凭证管理与影视媒体库自动化刮削。

---

## 📦 快速安装 (Installation)

### 方式 1：uv tool 安装（推荐，隔离环境）
```bash
uv tool install bdpan-cli@{ver_clean}
# 若已安装旧版，执行升级：
uv tool upgrade bdpan-cli
```

### 方式 2：即用即走（免安装运行）
```bash
uvx bdpan-cli@{ver_clean} --help
```

### 方式 3：传统 pip 安装
```bash
pip install --upgrade bdpan-cli=={ver_clean}
```

### 方式 4：跨平台单文件二进制（免 Python 运行时）
可在下方 **Assets** 附件中直接下载对应操作系统单文件独立二进制可执行包，赋予执行权限后加入 `PATH` 即可运行：
- `bdpan-linux-amd64` (Linux x86_64)
- `bdpan-macos-arm64` (macOS Apple Silicon)
- `bdpan-windows-amd64.exe` (Windows x86_64)

---

## ⚡ 快速配置与登录 (Quickstart)

```bash
# 1. 配置百度开放平台凭证（全局配置一次，写入 ~/.config/bdpan/.env）
bdpan auth config --app-key <YOUR_APP_KEY> --secret-key <YOUR_SECRET_KEY>

# 2. 授权登录网盘账号（自动唤起默认浏览器打开授权页）
bdpan auth login

# 3. 立即使用
bdpan whoami
bdpan ls /
```

---

## 📝 详细更新日志 (Changelog)

"""
    if notes:
        return header + notes + "\n"

    return header + f"查看完整历史记录请参阅 [CHANGELOG.md](https://github.com/CodingRookie98/bdpan-cli/blob/main/docs/project/changelog.md)。\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="提取 GitHub Release 发布说明")
    parser.add_argument("--tag", help="Git Tag 名称 (如 v0.2.0)")
    parser.add_argument("--version", help="版本号 (如 0.2.0)")
    parser.add_argument(
        "--changelog",
        default="docs/project/changelog.md",
        help="Changelog 文件相对或绝对路径 (默认: docs/project/changelog.md)",
    )
    parser.add_argument("--output", help="输出 Markdown 文件路径 (默认打印到 stdout)")

    args = parser.parse_args()

    target_ver = args.version or args.tag
    if not target_ver:
        # 如果未提供，尝试从 src/bdpan_cli/_version.py 读取
        try:
            from bdpan_cli._version import __version__
            target_ver = __version__
        except ImportError:
            print("❌ 错误：请通过 --tag 或 --version 指定版本号", file=sys.stderr)
            return 1

    changelog_path = Path(args.changelog).resolve()
    notes = extract_notes_from_changelog(changelog_path, target_ver)
    body = build_release_body(target_ver, notes)

    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body, encoding="utf-8")
        print(f"✅ 成功生成发布说明至: {out_path} (版本: {target_ver})")
    else:
        print(body)

    return 0


if __name__ == "__main__":
    sys.exit(main())
