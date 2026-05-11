"""Anthropic / Bedrock 클라이언트 팩토리.

환경변수 USE_BEDROCK=1이면 AnthropicBedrock으로 라우팅, 그 외에는 기본 Anthropic API 사용.
호출부는 표준 canonical 모델명(e.g. "claude-opus-4-7")을 그대로 쓰고, 이 모듈이
Bedrock 모드일 때 적절한 Bedrock 모델 ID로 치환한다.

설정 env vars:
  USE_BEDROCK         "1"이면 Bedrock 사용
  AWS_REGION          Bedrock 리전 (e.g. ap-northeast-2, us-east-1)
  AWS_BEARER_TOKEN_BEDROCK  또는 표준 AWS 자격 증명 (boto3 chain)
  BEDROCK_MODEL_OPUS_4_7     Opus 모델 ID 오버라이드
  BEDROCK_MODEL_SONNET_4_6   Sonnet 모델 ID 오버라이드
  BEDROCK_MODEL_HAIKU_4_5    Haiku 모델 ID 오버라이드
"""

from __future__ import annotations

import os
from typing import Any

# canonical 모델명 → 기본 Bedrock 모델 ID.
# inference profile 접두사(global./us./apac.)는 리전/계정 권한에 따라 조정 필요.
# env var로 오버라이드 가능.
_BEDROCK_DEFAULTS: dict[str, str] = {
    "claude-opus-4-7": "global.anthropic.claude-opus-4-7",
    "claude-sonnet-4-6": "global.anthropic.claude-sonnet-4-6",
    "claude-haiku-4-5-20251001": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
}

_BEDROCK_ENV_OVERRIDES: dict[str, str] = {
    "claude-opus-4-7": "BEDROCK_MODEL_OPUS_4_7",
    "claude-sonnet-4-6": "BEDROCK_MODEL_SONNET_4_6",
    "claude-haiku-4-5-20251001": "BEDROCK_MODEL_HAIKU_4_5",
}


def use_bedrock() -> bool:
    return os.getenv("USE_BEDROCK", "").strip() in ("1", "true", "yes")


def resolve_model(canonical: str) -> str:
    """canonical 모델명을 현재 백엔드에 맞는 모델 ID로 변환."""
    if not use_bedrock():
        return canonical
    env_key = _BEDROCK_ENV_OVERRIDES.get(canonical)
    if env_key:
        override = os.getenv(env_key, "").strip()
        if override:
            return override
    default = _BEDROCK_DEFAULTS.get(canonical)
    if default:
        return default
    # 매핑이 없으면 canonical 그대로 — Bedrock 측에서 거부될 수 있음.
    return canonical


def make_client() -> Any:
    """동기 Anthropic 또는 AnthropicBedrock 클라이언트 반환."""
    if use_bedrock():
        from anthropic import AnthropicBedrock
        kwargs: dict[str, Any] = {}
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        if region:
            kwargs["aws_region"] = region
        return AnthropicBedrock(**kwargs)
    from anthropic import Anthropic
    return Anthropic()


def make_async_client() -> Any:
    """비동기 AsyncAnthropic 또는 AsyncAnthropicBedrock 클라이언트 반환."""
    if use_bedrock():
        from anthropic import AsyncAnthropicBedrock
        kwargs: dict[str, Any] = {}
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        if region:
            kwargs["aws_region"] = region
        return AsyncAnthropicBedrock(**kwargs)
    from anthropic import AsyncAnthropic
    return AsyncAnthropic()
