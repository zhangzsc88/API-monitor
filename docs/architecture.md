# API Monitor - 系统架构设计

> 版本: 1.0
> 日期: 2026-06-14
> 基于: [DeepSeek Monitor](https://github.com/zhangzsc88/API-monitor) 二开

---

## 1. 系统架构概览

### 1.1 架构总图

```
┌──────────────────────────────────────────────────────────────────────┐
│                        API Monitor (Python)                          │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────────┐     │
│  │  main.py     │───▶│  App         │───▶│  TrayIcon            │     │
│  │  程序入口     │    │  应用核心     │    │  托盘图标 + 菜单      │     │
│  └─────────────┘    └──────┬───────┘    └──────────────────────┘     │
│                            │                                        │
│                     ┌──────▼───────┐                                │
│                     │  ProviderMgr │                                │
│                     │  供应商管理器  │                                │
│                     └──────┬───────┘                                │
│                            │                                        │
│          ┌─────────────────┼─────────────────┐                     │
│          │                 │                  │                     │
│   ┌──────▼─────┐  ┌───────▼──────┐  ┌───────▼──────┐              │
│   │ DeepSeek   │  │ MiniMax      │  │ MiMo         │              │
│   │ Provider   │  │ Provider(s)  │  │ Provider     │              │
│   └────────────┘  └──────────────┘  └──────────────┘              │
│                                                                      │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────────┐     │
│  │  config.py   │    │  settings.py │    │  icon_renderer.py    │     │
│  │  配置管理     │    │  Web 设置     │    │  图标渲染             │     │
│  └─────────────┘    └──────────────┘    └──────────────────────┘     │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心设计原则

1. **Provider 抽象**: 每个平台实现统一接口，新增平台只需添加一个 Provider 类
2. **配置驱动**: 所有平台账号通过配置文件管理，运行时可增删改
3. **解耦渲染**: 托盘图标渲染与数据查询分离，便于适配不同显示策略
4. **向后兼容**: 配置文件兼容原 DeepSeek Monitor 格式，首次启动自动迁移

### 1.3 调用流程

```
启动
 │
 ▼
main.py → App.__init__() → 加载配置 → 注册 Providers
 │
 ▼
App.run() → TrayIcon.run() → 启动定时刷新
 │
 ▼ (定时/手动触发)
ProviderMgr.refresh_all()
 │
 ├──▶ DeepSeekProvider.fetch()     → HTTP GET → 解析 → ProviderResult
 ├──▶ MiniMaxTokenProvider.fetch()  → HTTP GET → 解析 → ProviderResult
 ├──▶ MiniMaxCodingProvider.fetch() → HTTP GET → 解析 → ProviderResult
 └──▶ MiMoProvider.fetch()         → HTTP GET → 解析 → ProviderResult
       │
       ▼
TrayIcon.update(results[]) → 渲染图标 + 更新菜单 + 更新 Tooltip
```

---

## 2. 文件列表

```
src/
├── main.py                  # 程序入口，日志初始化
├── app.py                   # 应用核心类 App，协调各模块
├── tray.py                  # 托盘图标 + 右键菜单 + 事件处理
├── icon_renderer.py         # 图标渲染逻辑（颜色、文字、状态）
├── config.py                # 多平台配置管理（加载/保存/迁移）
├── settings.py              # Web 设置界面（本地 HTTP 服务 + 浏览器）
├── providers/
│   ├── __init__.py          # 导出所有 Provider + 注册表
│   ├── base.py              # Provider 抽象基类
│   ├── deepseek.py          # DeepSeek 余额查询
│   ├── minimax_token.py     # MiniMax Token Plan 余额查询
│   ├── minimax_coding.py   # MiniMax Coding Plan 余额查询
│   └── mimo.py              # 小米 MiMo Token Plan 用量查询
└── models.py                # 数据模型（ProviderResult, AccountConfig 等）
```

### 2.1 各文件职责

| 文件 | 职责 | 主要类/函数 |
|------|------|------------|
| `main.py` | 入口，日志初始化，异常捕获 | `main()` |
| `app.py` | 应用生命周期管理，协调 ProviderMgr / TrayIcon / Settings | `class App` |
| `tray.py` | pystray 托盘图标，右键菜单构建，定时刷新调度 | `class TrayIcon` |
| `icon_renderer.py` | 根据多平台状态渲染托盘图标（圆形+文字） | `class IconRenderer` |
| `config.py` | 配置文件读写，旧格式迁移，默认值管理 | `load_config()`, `save_config()`, `migrate_config()` |
| `settings.py` | 本地 HTTP 服务器，设置页面 HTML/JS，API Key 测试 | `class SettingsHandler`, `open_settings()` |
| `providers/base.py` | Provider 抽象基类，定义统一接口 | `class BaseProvider` |
| `providers/deepseek.py` | DeepSeek API 余额查询与解析 | `class DeepSeekProvider` |
| `providers/minimax_token.py` | MiniMax Token Plan 查询与解析 | `class MiniMaxTokenProvider` |
| `providers/minimax_coding.py` | MiniMax Coding Plan 查询与解析 | `class MiniMaxCodingProvider` |
| `providers/mimo.py` | 小米 MiMo Token Plan 用量查询与解析 | `class MiMoProvider` |
| `providers/__init__.py` | Provider 注册表，按 type 名创建实例 | `get_provider()`, `ALL_PROVIDERS` |
| `models.py` | 数据模型定义 | `ProviderResult`, `AccountConfig`, `ModelQuota` |

---

## 3. 数据模型 (`models.py`)

```python
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class StatusLevel(Enum):
    """状态级别"""
    NORMAL = "normal"       # 余额/用量正常
    WARNING = "warning"     # 余额偏低 / 用量偏高
    ERROR = "error"         # 查询失败
    LOADING = "loading"     # 查询中
    DISABLED = "disabled"   # 已禁用


@dataclass
class ModelQuota:
    """单个模型的配额信息"""
    name: str                           # 模型名称，如 "general", "deepseek-chat"
    remaining_percent: Optional[float]  # 剩余百分比 0-100
    used: Optional[float] = None        # 已用量（次数/token数）
    total: Optional[float] = None       # 总量（次数/token数）
    unit: str = ""                      # 单位，如 "%", "次", "tokens"


@dataclass
class ProviderResult:
    """Provider 查询结果（统一输出格式）"""
    provider_type: str                  # "deepseek", "minimax_token" 等
    account_name: str                   # 用户自定义名称，如 "DeepSeek 账号1"
    status: StatusLevel                 # 当前状态
    display_value: str                  # 主显示值，如 "¥123.45", "85%", "3.1B"
    display_unit: str                   # 单位说明，如 "CNY", "%", "tokens"
    remaining_percent: Optional[float]  # 总体剩余百分比（用于图标颜色判断）
    detail: str = ""                    # 详情文字（tooltip 用），多行
    models: List[ModelQuota] = field(default_factory=list)  # 模型级配额明细
    error_message: str = ""            # 错误信息（status=ERROR 时）
    raw_data: dict = field(default_factory=dict)  # 原始 API 响应（调试用）


@dataclass
class AccountConfig:
    """单个账号配置"""
    id: str                             # 唯一标识，如 "deepseek_1"
    type: str                           # Provider 类型，如 "deepseek"
    name: str                           # 显示名称，如 "DeepSeek 账号1"
    api_key: str                        # API Key（加密存储）
    enabled: bool = True                # 是否启用
    warning_threshold: Optional[float] = None  # 自定义预警阈值（覆盖全局）
    extra: dict = field(default_factory=dict)   # 扩展字段（如 Cookie 等）
```

---

## 4. Provider 抽象层设计

### 4.1 基类接口 (`providers/base.py`)

```python
from abc import ABC, abstractmethod
from typing import Optional
from ..models import ProviderResult, AccountConfig


class BaseProvider(ABC):
    """API 供应商抽象基类"""

    # 类属性：Provider 元信息（子类覆盖）
    PROVIDER_TYPE: str = ""           # 类型标识，如 "deepseek"
    PROVIDER_LABEL: str = ""          # 显示名称，如 "DeepSeek"
    API_BASE: str = ""                # API 基础 URL
    AUTH_TYPE: str = "bearer"         # 认证方式: "bearer" | "cookie"
    TIMEOUT: int = 15                 # 请求超时（秒）

    def __init__(self, account: AccountConfig):
        self.account = account
        self._session = None

    def _get_session(self):
        """懒初始化 requests.Session"""
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._set_auth(self._session)
        return self._session

    def _set_auth(self, session):
        """设置认证头（子类可覆盖）"""
        session.headers.update({
            "Authorization": f"Bearer {self.account.api_key}",
            "Accept": "application/json",
        })

    @abstractmethod
    def fetch(self) -> ProviderResult:
        """查询余额/用量，返回统一结果"""
        ...

    def test_connection(self) -> tuple[bool, str]:
        """测试连接是否正常，返回 (成功?, 消息)"""
        result = self.fetch()
        return (result.status != StatusLevel.ERROR,
                "连接成功" if result.status != StatusLevel.ERROR else result.error_message)

    def _handle_error(self, error: Exception) -> ProviderResult:
        """统一错误处理"""
        import requests
        msg = "查询失败"
        if isinstance(error, requests.exceptions.Timeout):
            msg = "请求超时"
        elif isinstance(error, requests.exceptions.ConnectionError):
            msg = "网络连接失败"
        elif isinstance(error, requests.exceptions.HTTPError):
            code = error.response.status_code if error.response else 0
            if code == 401:
                msg = "API Key 无效或已过期"
            elif code == 429:
                msg = "请求过于频繁"
            else:
                msg = f"HTTP {code}"
        else:
            msg = str(error)

        return ProviderResult(
            provider_type=self.PROVIDER_TYPE,
            account_name=self.account.name,
            status=StatusLevel.ERROR,
            display_value="--",
            display_unit="",
            remaining_percent=None,
            error_message=msg,
        )
```

### 4.2 各平台实现

#### DeepSeek (`providers/deepseek.py`)

```python
class DeepSeekProvider(BaseProvider):
    PROVIDER_TYPE = "deepseek"
    PROVIDER_LABEL = "DeepSeek"
    API_BASE = "https://api.deepseek.com"

    def fetch(self) -> ProviderResult:
        try:
            resp = self._get_session().get(
                f"{self.API_BASE}/user/balance",
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            return self._parse(data)
        except Exception as e:
            return self._handle_error(e)

    def _parse(self, data: dict) -> ProviderResult:
        balance_infos = data.get("balance_infos", [])
        if not balance_infos:
            return self._empty_result("无余额数据")

        info = balance_infos[0]  # 取第一个币种
        currency = info.get("currency", "CNY")
        total = float(info.get("total_balance", 0))
        granted = float(info.get("granted_balance", 0))
        topped = float(info.get("topped_up_balance", 0))
        symbol = "¥" if currency == "CNY" else "$"

        # 显示值格式化
        display = format_balance(total, symbol)

        # 状态判断（使用余额绝对值 + 全局/自定义阈值）
        threshold = self.account.warning_threshold  # 由上层填充全局默认值
        status = StatusLevel.NORMAL
        if total <= 0:
            status = StatusLevel.ERROR
        elif threshold and total < threshold:
            status = StatusLevel.WARNING

        return ProviderResult(
            provider_type=self.PROVIDER_TYPE,
            account_name=self.account.name,
            status=status,
            display_value=f"{symbol}{total:,.2f}",
            display_unit=currency,
            remaining_percent=None,  # DeepSeek 无百分比，用金额判断
            detail=f"总额: {symbol}{total:,.2f}\n"
                   f"赠送: {symbol}{granted:,.2f}\n"
                   f"充值: {symbol}{topped:,.2f}",
            raw_data=data,
        )
```

#### MiniMax Token Plan (`providers/minimax_token.py`)

```python
class MiniMaxTokenProvider(BaseProvider):
    PROVIDER_TYPE = "minimax_token"
    PROVIDER_LABEL = "MiniMax Token"
    API_BASE = "https://www.minimaxi.com"

    def fetch(self) -> ProviderResult:
        try:
            resp = self._get_session().get(
                f"{self.API_BASE}/v1/token_plan/remains",
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            return self._parse(data)
        except Exception as e:
            return self._handle_error(e)

    def _parse(self, data: dict) -> ProviderResult:
        base = data.get("base_resp", {})
        if base.get("status_code") != 0:
            return self._error_result(base.get("status_msg", "查询失败"))

        models = data.get("model_remains", [])
        if not models:
            return self._empty_result("无配额数据")

        # 取第一个模型的百分比作为主状态
        primary = models[0]
        remaining = primary.get("current_interval_remaining_percent", 0)
        weekly = primary.get("current_weekly_remaining_percent", 0)
        min_pct = min(remaining, weekly)

        # 构建模型配额列表
        quotas = []
        for m in models:
            quotas.append(ModelQuota(
                name=m.get("model_name", "unknown"),
                remaining_percent=m.get("current_interval_remaining_percent"),
                used=m.get("current_interval_usage_count"),
                total=m.get("current_interval_total_count"),
                unit="%",
            ))

        status = self._status_from_percent(min_pct)

        return ProviderResult(
            provider_type=self.PROVIDER_TYPE,
            account_name=self.account.name,
            status=status,
            display_value=f"{min_pct}%",
            display_unit="%",
            remaining_percent=min_pct,
            detail=self._build_detail(quotas, weekly),
            models=quotas,
            raw_data=data,
        )
```

#### MiniMax Coding Plan (`providers/minimax_coding.py`)

```python
class MiniMaxCodingProvider(BaseProvider):
    PROVIDER_TYPE = "minimax_coding"
    PROVIDER_LABEL = "MiniMax Coding"
    API_BASE = "https://www.minimaxi.com"

    def fetch(self) -> ProviderResult:
        try:
            resp = self._get_session().get(
                f"{self.API_BASE}/v1/api/openplatform/coding_plan/remains",
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            return self._parse(data)
        except Exception as e:
            return self._handle_error(e)

    def _parse(self, data: dict) -> ProviderResult:
        # 类似 MiniMaxTokenProvider，但字段不同
        # 使用 current_interval_remaining_percent 作为主要指标
        # 包含 current_interval_usage_count 和 current_interval_total_count
        ...
```

#### 小米 MiMo (`providers/mimo.py`)

```python
class MiMoProvider(BaseProvider):
    PROVIDER_TYPE = "mimo"
    PROVIDER_LABEL = "小米 MiMo"
    API_BASE = "https://token-plan-cn.xiaomimimo.com"

    def fetch(self) -> ProviderResult:
        try:
            resp = self._get_session().get(
                f"{self.API_BASE}/v1/usage",
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            return self._parse(data)
        except Exception as e:
            return self._handle_error(e)

    def _parse(self, data: dict) -> ProviderResult:
        total = data.get("total", 0)
        used = data.get("used", 0)
        remaining = data.get("remaining", 0)

        pct = (remaining / total * 100) if total > 0 else 0

        return ProviderResult(
            provider_type=self.PROVIDER_TYPE,
            account_name=self.account.name,
            status=self._status_from_percent(pct),
            display_value=format_tokens(remaining),  # 如 "3.1B"
            display_unit="tokens",
            remaining_percent=pct,
            detail=f"总量: {format_tokens(total)}\n"
                   f"已用: {format_tokens(used)}\n"
                   f"剩余: {format_tokens(remaining)}",
            raw_data=data,
        )
```

### 4.3 Provider 注册表 (`providers/__init__.py`)

```python
from .base import BaseProvider
from .deepseek import DeepSeekProvider
from .minimax_token import MiniMaxTokenProvider
from .minimax_coding import MiniMaxCodingProvider
from .mimo import MiMoProvider

# 类型 → Provider 类的映射
ALL_PROVIDERS: dict[str, type[BaseProvider]] = {
    "deepseek": DeepSeekProvider,
    "minimax_token": MiniMaxTokenProvider,
    "minimax_coding": MiniMaxCodingProvider,
    "mimo": MiMoProvider,
}


def create_provider(account: AccountConfig) -> BaseProvider:
    """根据 AccountConfig.type 创建对应的 Provider 实例"""
    cls = ALL_PROVIDERS.get(account.type)
    if cls is None:
        raise ValueError(f"未知的 Provider 类型: {account.type}")
    return cls(account)


def get_provider_label(provider_type: str) -> str:
    """获取 Provider 的显示名称"""
    cls = ALL_PROVIDERS.get(provider_type)
    return cls.PROVIDER_LABEL if cls else provider_type
```

---

## 5. 配置结构 (`config.py`)

### 5.1 配置文件路径

- 配置目录: `%APPDATA%/APIMonitor/`（Windows）或 `~/.api-monitor/`（其他）
- 配置文件: `config.json`
- 日志目录: `%APPDATA%/APIMonitor/logs/`

### 5.2 配置 Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "APIMonitor Config",
  "type": "object",
  "properties": {
    "version": {
      "type": "integer",
      "description": "配置版本号，用于迁移",
      "const": 2
    },
    "accounts": {
      "type": "array",
      "description": "所有平台账号列表",
      "items": {
        "type": "object",
        "required": ["id", "type", "name", "api_key"],
        "properties": {
          "id": {
            "type": "string",
            "description": "唯一标识，格式: {type}_{序号}",
            "pattern": "^[a-z_]+_[0-9]+$"
          },
          "type": {
            "type": "string",
            "enum": ["deepseek", "minimax_token", "minimax_coding", "mimo"]
          },
          "name": {
            "type": "string",
            "description": "显示名称",
            "minLength": 1,
            "maxLength": 50
          },
          "api_key": {
            "type": "string",
            "minLength": 1
          },
          "enabled": {
            "type": "boolean",
            "default": true
          },
          "warning_threshold": {
            "type": ["number", "null"],
            "description": "自定义预警阈值（覆盖全局）",
            "default": null
          },
          "extra": {
            "type": "object",
            "description": "扩展字段",
            "properties": {
              "cookie": { "type": "string" }
            }
          }
        }
      }
    },
    "global": {
      "type": "object",
      "description": "全局设置",
      "properties": {
        "refresh_interval": {
          "type": "integer",
          "minimum": 30,
          "maximum": 3600,
          "default": 300,
          "description": "刷新间隔（秒）"
        },
        "warning_threshold_percent": {
          "type": "number",
          "minimum": 0,
          "maximum": 100,
          "default": 20,
          "description": "百分比类平台预警阈值（剩余%）"
        },
        "warning_threshold_balance": {
          "type": "number",
          "minimum": 0,
          "default": 10,
          "description": "金额类平台预警阈值（元）"
        },
        "critical_threshold_percent": {
          "type": "number",
          "minimum": 0,
          "maximum": 100,
          "default": 5,
          "description": "百分比类平台严重阈值（剩余%）"
        },
        "icon_display": {
          "type": "string",
          "enum": ["primary", "worst", "list"],
          "default": "worst",
          "description": "图标显示策略: primary=显示首个账号, worst=显示最差状态, list=多图标"
        }
      }
    },
    "first_run": {
      "type": "boolean",
      "default": true
    }
  }
}
```

### 5.3 默认配置

```python
DEFAULT_CONFIG = {
    "version": 2,
    "accounts": [],
    "global": {
        "refresh_interval": 300,
        "warning_threshold_percent": 20,
        "warning_threshold_balance": 10,
        "critical_threshold_percent": 5,
        "icon_display": "worst",
    },
    "first_run": True,
}
```

### 5.4 旧版配置迁移

首次加载时检测 `version` 字段，若不存在则自动从旧版 DeepSeek Monitor 格式迁移：

```python
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
        return new
    return DEFAULT_CONFIG.copy()
```

---

## 6. 托盘 UI 设计

### 6.1 图标渲染逻辑 (`icon_renderer.py`)

**显示策略** (`icon_display` 配置项):

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| `worst` | 显示所有账号中状态最差的那个 | 关注整体健康度（默认） |
| `primary` | 显示 accounts[0] 的状态 | 只关心主账号 |
| `list` | 为每个启用的账号生成独立托盘图标 | 账号少且需分别监控 |

**worst 策略下图标文字选择优先级**:
1. 若有账号余额偏低 (WARNING) → 显示该账号缩写 + `!`
2. 若有账号错误 (ERROR) → 显示 `X`
3. 所有正常 → 显示首个账号缩写值

**图标颜色规则**:

| 状态 | 颜色 | RGB | 触发条件 |
|------|------|-----|---------|
| NORMAL | 绿色 | (67, 160, 71) | 所有账号正常 |
| WARNING | 橙色 | (255, 152, 0) | 任一账号剩余 < 阈值 |
| ERROR | 红色 | (229, 57, 53) | 任一账号查询失败 / 余额=0 |
| LOADING | 灰色 | (158, 158, 158) | 首次加载中 |
| DISABLED | 深灰 | (97, 97, 97) | 所有账号禁用 |

**图标文字缩写规则**:
- 金额类: `¥10` / `1.2K` / `12W`（保留原 DeepSeek 逻辑）
- 百分比类: `85` / `92`（去掉 % 符号，省空间）
- Token 数: `3.1B` / `500M`
- 错误: `X`
- 加载: `..`

### 6.2 右键菜单结构

```
┌─ API Monitor ──────────────────────────────────┐
│                                                 │
│  MiniMax Token                                  │
│    ├─ 剩余: 85%  (区间) / 100% (周)             │
│    └─ general: 85%  video: 66%                  │
│  ─────────────────────────────────────────────  │
│  MiniMax Coding                                 │
│    ├─ 剩余: 92%  (已用 150/1000 次)              │
│    └─ deepseek-chat: 85%                        │
│  ─────────────────────────────────────────────  │
│  小米 MiMo                                      │
│    ├─ 剩余: 76%  (3.1B / 4.1B)                  │
│    └─ 过期: 2026-07-01                          │
│  ─────────────────────────────────────────────  │
│  DeepSeek 账号1                                 │
│    └─ 余额: ¥123.45 (充值 ¥123.45)              │
│                                                 │
│  ─────────────────────────────────────────────  │
│  更新: 14:30:25                                 │
│  ─────────────────────────────────────────────  │
│  刷新                                          │
│  设置...                                       │
│  ─────────────────────────────────────────────  │
│  退出                                          │
└─────────────────────────────────────────────────┘
```

**菜单构建规则**:
- 每个启用的账号一个分组，包含名称 + 详情子项
- 禁用的账号不显示
- 分组之间用分隔线隔开
- 最后统一显示更新时间 + 操作按钮

### 6.3 Tooltip 格式

```
API Monitor
──────────
MiniMax Token: 85%
MiniMax Coding: 92% (150/1000)
小米 MiMo: 76% (3.1B)
DeepSeek: ¥123.45
──────────
更新: 14:30:25
```

---

## 7. 应用核心 (`app.py`)

```python
class App:
    """应用核心：协调 Provider、Tray、Settings"""

    def __init__(self):
        self.config = load_config()
        self.providers: dict[str, BaseProvider] = {}  # id → provider
        self.results: dict[str, ProviderResult] = {}  # id → last result
        self._lock = threading.Lock()

        self._init_providers()

    def _init_providers(self):
        """根据配置创建所有 Provider 实例"""
        for acc in self.config.get("accounts", []):
            if acc.get("enabled", True):
                account = AccountConfig(**acc)
                self.providers[account.id] = create_provider(account)

    def refresh_all(self):
        """刷新所有已启用的 Provider"""
        with self._lock:
            for pid, provider in self.providers.items():
                try:
                    result = provider.fetch()
                    # 应用阈值判断
                    self._apply_threshold(result)
                    self.results[pid] = result
                except Exception as e:
                    logger.error(f"Provider {pid} 刷新异常: {e}")
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
        if provider:
            with self._lock:
                result = provider.fetch()
                self._apply_threshold(result)
                self.results[account_id] = result

    def _apply_threshold(self, result: ProviderResult):
        """根据阈值更新 result.status"""
        if result.status != StatusLevel.NORMAL:
            return

        global_cfg = self.config.get("global", {})
        if result.remaining_percent is not None:
            # 百分比类平台
            warn = global_cfg.get("warning_threshold_percent", 20)
            crit = global_cfg.get("critical_threshold_percent", 5)
            if result.remaining_percent <= crit:
                result.status = StatusLevel.ERROR
            elif result.remaining_percent <= warn:
                result.status = StatusLevel.WARNING

    def get_worst_status(self) -> StatusLevel:
        """获取所有结果中最差的状态"""
        if not self.results:
            return StatusLevel.LOADING
        levels = {StatusLevel.ERROR: 0, StatusLevel.WARNING: 1,
                  StatusLevel.LOADING: 2, StatusLevel.NORMAL: 3}
        return min(self.results.values(),
                   key=lambda r: levels.get(r.status, 4)).status

    def on_config_saved(self, new_config: dict):
        """配置保存回调：重建 Provider"""
        self.config = new_config
        save_config(new_config)
        self.providers.clear()
        self.results.clear()
        self._init_providers()

    def run(self):
        """启动应用"""
        tray = TrayIcon(self)
        tray.run()
```

---

## 8. 任务分解（按实现顺序）

### Phase 0: 基础设施 (无依赖)

| # | 任务 | 依赖 | 说明 |
|---|------|------|------|
| T0.1 | 创建 `models.py` 数据模型 | 无 | ProviderResult, AccountConfig, ModelQuota, StatusLevel |
| T0.2 | 重构 `config.py` 多平台配置 | T0.1 | 新 schema + 旧格式迁移 + 默认值 |
| T0.3 | 创建 `providers/base.py` 基类 | T0.1 | BaseProvider 抽象类 |

### Phase 1: Provider 实现 (依赖 Phase 0)

| # | 任务 | 依赖 | 说明 |
|---|------|------|------|
| T1.1 | 实现 `providers/deepseek.py` | T0.3 | 从原 api.py 迁移，适配新接口 |
| T1.2 | 实现 `providers/minimax_token.py` | T0.3 | MiniMax Token Plan |
| T1.3 | 实现 `providers/minimax_coding.py` | T0.3 | MiniMax Coding Plan |
| T1.4 | 实现 `providers/mimo.py` | T0.3 | 小米 MiMo |
| T1.5 | 创建 `providers/__init__.py` 注册表 | T1.1-T1.4 | 工厂函数 |

### Phase 2: 应用核心 (依赖 Phase 1)

| # | 任务 | 依赖 | 说明 |
|---|------|------|------|
| T2.1 | 实现 `app.py` 应用核心 | T1.5 | App 类，ProviderMgr，刷新调度 |
| T2.2 | 实现 `icon_renderer.py` | T0.1 | 多平台图标渲染逻辑 |

### Phase 3: UI 层 (依赖 Phase 2)

| # | 任务 | 依赖 | 说明 |
|---|------|------|------|
| T3.1 | 重构 `tray.py` 托盘模块 | T2.1, T2.2 | 多平台菜单 + 图标更新 |
| T3.2 | 重构 `settings.py` 设置页面 | T2.1 | 多平台配置 UI + API Key 测试 |
| T3.3 | 重构 `main.py` 入口 | T2.1 | 适配新 App 类 |

### Phase 4: 集成测试

| # | 任务 | 依赖 | 说明 |
|---|------|------|------|
| T4.1 | 端到端集成测试 | T3.1-T3.3 | 各平台查询 + 托盘显示 + 设置修改 |
| T4.2 | 打包 EXE 测试 | T4.1 | PyInstaller 打包验证 |

### 依赖关系图

```
T0.1 ──┬── T0.2 ──────────────────────────┐
        ├── T0.3 ──┬── T1.1 ──┐            │
        │           ├── T1.2 ──┤            │
        │           ├── T1.3 ──┼── T1.5 ── T2.1 ──┬── T3.1
        │           └── T1.4 ──┘            │       ├── T3.2
        │                                   │       └── T3.3 ── T4.1 ── T4.2
        └── T2.2 ───────────────────────────┘
```

---

## 9. 依赖包列表

```
# requirements.txt
pystray>=0.19.0          # 系统托盘图标
Pillow>=10.0.0          # 图像处理（图标渲染）
requests>=2.28.0        # HTTP 请求
```

无新增依赖。所有功能基于 Python 标准库 + 原有依赖实现。

---

## 10. 共享知识 - 跨文件约定

### 10.1 命名约定

| 范围 | 约定 | 示例 |
|------|------|------|
| Provider 类型标识 | 小写 + 下划线 | `deepseek`, `minimax_token`, `minimax_coding`, `mimo` |
| Account ID | `{type}_{序号}` | `deepseek_1`, `minimax_token_1` |
| 配置文件键 | snake_case | `refresh_interval`, `warning_threshold` |
| 日志 logger | `"api-monitor"` | 统一 logger 名称 |
| Provider 类名 | PascalCase + Provider 后缀 | `DeepSeekProvider`, `MiniMaxTokenProvider` |
| 数据模型类 | PascalCase | `ProviderResult`, `AccountConfig` |

### 10.2 编码约定

- **文件编码**: 所有 `.py` 和 `.html` 文件使用 UTF-8
- **类型注解**: 所有公共方法签名使用 type hints
- **dataclass**: 数据模型统一使用 `@dataclass`，不可变场景用 `frozen=True`
- **异常处理**: Provider 层捕获所有异常，返回 `ProviderResult(status=ERROR)`，不向上抛出
- **日志级别**: DEBUG=API 响应体, INFO=正常操作, WARNING=重试/降级, ERROR=失败

### 10.3 线程安全

- `App._lock` 保护 `self.results` 的读写
- `TrayIcon` 所有 UI 更新在主线程执行（pystray 要求）
- `Provider.fetch()` 无状态，可安全并发调用
- `config.py` 的 `save_config()` 使用原子写入（写临时文件后 rename）

### 10.4 错误处理策略

| 层级 | 策略 |
|------|------|
| Provider.fetch() | 捕获所有异常 → 返回 `ProviderResult(status=ERROR, error_message=...)` |
| App.refresh_all() | 单个 Provider 失败不影响其他 Provider |
| TrayIcon | 查询失败时图标变红，菜单显示错误原因 |
| Settings | API Key 测试失败时在页面显示具体错误 |

### 10.5 HTTP 请求约定

- 使用 `requests.Session()`（连接复用 + 统一 headers）
- 超时: 连接 5s + 读取 10s（总 15s）
- 不做请求重试（避免阻塞刷新周期）
- User-Agent: `APIMonitor/2.0`

### 10.6 配置文件兼容性

- 检测 `config.json` 中是否有 `version` 字段
- `version` 缺失 → 视为 v1 格式，自动迁移
- 迁移后立即保存新格式
- 旧配置目录 `%APPDATA%/DeepSeekMonitor/` → 新目录 `%APPDATA%/APIMonitor/`
- 首次运行时自动检测旧目录并提示迁移

### 10.7 打包 (EXE) 约定

- 使用 PyInstaller
- `--onefile` 模式
- `--noconsole` 隐藏控制台窗口
- `--add-data` 包含字体文件
- Provider 类使用 `importlib` 动态加载（避免 PyInstaller 遗漏）
- 入口文件 `main.py` 使用 `if __name__ == "__main__"` 保护

---

## 附录 A: 完整配置示例

```json
{
  "version": 2,
  "accounts": [
    {
      "id": "minimax_token_1",
      "type": "minimax_token",
      "name": "MiniMax Token",
      "api_key": "eyJhbGci...",
      "enabled": true,
      "warning_threshold": null,
      "extra": {}
    },
    {
      "id": "minimax_coding_1",
      "type": "minimax_coding",
      "name": "MiniMax Coding",
      "api_key": "eyJhbGci...",
      "enabled": true,
      "warning_threshold": null,
      "extra": {}
    },
    {
      "id": "mimo_1",
      "type": "mimo",
      "name": "小米 MiMo",
      "api_key": "sk-xxx...",
      "enabled": true,
      "warning_threshold": null,
      "extra": {}
    },
    {
      "id": "deepseek_1",
      "type": "deepseek",
      "name": "DeepSeek 账号1",
      "api_key": "sk-xxx...",
      "enabled": true,
      "warning_threshold": 10.0,
      "extra": {}
    },
    {
      "id": "deepseek_2",
      "type": "deepseek",
      "name": "DeepSeek 账号2",
      "api_key": "sk-yyy...",
      "enabled": true,
      "warning_threshold": null,
      "extra": {}
    }
  ],
  "global": {
    "refresh_interval": 300,
    "warning_threshold_percent": 20,
    "warning_threshold_balance": 10,
    "critical_threshold_percent": 5,
    "icon_display": "worst"
  },
  "first_run": false
}
```

## 附录 B: ProviderResult 各平台示例

### DeepSeek

```python
ProviderResult(
    provider_type="deepseek",
    account_name="DeepSeek 账号1",
    status=StatusLevel.NORMAL,
    display_value="¥123.45",
    display_unit="CNY",
    remaining_percent=None,
    detail="总额: ¥123.45\n赠送: ¥0.00\n充值: ¥123.45",
    models=[],
)
```

### MiniMax Token Plan

```python
ProviderResult(
    provider_type="minimax_token",
    account_name="MiniMax Token",
    status=StatusLevel.NORMAL,
    display_value="85%",
    display_unit="%",
    remaining_percent=85.0,
    detail="区间剩余: 85%\n周剩余: 100%\ngeneral: 85%  video: 66%",
    models=[
        ModelQuota(name="general", remaining_percent=85, unit="%"),
        ModelQuota(name="video", remaining_percent=66, unit="%"),
    ],
)
```

### MiniMax Coding Plan

```python
ProviderResult(
    provider_type="minimax_coding",
    account_name="MiniMax Coding",
    status=StatusLevel.NORMAL,
    display_value="85%",
    display_unit="%",
    remaining_percent=85.0,
    detail="区间剩余: 85% (150/1000 次)\ndeepseek-chat: 85%",
    models=[
        ModelQuota(name="deepseek-chat", remaining_percent=85, used=150, total=1000, unit="次"),
    ],
)
```

### 小米 MiMo

```python
ProviderResult(
    provider_type="mimo",
    account_name="小米 MiMo",
    status=StatusLevel.WARNING,
    display_value="3.1B",
    display_unit="tokens",
    remaining_percent=76.0,
    detail="总量: 4.1B\n已用: 1.0B\n剩余: 3.1B\n过期: 2026-07-01",
    models=[],
)
```

## 附录 C: 新增平台扩展指南

添加新平台只需 3 步：

1. **创建 Provider 类**: 在 `src/providers/` 下新建文件，继承 `BaseProvider`，实现 `fetch()` 方法
2. **注册到注册表**: 在 `providers/__init__.py` 的 `ALL_PROVIDERS` 中添加映射
3. **更新设置页面**: 在 `settings.py` 的平台列表中添加对应选项

示例 — 添加京东云 Provider:

```python
# src/providers/jdcloud.py
class JDCloudProvider(BaseProvider):
    PROVIDER_TYPE = "jdcloud"
    PROVIDER_LABEL = "京东云"
    API_BASE = "https://api.jdcloud.com"

    def fetch(self) -> ProviderResult:
        # 实现京东云的查询逻辑
        ...
```

```python
# src/providers/__init__.py
from .jdcloud import JDCloudProvider

ALL_PROVIDERS["jdcloud"] = JDCloudProvider
```
