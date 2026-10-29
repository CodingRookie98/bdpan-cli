import logging
from pathlib import Path
import sys

from bdpan_cli.logger import setup_logging, get_logger, get_log_file_path


def test_setup_logging_console_and_file(tmp_path):
    log_file = tmp_path / "logs" / "bdpan.log"
    setup_logging(debug=False, quiet=False, log_file=log_file)
    logger = get_logger("bdpan_cli.test")

    logger.info("Test info message")
    logger.debug("Test debug message")

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Test info message" in content
    # 文件 Handler 始终记录完整 DEBUG 诊断细节
    assert "Test debug message" in content


def test_setup_logging_debug_mode(tmp_path):
    log_file = tmp_path / "logs" / "bdpan_debug.log"
    setup_logging(debug=True, quiet=False, log_file=log_file)

    root_logger = get_logger("bdpan_cli")
    console_handler = [h for h in root_logger.handlers if not hasattr(h, "baseFilename")][0]
    assert console_handler.level == logging.DEBUG
    assert console_handler.stream == sys.stderr


def test_setup_logging_quiet_mode(tmp_path):
    log_file = tmp_path / "logs" / "bdpan_quiet.log"
    setup_logging(debug=False, quiet=True, log_file=log_file)

    root_logger = get_logger("bdpan_cli")
    console_handler = [h for h in root_logger.handlers if not hasattr(h, "baseFilename")][0]
    assert console_handler.level == logging.ERROR


def test_get_log_file_path_env_override(tmp_path, monkeypatch):
    custom_log = tmp_path / "custom.log"
    monkeypatch.setenv("BDPAN_LOG_FILE", str(custom_log))
    assert get_log_file_path() == custom_log
