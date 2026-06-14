"""
API Monitor - 数据模型定义
"""
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
    account_name: str                   # 用户自定义名称
    status: StatusLevel                 # 当前状态
    display_value: str                  # 主显示值，如 "¥123.45", "85%"
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
    api_key: str                        # API Key
    enabled: bool = True                # 是否启用
    warning_threshold: Optional[float] = None  # 自定义预警阈值（覆盖全局）
    extra: dict = field(default_factory=dict)   # 扩展字段（如 Cookie 等）
