"""DeepSeek Monitor - 纯托盘方案"""
import sys, os, logging, traceback
from pathlib import Path

if sys.platform == "win32":
    LOG_DIR = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "DeepSeekMonitor" / "logs"
else:
    LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "monitor.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("deepseek-monitor")

def main():
    logger.info("=" * 50)
    logger.info("DeepSeek Monitor 启动")
    try:
        from src.tray import DeepSeekMonitor
    except ImportError as e:
        logger.error(f"模块导入失败: {e}")
        print(f"\n[ERROR] {e}"); input("\n按回车键退出..."); sys.exit(1)
    try:
        DeepSeekMonitor().run()
    except KeyboardInterrupt:
        logger.info("用户中断")
    except SystemExit:
        pass
    except Exception as e:
        logger.error(f"异常: {e}\n{traceback.format_exc()}")
        print(f"\n[ERROR] {e}\n日志: {LOG_DIR / 'monitor.log'}")
        input("\n按回车键退出..."); sys.exit(1)

if __name__ == "__main__":
    main()
