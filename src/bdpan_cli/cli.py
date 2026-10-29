"""统一命令行工具入口 (bd-net-disc-mgr CLI)。"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any

from bdpan_cli.account import AccountClient, AccountError
from bdpan_cli.auth import TOKEN_CACHE, TokenManager
from bdpan_cli.config import load_config
from bdpan_cli.dedup import execute_dedup, plan_dedup
from bdpan_cli.downloader import DownloadError, Downloader
from bdpan_cli.file_manager import FileManager, FileManagerError
from bdpan_cli.foldering import execute_foldering, plan_foldering
from bdpan_cli.media_info import MediaInfoClient, MediaInfoError
from bdpan_cli.mcp_server import BdpanMcpServer
from bdpan_cli.ops import OperationLogger, UndoEngine, UndoError
from bdpan_cli.preview_scrape import generate_preview
from bdpan_cli.uploader import Uploader
from bdpan_cli.apply_scrape_rename import apply_renames
from bdpan_cli.logger import setup_logging, get_logger

logger = get_logger("bdpan_cli.cli")

# 断点续传状态文件：与 token 缓存同目录（项目根，git-ignored）
UPLOAD_STATE_FILE = TOKEN_CACHE.parent / ".bdpan_uploads.json"


def _output_envelope(data: Any = None, success: bool = True, code: int = 0, error: str | None = None) -> int:
    """输出标准结构化 JSON 信封，适用于 --json 模式。"""
    payload = {
        "success": success,
        "code": code,
        "data": data,
        "error": error,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


def _get_token_manager(args: argparse.Namespace | None = None) -> TokenManager:
    config = load_config()
    account = getattr(args, "account", None) if args else None
    return TokenManager(config, account=account)


def _get_file_manager(args: argparse.Namespace | None = None) -> FileManager:
    token = _get_token_manager(args).get_access_token()
    return FileManager(token)


def _get_account_client(args: argparse.Namespace | None = None) -> AccountClient:
    token = _get_token_manager(args).get_access_token()
    return AccountClient(token)


def _get_downloader(args: argparse.Namespace | None = None) -> Downloader:
    token = _get_token_manager(args).get_access_token()
    return Downloader(token)


def _get_media_info_client(args: argparse.Namespace | None = None) -> MediaInfoClient:
    token = _get_token_manager(args).get_access_token()
    return MediaInfoClient(token)


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
    mgr = _get_file_manager(args)
    raw_path = args.path or "/"
    path = "/" + raw_path.strip("/") if raw_path != "/" else "/"
    entries = mgr.list_dir(path, limit=args.limit)

    if not entries and path != "/":
        parent_dir = os.path.dirname(path) or "/"
        target_name = os.path.basename(path)
        try:
            siblings = mgr.list_dir(parent_dir)
            match = next(
                (e for e in siblings if e.get("server_filename") == target_name or e.get("path") == path),
                None,
            )
            if not match:
                if getattr(args, "json", False):
                    return _output_envelope(None, success=False, code=1, error=f"路径不存在: {path}")
                print(f"❌ 路径不存在: {path}")
                return 1
            if match.get("isdir") != 1:
                if getattr(args, "json", False):
                    return _output_envelope([match])
                size_str = _format_size(match.get("size", 0))
                print(f"\n📄 文件: {path} ({size_str})\n")
                return 0
        except FileManagerError:
            pass

    if getattr(args, "json", False):
        return _output_envelope(entries)

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
    mgr = _get_file_manager(args)
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
        logger.warning(
            "探测 dest 父目录失败 [%s 不可读]，按「目标目录/新名」改名语义处理，真实错误由后续 copy/move 报出",
            dest_dir,
        )
        return dest_dir, dest_name
    dest_is_dir = any(
        e.get("path") == dest and e.get("isdir") == 1 for e in siblings
    )
    return (dest, src_name) if dest_is_dir else (dest_dir, dest_name)


def _require_dest_dir(mgr: FileManager, dest: str) -> str:
    """多源批量目标必须是目录语义。

    dest 以 / 结尾直接放行；否则探测父目录确认 dest 为已存在目录。
    不满足时抛 FileManagerError（调用方转译为退出码 1）。
    """
    if dest.endswith("/"):
        return dest.rstrip("/") or "/"
    try:
        siblings = mgr.list_dir(os.path.dirname(dest) or "/")
    except FileManagerError:
        siblings = []
    if any(e.get("path") == dest and e.get("isdir") == 1 for e in siblings):
        return dest
    raise FileManagerError(f"多源批量操作要求目标为已存在目录（或以 / 结尾）: {dest}")


def cmd_cp(args: argparse.Namespace) -> int:
    mgr = _get_file_manager(args)
    srcs = args.srcs
    if len(srcs) == 1:
        dest_dir, new_name = _resolve_dest(mgr, srcs[0], args.dest)
        logger.info("正在复制: %s -> %s/%s", srcs[0], dest_dir, new_name)
        mgr.copy(srcs[0], dest_dir, new_name)
        print(f"✅ 复制成功: {srcs[0]} -> {dest_dir}/{new_name}")
        return 0

    try:
        dest_dir = _require_dest_dir(mgr, args.dest)
    except FileManagerError as e:
        print(f"❌ {e}")
        return 1
    payloads = [(s, dest_dir, os.path.basename(s.rstrip("/"))) for s in srcs]
    logger.info("正在批量复制 %d 项 -> %s/", len(payloads), dest_dir)
    mgr.batch_copy(payloads)
    print(f"✅ 批量复制成功: {len(payloads)} 项 -> {dest_dir}/")
    return 0


def cmd_mv(args: argparse.Namespace) -> int:
    mgr = _get_file_manager(args)
    srcs = args.srcs
    account = getattr(args, "account", None) or "default"
    if len(srcs) == 1:
        src = srcs[0]
        dest_dir, dest_name = _resolve_dest(mgr, src, args.dest)
        logger.info("正在移动: %s -> %s/%s", src, dest_dir, dest_name)
        mgr.batch_move([(src, dest_dir, dest_name)])
        dest_path = f"{dest_dir.rstrip('/')}/{dest_name}"
        op_id = OperationLogger().record_operation("mv", [{"src": src, "dest": dest_path}], account=account)
        print(f"✅ 移动成功: {src} -> {dest_path} (流水号: {op_id})")
        return 0

    try:
        dest_dir = _require_dest_dir(mgr, args.dest)
    except FileManagerError as e:
        print(f"❌ {e}")
        return 1
    payloads = [(s, dest_dir, os.path.basename(s.rstrip("/"))) for s in srcs]
    logger.info("正在批量移动 %d 项 -> %s/", len(payloads), dest_dir)
    mgr.batch_move(payloads)
    items = [{"src": s, "dest": f"{dest_dir.rstrip('/')}/{n}"} for s, _, n in payloads]
    op_id = OperationLogger().record_operation("mv", items, account=account)
    print(f"✅ 批量移动成功: {len(payloads)} 项 -> {dest_dir}/ (流水号: {op_id})")
    return 0


def cmd_rm(args: argparse.Namespace) -> int:
    mgr = _get_file_manager(args)
    targets = args.paths
    print("⚠️  将从网盘删除以下条目（服务端移入回收站）:")
    for p in targets:
        print(f"  - {p}")
    if not args.yes:
        try:
            answer = input(f"确认删除 {len(targets)} 项? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            # 非交互 stdin 或 Ctrl-C 视作取消，与主动回答 N 同语义
            print("\n已取消，未做任何变更。")
            return 0
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
    mgr = _get_file_manager(args)
    logger.info("正在重命名: %s -> %s", args.path, args.new_name)
    mgr.rename(args.path, args.new_name)
    parent = os.path.dirname(args.path) or "/"
    dest_path = f"{parent.rstrip('/')}/{args.new_name}"
    account = getattr(args, "account", None) or "default"
    op_id = OperationLogger().record_operation("rename", [{"src": args.path, "dest": dest_path}], account=account)
    print(f"✅ 重命名成功: {args.path} -> {args.new_name} (流水号: {op_id})")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    mgr = _get_file_manager(args)
    entries = mgr.search(
        args.key,
        dir_path=args.dir,
        recursion=not args.no_recursion,
        page=args.page,
        num=args.num,
    )
    if getattr(args, "json", False):
        return _output_envelope(entries)

    if not entries:
        print(f"🔍 未找到与「{args.key}」匹配的条目。")
        return 0
    dirs = [e for e in entries if e.get("isdir") == 1]
    files = [e for e in entries if e.get("isdir") != 1]
    total_size = sum(f.get("size", 0) for f in files)
    print(
        f"\n🔍 搜索「{args.key}」第 {args.page} 页: 共 {len(entries)} 项"
        f"（{len(dirs)} 个目录，{len(files)} 个文件，合计 {_format_size(total_size)}）\n"
    )
    for idx, e in enumerate(entries, 1):
        is_dir = e.get("isdir") == 1
        tag = "[DIR] " if is_dir else "[FILE]"
        size_str = "" if is_dir else f" ({_format_size(e.get('size', 0))})"
        print(f" {idx:3d}. {tag} {e.get('path')}{size_str}")
    if len(entries) == args.num:
        print(f"\n💡 本页结果已满，可能还有更多，可尝试 --page {args.page + 1} 翻页。")
    print()
    return 0


def cmd_tree(args: argparse.Namespace) -> int:
    mgr = _get_file_manager(args)
    root = args.path or "/"
    logger.info("递归遍历目录树: root=%s, max_depth=%s", root, args.depth)
    entries, errors = mgr.walk(root, max_depth=args.depth)

    dirs = [e for _, e in entries if e.get("isdir") == 1]
    files = [e for _, e in entries if e.get("isdir") != 1]
    total_size = sum(f.get("size", 0) for f in files)
    print(
        f"🌲 {root} (递归 {len(dirs)} 个子目录，{len(files)} 个文件，"
        f"总计 {_format_size(total_size)})\n"
    )
    for depth, e in entries:
        is_dir = e.get("isdir") == 1
        indent = "    " * depth
        marker = "📁" if is_dir else "📄"
        size_str = "" if is_dir else f" ({_format_size(e.get('size', 0))})"
        print(f"{indent}{marker} {e.get('server_filename')}{size_str}")

    if args.index:
        payload = {
            "version": 1,
            "root": root,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "stats": {"dirs": len(dirs), "files": len(files), "total_size": total_size},
            "errors": [{"path": p, "error": msg} for p, msg in errors],
            "entries": [e for _, e in entries],
        }
        with open(args.index, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\n💾 本地索引已写入: {args.index} ({len(entries)} 条)")

    if errors:
        print(f"\n⚠️  {len(errors)} 个子目录读取失败，遍历结果不完整:")
        for path, msg in errors:
            print(f"  - {path}: {msg}")
        return 1
    return 0


def _print_upload_progress(event: dict[str, Any]) -> None:
    phase = event["phase"]
    if phase == "precreate":
        print("📡 预上传完成，已获取上传任务 ID")
    elif phase == "resume":
        print(f"💡 断点续传: 已有 {event['present']} 片在云端，补传 {event['missing']} 片")
    elif phase == "chunk":
        print(f"  ⬆️  分片 {event['seq'] + 1}/{event['total']} 上传成功")


def cmd_upload(args: argparse.Namespace) -> int:
    local = args.local_path
    if not os.path.isfile(local):
        print(f"❌ 本地文件不存在: {local}")
        return 1

    mgr = _get_file_manager(args)
    # 目标语义与 cp 一致：尾斜杠/已存在目录 → 保持本地文件名；否则 目标目录/新名
    dest_dir, new_name = _resolve_dest(mgr, local, args.remote_dest)
    remote_path = (dest_dir.rstrip("/") or "") + "/" + new_name

    uploader = Uploader(mgr.access_token, mgr.api_client)
    rtype = 3 if args.overwrite else 1
    logger.info("开始上传: %s -> %s (rtype=%d)", local, remote_path, rtype)
    res = uploader.upload(
        local,
        remote_path,
        rtype=rtype,
        progress=_print_upload_progress,
        state_file=UPLOAD_STATE_FILE,
    )
    size_str = _format_size(int(res.get("size") or 0))
    print(f"✅ 上传成功: {res.get('path') or remote_path} ({size_str})")
    if res.get("server_filename") and res.get("server_filename") != new_name:
        print(f"ℹ️  云端冲突已自动改名: {new_name} -> {res['server_filename']}")
    return 0


def cmd_scrape_preview(args: argparse.Namespace) -> int:
    target_dir = args.dir
    output_file = args.output
    skip_conforming = not args.all
    name_format = getattr(args, "format", None)
    logger.info("启动刮削预演: dir=%s, output=%s, format=%s, skip_conforming=%s", target_dir, output_file, name_format, skip_conforming)
    generate_preview(
        target_dir=target_dir,
        output_file=output_file,
        skip_conforming=skip_conforming,
        limit=args.limit,
        name_format=name_format,
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
    mgr = _get_file_manager(args)
    target_dir = args.dir
    dry_run = args.dry_run
    batch_size = args.batch_size
    name_format = getattr(args, "format", None)

    plan = plan_foldering(target_dir, mgr, name_format=name_format)
    if not plan:
        print(f"⚠️  在目录 {target_dir} 中未发现任何待整理的媒体文件。")
        return 0

    total_files = sum(len(g["files"]) for g in plan)
    fmt_desc = f"（使用自定义模板: {name_format}）" if name_format else "（方案 A 规范）"
    print(f"\n📋 扫描发现 {total_files} 个散落媒体文件，拟归集为 {len(plan)} 个电影目录 {fmt_desc}：\n")
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


def _format_vip(vip_type: Any) -> str:
    return {0: "普通用户", 1: "普通会员", 2: "超级会员"}.get(vip_type, f"未知({vip_type})")


def cmd_quota(args: argparse.Namespace) -> int:
    client = _get_account_client(args)
    res = client.quota(check_expire=args.check_expire, check_free=args.check_free)
    if getattr(args, "json", False):
        return _output_envelope(res)
    total = int(res.get("total") or 0)
    used = int(res.get("used") or 0)
    print("💾 网盘容量:")
    print(f"  总容量: {_format_size(total)}")
    print(f"  已用:   {_format_size(used)}")
    if total > 0:
        print(f"  可用:   {_format_size(max(total - used, 0))} (使用率 {used / total * 100:.1f}%)")
    if res.get("free") is not None:
        print(f"  免费配额: {_format_size(int(res['free']))}")
    expire = res.get("expire")
    if expire:
        expire_str = datetime.fromtimestamp(int(expire)).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  会员容量到期: {expire_str}")
    return 0


def cmd_whoami(args: argparse.Namespace) -> int:
    client = _get_account_client(args)
    res = client.user_info()
    if getattr(args, "json", False):
        return _output_envelope(res)
    print("👤 网盘账户信息:")
    print(f"  百度账号: {res.get('baidu_name') or '-'}")
    print(f"  网盘名:   {res.get('netdisk_name') or '-'}")
    print(f"  会员类型: {_format_vip(res.get('vip_type'))}")
    return 0


def cmd_dedup(args: argparse.Namespace) -> int:
    mgr = _get_file_manager(args)
    raw_path = args.path or "/"
    target_dir = "/" + raw_path.strip("/") if raw_path != "/" else "/"

    if args.staging_dir:
        staging_dir = "/" + args.staging_dir.strip("/")
        if staging_dir == target_dir:
            print(f"❌ 隔离目录不能与待扫描目录相同: {staging_dir}")
            return 1
    else:
        staging_dir = None

    logger.info("扫描冲突副本: target=%s, recursive=%s", target_dir, args.recursive)
    try:
        plan = plan_dedup(
            dir_path=target_dir,
            mgr=mgr,
            recursive=args.recursive,
            include_orphans=args.include_orphans,
            include_empty=args.include_empty,
        )
    except FileManagerError as e:
        print(f"❌ 扫描失败: {e}")
        return 1

    if not plan.candidates:
        print(f"✨ 目录 {target_dir} 中未发现任何冲突副本或重复条目。")
        if plan.orphan_groups_count > 0:
            print(f"💡 发现 {plan.orphan_groups_count} 组无主冲突副本（如仅有 (1) 与 (2)），可添加 --include-orphans 一并治理。")
        return 0

    dirs_count = sum(1 for c in plan.candidates if c.isdir)
    files_count = sum(1 for c in plan.candidates if not c.isdir)
    print(
        f"\n📋 发现 {len(plan.candidates)} 个冲突与重复条目"
        f"（{dirs_count} 个目录，{files_count} 个文件，合计 {_format_size(plan.total_size)}）：\n"
    )
    for idx, c in enumerate(plan.candidates, 1):
        tag = "[DIR] " if c.isdir else "[FILE]"
        size_str = "" if c.isdir else f" ({_format_size(c.size)})"
        print(f" {idx:3d}. {tag} {c.path}{size_str}")
        print(f"      原因: {c.reason}")
    print()

    # 动作决策
    if args.dry_run or (not staging_dir and not args.delete):
        if args.dry_run:
            print("💡 当前为 --dry-run 预演模式，未对网盘进行任何实际变更。")
            if staging_dir:
                print(f"   拟隔离至: {staging_dir}")
            elif args.delete:
                print("   拟移入回收站直接删除。")
            return 0
        print("💡 提示: 当前未指定治理动作（预览模式）。可使用以下参数执行治理：")
        print("  --staging-dir <dir>  移动至指定暂存目录隔离（推荐，如 /videos/movies/pending_delete）")
        print("  --delete             直接删除移入回收站")
        print("  --dry-run            预演查看影响范围")
        return 0

    if staging_dir:
        if not args.yes:
            try:
                ans = input(f"确认将 {len(plan.candidates)} 项移动到隔离目录 {staging_dir}? [y/N]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n已取消，未做任何变更。")
                return 0
            if ans != "y":
                print("已取消，未做任何变更。")
                return 0

        res = execute_dedup(plan, mgr, staging_dir=staging_dir, batch_size=50)
        print(f"\n🎉 治理完成！已成功将 {res['moved']} 项移入隔离目录: {staging_dir}\n")
        return 0

    if args.delete:
        if not args.yes:
            try:
                ans = input(f"⚠️  确认将 {len(plan.candidates)} 项从网盘删除（服务端移入回收站）? [y/N]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n已取消，未做任何变更。")
                return 0
            if ans != "y":
                print("已取消，未做任何变更。")
                return 0

        res = execute_dedup(plan, mgr, delete=True, batch_size=50)
        print(f"\n🎉 治理完成！已成功从网盘删除 {res['deleted']} 项（已移入回收站）。\n")
        return 0

    return 0


def cmd_download(args: argparse.Namespace) -> int:
    """下载网盘文件到本地。"""
    downloader = _get_downloader()
    dest = args.dest or "."
    paths = args.paths
    if not paths:
        print("❌ 请指定要下载的网盘文件路径")
        return 1

    success_count = 0
    fail_count = 0

    print(f"\n📦 开始批量下载任务，共 {len(paths)} 个目标，保存至: {dest}\n")

    for idx, remote_path in enumerate(paths, 1):
        print(f"[{idx}/{len(paths)}] ⬇️  正在下载: {remote_path}")

        def _progress(ev: dict[str, Any]) -> None:
            if ev.get("phase") == "download":
                cur = _format_size(ev["downloaded"])
                tot = _format_size(ev["total"])
                spd = _format_size(int(ev.get("speed", 0)))
                pct = (ev["downloaded"] / ev["total"] * 100) if ev["total"] > 0 else 0
                print(f"\r    ⏳ 进度: {pct:.1f}% ({cur}/{tot}) @ {spd}/s", end="", flush=True)

        try:
            local_path = downloader.download_file(
                remote_path,
                local_dest=dest,
                overwrite=args.overwrite,
                progress=_progress,
            )
            print(f"\n    ✅ 完成: {local_path}")
            success_count += 1
        except DownloadError as e:
            print(f"\n    ❌ 失败: {e}")
            fail_count += 1

    print(f"\n🏁 下载任务结束: 成功 {success_count} 个，失败 {fail_count} 个。\n")
    return 1 if fail_count > 0 else 0


def cmd_dlink(args: argparse.Namespace) -> int:
    """查询或导出网盘文件高速下载直链。"""
    downloader = _get_downloader(args)
    paths = args.paths
    if not paths:
        print("❌ 请指定网盘文件路径")
        return 1

    fail_count = 0
    for path in paths:
        try:
            meta = downloader.get_dlink(path)
            dlink = meta["dlink"]
            size_str = _format_size(meta.get("size", 0))
            filename = meta.get("server_filename", os.path.basename(path))

            if args.aria2:
                cmd = downloader.generate_export_command(dlink, filename, style="aria2")
                print(cmd)
            elif args.curl:
                cmd = downloader.generate_export_command(dlink, filename, style="curl")
                print(cmd)
            else:
                print(f"📄 文件: {path} ({size_str})")
                print(f"🔗 直链: {dlink}")
                print(f"💡 说明: 直链请求头须携带 User-Agent: pan.baidu.com\n")
        except DownloadError as e:
            print(f"❌ 获取失败 [{path}]: {e}", file=sys.stderr)
            fail_count += 1

    return 1 if fail_count > 0 else 0


def cmd_ops(args: argparse.Namespace) -> int:
    """查看网盘操作审计流水。"""
    subcmd = getattr(args, "ops_subcmd", None)
    logger_instance = OperationLogger()

    if subcmd == "show":
        op = logger_instance.get_operation(args.op_id)
        if getattr(args, "json", False):
            if not op:
                return _output_envelope(None, success=False, code=1, error=f"未找到操作流水: {args.op_id}")
            return _output_envelope(op)
        if not op:
            print(f"❌ 未找到操作流水: {args.op_id}", file=sys.stderr)
            return 1
        status_str = "已撤销" if op.get("undone") else "正常"
        print(f"\n📋 操作流水详情 [{op['op_id']}]")
        print(f"  时间: {op.get('created_at')}")
        print(f"  命令: {op.get('command')}")
        print(f"  账号: {op.get('account')}")
        print(f"  状态: {status_str}")
        if op.get("undone_at"):
            print(f"  撤销时间: {op.get('undone_at')}")
        items = op.get("items") or []
        print(f"\n  变更映射清单 (共 {len(items)} 项):")
        for idx, item in enumerate(items, 1):
            print(f"    {idx}. {item.get('src')} -> {item.get('dest')}")
        print()
        return 0

    # 默认 list
    limit = getattr(args, "limit", 20) or 20
    ops = logger_instance.list_operations(limit=limit)
    if getattr(args, "json", False):
        return _output_envelope(ops)
    if not ops:
        print("📜 暂无操作审计流水。")
        return 0

    print(f"\n📜 历史操作审计流水 (最近 {len(ops)} 条):")
    print("-" * 80)
    for op in ops:
        status_tag = "[已撤销]" if op.get("undone") else "正常"
        items_cnt = len(op.get("items") or [])
        print(
            f"  [{op['op_id']}] | {op.get('created_at', '')[:19]} | "
            f"命令: {op.get('command', ''):<6} | 账号: {op.get('account', 'default'):<8} | "
            f"影响: {items_cnt} 项 | 状态: {status_tag}"
        )
    print("-" * 80)
    print("💡 使用 bdpan ops show <op_id> 查看详情，或 bdpan undo <op_id> 进行逆向回滚。\n")
    return 0


def cmd_undo(args: argparse.Namespace) -> int:
    """逆向撤销历史批量操作。"""
    mgr = _get_file_manager(args)
    engine = UndoEngine(mgr)
    op_id = args.op_id

    try:
        plan = engine.plan_undo(op_id)
    except UndoError as e:
        print(f"❌ 无法撤销: {e}", file=sys.stderr)
        return 1

    reversals = plan.get("reversals") or []
    if not reversals:
        print(f"⚠️  操作 [{op_id}] 无可撤销条目。")
        return 0

    print(f"\n🔍 逆向回滚计划 [{op_id}] (共 {len(reversals)} 项):")
    for r in reversals:
        print(f"  ↩️  {r['src']} -> {r['dest_dir']}/{r['newname']}")
    print()

    if args.dry_run:
        print("💡 [dry-run] 仅预演逆向方案，未执行任何网盘变更。")
        return 0

    if not args.yes:
        try:
            ans = input(f"⚠️  确认执行逆向回滚（共 {len(reversals)} 项）? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消，未做任何变更。")
            return 0
        if ans != "y":
            print("已取消，未做任何变更。")
            return 0

    try:
        res = engine.execute_undo(op_id, dry_run=False)
        print(f"🎉 撤销成功！已成功逆向还原 {res['undone_count']} 项。\n")
        return 0
    except UndoError as e:
        print(f"❌ 撤销执行失败: {e}", file=sys.stderr)
        return 1


def cmd_auth(args: argparse.Namespace) -> int:
    """网盘账号认证与多租户管理。"""
    subcmd = getattr(args, "auth_subcmd", None)
    tm = _get_token_manager(args)

    if subcmd == "switch":
        alias = args.alias
        try:
            tm.switch_account(alias)
            print(f"✅ 成功切换当前活跃账号为: {alias}")
            return 0
        except ValueError as e:
            print(f"❌ 切换失败: {e}", file=sys.stderr)
            return 1

    if subcmd == "login":
        alias = getattr(args, "account", None) or tm.get_active_account()
        print(f"🔑 正在为账号 [{alias}] 启动设备码授权流程...")
        tm._account = alias
        try:
            tm.get_access_token()
            print(f"🎉 账号 [{alias}] 授权成功！")
            return 0
        except Exception as e:
            print(f"❌ 授权失败: {e}", file=sys.stderr)
            return 1

    # 默认 list
    accounts = tm.list_accounts()
    active = tm.get_active_account()
    if getattr(args, "json", False):
        return _output_envelope({"current": active, "accounts": accounts})
    print("\n🔑 本地网盘账号认证列表:")
    print("-" * 65)
    if not accounts:
        print("  (暂无保存的账号，请执行 bdpan auth login 进行首次登录)")
    else:
        for acc in accounts:
            marker = "*" if acc["is_current"] else " "
            status = "有效" if acc["valid"] else "已过期"
            exp_str = datetime.fromtimestamp(acc["expires_at"]).strftime("%Y-%m-%d %H:%M:%S") if acc["expires_at"] else "未知"
            print(f"  {marker} {acc['account']:<12} | {status:<6} | 到期时间: {exp_str}")
    print("-" * 65)
    print(f"当前活跃账号: {active}")
    print("💡 使用 bdpan auth switch <alias> 切换当前默认账号")
    print("💡 或在任意命令前指定全局参数 bdpan --account <alias> <subcommand>\n")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """探测视频与多媒体文件的深度元数据。"""
    mc = _get_media_info_client(args)
    path = args.path
    try:
        info = mc.get_media_info(path)
    except MediaInfoError as e:
        if getattr(args, "json", False):
            return _output_envelope(None, success=False, code=1, error=str(e))
        print(f"❌ 解析失败: {e}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        return _output_envelope(info)

    print(f"\n🎬 媒体元数据 [{info['filename']}]:")
    print(f"  文件路径: {info['path']}")
    print(f"  文件大小: {_format_size(info['size'])}")
    print(f"  媒体分类: {info['category']}")
    if info["is_video"]:
        print(f"  视频分辨率: {info['resolution']}")
        print(f"  视频时长:   {info['duration_formatted']} ({info['duration_seconds']} 秒)")
        print(f"  视频编码:   {info['video_codec']}")
        print(f"  包含音轨:   {info['audio_tracks_count']} 条")
    print(f"  MD5 校验值: {info.get('md5') or '-'}\n")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """递归聚合统计目录下的容量、文件数与媒体分类分布。"""
    mc = _get_media_info_client(args)
    path = args.path or "/"
    stats = mc.get_dir_stats(path, max_depth=args.depth)
    if getattr(args, "json", False):
        return _output_envelope(stats)

    print(f"\n📊 目录聚合统计 [{stats['root']}]:")
    print(f"  总容量: {_format_size(stats['total_size'])}")
    print(f"  文件总数: {stats['total_files']} 个")
    print(f"  子目录数: {stats['total_dirs']} 个")
    print("\n  媒体类别分布:")
    for cat, detail in stats["by_category"].items():
        if detail["count"] > 0:
            print(f"    - {cat:<10}: {detail['count']:>4d} 个 ({_format_size(detail['size'])})")
    if stats["by_extension"]:
        print("\n  扩展名分布 Top 5:")
        for ext, detail in list(stats["by_extension"].items())[:5]:
            print(f"    - {ext:<10}: {detail['count']:>4d} 个 ({_format_size(detail['size'])})")
    print()
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    """启动原生 Model Context Protocol (MCP) Server。"""
    def _token_getter() -> str:
        return _get_token_manager(args).get_access_token()

    server = BdpanMcpServer(_token_getter)
    server.run_stdio_server()
    return 0


# ---------------------------------------------------------------------------
# CLI 参数解析与调度
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bdpan",
        description="""百度网盘工程化 CLI 管理工具
