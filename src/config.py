"""
API Monitor - 多平台配置管理模块
"""
import os
import sys
import json
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger("api-monitor")


def _resolve_app_dir() -> Path:
    """
    解析应用数据目录。
    优先级：
    1. 环境变量 APIMONITOR_HOME（手动指定）
    2. 与可执行文件同目录的 data/ 子目录（PyInstaller 打包后默认）
    3. 用户主目录下的 .api-monitor/（开发模式兜底）
    """
    env = os.environ.get("APIMONITOR_HOME")
    if env:
        return Path(env)

    if getattr(sys, "frozen", False):
        # PyInstaller 打包：exe 同目录的 data/
        exe_dir = Path(sys.executable).resolve().parent
        return exe_dir / "data"

    # 开发模式：当前工作目录下的 data/
    return Path.cwd() / "data"


CONFIG_DIR = _resolve_app_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"

# 旧版配置路径（仅 Windows，用于迁移检测；保留 APPDATA 路径）
if sys.platform == "win32":
    OLD_CONFIG_DIR = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "DeepSeekMonitor"
else:
    OLD_CONFIG_DIR = Path.home() / ".deepseek-monitor"
OLD_CONFIG_FILE = OLD_CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "version": 2,
    "accounts": [],
    "global": {
        "refresh_interval": 300,
        "warning_threshold_percent": 20,
        "warning_threshold_balance": 10,
        "critical_threshold_percent": 5,
        "icon_display": "worst",
        "show_floating_on_start": True,
    },
    "first_run": True,
}


def get_config_dir() -> Path:
    """返回配置目录路径"""
    return CONFIG_DIR


def get_log_dir() -> Path:
    """返回日志目录路径"""
    log_dir = CONFIG_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _ensure_config_dir() -> None:
    """确保配置目录存在"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def migrate_config(old: dict) -> dict:
    """从 v1 (DeepSeek Monitor) 迁移到 v2 (API Monitor)"""
    if old.get("api_key"):
        new = {
            "version": 2,
            "accounts": [{
                "id": "deepseek_1",
                "type": "deepseek",
                "name": "DeepSeek",
                "api_key": old["api_key"],
                "enabled": True,
                "warning_threshold": old.get("low_balance_warning", 10),
            }],
            "global": {
                "refresh_interval": old.get("refresh_interval", 300),
                "warning_threshold_percent": 20,
                "warning_threshold_balance": old.get("low_balance_warning", 10),
                "critical_threshold_percent": 5,
                "icon_display": "worst",
            },
            "first_run": False,
        }
        logger.info("配置从 v1 迁移到 v2 完成")
        return new
    return DEFAULT_CONFIG.copy()


def load_config() -> dict:
    """加载配置文件"""
    _ensure_config_dir()

    # 优先尝试新版配置
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            # 检查版本，无 version 字段则迁移
            if "version" not in config:
                config = migrate_config(config)
                save_config(config)
            return config
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"加载配置文件失败: {e}")
            return DEFAULT_CONFIG.copy()

    # 尝试从旧版配置迁移
    if OLD_CONFIG_FILE.exists():
        try:
            with open(OLD_CONFIG_FILE, "r", encoding="utf-8") as f:
                old_config = json.load(f)
            config = migrate_config(old_config)
            save_config(config)
            logger.info("已从旧版配置迁移")
            return config
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"旧版配置迁移失败: {e}")

    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """原子写入配置文件（写临时文件后 rename）"""
    _ensure_config_dir()
    try:
        # 在同一目录创建临时文件，确保 rename 是原子操作
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(CONFIG_DIR), suffix=".tmp", prefix="config_"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            # Windows 上需要先删除目标文件
            if CONFIG_FILE.exists():
                CONFIG_FILE.unlink()
            os.rename(tmp_path, str(CONFIG_FILE))
        except Exception:
            # 清理临时文件
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")
        # 回退：直接写入
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except IOError as e2:
            logger.error(f"配置文件回退写入也失败: {e2}")
