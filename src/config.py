"""
DeepSeek Monitor - 配置管理模块
"""
import os
import json
import sys
from pathlib import Path

# 配置文件夹（Windows: %APPDATA%/DeepSeekMonitor）
if sys.platform == "win32":
    CONFIG_DIR = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "DeepSeekMonitor"
else:
    CONFIG_DIR = Path.home() / ".deepseek-monitor"

CONFIG_FILE = CONFIG_DIR / "config.json"
HISTORY_FILE = CONFIG_DIR / "history.json"

DEFAULT_CONFIG = {
    "api_key": "",
    "currency": "CNY",
    "refresh_interval": 300,       # 秒，默认 5 分钟
    "low_balance_warning": 10.0,   # 低于此金额（元）显示警告
    "token_server": "",             # Token 统计服务器地址，如 http://1.2.3.4:18799
    "token_server_auth": "",        # 服务器鉴权密钥
    "first_run": True,
}


def ensure_config_dir():
    """确保配置目录存在"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    """加载配置文件"""
    ensure_config_dir()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            # 合并默认值，确保新字段有默认值
            merged = {**DEFAULT_CONFIG, **config}
            return merged
        except (json.JSONDecodeError, IOError):
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """保存配置文件"""
    ensure_config_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_history():
    """加载历史余额记录（用于计算当日消耗）"""
    ensure_config_dir()
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "day_start_balance": None,
        "day_start_date": None,
        "last_balance": None,
        "last_update": None,
    }


def save_history(history):
    """保存历史记录"""
    ensure_config_dir()
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