开源仓库: https://github.com/CodingRookie98/bdpan-cli
作者信息: CodingRookie98 <520whjoker@gmail.com>

提供文件组织、大文件断点续传、影视媒体规范化刮削、安全审计流水与原生 MCP 集成。""",
        epilog="""示例:
  bdpan ls /videos/movies
  bdpan upload ./local.mkv /videos/movies/
  bdpan download /videos/movies/Inception.mkv -d ./downloads/
  bdpan scrape foldering /videos/unscraped --dry-run
  bdpan ops list
  bdpan mcp

开源仓库与作者:
  开源仓库: https://github.com/CodingRookie98/bdpan-cli
  问题反馈: https://github.com/CodingRookie98/bdpan-cli/issues
  作者信息: CodingRookie98 <520whjoker@gmail.com>
  用户指南: docs/tutorials/user-guide.md""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--account",
        default=None,
        help="指定当前命令所操作的网盘账号别名 (默认使用当前活跃账号)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以标准化 JSON 格式输出结果 (便于脚本与机器解析)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        "--debug",
        dest="debug",
        action="store_true",
        help="开启详细调试日志输出 (输出 HTTP 诊断与详细异常追踪)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="静音非错误输出",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用子命令")

    # 1. ls
    p_ls = subparsers.add_parser(
        "ls",
        help="列出网盘指定路径内容",
        description="列出百度网盘指定路径下的文件与子目录列表。",
        epilog="""示例:
  bdpan ls
  bdpan ls /videos/movies
  bdpan ls /videos/movies --limit 500
  bdpan ls /videos/movies --json""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_ls.add_argument("path", nargs="?", default="/", help="网盘目录路径 (默认: /)")
    p_ls.add_argument("--limit", type=int, default=1000, help="最多读取条目数 (默认: 1000)")
    p_ls.set_defaults(func=cmd_ls)

    # 2. mkdir
    p_mkdir = subparsers.add_parser(
        "mkdir",
        help="在网盘中创建新目录",
        description="在百度网盘中递归创建新目录（若目录已存在则安全跳过）。",
        epilog="""示例:
  bdpan mkdir /videos/movies/科幻
  bdpan mkdir /backup/2026/10""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_mkdir.add_argument("path", help="待创建的目录路径")
    p_mkdir.set_defaults(func=cmd_mkdir)

    # 3. mv
    p_mv = subparsers.add_parser(
        "mv",
        help="移动网盘文件或目录（多源时目标须为已存在目录；单源支持移动改名）",
        description="移动网盘文件或目录（操作自动落盘流水审计，支持 bdpan undo 逆向撤销）。\n多源参数时目标必须为已存在目录；单源参数时支持移动并改名。",
        epilog="""示例:
  bdpan mv /videos/old_name.mkv /videos/movies/new_name.mkv   # 单源移动并更名
  bdpan mv /videos/f1.mkv /videos/f2.mkv /videos/movies/    # 多源批量移入已存在目录""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_mv.add_argument("srcs", nargs="+", help="一个或多个源路径")
    p_mv.add_argument("dest", help="目标目录路径（单源时可为 目标目录/新名）")
    p_mv.set_defaults(func=cmd_mv)

    # 3.1 cp
    p_cp = subparsers.add_parser(
        "cp",
        help="复制网盘文件或目录（多源时目标须为已存在目录；单源目标为已存在目录时复制入内，否则视为 目标目录/新名）",
        description="复制网盘文件或目录（底层单批次最大 50 项安全防护）。\n多源参数时目标必须为已存在目录；单源目标为已存在目录时复制入内，否则视为 目标目录/新名。",
        epilog="""示例:
  bdpan cp /videos/source.mkv /backup/movies/              # 复制入目录保持原名
  bdpan cp /videos/source.mkv /backup/movies/target.mkv    # 复制并指定新名称
  bdpan cp /videos/f1.mkv /videos/f2.mkv /backup/movies/   # 多源批量复制""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_cp.add_argument("srcs", nargs="+", help="一个或多个源路径")
    p_cp.add_argument("dest", help="目标目录路径，或 目标目录/新名（仅单源）")
    p_cp.set_defaults(func=cmd_cp)

    # 3.2 rm
    p_rm = subparsers.add_parser(
        "rm",
        help="删除网盘文件或目录（默认交互确认，-y 跳过；服务端移入回收站）",
        description="删除网盘文件或目录。默认开启交互式确认提示，删除后移入百度网盘云端回收站。",
        epilog="""示例:
  bdpan rm /videos/junk.mkv               # 交互式提示确认后删除
  bdpan rm /videos/f1.mkv /videos/f2.mkv -y # 免交互确认直接移入回收站""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_rm.add_argument("paths", nargs="+", help="待删除的一个或多个路径")
    p_rm.add_argument("-y", "--yes", action="store_true", help="跳过确认直接删除")
    p_rm.set_defaults(func=cmd_rm)

    # 3.3 rename
    p_rename = subparsers.add_parser(
        "rename",
        help="原地重命名网盘文件或目录",
        description="原地重命名网盘文件或目录（操作自动落盘流水审计，支持 bdpan undo 逆向撤销）。",
        epilog="""示例:
  bdpan rename /videos/movies/Inception.2010.mkv "盗梦空间 (2010).mkv" """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_rename.add_argument("path", help="待重命名的文件或目录路径")
    p_rename.add_argument("new_name", help="新名称（仅名称，不含目录）")
    p_rename.set_defaults(func=cmd_rename)

    # 4. scrape
    p_scrape = subparsers.add_parser(
        "scrape",
        help="媒体库电影刮削与整理系统",
        description="媒体库电影刮削与自动化整理系统，支持散落文件建目录归集与方案 A / 自定义模板重命名。",
        epilog="""示例:
  bdpan scrape foldering /videos/unscraped --dry-run
  bdpan scrape preview /videos/movies/unwatched -o preview.csv
  bdpan scrape apply preview.csv --target-dir /videos/movies/unwatched""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    scrape_sub = p_scrape.add_subparsers(dest="scrape_cmd", help="刮削子命令")

    # 4.1 scrape preview
    p_preview = scrape_sub.add_parser(
        "preview",
        help="扫描并生成方案 A 刮削更名预览",
        description="扫描目标目录，匹配 TMDB/IMDb 电影元数据，生成重命名预演对照表（支持 --format 自定义模板）。",
        epilog="""示例:
  bdpan scrape preview /videos/movies/unwatched -o preview.csv
  bdpan scrape preview /videos/movies --format "{title} ({year})"
  bdpan scrape preview /videos/movies --format "{title} ({year}) {{imdb-{imdb_id}}}" """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_preview.add_argument("dir", nargs="?", default="/影视/电影/watched", help="目标目录 (默认: /影视/电影/watched)")
    p_preview.add_argument("-o", "--output", default="scrape_preview.json", help="输出 json/csv 路径 (默认: scrape_preview.json)")
    p_preview.add_argument("--all", action="store_true", help="不跳过已合规目录，全量扫描")
    p_preview.add_argument("--limit", type=int, default=None, help="最大条目限制 (默认: 不限)")
    p_preview.add_argument(
        "--format",
        default=None,
        help="自定义目录命名模板，支持 {title}, {original_title}, {year}, {id}, {imdb_id}, {tmdb_id}, {edition} (默认方案 A)",
    )
    p_preview.set_defaults(func=cmd_scrape_preview)

    # 4.2 scrape apply
    p_apply = scrape_sub.add_parser(
        "apply",
        help="安全应用预览结果并执行网盘批量重命名",
        description="安全应用预演生成的 CSV/JSON 对照表，批量执行网盘重命名（底层 50 项/批保护）。",
        epilog="""示例:
  bdpan scrape apply preview.csv
  bdpan scrape apply preview.csv --target-dir /videos/movies/unwatched --batch-size 25""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_apply.add_argument("preview_file", nargs="?", default="scrape_preview.json", help="预览 json/csv 文件 (默认: scrape_preview.json)")
    p_apply.add_argument("--target-dir", default=None, help="覆盖校验目录")
    p_apply.add_argument("--batch-size", type=int, default=25, help="单批提交大小 (默认: 25)")
    p_apply.set_defaults(func=cmd_scrape_apply)

    # 4.3 scrape foldering
    p_folder = scrape_sub.add_parser(
        "foldering",
        help="自动为散落媒体文件创建方案 A 独立规范目录并移入",
        description="自动扫描散落媒体文件与外挂字幕，依据刮削元数据为其创建独立规范目录并原子移入。",
        epilog="""示例:
  bdpan scrape foldering /videos/unscraped --dry-run
  bdpan scrape foldering /videos/unscraped --format "{title} ({year}) {{imdb-{imdb_id}}}"
  bdpan scrape foldering /videos/unscraped --batch-size 25""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_folder.add_argument("dir", nargs="?", default="/影视/电影/unscraped", help="散落文件所在父目录 (默认: /影视/电影/unscraped)")
    p_folder.add_argument("--dry-run", action="store_true", help="仅预演规划，不实际修改网盘")
    p_folder.add_argument("--batch-size", type=int, default=25, help="单批移动大小 (默认: 25)")
    p_folder.add_argument(
        "--format",
        default=None,
        help="自定义目录命名模板，支持 {title}, {original_title}, {year}, {id}, {imdb_id}, {tmdb_id}, {edition} (默认方案 A)",
    )
    p_folder.set_defaults(func=cmd_scrape_foldering)

    # 5. meta (第三阶段预留)
    p_meta = subparsers.add_parser(
        "meta",
        help="元数据与海报抓取上传子系统",
        description="媒体元数据与海报抓取上传子系统（Kodi/Emby/Jellyfin 兼容性支持）。",
        epilog="""示例:
  bdpan meta nfo /videos/movies/watched --dry-run
  bdpan meta poster /videos/movies/watched --dry-run""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    meta_sub = p_meta.add_subparsers(dest="meta_cmd", help="元数据子命令")

    p_nfo = meta_sub.add_parser(
        "nfo",
        help="批量生成 movie.nfo",
        description="依据方案 A 目录名末尾的 IMDb/TMDB ID 精准查询电影元数据并生成标准 movie.nfo。",
        epilog="""示例:
  bdpan meta nfo /videos/movies/watched --dry-run""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_nfo.add_argument("dir", help="电影目录或父目录")
    p_nfo.add_argument("--dry-run", action="store_true", help="仅预演生成，不上传")
    p_nfo.set_defaults(func=cmd_meta_nfo)

    p_poster = meta_sub.add_parser(
        "poster",
        help="批量下载并上传 poster.jpg",
        description="下载 TMDB 官方最高清竖版海报并流式上传至电影根目录的 poster.jpg。",
        epilog="""示例:
  bdpan meta poster /videos/movies/watched --dry-run""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_poster.add_argument("dir", help="电影目录或父目录")
    p_poster.add_argument("--dry-run", action="store_true", help="仅预演抓取，不上传")
    p_poster.set_defaults(func=cmd_meta_poster)

    # 6. quota
    p_quota = subparsers.add_parser(
        "quota",
        help="查询网盘容量配额",
        description="查询当前百度网盘账户的存储空间配额（已用空间、总容量、使用百分比及会员到期时间）。",
        epilog="""示例:
  bdpan quota
  bdpan quota --check-expire --check-free
  bdpan quota --json""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_quota.add_argument("--check-expire", action="store_true", help="同时检查会员容量过期时间")
    p_quota.add_argument("--check-free", action="store_true", help="同时查询免费容量配额")
    p_quota.set_defaults(func=cmd_quota)

    # 7. whoami
    p_whoami = subparsers.add_parser(
        "whoami",
        help="查询当前网盘账户信息",
        description="查询当前登录网盘账户的基本信息（用户名、百度 UID、VIP 会员等级等）。",
        epilog="""示例:
  bdpan whoami
  bdpan whoami --json""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_whoami.set_defaults(func=cmd_whoami)

    # 8. search
    p_search = subparsers.add_parser(
        "search",
        help="按关键词搜索网盘文件",
        description="按关键词搜索网盘文件，支持限定父目录与非递归单层检索。",
        epilog="""示例:
  bdpan search "阿凡达"
  bdpan search "Matrix" --dir /videos/movies
  bdpan search "*.mkv" --dir /videos --no-recursion
  bdpan search "4K" --json""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_search.add_argument("key", help="搜索关键词")
    p_search.add_argument("--dir", default=None, help="限定搜索目录 (默认: 全盘)")
    p_search.add_argument("--no-recursion", action="store_true", help="不递归子目录，仅搜当前层")
    p_search.add_argument("--page", type=int, default=1, help="页码 (默认: 1)")
    p_search.add_argument("--num", type=int, default=100, help="每页条数 (默认: 100)")
    p_search.set_defaults(func=cmd_search)

    # 9. tree
    p_tree = subparsers.add_parser(
        "tree",
        help="递归遍历网盘目录树（客户端逐层遍历，可选落地本地索引）",
        description="客户端深度递归遍历网盘目录树拓扑，可选输出全盘保真 JSON 索引文件。",
        epilog="""示例:
  bdpan tree /videos
  bdpan tree /videos/movies --depth 2
  bdpan tree /videos --index /tmp/movies_index.json""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_tree.add_argument("path", nargs="?", default="/", help="网盘目录路径 (默认: /)")
    p_tree.add_argument("--depth", type=int, default=None, help="最大遍历深度 (默认: 不限)")
    p_tree.add_argument("--index", default=None, metavar="FILE", help="将遍历索引写入本地 JSON 文件")
    p_tree.set_defaults(func=cmd_tree)

    # 10. upload
    p_upload = subparsers.add_parser(
        "upload",
        help="上传本地文件（预上传→分片→创建，支持断点续传）",
        description="大文件切片上传引擎，具备首片特征预计算极速秒传、动态最优机房请求与本地断点续传能力。",
        epilog="""示例:
  bdpan upload ./movie.mkv /videos/movies/
  bdpan upload ./movie.mkv /videos/movies/new_name.mkv
  bdpan upload ./movie.mkv /videos/movies/ --overwrite""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_upload.add_argument("local_path", help="本地文件路径")
    p_upload.add_argument(
        "remote_dest",
        help="网盘目标目录（尾斜杠或已存在目录则保持文件名），或 目标目录/新名",
    )
    p_upload.add_argument("--overwrite", action="store_true", help="同名冲突时覆盖（默认自动改名）")
    p_upload.set_defaults(func=cmd_upload)

    # 11. dedup
    p_dedup = subparsers.add_parser(
        "dedup",
        help="扫描并治理网盘冲突副本与重复项 (1)/(2)（支持隔离与删除）",
        description="扫描并治理网盘冲突副本 (1)、(2) 与无主孤儿重复项，支持暂存隔离与回收站安全清理。",
        epilog="""示例:
  bdpan dedup /videos/movies --dry-run
  bdpan dedup /videos/movies --staging-dir /videos/pending_delete
  bdpan dedup /videos/movies --delete -y""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_dedup.add_argument("path", nargs="?", default="/", help="待扫描的网盘目录路径 (默认: /)")
    action_grp = p_dedup.add_mutually_exclusive_group()
    action_grp.add_argument(
        "--staging-dir",
        default=None,
        help="将冲突副本移动到指定的隔离暂存目录（推荐，如 /videos/movies/pending_delete）",
    )
    action_grp.add_argument(
        "--delete",
        action="store_true",
        help="将冲突副本直接删除（服务端移入回收站）",
    )
    p_dedup.add_argument("--dry-run", action="store_true", help="仅预演规划，不实际修改网盘")
    p_dedup.add_argument("-y", "--yes", action="store_true", help="跳过确认提示直接执行")
    p_dedup.add_argument("-r", "--recursive", action="store_true", help="递归扫描所有子目录")
    p_dedup.add_argument("--include-orphans", action="store_true", help="处理无主冲突副本组（保留 (1)，清理 (2)+）")
    p_dedup.add_argument("--include-empty", action="store_true", help="同时扫描并清理空目录")
    p_dedup.set_defaults(func=cmd_dedup)

    # 12. download
    p_download = subparsers.add_parser(
        "download",
        help="下载网盘文件至本地（支持断点续传与批量下载）",
        description="网盘大文件断点续传下载引擎，注入 pan.baidu.com User-Agent 防限速，支持多文件并发批量下载。",
        epilog="""示例:
  bdpan download /videos/movies/Inception.mkv
  bdpan download /videos/movies/f1.mkv /videos/movies/f2.mkv -d ./downloads/
  bdpan download /videos/movies/Inception.mkv -d ./downloads/ --overwrite""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_download.add_argument("paths", nargs="+", help="网盘文件路径 (支持多个)")
    p_download.add_argument("-d", "--dest", default=".", help="本地保存目标目录或文件路径 (默认: 当前目录)")
    p_download.add_argument("--overwrite", action="store_true", help="本地同名文件存在时强制覆盖")
    p_download.set_defaults(func=cmd_download)

    # 13. dlink
    p_dlink = subparsers.add_parser(
        "dlink",
        help="查询网盘文件高速下载直链 (支持导出 aria2c / curl 命令)",
        description="查询网盘文件的高速下载直链（带防盗链验证），支持直接导出 aria2c 多线程或 curl 脚本。",
        epilog="""示例:
  bdpan dlink /videos/movies/Inception.mkv
  bdpan dlink /videos/movies/Inception.mkv --aria2
  bdpan dlink /videos/movies/Inception.mkv --curl""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_dlink.add_argument("paths", nargs="+", help="网盘文件路径 (支持多个)")
    dlink_export_grp = p_dlink.add_mutually_exclusive_group()
    dlink_export_grp.add_argument("--aria2", action="store_true", help="输出适用于 aria2c 的多线程高速下载命令")
    dlink_export_grp.add_argument("--curl", action="store_true", help="输出适用于 curl 的断点续传下载命令")
    p_dlink.set_defaults(func=cmd_dlink)

    # 14. ops
    p_ops = subparsers.add_parser(
        "ops",
        help="查看网盘操作审计流水",
        description="网盘关键变更操作流水审计日志，记录每次批量改名、移动与归集的映射细节。",
        epilog="""示例:
  bdpan ops list
  bdpan ops list --limit 50
  bdpan ops show 20261029_095105_mv_7ac7a2""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ops_sub = p_ops.add_subparsers(dest="ops_subcmd", help="流水子命令")
    p_ops_list = ops_sub.add_parser(
        "list",
        help="列出历史操作审计流水",
        description="列出历史操作审计流水概览（流水号、时间戳、命令类型、影响文件数、执行状态）。",
        epilog="""示例:
  bdpan ops list
  bdpan ops list --limit 50""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_ops_list.add_argument("--limit", type=int, default=20, help="最多显示记录数 (默认: 20)")
    p_ops_list.set_defaults(func=cmd_ops)

    p_ops_show = ops_sub.add_parser(
        "show",
        help="查看指定操作流水详情与变更清单",
        description="查看指定操作流水号的详细映射清单与变更前后真实路径对比。",
        epilog="""示例:
  bdpan ops show 20261029_095105_mv_7ac7a2""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_ops_show.add_argument("op_id", help="操作流水号")
    p_ops_show.set_defaults(func=cmd_ops)
    p_ops.set_defaults(func=cmd_ops)

    # 15. undo
    p_undo = subparsers.add_parser(
        "undo",
        help="逆向撤销历史批量操作 (基于操作流水)",
        description="依据操作流水号逆向撤销历史批量操作，原子恢复文件或目录的原有路径（支持 --dry-run 预演）。",
        epilog="""示例:
  bdpan undo 20261029_095105_mv_7ac7a2 --dry-run
  bdpan undo 20261029_095105_mv_7ac7a2 -y""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_undo.add_argument("op_id", help="操作流水号")
    p_undo.add_argument("--dry-run", action="store_true", help="仅预演逆向回滚方案，不实际修改网盘")
    p_undo.add_argument("-y", "--yes", action="store_true", help="跳过确认直接执行逆向回滚")
    p_undo.set_defaults(func=cmd_undo)

    # 16. auth
    p_auth = subparsers.add_parser(
        "auth",
        help="网盘账号认证与多账号管理",
        description="百度网盘多账号认证管理系统，支持多租户凭证隔离存储、活跃账号切换与单独授权。",
        epilog="""示例:
  bdpan auth list
  bdpan auth switch work_pan
  bdpan auth login --account personal_pan""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    auth_sub = p_auth.add_subparsers(dest="auth_subcmd", help="认证子命令")
    p_auth_list = auth_sub.add_parser(
        "list",
        help="列出本地所有网盘账号与到期状态",
        description="列出本地保存的所有网盘账号别名、UID 以及 Token 剩余有效期与刷新状态。",
        epilog="""示例:
  bdpan auth list""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_auth_list.set_defaults(func=cmd_auth)

    p_auth_switch = auth_sub.add_parser(
        "switch",
        help="切换当前默认活跃网盘账号",
        description="切换当前全局默认活跃网盘账号别名。",
        epilog="""示例:
  bdpan auth switch work_pan""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_auth_switch.add_argument("alias", help="账号别名")
    p_auth_switch.set_defaults(func=cmd_auth)

    p_auth_login = auth_sub.add_parser(
        "login",
        help="登录或重新授权指定网盘账号",
        description="登录或重新授权指定网盘账号别名（支持有头浏览器与无头终端授权）。",
        epilog="""示例:
  bdpan auth login
  bdpan auth login --account work_pan""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_auth_login.add_argument("--account", default=None, help="账号别名 (默认: 当前活跃账号)")
    p_auth_login.set_defaults(func=cmd_auth)
    p_auth.set_defaults(func=cmd_auth)

    # 17. info
    p_info = subparsers.add_parser(
        "info",
        help="探测视频媒体的深度元数据 (分辨率/时长/编码/音轨)",
        description="无需下载视频本体，直接基于网盘多媒体元数据探测视频精准分辨率(4K/1080P)、时长、HEVC/H.264编码与音轨。",
        epilog="""示例:
  bdpan info /videos/movies/Inception.mkv
  bdpan info /videos/movies/Inception.mkv --json""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_info.add_argument("path", help="网盘视频/多媒体文件绝对路径")
    p_info.set_defaults(func=cmd_info)

    # 18. stats
    p_stats = subparsers.add_parser(
        "stats",
        help="递归聚合统计目录下的容量、文件数与媒体分类分布",
        description="递归聚合统计网盘指定目录下的总容量、总文件数、子目录数及视频/音频/字幕等格式占比分布。",
        epilog="""示例:
  bdpan stats /videos/movies
  bdpan stats /videos/movies --depth 2
  bdpan stats /videos/movies --json""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_stats.add_argument("path", nargs="?", default="/", help="网盘目录路径 (默认: /)")
    p_stats.add_argument("--depth", type=int, default=None, help="最大递归深度 (默认: 不限)")
    p_stats.set_defaults(func=cmd_stats)

    # 19. mcp
    p_mcp = subparsers.add_parser(
        "mcp",
        help="启动原生 Model Context Protocol (MCP) Server (基于 stdio)",
        description="启动原生 Model Context Protocol (MCP) Server（基于标准 stdio），供 AI 助手直接调用 14 项网盘管理工具。",
        epilog="""示例:
  bdpan mcp
  claude mcp add bdpan uv run bdpan mcp""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_mcp.set_defaults(func=cmd_mcp)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args_list = argv if argv is not None else sys.argv[1:]

    # 向后兼容：如果第一个参数是以 '/' 开头的网盘路径且不是已定义的子命令，则自动重定向为 ls <path>
    if args_list and args_list[0].startswith("/") and args_list[0] not in parser._subparsers._group_actions[0].choices:
        args_list = ["ls", args_list[0]] + args_list[1:]

    args = parser.parse_args(args_list)

    setup_logging(debug=args.debug, quiet=args.quiet)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
