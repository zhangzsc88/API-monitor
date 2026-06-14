"""
API Monitor - Provider 注册表
"""
from ..models import AccountConfig
from .base import BaseProvider
from .deepseek import DeepSeekProvider
from .jdcloud import JDCloudProvider
from .minimax_token import MiniMaxTokenProvider
from .mimo import MiMoProvider
from .siliconflow import SiliconFlowProvider

# 类型 → Provider 类的映射
ALL_PROVIDERS: dict[str, type[BaseProvider]] = {
    "deepseek": DeepSeekProvider,
    "jdcloud": JDCloudProvider,
    "minimax_token": MiniMaxTokenProvider,
    "mimo": MiMoProvider,
    "siliconflow": SiliconFlowProvider,
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
