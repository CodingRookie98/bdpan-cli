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
from bdpan_cli.preview_scrape import generate_preview
from bdpan_cli.uploader import Uploader
from bdpan_cli.apply_scrape_rename import apply_renames

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bdpan_cli.cli")

# 断点续传状态文件：与 token 缓存同目录（项目根，git-ignored）
UPLOAD_STATE_FILE = TOKEN_CACHE.parent / ".bdpan_uploads.json"


def _get_file_manager() -> FileManager:
    config = load_config()
    token = TokenManager(config).get_access_token()
    return FileManager(token)


def _get_account_client() -> AccountClient:
    config = load_config()
    token = TokenManager(config).get_access_token()
    return AccountClient(token)


def _get_downloader() -> Downloader:
    config = load_config()
    token = TokenManager(config).get_access_token()
    return Downloader(token)


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
                print(f"❌ 路径不存在: {path}")
                return 1
            if match.get("isdir") != 1:
                size_str = _format_size(match.get("size", 0))
                print(f"\n📄 文件: {path} ({size_str})\n")
                return 0
        except FileManagerError:
            pass

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
    mgr = _get_file_manager()
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
    mgr = _get_file_manager()
    srcs = args.srcs
    if len(srcs) == 1:
        src = srcs[0]
        dest_dir, dest_name = _resolve_dest(mgr, src, args.dest)
        logger.info("正在移动: %s -> %s/%s", src, dest_dir, dest_name)
        mgr.batch_move([(src, dest_dir, dest_name)])
        print(f"✅ 移动成功: {src} -> {dest_dir}/{dest_name}")
        return 0

    try:
        dest_dir = _require_dest_dir(mgr, args.dest)
    except FileManagerError as e:
        print(f"❌ {e}")
        return 1
    payloads = [(s, dest_dir, os.path.basename(s.rstrip("/"))) for s in srcs]
    logger.info("正在批量移动 %d 项 -> %s/", len(payloads), dest_dir)
    mgr.batch_move(payloads)
    print(f"✅ 批量移动成功: {len(payloads)} 项 -> {dest_dir}/")
    return 0


def cmd_rm(args: argparse.Namespace) -> int:
    mgr = _get_file_manager()
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
    mgr = _get_file_manager()
    logger.info("正在重命名: %s -> %s", args.path, args.new_name)
    mgr.rename(args.path, args.new_name)
    print(f"✅ 重命名成功: {args.path} -> {args.new_name}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    mgr = _get_file_manager()
    entries = mgr.search(
        args.key,
        dir_path=args.dir,
        recursion=not args.no_recursion,
        page=args.page,
        num=args.num,
    )
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
    mgr = _get_file_manager()
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

    mgr = _get_file_manager()
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


def _format_vip(vip_type: Any) -> str:
    return {0: "普通用户", 1: "普通会员", 2: "超级会员"}.get(vip_type, f"未知({vip_type})")


def cmd_quota(args: argparse.Namespace) -> int:
    client = _get_account_client()
    res = client.quota(check_expire=args.check_expire, check_free=args.check_free)
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
    client = _get_account_client()
    res = client.user_info()
    print("👤 网盘账户信息:")
    print(f"  百度账号: {res.get('baidu_name') or '-'}")
    print(f"  网盘名:   {res.get('netdisk_name') or '-'}")
    print(f"  会员类型: {_format_vip(res.get('vip_type'))}")
    return 0


def cmd_dedup(args: argparse.Namespace) -> int:
    mgr = _get_file_manager()
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
    downloader = _get_downloader()
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
    p_mv = subparsers.add_parser(
        "mv",
        help="移动网盘文件或目录（多源时目标须为已存在目录；单源支持移动改名）",
    )
    p_mv.add_argument("srcs", nargs="+", help="一个或多个源路径")
    p_mv.add_argument("dest", help="目标目录路径（单源时可为 目标目录/新名）")
    p_mv.set_defaults(func=cmd_mv)

    # 3.1 cp
    p_cp = subparsers.add_parser(
        "cp",
        help="复制网盘文件或目录（多源时目标须为已存在目录；单源目标为已存在目录时复制入内，否则视为 目标目录/新名）",
    )
    p_cp.add_argument("srcs", nargs="+", help="一个或多个源路径")
    p_cp.add_argument("dest", help="目标目录路径，或 目标目录/新名（仅单源）")
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

    # 6. quota
    p_quota = subparsers.add_parser("quota", help="查询网盘容量配额")
    p_quota.add_argument("--check-expire", action="store_true", help="同时检查会员容量过期时间")
    p_quota.add_argument("--check-free", action="store_true", help="同时查询免费容量配额")
    p_quota.set_defaults(func=cmd_quota)

    # 7. whoami
    p_whoami = subparsers.add_parser("whoami", help="查询当前网盘账户信息")
    p_whoami.set_defaults(func=cmd_whoami)

    # 8. search
    p_search = subparsers.add_parser("search", help="按关键词搜索网盘文件")
    p_search.add_argument("key", help="搜索关键词")
    p_search.add_argument("--dir", default=None, help="限定搜索目录 (默认: 全盘)")
    p_search.add_argument("--no-recursion", action="store_true", help="不递归子目录，仅搜当前层")
    p_search.add_argument("--page", type=int, default=1, help="页码 (默认: 1)")
    p_search.add_argument("--num", type=int, default=100, help="每页条数 (默认: 100)")
    p_search.set_defaults(func=cmd_search)

    # 9. tree
    p_tree = subparsers.add_parser("tree", help="递归遍历网盘目录树（客户端逐层遍历，可选落地本地索引）")
    p_tree.add_argument("path", nargs="?", default="/", help="网盘目录路径 (默认: /)")
    p_tree.add_argument("--depth", type=int, default=None, help="最大遍历深度 (默认: 不限)")
    p_tree.add_argument("--index", default=None, metavar="FILE", help="将遍历索引写入本地 JSON 文件")
    p_tree.set_defaults(func=cmd_tree)

    # 10. upload
    p_upload = subparsers.add_parser(
        "upload",
        help="上传本地文件（预上传→分片→创建，支持断点续传）",
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
    )
    p_download.add_argument("paths", nargs="+", help="网盘文件路径 (支持多个)")
    p_download.add_argument("-d", "--dest", default=".", help="本地保存目标目录或文件路径 (默认: 当前目录)")
    p_download.add_argument("--overwrite", action="store_true", help="本地同名文件存在时强制覆盖")
    p_download.set_defaults(func=cmd_download)

    # 13. dlink
    p_dlink = subparsers.add_parser(
        "dlink",
        help="查询网盘文件高速下载直链 (支持导出 aria2c / curl 命令)",
    )
    p_dlink.add_argument("paths", nargs="+", help="网盘文件路径 (支持多个)")
    dlink_export_grp = p_dlink.add_mutually_exclusive_group()
    dlink_export_grp.add_argument("--aria2", action="store_true", help="输出适用于 aria2c 的多线程高速下载命令")
    dlink_export_grp.add_argument("--curl", action="store_true", help="输出适用于 curl 的断点续传下载命令")
    p_dlink.set_defaults(func=cmd_dlink)

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
