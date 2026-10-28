"""操作流水审计与逆向撤销体系 (Operation Audit Logging & Undo Engine - BK-0034)."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from bdpan_cli.file_manager import FileManager, FileManagerError

logger = logging.getLogger(__name__)

DEFAULT_OPS_DIR = Path(__file__).resolve().parents[2] / ".bdpan_ops"


class UndoError(RuntimeError):
    """撤销操作异常基类。"""


class OperationLogger:
    """操作审计流水记录器，将每一次破坏性/批量操作落盘为结构化 JSON 日志。"""

    def __init__(self, ops_dir: str | Path | None = None) -> None:
        self.ops_dir = Path(ops_dir).resolve() if ops_dir else DEFAULT_OPS_DIR
        self.ops_dir.mkdir(parents=True, exist_ok=True)

    def record_operation(
        self,
        command: str,
        items: list[dict[str, Any]],
        account: str = "default",
    ) -> str:
        """记录一次批量操作流水。

        Args:
            command: 命令类型，如 mv, rename, foldering, dedup 等。
            items: 操作的映射项列表，每项形如 {"src": "/old/path", "dest": "/new/path"}。
            account: 操作所使用的网盘账号标识。

        Returns:
            分配的唯一操作批次 ID (op_id)。
        """
        now = datetime.now()
        op_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{command}_{uuid.uuid4().hex[:6]}"
        record = {
            "op_id": op_id,
            "command": command,
            "timestamp": int(time.time()),
            "created_at": now.isoformat(),
            "account": account,
            "undone": False,
            "undone_at": None,
            "items": items,
        }
        file_path = self.ops_dir / f"{op_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        logger.debug("已记录操作流水 [%s]: %d 项映射", op_id, len(items))
        return op_id

    def list_operations(self, limit: int = 20) -> list[dict[str, Any]]:
        """按时间倒序列出最近的操作审计流水。"""
        if not self.ops_dir.exists():
            return []

        ops: list[dict[str, Any]] = []
        # 按文件名排序，文件名以时间戳开头，因此逆序即为最新在前
        for f in sorted(self.ops_dir.glob("*.json"), reverse=True):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                if isinstance(data, dict) and "op_id" in data:
                    ops.append(data)
                    if len(ops) >= limit:
                        break
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("跳过不可读流水文件 [%s]: %s", f, e)

        return ops

    def get_operation(self, op_id: str) -> dict[str, Any] | None:
        """读取指定 op_id 的完整流水记录。"""
        file_path = self.ops_dir / f"{op_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("读取流水失败 [%s]: %s", op_id, e)
            return None

    def mark_undone(self, op_id: str) -> None:
        """标记指定操作为已撤销。"""
        file_path = self.ops_dir / f"{op_id}.json"
        if not file_path.exists():
            raise UndoError(f"流水文件不存在: {op_id}")

        with open(file_path, "r", encoding="utf-8") as f:
            record = json.load(f)

        record["undone"] = True
        record["undone_at"] = datetime.now().isoformat()

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)


class UndoEngine:
    """逆向撤销执行引擎，将历史操作中的 dest 反向移回原 src。"""

    def __init__(self, file_manager: FileManager, ops_logger: OperationLogger | None = None) -> None:
        self.file_manager = file_manager
        self.ops_logger = ops_logger or OperationLogger()

    def plan_undo(self, op_id: str) -> dict[str, Any]:
        """为指定操作生成逆向回滚计划。"""
        op = self.ops_logger.get_operation(op_id)
        if not op:
            raise UndoError(f"未找到对应的操作流水: {op_id}")
        if op.get("undone"):
            raise UndoError(f"操作 [{op_id}] 此前已被撤销过 (撤销时间: {op.get('undone_at')})，禁止重复撤销")

        items = op.get("items") or []
        reversals: list[dict[str, str]] = []
        for item in items:
            src = item.get("src")
            dest = item.get("dest")
            if not src or not dest:
                continue
            # 逆向：现在的源是以前的 dest，现在的目标目录是以前 src 的父目录，文件名是以前 src 的文件名
            dest_dir = os.path.dirname(src) or "/"
            newname = os.path.basename(src)
            reversals.append({
                "src": dest,
                "dest_dir": dest_dir,
                "newname": newname,
            })

        return {
            "op_id": op_id,
            "command": op.get("command"),
            "account": op.get("account"),
            "created_at": op.get("created_at"),
            "reversals": reversals,
        }

    def execute_undo(self, op_id: str, dry_run: bool = False) -> dict[str, Any]:
        """执行逆向回滚。"""
        plan = self.plan_undo(op_id)
        reversals = plan["reversals"]
        if not reversals:
            return {"op_id": op_id, "undone_count": 0, "dry_run": dry_run}

        if dry_run:
            return {"op_id": op_id, "undone_count": len(reversals), "dry_run": True, "plan": reversals}

        # 转换为 batch_move 所需的三元组列表：(src, dest_dir, newname)
        move_tuples = [(r["src"], r["dest_dir"], r["newname"]) for r in reversals]
        try:
            self.file_manager.batch_move(move_tuples, batch_size=50)
        except FileManagerError as e:
            raise UndoError(f"执行回滚移动失败: {e}") from e

        # 标记已撤销
        self.ops_logger.mark_undone(op_id)
        return {"op_id": op_id, "undone_count": len(reversals), "dry_run": False}
