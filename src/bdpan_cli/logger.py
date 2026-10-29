"""bdpan-cli 日志治理模块 (BK-0041).

实现方案 A 日志体系：
1. 终端与日志流解耦：控制台日志输出至 sys.stderr，保留 sys.stdout 给表格、进度与 --json 机器信封；
2. 动态级别控制：支持全局 --debug / -v（输出详细诊断与异常追踪）与 --quiet / -q（静音非错误输出）；
3. 本地滚动日志双写：自动将完整诊断日志（DEBUG 级别）持久化写入 ~/.config/bdpan/logs/bdpan.log（10MB x 5 轮转备份）。
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys

DEFAULT_LOG_DIR = Path.home() / ".config" / "bdpan" / "logs"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "bdpan.log"

_LOGGING_INITIALIZED = False


def get_log_file_path() -> Path:
    """获取默认日志落盘路径，支持 BDPAN_LOG_FILE 环境变量覆盖。"""
    env_path = os.environ.get("BDPAN_LOG_FILE")
    if env_path:
        return Path(env_path)
    return DEFAULT_LOG_FILE


def setup_logging(
    debug: bool = False,
    quiet: bool = False,
    log_file: Path | str | None = None,
) -> None:
    """初始化并配置全局日志系统。
    
    :param debug: 是否开启调试模式（详细 Traceback、代码行号与请求响应体）
    :param quiet: 是否开启静音模式（仅打印 ERROR 及以上）
    :param log_file: 自定义日志文件路径，为 None 时使用默认 ~/.config/bdpan/logs/bdpan.log
    """
    global _LOGGING_INITIALIZED

    target_log_file = Path(log_file) if log_file else get_log_file_path()

    # 确定控制台输出级别
    if quiet:
        console_level = logging.ERROR
    elif debug:
        console_level = logging.DEBUG
    else:
        console_level = logging.INFO

    # 确定格式
    if debug:
        console_fmt = "%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s"
    else:
        console_fmt = "%(asctime)s [%(levelname)s] %(message)s"
    file_fmt = "%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s"

    # 配置根 bdpan_cli logger
    logger = logging.getLogger("bdpan_cli")
    logger.setLevel(logging.DEBUG)  # 保持最低级别，由 handlers 分别过滤

    # 清理既有 handlers 避免重复添加
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    # 1. 控制台 Handler (输出至 stderr，确保 stdout 纯净)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter(console_fmt))
    logger.addHandler(console_handler)

    # 2. 文件 Handler (自动滚动记录，始终保留完整 DEBUG 诊断细节)
    try:
        target_log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            target_log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(file_fmt))
        logger.addHandler(file_handler)
    except OSError as err:
        # 权限或文件系统异常时降级处理，不阻断主业务
        logger.warning("无法创建本地日志文件 %s: %s", target_log_file, err)

    # 调整底层 HTTP 客户端日志级别
    urllib3_logger = logging.getLogger("urllib3")
    if debug:
        urllib3_logger.setLevel(logging.DEBUG)
    else:
        urllib3_logger.setLevel(logging.WARNING)

    _LOGGING_INITIALIZED = True


def get_logger(name: str = "bdpan_cli") -> logging.Logger:
    """获取标准命名空间 logger。"""
    return logging.getLogger(name)
