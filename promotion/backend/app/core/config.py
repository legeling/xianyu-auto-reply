"""
推广返佣系统 - 服务配置模块

功能：
1. 继承common配置基类
2. 添加推广返佣系统特定配置
3. 从.env文件读取配置
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import List

from pydantic import Field, computed_field, field_validator

from common.core.config import BaseConfig
from common.utils.security import is_weak_jwt_secret


class PromotionConfig(BaseConfig):
    """
    推广返佣系统配置类

    包含推广返佣系统特定配置：
    - 服务端口
    - JWT配置
    - CORS配置
    """

    # 服务配置
    project_name: str = Field(default="推广返佣系统")
    version: str = Field(default="0.1.0")
    api_v1_prefix: str = Field(default="/api/v1")
    service_port: int = Field(default=8092, alias="PROMOTION_PORT")

    # JWT配置
    # 安全（H1 修复）：jwt_secret_key 无默认值、启动必填（环境变量 JWT_SECRET_KEY），
    # 且拒绝弱/占位密钥——避免部署时使用恒定的 "change-me" 导致令牌可被任意伪造。
    jwt_secret_key: str = Field(..., repr=False)
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_minutes: int = Field(default=60 * 24 * 7)

    # CORS配置
    cors_origins_raw: str = Field(default="*", alias="CORS_ORIGINS")

    @field_validator("jwt_secret_key")
    @classmethod
    def _reject_weak_jwt_secret(cls, value: str) -> str:
        """安全：启动时拒绝弱/占位 JWT 密钥（fail-closed，配置校验失败即无法启动）。"""
        if is_weak_jwt_secret(value):
            raise ValueError(
                "JWT_SECRET_KEY 为弱/占位密钥或长度不足（至少16位强随机值），"
                "请使用如 `openssl rand -hex 32` 生成的强随机密钥后重新启动"
            )
        return value

    # 静态文件目录
    static_dir: str = Field(default="static", alias="STATIC_DIR")

    @computed_field(return_type=list[str])
    @property
    def cors_origins(self) -> List[str]:
        """解析CORS配置"""
        raw_value = self.cors_origins_raw.strip()
        if not raw_value:
            return ["*"]
        if raw_value == "*":
            return ["*"]
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return [str(origin).strip() for origin in parsed if str(origin).strip()]
        except json.JSONDecodeError:
            pass
        return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


@lru_cache
def get_settings() -> PromotionConfig:
    """返回缓存的配置实例"""
    return PromotionConfig()
