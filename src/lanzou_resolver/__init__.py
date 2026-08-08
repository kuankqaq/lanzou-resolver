"""lanzou-resolver - 蓝奏云分享链接解析/下载客户端。"""

from .client import LANZOU_DOMAINS, LanzouClient, LanzouError, ResolveResult

__version__ = "0.1.1"

__all__ = [
    "__version__",
    "LANZOU_DOMAINS",
    "LanzouClient",
    "LanzouError",
    "ResolveResult",
]


def resolve(share_url: str, password: str | None = None) -> ResolveResult:
    """解析蓝奏云分享链接，返回包含最终直链的 ResolveResult。

    无密码分享可直接传 URL；需要密码的分享在缺密码时抛出 LanzouError。
    """
    return LanzouClient().resolve(share_url, password)
