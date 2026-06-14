"""
API Monitor - 程序入口
"""
import sys
import os
import logging
import traceback
from pathlib import Path

# 在 setup_logging 之前先解析日志目录（与 config 保持一致）
def _resolve_log_dir() -> Path:
    env = os.environ.get("APIMONITOR_HOME")
    if env:
        return Path(env) / "logs"

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        return exe_dir / "data" / "logs"

    return Path.cwd() / "data" / "logs"


LOG_DIR = _resolve_log_dir()
os.makedirs(LOG_DIR, exist_ok=True)


def setup_logging():
    """配置日志"""
    log_file = os.path.join(LOG_DIR, "api_monitor.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    """程序入口"""
    setup_logging()
    logger = logging.getLogger("api-monitor")
    logger.info("=" * 50)
    logger.info("API Monitor 启动")
    logger.info(f"应用数据目录: {_resolve_log_dir().parent}")

    try:
        from src.app import App
    except ImportError as e:
        logger.error(f"模块导入失败: {e}")
        print(f"\n[ERROR] {e}")
        input("\n按回车键退出...")
        sys.exit(1)

    try:
        app = App()
        app.run()
    except KeyboardInterrupt:
        logger.info("用户中断")
    except SystemExit:
        pass
    except Exception as e:
        logger.critical(f"程序异常退出: {e}", exc_info=True)
        print(f"\n[ERROR] {e}\n日志: {LOG_DIR / 'api_monitor.log'}")
        input("\n按回车键退出...")
        sys.exit(1)


if __name__ == "__main__":
    main()
