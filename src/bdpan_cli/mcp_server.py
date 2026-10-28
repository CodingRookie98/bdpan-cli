"""BdpanMcpServer: 百度网盘官方开放平台 MCP (Model Context Protocol) 服务的原生纯净实现。

遵循 Model Context Protocol 规范与 JSON-RPC 2.0 协议标准，通过标准 stdio 与 LLM（Claude Code、
Antigravity、Cursor 等 AI 编程助手）进行双向通信，自省暴露网盘核心文件管理与可观测性能力。
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Callable

from bdpan_cli.account import AccountClient
from bdpan_cli.file_manager import FileManager, FileManagerError
from bdpan_cli.media_info import MediaInfoClient, MediaInfoError
from bdpan_cli.ops import OperationLogger, UndoEngine, UndoError

logger = logging.getLogger("bdpan_cli.mcp")


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class BdpanMcpServer:
    """网盘原生 MCP Server。"""

    def __init__(self, token_getter: Callable[[], str]) -> None:
        self.token_getter = token_getter
        self.protocol_version = "2024-11-05"
        self.server_info = {
            "name": "bdpan-mcp",
            "version": "0.1.0",
        }

    def _get_file_manager(self) -> FileManager:
        token = self.token_getter()
        return FileManager(token)

    def _get_account_client(self) -> AccountClient:
        token = self.token_getter()
        return AccountClient(token)

    def _get_media_info_client(self) -> MediaInfoClient:
        token = self.token_getter()
        return MediaInfoClient(token)

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """获取所有自省暴露的 MCP 工具元数据清单与 JSON Schema。"""
        return [
            {
                "name": "bdpan_ls",
                "description": "列出网盘指定目录的内容，获取子目录与文件条目清单（包含文件名、大小、修改时间与类型）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "网盘目录绝对路径 (默认: '/')",
                            "default": "/",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "最多读取条目数 (默认: 1000)",
                            "default": 1000,
                        },
                    },
                },
            },
            {
                "name": "bdpan_mkdir",
                "description": "在网盘中创建新目录",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "待创建的目录绝对路径",
                        },
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "bdpan_mv",
                "description": "在网盘中移动或重命名文件/目录（支持单源移动改名，多源批量移动至已存在目录）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "srcs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "一个或多个源文件/目录绝对路径",
                        },
                        "dest": {
                            "type": "string",
                            "description": "目标目录路径或 '目标目录/新文件名'",
                        },
                    },
                    "required": ["srcs", "dest"],
                },
            },
            {
                "name": "bdpan_cp",
                "description": "在网盘中复制文件或目录",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "srcs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "一个或多个待复制的源路径",
                        },
                        "dest": {
                            "type": "string",
                            "description": "目标目录路径",
                        },
                    },
                    "required": ["srcs", "dest"],
                },
            },
            {
                "name": "bdpan_rm",
                "description": "删除网盘文件或目录（服务端安全移入回收站）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "一个或多个待删除的网盘文件/目录路径",
                        },
                    },
                    "required": ["paths"],
                },
            },
            {
                "name": "bdpan_rename",
                "description": "原地重命名网盘文件或目录",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "待重命名的文件或目录路径",
                        },
                        "new_name": {
                            "type": "string",
                            "description": "新文件名（仅名称，不包含父目录）",
                        },
                    },
                    "required": ["path", "new_name"],
                },
            },
            {
                "name": "bdpan_search",
                "description": "按关键词全盘或在指定目录下搜索文件与目录",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "搜索关键词",
                        },
                        "dir": {
                            "type": "string",
                            "description": "限定搜索目录 (默认全盘)",
                        },
                        "recursion": {
                            "type": "boolean",
                            "description": "是否递归子目录 (默认 True)",
                            "default": True,
                        },
                        "page": {"type": "integer", "default": 1},
                        "num": {"type": "integer", "default": 100},
                    },
                    "required": ["key"],
                },
            },
            {
                "name": "bdpan_tree",
                "description": "递归遍历网盘目录树结构，输出完整的层级拓扑与容量统计",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "待遍历的根目录绝对路径 (默认: '/')",
                            "default": "/",
                        },
                        "depth": {
                            "type": "integer",
                            "description": "最大递归深度 (默认不限)",
                        },
                    },
                },
            },
            {
                "name": "bdpan_quota",
                "description": "查询网盘账号的总容量、已用空间、剩余可用配额及会员到期时间",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "check_expire": {"type": "boolean", "default": True},
                    },
                },
            },
            {
                "name": "bdpan_whoami",
                "description": "查询当前网盘账号身份、百度用户名、网盘名与会员等级 (普通/普通会员/超级会员)",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "bdpan_info",
                "description": "探测网盘视频媒体的深度元数据（包括精准分辨率、4K/1080P标称、时长、视频编码格式HEVC/H.264、音轨信息与大小）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "视频文件网盘绝对路径",
                        },
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "bdpan_stats",
                "description": "递归聚合统计网盘指定目录下的总文件数、子目录数、总容量大小及各类媒体扩展名分布",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "网盘目录绝对路径 (默认: '/')",
                            "default": "/",
                        },
                        "depth": {
                            "type": "integer",
                            "description": "最大遍历深度",
                        },
                    },
                },
            },
            {
                "name": "bdpan_ops_list",
                "description": "查看近期执行的网盘批量操作审计流水列表（包含操作ID、时间、涉及条目数与撤销状态）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20},
                    },
                },
            },
            {
                "name": "bdpan_undo",
                "description": "基于操作审计流水号，对历史误操作或批量变更进行一键逆向撤销回滚复原",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "op_id": {
                            "type": "string",
                            "description": "操作流水号 (如 op_xxxx)",
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "是否仅预演逆向方案，不实际执行变更 (默认 False)",
                            "default": False,
                        },
                    },
                    "required": ["op_id"],
                },
            },
        ]

    def execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """执行具体的 MCP 工具调用，返回 MCP 标准结果。"""
        try:
            if name == "bdpan_ls":
                fm = self._get_file_manager()
                path = args.get("path", "/")
                limit = args.get("limit", 1000)
                entries = fm.list_dir(path, limit=limit)
                dirs = [e for e in entries if e.get("isdir") == 1]
                files = [e for e in entries if e.get("isdir") != 1]
                total_sz = sum(f.get("size", 0) for f in files)
                txt = f"📂 目录: {path} (共 {len(entries)} 项，包含 {len(dirs)} 个子目录，{len(files)} 个文件，总大小: {_format_size(total_sz)})\n"
                for idx, e in enumerate(entries, 1):
                    tag = "[DIR]" if e.get("isdir") == 1 else "[FILE]"
                    sz = "" if e.get("isdir") == 1 else f" ({_format_size(e.get('size', 0))})"
                    txt += f"  {idx}. {tag} {e.get('server_filename')}{sz}\n"
                return {"content": [{"type": "text", "text": txt}], "isError": False}

            elif name == "bdpan_mkdir":
                fm = self._get_file_manager()
                path = args["path"]
                fm.mkdir(path)
                return {"content": [{"type": "text", "text": f"✅ 目录创建成功: {path}"}], "isError": False}

            elif name == "bdpan_mv":
                fm = self._get_file_manager()
                srcs = args["srcs"]
                dest = args["dest"]
                if len(srcs) == 1:
                    src = srcs[0]
                    dest_dir = dest.rstrip("/") if dest.endswith("/") else os.path.dirname(dest)
                    dest_name = os.path.basename(dest) if not dest.endswith("/") else os.path.basename(src)
                    fm.batch_move([(src, dest_dir, dest_name)])
                    dest_path = f"{dest_dir.rstrip('/')}/{dest_name}"
                    op_id = OperationLogger().record_operation("mv", [{"src": src, "dest": dest_path}], account="mcp")
                    return {"content": [{"type": "text", "text": f"✅ 移动成功: {src} -> {dest_path} (流水号: {op_id})"}], "isError": False}
                else:
                    dest_dir = dest.rstrip("/")
                    payloads = [(s, dest_dir, os.path.basename(s.rstrip("/"))) for s in srcs]
                    fm.batch_move(payloads)
                    items = [{"src": s, "dest": f"{dest_dir.rstrip('/')}/{n}"} for s, _, n in payloads]
                    op_id = OperationLogger().record_operation("mv", items, account="mcp")
                    return {"content": [{"type": "text", "text": f"✅ 批量移动成功: {len(payloads)} 项 -> {dest_dir}/ (流水号: {op_id})"}], "isError": False}

            elif name == "bdpan_cp":
                fm = self._get_file_manager()
                srcs = args["srcs"]
                dest = args["dest"].rstrip("/")
                payloads = [(s, dest, os.path.basename(s.rstrip("/"))) for s in srcs]
                fm.batch_copy(payloads)
                return {"content": [{"type": "text", "text": f"✅ 批量复制成功: {len(payloads)} 项 -> {dest}/"}], "isError": False}

            elif name == "bdpan_rm":
                fm = self._get_file_manager()
                paths = args["paths"]
                failed = 0
                for p in paths:
                    try:
                        fm.delete(p)
                    except FileManagerError:
                        failed += 1
                return {"content": [{"type": "text", "text": f"✅ 删除执行完毕: 成功 {len(paths) - failed} 项，失败 {failed} 项（移入回收站）"}], "isError": failed > 0}

            elif name == "bdpan_rename":
                fm = self._get_file_manager()
                path = args["path"]
                new_name = args["new_name"]
                fm.rename(path, new_name)
                parent = os.path.dirname(path) or "/"
                dest_path = f"{parent.rstrip('/')}/{new_name}"
                op_id = OperationLogger().record_operation("rename", [{"src": path, "dest": dest_path}], account="mcp")
                return {"content": [{"type": "text", "text": f"✅ 重命名成功: {path} -> {new_name} (流水号: {op_id})"}], "isError": False}

            elif name == "bdpan_search":
                fm = self._get_file_manager()
                entries = fm.search(args["key"], dir_path=args.get("dir"), recursion=args.get("recursion", True), page=args.get("page", 1), num=args.get("num", 100))
                txt = f"🔍 搜索关键词 [{args['key']}] (匹配到 {len(entries)} 项):\n"
                for idx, e in enumerate(entries, 1):
                    tag = "[DIR]" if e.get("isdir") == 1 else "[FILE]"
                    sz = "" if e.get("isdir") == 1 else f" ({_format_size(e.get('size', 0))})"
                    txt += f"  {idx}. {tag} {e.get('path')}{sz}\n"
                return {"content": [{"type": "text", "text": txt}], "isError": False}

            elif name == "bdpan_tree":
                fm = self._get_file_manager()
                entries, errors = fm.walk(args.get("path", "/"), max_depth=args.get("depth"))
                dirs = [e for _, e in entries if e.get("isdir") == 1]
                files = [e for _, e in entries if e.get("isdir") != 1]
                total_sz = sum(f.get("size", 0) for f in files)
                txt = f"🌲 目录树: {args.get('path', '/')} (共 {len(dirs)} 目录, {len(files)} 文件, 总计 {_format_size(total_sz)}):\n"
                for depth, e in entries:
                    indent = "  " * depth
                    marker = "📁" if e.get("isdir") == 1 else "📄"
                    sz = "" if e.get("isdir") == 1 else f" ({_format_size(e.get('size', 0))})"
                    txt += f"{indent}{marker} {e.get('server_filename')}{sz}\n"
                return {"content": [{"type": "text", "text": txt}], "isError": False}

            elif name == "bdpan_quota":
                ac = self._get_account_client()
                res = ac.quota(check_expire=args.get("check_expire", True))
                tot = int(res.get("total") or 0)
                used = int(res.get("used") or 0)
                txt = f"💾 网盘空间配额:\n  总空间: {_format_size(tot)}\n  已用: {_format_size(used)}\n  可用: {_format_size(max(tot - used, 0))} ({used/tot*100:.1f}%)"
                return {"content": [{"type": "text", "text": txt}], "isError": False}

            elif name == "bdpan_whoami":
                ac = self._get_account_client()
                res = ac.user_info()
                vip_map = {0: "普通用户", 1: "普通会员", 2: "超级会员"}
                vip_desc = vip_map.get(res.get("vip_type"), f"未知({res.get('vip_type')})")
                txt = f"👤 网盘用户信息:\n  百度账号: {res.get('baidu_name') or '-'}\n  网盘昵称: {res.get('netdisk_name') or '-'}\n  会员等级: {vip_desc}"
                return {"content": [{"type": "text", "text": txt}], "isError": False}

            elif name == "bdpan_info":
                mc = self._get_media_info_client()
                info = mc.get_media_info(args["path"])
                txt = (
                    f"🎬 媒体元数据 [{info['filename']}]:\n"
                    f"  路径: {info['path']}\n"
                    f"  大小: {_format_size(info['size'])}\n"
                    f"  分辨率: {info['resolution']}\n"
                    f"  时长: {info['duration_formatted']} ({info['duration_seconds']} 秒)\n"
                    f"  视频编码: {info['video_codec']}\n"
                    f"  音轨数: {info['audio_tracks_count']}"
                )
                return {"content": [{"type": "text", "text": txt}], "isError": False}

            elif name == "bdpan_stats":
                mc = self._get_media_info_client()
                stats = mc.get_dir_stats(args.get("path", "/"), max_depth=args.get("depth"))
                txt = (
                    f"📊 目录聚合统计 [{stats['root']}]:\n"
                    f"  总容量: {_format_size(stats['total_size'])}\n"
                    f"  文件总数: {stats['total_files']} 个\n"
                    f"  子目录数: {stats['total_dirs']} 个\n"
                    f"  类别分布: 视频 {stats['by_category']['video']['count']} 个 ({_format_size(stats['by_category']['video']['size'])}), "
                    f"字幕 {stats['by_category']['subtitle']['count']} 个, "
                    f"图片 {stats['by_category']['image']['count']} 个"
                )
                return {"content": [{"type": "text", "text": txt}], "isError": False}

            elif name == "bdpan_ops_list":
                ops = OperationLogger().list_operations(limit=args.get("limit", 20))
                txt = f"📜 最近操作审计流水 (共 {len(ops)} 条):\n"
                for o in ops:
                    status = "[已撤销]" if o.get("undone") else "[正常]"
                    cnt = len(o.get("items") or [])
                    txt += f"  [{o['op_id']}] | {o.get('created_at', '')[:19]} | 命令: {o.get('command')} | 影响: {cnt} 项 | {status}\n"
                return {"content": [{"type": "text", "text": txt}], "isError": False}

            elif name == "bdpan_undo":
                fm = self._get_file_manager()
                engine = UndoEngine(fm)
                op_id = args["op_id"]
                dry_run = args.get("dry_run", False)
                if dry_run:
                    plan = engine.plan_undo(op_id)
                    reversals = plan.get("reversals") or []
                    txt = f"🔍 [dry-run] 逆向回滚预演 [{op_id}] (共 {len(reversals)} 项):\n"
                    for r in reversals:
                        txt += f"  ↩️ {r['src']} -> {r['dest_dir']}/{r['newname']}\n"
                    return {"content": [{"type": "text", "text": txt}], "isError": False}
                res = engine.execute_undo(op_id, dry_run=False)
                return {"content": [{"type": "text", "text": f"🎉 成功逆向还原 {res['undone_count']} 项！"}], "isError": False}

            else:
                return {
                    "content": [{"type": "text", "text": f"❌ 未知的工具: {name}"}],
                    "isError": True,
                }
        except Exception as e:
            logger.exception("执行 MCP 工具异常: %s", name)
            return {
                "content": [{"type": "text", "text": f"❌ 工具执行失败 [{name}]: {e}"}],
                "isError": True,
            }

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """处理单次 JSON-RPC 2.0 请求并返回响应。"""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": self.protocol_version,
                    "serverInfo": self.server_info,
                    "capabilities": {
                        "tools": {},
                    },
                },
            }

        elif method == "notifications/initialized":
            # 客户端通知无需响应
            return {}

        elif method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {},
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self.get_tool_definitions(),
                },
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments") or {}
            result = self.execute_tool(tool_name, tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result,
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }

    def run_stdio_server(self) -> None:
        """启动基于标准输入输出 (stdio) 的 MCP 服务监听循环。"""
        logger.info("bdpan MCP Server starting on stdio...")
        for line in sys.stdin:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                req = json.loads(line_str)
                resp = self.handle_request(req)
                if resp:  # 通知无需响应
                    sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                    sys.stdout.flush()
            except Exception as e:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error or unhandled exception: {e}",
                    },
                }
                sys.stdout.write(json.dumps(err_resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
