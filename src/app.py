"""
API Monitor - 应用核心
协调 Provider、Tray、Settings
"""
import threading
import logging
from datetime import datetime

from .models import StatusLevel, ProviderResult, AccountConfig
from .providers import create_provider
from .config import load_config, save_config

logger = logging.getLogger("api-monitor")


class App:
    """应用核心：协调 Provider、Tray、Settings"""

    def __init__(self):
        self.config = load_config()
        self.providers: dict[str, 'BaseProvider'] = {}  # id → provider
        self.results: dict[str, ProviderResult] = {}    # id → last result
        self._lock = threading.Lock()
        self._init_providers()

    def _init_providers(self):
        """根据配置创建所有 Provider 实例"""
        for acc in self.config.get("accounts", []):
            if not acc.get("enabled", True):
                continue
            try:
                account = AccountConfig(
                    id=acc["id"],
                    type=acc["type"],
                    name=acc["name"],
                    api_key=acc["api_key"],
                    enabled=acc.get("enabled", True),
                    warning_threshold=acc.get("warning_threshold"),
                    extra=acc.get("extra", {}),
                )
                self.providers[account.id] = create_provider(account)
            except Exception as e:
                logger.error(f"创建 Provider 失败 [{acc.get('id', '?')}]: {e}")

    def refresh_all(self):
        """刷新所有已启用的 Provider，每个独立 try/except"""
        with self._lock:
            for pid, provider in self.providers.items():
                try:
                    result = provider.fetch()
                    self._apply_threshold(result)
                    self.results[pid] = result
                except Exception as e:
                    logger.error(f"Provider {pid} 刷新异常: {e}", exc_info=True)
                    self.results[pid] = ProviderResult(
                        provider_type=provider.PROVIDER_TYPE,
                        account_name=provider.account.name,
                        status=StatusLevel.ERROR,
                        display_value="--",
                        display_unit="",
                        remaining_percent=None,
                        error_message=str(e),
                    )

    def refresh_one(self, account_id: str):
        """刷新单个 Provider"""
        provider = self.providers.get(account_id)
        if not provider:
            return
        with self._lock:
            try:
                result = provider.fetch()
                self._apply_threshold(result)
                self.results[account_id] = result
            except Exception as e:
                logger.error(f"Provider {account_id} 刷新异常: {e}")
                self.results[account_id] = ProviderResult(
                    provider_type=provider.PROVIDER_TYPE,
                    account_name=provider.account.name,
                    status=StatusLevel.ERROR,
                    display_value="--",
                    display_unit="",
                    remaining_percent=None,
                    error_message=str(e),
                )

    def _apply_threshold(self, result: ProviderResult):
        """根据全局阈值更新 result.status"""
        if result.status != StatusLevel.NORMAL:
            return

        global_cfg = self.config.get("global", {})

        if result.remaining_percent is not None:
            # 百分比类: <=5% ERROR, <=20% WARNING
            warn = global_cfg.get("warning_threshold_percent", 20)
            crit = global_cfg.get("critical_threshold_percent", 5)
            if result.remaining_percent <= crit:
                result.status = StatusLevel.ERROR
            elif result.remaining_percent <= warn:
                result.status = StatusLevel.WARNING
        else:
            # 金额类: 用 warning_threshold_balance
            warn_balance = global_cfg.get("warning_threshold_balance", 10)
            # 从 display_value 中提取金额
            try:
                val = result.display_value
                if val.startswith("¥") or val.startswith("$"):
                    amount = float(val[1:].replace(",", ""))
                    if amount <= 0:
                        result.status = StatusLevel.ERROR
                    elif amount < warn_balance:
                        result.status = StatusLevel.WARNING
            except (ValueError, AttributeError):
                pass

    def get_worst_status(self) -> StatusLevel:
        """获取所有结果中最差的状态"""
        with self._lock:
            if not self.results:
                return StatusLevel.LOADING
            priority = {
                StatusLevel.ERROR: 0,
                StatusLevel.WARNING: 1,
                StatusLevel.LOADING: 2,
                StatusLevel.NORMAL: 3,
                StatusLevel.DISABLED: 4,
            }
            return min(self.results.values(),
                       key=lambda r: priority.get(r.status, 5)).status

    def get_results_list(self) -> list[ProviderResult]:
        """按配置顺序返回结果列表"""
        with self._lock:
            result_list = []
            for acc in self.config.get("accounts", []):
                aid = acc.get("id")
                if aid in self.results:
                    result_list.append(self.results[aid])
            # 补充不在配置中但已有结果的（防御性）
            for aid, r in self.results.items():
                if aid not in {a.get("id") for a in self.config.get("accounts", [])}:
                    result_list.append(r)
            return result_list

    def on_config_saved(self, new_config: dict):
        """配置保存回调：重建 Provider"""
        self.config = new_config
        save_config(new_config)
        with self._lock:
            self.providers.clear()
            self.results.clear()
        self._init_providers()

    def run(self):
        """启动应用 → 创建 TrayIcon → run"""
        from .tray import TrayIcon
        tray = TrayIcon(self)
        self._tray = tray
        tray.run()
