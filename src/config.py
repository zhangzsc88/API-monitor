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
    "refresh_interval": 300,  # 秒，默认 5 分钟
    "low_balance_warning": 10.0,  # 低于此金额（元）显示警告
    "first_run": True,
}

# DeepSeek V4 Pro 价格 (CNY / 1M tokens) — 作为估算基准
# 输入: ¥2 / 1M tokens, 输出: ¥8 / 1M tokens
# 这里用加权平均 ~¥5 / 1M tokens 来估算
PRICE_PER_M_TOKEN_CNY = {
    "input": 2.0,
    "output": 8.0,
    "cached_input": 0.5,
}
# 估算时用混合均价 ¥4 / 1M tokens
EST_PRICE_PER_M_TOKEN = 4.0


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
