"""
API Monitor - 托盘图标模块
基于 App 类实现系统托盘图标 + 右键菜单
"""
import threading
import time
import logging
from datetime import datetime

import pystray
from PIL import Image

from .models import StatusLevel, ProviderResult
from .icon_renderer import IconRenderer
from .providers import get_provider_label

logger = logging.getLogger("api-monitor")


class TrayIcon:
    """系统托盘图标"""

    def __init__(self, app):
        self.app = app
        self.icon_renderer = IconRenderer()
        self._icon = None
        self._timer = None
        self._running = False
        self._last_update = None

    def run(self):
        """启动托盘图标"""
        self._running = True

        # 初始图标 = loading
        initial_icon = self.icon_renderer.render_status(StatusLevel.LOADING)

        self._icon = pystray.Icon(
            "api_monitor",
            initial_icon,
            "API Monitor",
            menu=self._create_menu(),
        )

        # 启动后立即刷新
        threading.Thread(target=self._init_refresh, daemon=True).start()

        # 启动定时刷新
        self._start_timer()

        self._icon.run()

    def _init_refresh(self):
        """启动后延迟刷新"""
        time.sleep(1.5)
        try:
            self._refresh()
        except Exception as e:
            logger.error(f"初始刷新异常: {e}")

    def _create_menu(self) -> pystray.Menu:
        """构建右键菜单"""
        items = []

        results = self.app.get_results_list()

        for i, r in enumerate(results):
            # 账号分组标题
            label = get_provider_label(r.provider_type)
            header_text = f"{r.account_name} ({label})"
            items.append(pystray.MenuItem(header_text, None, enabled=False))

            # 主显示值
            status_emoji = {
                StatusLevel.NORMAL: "OK",
                StatusLevel.WARNING: "WARN",
                StatusLevel.ERROR: "ERR",
                StatusLevel.LOADING: "...",
                StatusLevel.DISABLED: "OFF",
            }.get(r.status, "?")

            main_text = f"  {r.display_value}  [{status_emoji}]"
            items.append(pystray.MenuItem(main_text, None, enabled=False))

            # 详情行
            if r.detail:
                for line in r.detail.strip().split("\n"):
                    line = line.strip()
                    if line:
                        items.append(pystray.MenuItem(f"  {line}", None, enabled=False))

            # 错误信息
            if r.error_message:
                items.append(pystray.MenuItem(f"  Error: {r.error_message}", None, enabled=False))

            # 分隔线（账号之间）
            if i < len(results) - 1:
                items.append(pystray.Menu.SEPARATOR)

        # 更新时间
        if results:
            items.append(pystray.Menu.SEPARATOR)
        if self._last_update:
            items.append(pystray.MenuItem(
                f"更新: {self._last_update.strftime('%H:%M:%S')}", None, enabled=False))
        else:
            items.append(pystray.MenuItem("更新: ...", None, enabled=False))

        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("刷新", self._manual_refresh, default=True))
        items.append(pystray.MenuItem("设置...", self._open_settings))
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("退出", self._quit))

        return pystray.Menu(*items)

    def _build_tooltip(self) -> str:
        """构建 Tooltip 文字"""
        parts = ["API Monitor", "─" * 12]

        results = self.app.get_results_list()
        for r in results:
            label = get_provider_label(r.provider_type)
            parts.append(f"{r.account_name}: {r.display_value}")

        parts.append("─" * 12)
        if self._last_update:
            parts.append(f"更新: {self._last_update.strftime('%H:%M:%S')}")

        return "\n".join(parts)

    def _refresh(self):
        """刷新所有数据并更新图标+菜单"""
        self.app.refresh_all()
        self._last_update = datetime.now()

        # 更新图标和菜单（必须在主线程）
        if self._icon:
            try:
                strategy = self.app.config.get("global", {}).get("icon_display", "worst")
                new_icon = self.icon_renderer.render(self.app.results, strategy)
                self._icon.icon = new_icon
                self._icon.title = self._build_tooltip()
                self._icon._menu = self._create_menu()
                self._icon.update_menu()
            except Exception as e:
                logger.error(f"更新托盘图标异常: {e}")

    def _manual_refresh(self, icon=None, item=None):
        """手动刷新菜单项回调"""
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _do_refresh(self):
        """执行刷新（后台线程）"""
        try:
            self._refresh()
        except Exception as e:
            logger.error(f"手动刷新异常: {e}")

    def _open_settings(self, icon=None, item=None):
        """打开设置页面"""
        from .settings import open_settings_window
        open_settings_window(self.app.config, self.app.on_config_saved)

    def _quit(self, icon=None, item=None):
        """退出"""
        self._running = False
        if self._timer:
            self._timer.cancel()
        if icon:
            icon.stop()

    def _start_timer(self):
        """启动定时刷新"""
        if not self._running:
            return
        interval = self.app.config.get("global", {}).get("refresh_interval", 300)
        self._timer = threading.Timer(interval, self._on_tick)
        self._timer.daemon = True
        self._timer.start()

    def _on_tick(self):
        """定时刷新回调"""
        if self._running:
            try:
                self._refresh()
            except Exception as e:
                logger.error(f"定时刷新异常: {e}")
            finally:
                self._start_timer()
