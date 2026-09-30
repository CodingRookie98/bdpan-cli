"""统一命令行工具入口 (bd-net-disc-mgr CLI)。"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any

from bdpan_cli.auth import TokenManager
from bdpan_cli.config import load_config
from bdpan_cli.file_manager import FileManager, FileManagerError
from bdpan_cli.foldering import execute_foldering, plan_foldering
from bdpan_cli.preview_scrape import generate_preview
from bdpan_cli.apply_scrape_rename import apply_renames

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bdpan_cli.cli")


def _get_file_manager() -> FileManager:
    config = load_config()
    token = TokenManager(config).get_access_token()
    return FileManager(token)


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


# ---------------------------------------------------------------------------
# 子命令实现
# ---------------------------------------------------------------------------

def cmd_ls(args: argparse.Namespace) -> int:
    mgr = _get_file_manager()
    path = args.path or "/"
    entries = mgr.list_dir(path, limit=args.limit)

    dirs = [e for e in entries if e.get("isdir") == 1]
    files = [e for e in entries if e.get("isdir") != 1]
    total_size = sum(f.get("size", 0) for f in files)

    print(f"\n📂 目录: {path} (共 {len(entries)} 项，包含 {len(dirs)} 个子目录，{len(files)} 个文件，总大小: {_format_size(total_size)})\n")
    for idx, e in enumerate(entries, 1):
        is_dir = e.get("isdir") == 1
        tag = "[DIR] " if is_dir else "[FILE]"
        size_str = "" if is_dir else f" ({_format_size(e.get('size', 0))})"
        print(f" {idx:3d}. {tag} {e.get('server_filename')}{size_str}")
    print()
    return 0


def cmd_mkdir(args: argparse.Namespace) -> int:
    mgr = _get_file_manager()
    path = args.path
    logger.info("正在创建目录: %s", path)
    res = mgr.mkdir(path)
    print(f"✅ 目录创建成功: {path}")
    return 0


def _resolve_dest(mgr: FileManager, src: str, dest: str) -> tuple[str, str]:
    """解析目标语义 (cp/mv 共用)。

    - dest 以 `/` 结尾，或 dest 是网盘上已存在的目录 → 复制/移入该目录并保持源名；
    - 否则将 dest 视为 `目标目录/新名`，实现复制/移动并改名。

    存在性判定依赖 dest 父目录的条目列表（百度 xpanfilelist 对不存在路径
    返回空列表而非报错，故不能直接 list dest）；父目录不可读时按改名语义
    处理，由后续 copy/move 在服务端报出真实错误。
    """
    src_name = os.path.basename(src.rstrip("/"))
    if dest.endswith("/"):
        return dest.rstrip("/") or "/", src_name
    dest_dir = os.path.dirname(dest) or "/"
    dest_name = os.path.basename(dest)
    try:
        siblings = mgr.list_dir(dest_dir)
    except FileManagerError:
        return dest_dir, dest_name
    dest_is_dir = any(
        e.get("path") == dest and e.get("isdir") == 1 for e in siblings
    )
    return (dest, src_name) if dest_is_dir else (dest_dir, dest_name)


def cmd_cp(args: argparse.Namespace) -> int:
    mgr = _get_file_manager()
    dest_dir, new_name = _resolve_dest(mgr, args.src, args.dest)
    logger.info("正在复制: %s -> %s/%s", args.src, dest_dir, new_name)
    mgr.copy(args.src, dest_dir, new_name)
    print(f"✅ 复制成功: {args.src} -> {dest_dir}/{new_name}")
    return 0


def cmd_mv(args: argparse.Namespace) -> int:
    mgr = _get_file_manager()
    src = args.src
    dest_dir, dest_name = _resolve_dest(mgr, src, args.dest)
    logger.info("正在移动: %s -> %s/%s", src, dest_dir, dest_name)
    res = mgr.batch_move([(src, dest_dir, dest_name)])
    print(f"✅ 移动成功: {src} -> {dest_dir}/{dest_name}")
    return 0


def cmd_rm(args: argparse.Namespace) -> int:
    mgr = _get_file_manager()
    targets = args.paths
    print("⚠️  将从网盘删除以下条目（服务端移入回收站）:")
    for p in targets:
        print(f"  - {p}")
    if not args.yes:
        answer = input(f"确认删除 {len(targets)} 项? [y/N]: ").strip().lower()
        if answer != "y":
            print("已取消，未做任何变更。")
            return 0
    failed = 0
    for p in targets:
        try:
            mgr.delete(p)
            print(f"✅ 已删除: {p}")
        except FileManagerError as e:
            print(f"❌ 删除失败: {p} ({e})")
            failed += 1
    return 1 if failed else 0


def cmd_rename(args: argparse.Namespace) -> int:
    mgr = _get_file_manager()
    logger.info("正在重命名: %s -> %s", args.path, args.new_name)
    mgr.rename(args.path, args.new_name)
    print(f"✅ 重命名成功: {args.path} -> {args.new_name}")
    return 0


def cmd_scrape_preview(args: argparse.Namespace) -> int:
    target_dir = args.dir
    output_file = args.output
    skip_conforming = not args.all
    logger.info("启动刮削预演: dir=%s, output=%s, skip_conforming=%s", target_dir, output_file, skip_conforming)
    generate_preview(
        target_dir=target_dir,
        output_file=output_file,
        skip_conforming=skip_conforming,
        limit=args.limit,
    )
    print(f"\n✅ 刮削预演完成，对照表已生成至: {output_file}\n")
    return 0


def cmd_scrape_apply(args: argparse.Namespace) -> int:
    preview_file = args.preview_file
    target_dir = args.target_dir
    batch_size = args.batch_size
    logger.info("启动批量更名应用: preview=%s, batch_size=%d", preview_file, batch_size)
    apply_renames(preview_file=preview_file, target_dir=target_dir, batch_size=batch_size)
    print("\n✅ 批量重命名应用完成！\n")
    return 0


def cmd_scrape_foldering(args: argparse.Namespace) -> int:
    mgr = _get_file_manager()
    target_dir = args.dir
    dry_run = args.dry_run
    batch_size = args.batch_size

    plan = plan_foldering(target_dir, mgr)
    if not plan:
        print(f"⚠️  在目录 {target_dir} 中未发现任何待整理的媒体文件。")
        return 0

    total_files = sum(len(g["files"]) for g in plan)
    print(f"\n📋 扫描发现 {total_files} 个散落媒体文件，拟归集为 {len(plan)} 个方案 A 规范电影目录：\n")
    for idx, group in enumerate(plan, 1):
        print(f"[{idx:2d}] 📁 {group['target_folder_name']}")
        for f in group["files"]:
            print(f"     └── 📄 {f['filename']} ({_format_size(f['size'])})")
    print()

    if dry_run:
        print("💡 当前为 --dry-run 预演模式，未对网盘进行任何实际变更。")
        return 0

    logger.info("开始执行散落文件建目录与归集...")
    res = execute_foldering(target_dir, plan, mgr, batch_size=batch_size)
    print(f"\n🎉 整理归集执行完毕！成功创建 {res['folders_created']} 个规范目录，原子归集 {res['files_moved']} 个文件。\n")
    return 0


def cmd_meta_nfo(args: argparse.Namespace) -> int:
    print(f"🚧 元数据生成模块开发中 (Target: {args.dir})")
    return 0


def cmd_meta_poster(args: argparse.Namespace) -> int:
    print(f"🚧 海报抓取与上传模块开发中 (Target: {args.dir})")
    return 0


# ---------------------------------------------------------------------------
# CLI 参数解析与调度
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bdpan",
        description="百度网盘工程化 CLI 管理工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用子命令")

    # 1. ls
    p_ls = subparsers.add_parser("ls", help="列出网盘指定路径内容")
    p_ls.add_argument("path", nargs="?", default="/", help="网盘目录路径 (默认: /)")
    p_ls.add_argument("--limit", type=int, default=1000, help="最多读取条目数 (默认: 1000)")
    p_ls.set_defaults(func=cmd_ls)

    # 2. mkdir
    p_mkdir = subparsers.add_parser("mkdir", help="在网盘中创建新目录")
    p_mkdir.add_argument("path", help="待创建的目录路径")
    p_mkdir.set_defaults(func=cmd_mkdir)

    # 3. mv
    p_mv = subparsers.add_parser("mv", help="移动网盘文件或目录")
    p_mv.add_argument("src", help="源文件路径")
    p_mv.add_argument("dest", help="目标目录路径")
    p_mv.set_defaults(func=cmd_mv)

    # 3.1 cp
    p_cp = subparsers.add_parser(
        "cp",
        help="复制网盘文件或目录（目标为已存在目录时复制入内，否则视为 目标目录/新名）",
    )
    p_cp.add_argument("src", help="源文件或目录路径")
    p_cp.add_argument("dest", help="目标目录路径，或 目标目录/新名")
    p_cp.set_defaults(func=cmd_cp)

    # 3.2 rm
    p_rm = subparsers.add_parser(
        "rm",
        help="删除网盘文件或目录（默认交互确认，-y 跳过；服务端移入回收站）",
    )
    p_rm.add_argument("paths", nargs="+", help="待删除的一个或多个路径")
    p_rm.add_argument("-y", "--yes", action="store_true", help="跳过确认直接删除")
    p_rm.set_defaults(func=cmd_rm)

    # 3.3 rename
    p_rename = subparsers.add_parser("rename", help="原地重命名网盘文件或目录")
    p_rename.add_argument("path", help="待重命名的文件或目录路径")
    p_rename.add_argument("new_name", help="新名称（仅名称，不含目录）")
    p_rename.set_defaults(func=cmd_rename)

    # 4. scrape
    p_scrape = subparsers.add_parser("scrape", help="媒体库电影刮削与整理系统")
    scrape_sub = p_scrape.add_subparsers(dest="scrape_cmd", help="刮削子命令")

    # 4.1 scrape preview
    p_preview = scrape_sub.add_parser("preview", help="扫描并生成方案 A 刮削更名预览")
    p_preview.add_argument("dir", nargs="?", default="/影视/电影/watched", help="目标目录")
    p_preview.add_argument("-o", "--output", default="scrape_preview.json", help="输出 json 路径")
    p_preview.add_argument("--all", action="store_true", help="不跳过已合规目录，全量扫描")
    p_preview.add_argument("--limit", type=int, default=None, help="最大条目限制")
    p_preview.set_defaults(func=cmd_scrape_preview)

    # 4.2 scrape apply
    p_apply = scrape_sub.add_parser("apply", help="安全应用预览结果并执行网盘批量重命名")
    p_apply.add_argument("preview_file", nargs="?", default="scrape_preview.json", help="预览 json 文件")
    p_apply.add_argument("--target-dir", default=None, help="覆盖校验目录")
    p_apply.add_argument("--batch-size", type=int, default=25, help="单批提交大小 (默认: 25)")
    p_apply.set_defaults(func=cmd_scrape_apply)

    # 4.3 scrape foldering
    p_folder = scrape_sub.add_parser("foldering", help="自动为散落媒体文件创建方案 A 独立规范目录并移入")
    p_folder.add_argument("dir", nargs="?", default="/影视/电影/unscraped", help="散落文件所在父目录")
    p_folder.add_argument("--dry-run", action="store_true", help="仅预演规划，不实际修改网盘")
    p_folder.add_argument("--batch-size", type=int, default=25, help="单批移动大小")
    p_folder.set_defaults(func=cmd_scrape_foldering)

    # 5. meta (第三阶段预留)
    p_meta = subparsers.add_parser("meta", help="元数据与海报抓取上传子系统")
    meta_sub = p_meta.add_subparsers(dest="meta_cmd", help="元数据子命令")

    p_nfo = meta_sub.add_parser("nfo", help="批量生成 movie.nfo")
    p_nfo.add_argument("dir", help="电影目录或父目录")
    p_nfo.add_argument("--dry-run", action="store_true", help="仅预演生成，不上传")
    p_nfo.set_defaults(func=cmd_meta_nfo)

    p_poster = meta_sub.add_parser("poster", help="批量下载并上传 poster.jpg")
    p_poster.add_argument("dir", help="电影目录或父目录")
    p_poster.add_argument("--dry-run", action="store_true", help="仅预演抓取，不上传")
    p_poster.set_defaults(func=cmd_meta_poster)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args_list = argv if argv is not None else sys.argv[1:]

    # 向后兼容：如果第一个参数是以 '/' 开头的网盘路径且不是已定义的子命令，则自动重定向为 ls <path>
    if args_list and args_list[0].startswith("/") and args_list[0] not in parser._subparsers._group_actions[0].choices:
        args_list = ["ls", args_list[0]] + args_list[1:]

    args = parser.parse_args(args_list)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
