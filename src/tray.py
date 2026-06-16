"""
API Monitor - 托盘图标模块
基于 App 类实现系统托盘图标 + 右键菜单（精简版，含关键周期数据）
"""
import threading
import time
import logging
import re
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
        self._floating = None
        self._floating_window = None  # 持有悬浮窗实例引用

    def run(self):
        """启动托盘图标"""
        self._running = True
        initial_icon = self.icon_renderer.render_status(StatusLevel.LOADING)

        self._icon = pystray.Icon(
            "api_monitor",
            initial_icon,
            "API Monitor",
            menu=self._create_menu(),
        )

        threading.Thread(target=self._init_refresh, daemon=True).start()
        self._start_timer()
        self._icon.run()

    def _init_refresh(self):
        """启动后延迟刷新"""
        time.sleep(1.5)
        try:
            self._refresh()
        except Exception as e:
            logger.error(f"初始刷新异常: {e}", exc_info=True)
        # 启动后自动打开悬浮窗（如果配置开启）
        show_floating = self.app.config.get("global", {}).get("show_floating_on_start", True)
        if show_floating:
            try:
                self._open_floating()
            except Exception as e:
                logger.error(f"自动打开悬浮窗异常: {e}")

    def _compact_detail(self, r: ProviderResult) -> str:
        """为托盘菜单生成精简的周期摘要，一行搞定"""
        if not r.detail:
            return ""

        # 按 provider 类型定制精简格式
        provider_type = r.provider_type

        if provider_type in ("minimax_token",):
            # MiniMax: 5h池 + 周池
            # detail 格式: "5h 池: 剩余 97% (已用 3%)\n周池: 剩余 95% (已用 5%)"
            parts = []
            for line in r.detail.strip().split("\n"):
                line = line.strip()
                if "5h" in line:
                    # 提取剩余百分比
                    m = re.search(r"剩余\s*(\d+)%", line)
                    if m:
                        parts.append(f"5h:{m.group(1)}%")
                elif "周池" in line:
                    m = re.search(r"剩余\s*(\d+)%", line)
                    if m:
                        parts.append(f"周:{m.group(1)}%")
            return " ".join(parts) if parts else ""

        elif provider_type in ("mimo", "jdcloud", "xfyun"):
            # MiMo: 套餐积分/补偿积分/月度用量 (百分比)
            # JDCloud/Xfyun: 5小时/7天/月 (次数百分比)
            parts = []
            for line in r.detail.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("[") or line.startswith("到期") or line.startswith("当前"):
                    continue
                # MiMo 特有: 套餐积分/补偿积分/月度用量
                if "套餐积分" in line:
                    m = re.search(r"(\d+)%", line)
                    if m:
                        parts.append(f"套餐:{m.group(1)}%")
                elif "补偿积分" in line:
                    m = re.search(r"(\d+)%", line)
                    if m:
                        parts.append(f"补偿:{m.group(1)}%")
                elif "月度用量" in line:
                    m = re.search(r"(\d+)%", line)
                    if m:
                        parts.append(f"月:{m.group(1)}%")
                # JDCloud/Xfyun: 5小时/7天/月
                elif "5小时" in line or "5h" in line:
                    m = re.search(r"(\d+)%", line)
                    if m:
                        parts.append(f"5h:{m.group(1)}%")
                elif "7天" in line:
                    m = re.search(r"(\d+)%", line)
                    if m:
                        parts.append(f"周:{m.group(1)}%")
                elif "周" in line and "月" not in line:
                    m = re.search(r"(\d+)%", line)
                    if m:
                        parts.append(f"周:{m.group(1)}%")
                elif "月" in line:
                    m = re.search(r"(\d+)%", line)
                    if m:
                        parts.append(f"月:{m.group(1)}%")
            return " ".join(parts) if parts else ""

        return ""

    def _create_menu(self) -> pystray.Menu:
        """构建右键菜单（精简：每账号 1-2 行）"""
        items = []
        results = self.app.get_results_list()

        for r in results:
            # 状态标识
            status_char = {
                StatusLevel.NORMAL: "●",
                StatusLevel.WARNING: "◐",
                StatusLevel.ERROR: "○",
                StatusLevel.LOADING: "◌",
                StatusLevel.DISABLED: "—",
            }.get(r.status, "?")

            label = get_provider_label(r.provider_type)
            display = f"{r.display_value}{r.display_unit}"

            # 第一行：状态 + 平台 + 显示值
            text = f"{status_char} {label}  {display}"
            items.append(pystray.MenuItem(text, None, enabled=False))

            # 第二行：周期摘要（如有）
            compact = self._compact_detail(r)
            if compact:
                items.append(pystray.MenuItem(f"    {compact}", None, enabled=False))

        # 更新时间 + 操作
        if results:
            items.append(pystray.Menu.SEPARATOR)
        if self._last_update:
            items.append(pystray.MenuItem(
                f"更新: {self._last_update.strftime('%H:%M:%S')}", None, enabled=False))

        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("悬浮窗", self._open_floating))
        items.append(pystray.MenuItem("刷新", self._manual_refresh, default=True))
        items.append(pystray.MenuItem("设置...", self._open_settings))
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("退出", self._quit))

        return pystray.Menu(*items)

    def _build_tooltip(self) -> str:
        """构建 Tooltip（Windows 限制 128 字符）"""
        MAX_LEN = 127
        parts = ["API Monitor"]
        results = self.app.get_results_list()
        for r in results:
            parts.append(f"{r.account_name}: {r.display_value}")
        if self._last_update:
            parts.append(f"更新: {self._last_update.strftime('%H:%M:%S')}")

        tooltip = "\n".join(parts)
        if len(tooltip) > MAX_LEN:
            while len(tooltip) > MAX_LEN and len(parts) > 2:
                parts.pop(-2)
                tooltip = "\n".join(parts)
            if len(tooltip) > MAX_LEN:
                tooltip = tooltip[:MAX_LEN]
        return tooltip

    def _refresh(self):
        """刷新所有数据并更新图标+菜单+悬浮窗"""
        try:
            self.app.refresh_all()
        except Exception as e:
            logger.error(f"refresh_all 异常: {e}", exc_info=True)
            return

        self._last_update = datetime.now()

        if self._icon:
            try:
                strategy = self.app.config.get("global", {}).get("icon_display", "worst")
                new_icon = self.icon_renderer.render(self.app.results, strategy)
                self._icon.icon = new_icon
                self._icon.title = self._build_tooltip()
                self._icon._menu = self._create_menu()
                self._icon.update_menu()
            except Exception as e:
                logger.error(f"更新托盘图标异常: {e}", exc_info=True)

        # 同步刷新悬浮窗（如有打开）
        if self._floating_window and self._floating_window._visible:
            try:
                self._floating_window._refresh_content()
            except Exception as e:
                logger.error(f"同步刷新悬浮窗异常: {e}")

    def _manual_refresh(self, icon=None, item=None):
        """手动刷新"""
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _do_refresh(self):
        try:
            self._refresh()
        except Exception as e:
            logger.error(f"手动刷新异常: {e}", exc_info=True)

    def _open_floating(self, icon=None, item=None):
        """打开悬浮窗"""
        if self._floating and self._floating.is_alive():
            return
        from .floating import FloatingWindow
        fw = FloatingWindow(self.app)
        self._floating_window = fw  # 保存引用以便同步刷新
        self._floating = threading.Thread(target=fw.show, daemon=True)
        self._floating.start()

    def _open_settings(self, icon=None, item=None):
        from .settings import open_settings_window
        open_settings_window(self.app.config, self.app.on_config_saved)

    def _quit(self, icon=None, item=None):
        self._running = False
        if self._timer:
            self._timer.cancel()
        if icon:
            icon.stop()

    def _start_timer(self):
        if not self._running:
            return
        interval = self.app.config.get("global", {}).get("refresh_interval", 300)
        self._timer = threading.Timer(interval, self._on_tick)
        self._timer.daemon = True
        self._timer.start()

    def _on_tick(self):
        if self._running:
            try:
                self._refresh()
            except Exception as e:
                logger.error(f"定时刷新异常: {e}", exc_info=True)
            finally:
                self._start_timer()
        else:
            logger.info("定时器停止（_running=False）")
