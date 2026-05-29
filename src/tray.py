"""
DeepSeek Monitor - 托盘程序
悬停图标 → tooltip 显示余额/消耗/时间
右键菜单 → 刷新/设置/退出
Token 消耗从 OpenClaw session 日志精准统计（服务器上），Windows 上不可用
"""
import threading
import logging
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import pystray
import requests

from .config import load_config, save_config
from .api import DeepSeekAPI, parse_balance

logger = logging.getLogger("deepseek-monitor")

ICON_SIZE = 64

COLOR_GREEN  = (67, 160, 71)
COLOR_ORANGE = (255, 152, 0)
COLOR_RED    = (229, 57, 53)
COLOR_GRAY   = (158, 158, 158)
COLOR_WHITE  = (255, 255, 255)

_state = {
    "balance": None,
    "today_tokens": None,
    "today_tokens_ready": False,
    "status": "loading",
    "last_update": None,
}


class DeepSeekMonitor:

    def __init__(self):
        self.icon = None
        self.config = load_config()
        self.api = None
        self._timer = None
        self._running = False
        self._lock = threading.Lock()

        if self.config.get("api_key"):
            self.api = DeepSeekAPI(self.config["api_key"])

    # ─── 图标 ───────────────────────────────────────────

    def _make_icon(self, status="normal", text="DS"):
        img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        cmap = {"normal": COLOR_GREEN, "warning": COLOR_ORANGE,
                "error": COLOR_RED, "loading": COLOR_GRAY}
        bg = cmap.get(status, COLOR_GRAY)
        m = 4
        draw.ellipse([m, m, ICON_SIZE - m, ICON_SIZE - m], fill=bg)
        try:
            font = None
            fs = 28 if len(text) <= 2 else (22 if len(text) <= 3 else 17)
            for fn in ["Segoe UI", "Microsoft YaHei", "Arial"]:
                try:
                    font = ImageFont.truetype(fn + ".ttf", fs); break
                except Exception:
                    try:
                        font = ImageFont.truetype(fn, fs); break
                    except Exception:
                        continue
            if font is None:
                font = ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
        bb = draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.text(((ICON_SIZE - tw) / 2, (ICON_SIZE - th) / 2 - bb[1]),
                  text, fill=COLOR_WHITE, font=font)
        return img

    # ─── 菜单 ───────────────────────────────────────────

    def _build_menu(self):
        items = []

        if _state["balance"] is not None:
            b = _state["balance"]
            cs = "¥" if b["currency"] == "CNY" else "$"
            items.append(pystray.MenuItem(
                f'余额: {cs}{b["total_balance"]:,.2f}', None, enabled=False))
        elif _state["status"] == "error":
            items.append(pystray.MenuItem("余额: 查询失败", None, enabled=False))
        else:
            items.append(pystray.MenuItem("余额: 查询中...", None, enabled=False))

        if _state["today_tokens_ready"] and _state["today_tokens"]:
            items.append(pystray.MenuItem(
                f'今日消耗: {_fmt(_state["today_tokens"])} tokens', None, enabled=False))
        elif _state["balance"] is not None:
            items.append(pystray.MenuItem("今日消耗: 收集中...", None, enabled=False))
        else:
            items.append(pystray.MenuItem("今日消耗: 查询中...", None, enabled=False))

        smap = {"normal": "正常", "warning": "余额偏低",
                "error": "连接失败", "loading": "查询中..."}
        items.append(pystray.MenuItem(
            f'状态: {smap.get(_state["status"], "未知")}', None, enabled=False))

        if _state["last_update"]:
            items.append(pystray.MenuItem(
                f'更新: {_state["last_update"].strftime("%H:%M:%S")}',
                None, enabled=False))

        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("刷新", self._on_refresh, default=True))
        items.append(pystray.MenuItem("设置", self._on_settings))
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("退出", self._on_quit))
        return pystray.Menu(*items)

    def _update_menu(self):
        if not self.icon: return
        try:
            self.icon._menu = self._build_menu()
            self.icon.update_menu()
        except Exception:
            pass

    # ─── 看门狗 ─────────────────────────────────────────

    def _start_watchdog(self):
        def _loop():
            time.sleep(3)
            while self._running:
                self._update_menu()
                time.sleep(5)
        threading.Thread(target=_loop, daemon=True).start()

    # ─── 刷新 ───────────────────────────────────────────

    def _update_display(self):
        s = _state["status"]
        if s == "normal":
            b = _state["balance"]
            txt = f"{b['total_balance']/10000:.0f}W" if b and b['total_balance'] >= 10000 else \
                  (f"{b['total_balance']/1000:.1f}K" if b and b['total_balance'] >= 1000 else \
                   (f"{b['total_balance']:.0f}" if b else "DS"))
            self.icon.icon = self._make_icon("normal", txt)
        elif s == "warning":
            self.icon.icon = self._make_icon("warning", "!")
        elif s == "error":
            self.icon.icon = self._make_icon("error", "X")
        else:
            self.icon.icon = self._make_icon("loading", "..")

        # Tooltip — 鼠标悬停即见
        parts = ["DeepSeek Monitor"]
        if _state["balance"]:
            b = _state["balance"]
            cs = "¥" if b["currency"] == "CNY" else "$"
            parts.append(f'余额: {cs}{b["total_balance"]:,.2f}')
        if _state["today_tokens_ready"] and _state["today_tokens"]:
            parts.append(f'今日消耗: {_fmt(_state["today_tokens"])} tokens')
        if _state["last_update"]:
            parts.append(f'更新: {_state["last_update"].strftime("%H:%M:%S")}')
        self.icon.title = "\n".join(parts)

        self._update_menu()

    def refresh(self):
        with self._lock:
            if not self.api:
                _state["status"] = "error"
                self._update_display()
                return
            raw = self.api.get_balance()
            if raw is None:
                _state["status"] = "error"
                self._update_display()
                return
            bal = parse_balance(raw, self.config.get("currency", "CNY"))
            if bal is None:
                _state["status"] = "error"
                self._update_display()
                return
            _state["balance"] = bal
            _state["last_update"] = datetime.now()
            th = self.config.get("low_balance_warning", 10.0)
            if bal["total_balance"] <= 0:
                _state["status"] = "error"
            elif bal["total_balance"] < th:
                _state["status"] = "warning"
            else:
                _state["status"] = "normal"
            self._update_tokens()
            self._update_display()

    def _update_tokens(self):
        """获取今日 Token 消耗：优先远程服务器 → 本地 session 扫描"""
        server = self.config.get("token_server", "").strip()
        if server:
            try:
                headers = {}
                auth = self.config.get("token_server_auth", "").strip()
                if auth:
                    headers["Authorization"] = f"Bearer {auth}"
                url = f"{server.rstrip('/')}/tokens"
                logger.info(f"查询远程 Token: {url}")
                resp = requests.get(url, headers=headers, timeout=5)
                logger.info(f"远程响应: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    tokens = data.get("total_tokens", 0)
                    logger.info(f"远程 Token: {tokens:,}")
                    if tokens > 0:
                        _state["today_tokens"] = tokens
                        _state["today_tokens_ready"] = True
                        return
                else:
                    logger.warning(f"远程查询失败 HTTP {resp.status_code}: {resp.text[:100]}")
            except Exception as e:
                logger.warning(f"远程 Token 查询失败: {e}")

        # 回退：本地 session 扫描
        try:
            from .session_tracker import scan_today_tokens
            result = scan_today_tokens()
            if result and result.get("total_tokens", 0) > 0:
                _state["today_tokens"] = result["total_tokens"]
                _state["today_tokens_ready"] = True
                return
        except Exception as e:
            logger.debug(f"Session tracker 不可用: {e}")
        if not _state["today_tokens_ready"]:
            _state["today_tokens"] = None

    # ─── 定时 ───────────────────────────────────────────

    def _schedule(self):
        if not self._running: return
        self._timer = threading.Timer(
            self.config.get("refresh_interval", 300), self._on_tick)
        self._timer.daemon = True
        self._timer.start()

    def _on_tick(self):
        if self._running:
            try: self.refresh()
            except Exception as e: logger.error(f"刷新异常: {e}")
            finally: self._schedule()

    # ─── 回调 ───────────────────────────────────────────

    def _on_refresh(self, icon=None, item=None):
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _do_refresh(self):
        try: self.refresh()
        except Exception as e: logger.error(f"手动刷新异常: {e}")

    def _on_settings(self, icon=None, item=None):
        from .settings import open_settings_window
        open_settings_window(self.config, self._on_saved)

    def _on_saved(self, new_config):
        old_key = self.config.get("api_key")
        old_server = self.config.get("token_server", "")
        self.config = new_config
        save_config(new_config)
        self.api = DeepSeekAPI(new_config["api_key"]) if new_config["api_key"] else None
        # 任何设置变更都立即刷新
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _on_quit(self, icon=None, item=None):
        self._running = False
        if self._timer: self._timer.cancel()
        if icon: icon.stop()

    # ─── 启动 ───────────────────────────────────────────

    def run(self):
        self._running = True

        if self.config.get("first_run", True) or not self.config.get("api_key"):
            self._show_first_run()

        self.icon = pystray.Icon(
            "ds_monitor",
            self._make_icon("loading", "DS"),
            "DeepSeek Monitor",
            menu=self._build_menu())

        threading.Thread(target=self._init, daemon=True).start()
        self._schedule()
        self._start_watchdog()
        self.icon.run()

    def _init(self):
        time.sleep(1.5)
        try: self.refresh()
        except Exception as e: logger.error(f"初始刷新异常: {e}")

    def _show_first_run(self):
        from .settings import open_settings_window
        self.config["first_run"] = False
        save_config(self.config)
        open_settings_window(self.config, self._on_saved, is_first_run=True)


def _fmt(tokens):
    if tokens is None: return "0"
    if tokens >= 1_000_000: return f"{tokens/1_000_000:.1f}M"
    if tokens >= 1_000: return f"{tokens/1_000:.1f}K"
    return str(int(tokens))
