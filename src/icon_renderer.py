"""
API Monitor - 图标渲染模块
根据多平台查询结果渲染托盘图标
"""
import re
import logging
from PIL import Image, ImageDraw, ImageFont

from .models import StatusLevel, ProviderResult

logger = logging.getLogger("api-monitor")

ICON_SIZE = 64
COLOR_WHITE = (255, 255, 255)


class IconRenderer:
    """根据多平台查询结果渲染托盘图标"""

    COLORS = {
        StatusLevel.NORMAL: (229, 57, 53),       # 红色（品牌色）
        StatusLevel.WARNING: (255, 152, 0),      # 橙色
        StatusLevel.ERROR: (229, 57, 53),        # 红色
        StatusLevel.LOADING: (158, 158, 158),    # 灰色
        StatusLevel.DISABLED: (97, 97, 97),      # 深灰
    }

    # 正常状态图标显示的文字
    DEFAULT_ICON_TEXT = "M"

    def __init__(self, size=ICON_SIZE):
        self.size = size

    def render(self, results: dict[str, ProviderResult], strategy="worst") -> Image.Image:
        """根据结果和策略渲染图标

        Args:
            results: account_id → ProviderResult 映射
            strategy: 图标显示策略 ("worst", "primary")
        """
        if not results:
            return self._draw_icon(self.COLORS[StatusLevel.LOADING], "..")

        # 确定图标颜色（取最差状态）
        status = self._get_worst_status(results)
        color = self.COLORS.get(status, self.COLORS[StatusLevel.LOADING])

        # 确定图标文字
        text = self._get_icon_text(results, strategy)
        return self._draw_icon(color, text)

    def render_status(self, status: StatusLevel) -> Image.Image:
        """渲染指定状态的图标（用于加载/禁用等场景）"""
        color = self.COLORS.get(status, self.COLORS[StatusLevel.LOADING])
        text_map = {
            StatusLevel.LOADING: "..",
            StatusLevel.DISABLED: "--",
            StatusLevel.ERROR: "X",
        }
        text = text_map.get(status, "..")
        return self._draw_icon(color, text)

    def _get_worst_status(self, results: dict[str, ProviderResult]) -> StatusLevel:
        """获取所有结果中最差的状态"""
        priority = {
            StatusLevel.ERROR: 0,
            StatusLevel.WARNING: 1,
            StatusLevel.LOADING: 2,
            StatusLevel.NORMAL: 3,
            StatusLevel.DISABLED: 4,
        }
        return min(results.values(), key=lambda r: priority.get(r.status, 5)).status

    def _get_icon_text(self, results: dict[str, ProviderResult], strategy: str) -> str:
        """获取图标文字

        策略:
        - worst: 显示最差状态的账号缩写
        - primary: 显示首个账号缩写
        正常状态统一显示 "M"
        """
        if strategy == "primary":
            first = next(iter(results.values()))
            if first.status == StatusLevel.NORMAL:
                return self.DEFAULT_ICON_TEXT
            return self._format_display_text(first)

        # worst 策略
        # 1. 有 ERROR → X
        # 2. 有 WARNING → !
        # 3. 全部 NORMAL → M
        for r in results.values():
            if r.status == StatusLevel.ERROR:
                return "X"

        for r in results.values():
            if r.status == StatusLevel.WARNING:
                return self._format_display_text(r, suffix="!")

        # 全部正常
        return self.DEFAULT_ICON_TEXT

    def _format_display_text(self, result: ProviderResult, suffix: str = "") -> str:
        """将 display_value 格式化为图标文字

        金额类: ¥10, 1.2K, 12W
        百分比类: 85, 92（去掉%）
        Token数: 3.1B, 500M
        """
        val = result.display_value
        if not val or val == "--":
            return "X"

        # 百分比类: "85%" → "85"
        if "%" in val:
            num = val.replace("%", "").strip()
            try:
                pct = float(num)
                if pct >= 100:
                    return "100" + suffix
                elif pct >= 10:
                    return str(int(pct)) + suffix
                else:
                    return f"{pct:.0f}" + suffix
            except ValueError:
                return num + suffix

        # 金额类: "¥123.45" → 提取数字格式化
        m = re.match(r'[¥$](.+)', val)
        if m:
            try:
                amount = float(m.group(1).replace(',', ''))
                if amount >= 10000:
                    return f"{amount / 10000:.0f}W" + suffix
                elif amount >= 1000:
                    return f"{amount / 1000:.1f}K" + suffix
                else:
                    return f"{amount:.0f}" + suffix
            except ValueError:
                return val + suffix

        # Token数类: 已包含 B/M/K 后缀
        if any(c in val for c in ('B', 'M', 'K')):
            return val + suffix

        # 其他: 截取前4个字符
        return val[:4] + suffix

    def _draw_icon(self, color: tuple, text: str) -> Image.Image:
        """绘制圆形图标 + 文字"""
        img = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 绘制圆形背景
        margin = 4
        draw.ellipse(
            [margin, margin, self.size - margin, self.size - margin],
            fill=color
        )

        # 获取字体
        font = self._get_font(text)

        # 绘制文字居中
        bb = draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        x = (self.size - tw) / 2
        y = (self.size - th) / 2 - bb[1]
        draw.text((x, y), text, fill=COLOR_WHITE, font=font)

        return img

    def _get_font(self, text: str) -> ImageFont.FreeTypeFont:
        """获取合适的字体，根据文字长度调整大小"""
        fs = 28 if len(text) <= 2 else (22 if len(text) <= 3 else 17)
        font = None
        for fn in ["Segoe UI", "Microsoft YaHei", "Arial"]:
            try:
                font = ImageFont.truetype(fn + ".ttf", fs)
                break
            except Exception:
                try:
                    font = ImageFont.truetype(fn, fs)
                    break
                except Exception:
                    continue
        if font is None:
            try:
                font = ImageFont.load_default(size=fs)
            except TypeError:
                font = ImageFont.load_default()
        return font
