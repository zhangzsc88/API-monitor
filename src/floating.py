"""
API Monitor - 悬浮窗模块
半透明置顶小窗口，显示各账号余额摘要，可调节透明度

设计风格：白底黑字，低透明度背景
- 白色背景 #F5F5F7，卡片 #FFFFFF
- 主文字 #1A1A1A，副文字 #666666
- 背景透明度可调到30%，文字使用深色保证低透明度下也能看清
"""
import threading
import logging
import re

logger = logging.getLogger("api-monitor")

# -- Color Palette (白底黑字 + 低透明度) --
WINDOW_BG = "#F5F5F7"
CARD_BG = "#FFFFFF"
TITLE_BG = "#E8E8ED"
TEXT_PRIMARY = "#1A1A1A"
TEXT_SECONDARY = "#555555"
TEXT_TERTIARY = "#888888"
BORDER_COLOR = "#D0D0D5"
GREEN = "#2E7D32"
ORANGE = "#E65100"
RED = "#C62828"
GRAY = "#9E9E9E"
ACCENT_BLUE = "#1565C0"
STATUS_DOT_GREEN = "#43A047"
STATUS_DOT_ORANGE = "#F57C00"
STATUS_DOT_RED = "#E53935"


class FloatingWindow:
    """半透明置顶悬浮窗（白底黑字）"""

    STATUS_COLORS = {
        "NORMAL": STATUS_DOT_GREEN,
        "WARNING": STATUS_DOT_ORANGE,
        "ERROR": STATUS_DOT_RED,
        "LOADING": GRAY,
        "DISABLED": GRAY,
    }

    def __init__(self, app):
        self.app = app
        self._root = None
        self._opacity_idx = 2  # 默认 0.85
        # 透明度档位：从30%到100%，5档
        self._opacity_levels = [0.30, 0.50, 0.70, 0.85, 1.0]
        self._opacity_labels = ["30%", "50%", "70%", "85%", "100%"]
        self._visible = False
        self._drag_x = 0
        self._drag_y = 0

    def show(self):
        """显示悬浮窗（在新线程中运行 tkinter mainloop）"""
        try:
            import tkinter as tk
        except ImportError:
            logger.error("tkinter 未安装，悬浮窗不可用")
            return

        if self._root and self._visible:
            self._root.lift()
            self._root.focus_force()
            return

        self._root = tk.Tk()
        self._root.title("API Monitor")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", self._opacity_levels[self._opacity_idx])
        self._root.configure(bg=WINDOW_BG)

        # 拖拽
        self._root.bind("<ButtonPress-1>", self._start_drag)
        self._root.bind("<B1-Motion>", self._on_drag)

        # 主容器
        self._content = tk.Frame(self._root, bg=WINDOW_BG, padx=14, pady=10)
        self._content.pack(fill=tk.BOTH, expand=True)

        # ---- 标题栏 ----
        title_frame = tk.Frame(self._content, bg=TITLE_BG, padx=10, pady=6)
        title_frame.pack(fill=tk.X, pady=(0, 8))

        tk.Label(title_frame, text="API Monitor", bg=TITLE_BG, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT)

        # 透明度按钮
        self._opacity_btn = tk.Label(
            title_frame, text=f" {self._opacity_labels[self._opacity_idx]} ",
            bg=BORDER_COLOR, fg=TEXT_SECONDARY, font=("Segoe UI", 9), cursor="hand2",
            relief=tk.FLAT, padx=4, pady=1
        )
        self._opacity_btn.pack(side=tk.RIGHT, padx=(4, 0))
        self._opacity_btn.bind("<ButtonPress-1>", self._cycle_opacity)

        # 关闭按钮
        close_label = tk.Label(title_frame, text=" X ", bg=TITLE_BG, fg=TEXT_SECONDARY,
                               font=("Segoe UI", 13, "bold"), cursor="hand2")
        close_label.pack(side=tk.RIGHT)
        close_label.bind("<ButtonPress-1>", lambda e: self.hide())
        close_label.bind("<Enter>", lambda e: close_label.configure(bg=RED, fg="#FFFFFF"))
        close_label.bind("<Leave>", lambda e: close_label.configure(bg=TITLE_BG, fg=TEXT_SECONDARY))

        # ---- 账号列表容器 ----
        self._rows_frame = tk.Frame(self._content, bg=WINDOW_BG)
        self._rows_frame.pack(fill=tk.X)

        # ---- 底部状态栏 ----
        status_frame = tk.Frame(self._content, bg=WINDOW_BG, padx=4, pady=0)
        status_frame.pack(fill=tk.X, pady=(8, 0))
        self._time_label = tk.Label(status_frame, text="", bg=WINDOW_BG, fg=TEXT_TERTIARY,
                                    font=("Segoe UI", 9))
        self._time_label.pack(side=tk.LEFT)

        # 初始位置：右上角
        self._root.update_idletasks()
        sw = self._root.winfo_screenwidth()
        self._root.geometry(f"+{sw - 350}+60")

        self._visible = True
        self._refresh_content()
        self._schedule_refresh()

        try:
            self._root.mainloop()
        except Exception as e:
            logger.error(f"悬浮窗异常: {e}", exc_info=True)
        finally:
            self._visible = False
            self._root = None

    def hide(self):
        """隐藏悬浮窗"""
        if self._root:
            self._visible = False
            self._root.destroy()
            self._root = None

    def _refresh_content(self):
        """刷新内容"""
        if not self._root or not self._visible:
            return

        import tkinter as tk

        for widget in self._rows_frame.winfo_children():
            widget.destroy()

        results = self.app.get_results_list()
        for r in results:
            status_name = r.status.name if hasattr(r.status, 'name') else str(r.status)
            dot_color = self.STATUS_COLORS.get(status_name, GRAY)

            # ---- 卡片容器 ----
            card = tk.Frame(self._rows_frame, bg=CARD_BG, padx=10, pady=6,
                            highlightbackground=BORDER_COLOR, highlightthickness=1)
            card.pack(fill=tk.X, pady=3)

            # 第一行：状态点 + 平台名 + 余额值
            row1 = tk.Frame(card, bg=CARD_BG)
            row1.pack(fill=tk.X)

            # 状态圆点
            tk.Label(row1, text="●", bg=CARD_BG, fg=dot_color,
                     font=("Segoe UI", 11), anchor="w").pack(side=tk.LEFT)

            # 平台名
            label = get_provider_label_safe(r.provider_type)
            tk.Label(row1, text=f" {label}", bg=CARD_BG, fg=TEXT_PRIMARY,
                     font=("Segoe UI", 11, "bold"), anchor="w").pack(side=tk.LEFT)

            # 账号名
            if r.account_name and r.account_name != label:
                name_text = r.account_name
                if len(name_text) > 10:
                    name_text = name_text[:9] + "…"
                tk.Label(row1, text=f"({name_text})", bg=CARD_BG, fg=TEXT_TERTIARY,
                         font=("Segoe UI", 9), anchor="w").pack(side=tk.LEFT, padx=(2, 0))

            # 右侧余额值（大字加粗）
            display = f"{r.display_value}{r.display_unit}"
            tk.Label(row1, text=display, bg=CARD_BG, fg=dot_color,
                     font=("Consolas", 14, "bold"), anchor="e").pack(side=tk.RIGHT)

            # 详情行
            if r.detail:
                detail_lines = self._format_detail_lines(r)
                for dl in detail_lines:
                    row_d = tk.Frame(card, bg=CARD_BG)
                    row_d.pack(fill=tk.X, pady=(1, 0))
                    # 细分行（命中/未命中）用更浅的颜色
                    is_sub = dl.startswith("命中:") or dl.startswith("输入:")
                    fg = TEXT_TERTIARY if is_sub else TEXT_SECONDARY
                    tk.Label(row_d, text=dl, bg=CARD_BG, fg=fg,
                             font=("Consolas", 10), anchor="w").pack(side=tk.LEFT)

        # 更新时间
        from datetime import datetime
        self._time_label.configure(text=f"刷新 {datetime.now().strftime('%H:%M:%S')}")

    def _format_detail_lines(self, r) -> list[str]:
        """将 detail 格式化为悬浮窗的多行显示

        悬浮窗空间大，直接展示 Provider 输出的完整 detail 内容，
        只做少量过滤（跳过低价值行），保留总量等详细信息。
        """
        lines = []
        for line in r.detail.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("提示"):
                continue
            # 跳过"到期"行（太长且不是核心数据）
            if line.startswith("到期"):
                continue
            # 跳过模型名行（讯飞的 [mc987e0e] GLM-5）
            if line.startswith("[") and "]" in line and "剩余" not in line:
                continue
            lines.append(line)
        return lines

    def _compact_detail(self, r) -> str:
        """精简周期摘要 — 悬浮窗空间大，显示完整详情"""
        if not r.detail:
            return ""
        parts = []
        for line in r.detail.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("[") or line.startswith("到期") or line.startswith("当前") or line.startswith("提示") or line.startswith("套餐:"):
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
            # 百分比类平台：5h/周/月
            elif "5h" in line or "5小时" in line:
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
            # 金额类平台（DeepSeek等）
            elif "总额" in line or "赠送" in line or "充值" in line:
                m = re.search(r"¥([\d,.]+)", line)
                if m:
                    key = line.split(":")[0].strip() if ":" in line else ""
                    if "总额" in key:
                        continue
                    parts.append(f"{key}:¥{m.group(1)}")
        return "  ".join(parts)

    def _schedule_refresh(self):
        if not self._visible or not self._root:
            return
        try:
            # 先触发 API 数据刷新，再更新界面
            self.app.refresh_all()
            self._refresh_content()
        except Exception as e:
            logger.error(f"悬浮窗刷新异常: {e}")
        # 使用全局配置的刷新间隔
        interval = self.app.config.get("global", {}).get("refresh_interval", 300)
        self._root.after(interval * 1000, self._schedule_refresh)

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        x = self._root.winfo_x() + event.x - self._drag_x
        y = self._root.winfo_y() + event.y - self._drag_y
        self._root.geometry(f"+{x}+{y}")

    def _cycle_opacity(self, event=None):
        """点击切换透明度"""
        self._opacity_idx = (self._opacity_idx + 1) % len(self._opacity_levels)
        self._root.attributes("-alpha", self._opacity_levels[self._opacity_idx])
        self._opacity_btn.configure(text=f" {self._opacity_labels[self._opacity_idx]} ")


def get_provider_label_safe(provider_type: str) -> str:
    """安全获取 provider 标签"""
    try:
        from .providers import get_provider_label
        return get_provider_label(provider_type)
    except Exception:
        return provider_type
