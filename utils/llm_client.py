"""LLM 클라이언트 팩토리 — 3개 백엔드.

백엔드 선택 (env, 우선순위 순):
  USE_CLAUDE_CLI=1   → Claude Code 구독 경유 (`claude -p`). 공용망 어디서든 동작(사내망 불필요).
  USE_BEDROCK=1      → AnthropicBedrock.
  (둘 다 아니면)      → 기본 Anthropic API / 호환 프록시 (ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN
                        을 SDK 가 자동 인식 — 현행: F&F LiteLLM 사내망 프록시).

호출부는 canonical 모델명("claude-opus-4-8" 등)을 그대로 쓰고, resolve_model 이 각 백엔드에
맞는 식별자로 치환한다. 클라이언트 객체는 어느 백엔드든 `client.messages.create(...)`
(sync) / `await client.messages.create(...)` (async) 를 지원하고, 응답은 `.content[0].text`.

설정 env vars:
  USE_CLAUDE_CLI      "1"이면 claude -p 백엔드
  CLAUDE_CLI_BIN      claude 바이너리 경로 오버라이드 (기본: PATH 의 "claude")
  CLAUDE_CLI_TIMEOUT  claude -p 1콜 타임아웃 초 (기본 600)
  USE_BEDROCK         "1"이면 Bedrock
  AWS_REGION          Bedrock 리전
  ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN  기본 백엔드(프록시) 설정
  BEDROCK_MODEL_{OPUS_4_7,SONNET_4_6,HAIKU_4_5}  Bedrock 모델 ID 오버라이드
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from typing import Any

# 응답 전체가 단일 코드펜스 블록(```lang … ```)이고 내부에 펜스가 없을 때만 언랩.
# claude -p 는 JSON 을 종종 ```json … ``` 로 감싸는데, call-site 는 json.loads(text) 를 하므로
# 벗겨줘야 한다. 내부에 ``` 가 또 있으면(=여러 블록 섞인 마크다운) 손대지 않아 번역문 등이 안전.
_FENCE_RE = re.compile(r"^```[A-Za-z0-9_-]*\n(.*)\n```$", re.DOTALL)


def _strip_outer_fence(text: str) -> str:
    t = text.strip()
    m = _FENCE_RE.match(t)
    if m and "```" not in m.group(1):
        return m.group(1).strip()
    return text

# canonical 모델명 → 기본 Bedrock 모델 ID.
_BEDROCK_DEFAULTS: dict[str, str] = {
    "claude-opus-4-8": "global.anthropic.claude-opus-4-8",
    "claude-sonnet-5": "global.anthropic.claude-sonnet-5",
    "claude-haiku-4-5": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
}

_BEDROCK_ENV_OVERRIDES: dict[str, str] = {
    "claude-opus-4-8": "BEDROCK_MODEL_OPUS_4_7",
    "claude-sonnet-5": "BEDROCK_MODEL_SONNET_4_6",
    "claude-haiku-4-5": "BEDROCK_MODEL_HAIKU_4_5",
}

# canonical 모델명 → claude CLI --model 별칭. 별칭은 항상 현행 최신으로 해석돼 안전.
_CLI_ALIASES: dict[str, str] = {
    "claude-opus-4-8": "opus",
    "claude-sonnet-5": "sonnet",
    "claude-haiku-4-5": "haiku",
}
# CLI 별칭 → canonical (claude -p 실패 시 프록시 폴백에서 원래 모델명 복원용).
_CLI_TO_CANONICAL: dict[str, str] = {v: k for k, v in _CLI_ALIASES.items()}


def _proxy_configured() -> bool:
    """LiteLLM/Anthropic 프록시 폴백에 필요한 설정이 있는지."""
    return bool(
        os.getenv("ANTHROPIC_BASE_URL")
        or os.getenv("ANTHROPIC_AUTH_TOKEN")
        or os.getenv("ANTHROPIC_API_KEY")
    )


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes")


def use_claude_cli() -> bool:
    return _flag("USE_CLAUDE_CLI")


def use_bedrock() -> bool:
    return _flag("USE_BEDROCK")


def backend() -> str:
    if use_claude_cli():
        return "claude_cli"
    if use_bedrock():
        return "bedrock"
    return "anthropic"


def resolve_model(canonical: str) -> str:
    """canonical 모델명을 현재 백엔드에 맞는 식별자로 변환."""
    b = backend()
    if b == "claude_cli":
        return _CLI_ALIASES.get(canonical, canonical)
    if b == "bedrock":
        env_key = _BEDROCK_ENV_OVERRIDES.get(canonical)
        if env_key:
            override = os.getenv(env_key, "").strip()
            if override:
                return override
        return _BEDROCK_DEFAULTS.get(canonical, canonical)
    return canonical


# ---------------------------------------------------------------------------
# claude -p (Claude Code 구독) 어댑터 — anthropic SDK 의 messages.create 를 흉내낸다.
# ---------------------------------------------------------------------------

class _Block:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _Usage:
    def __init__(self, input_tokens: int = 0, output_tokens: int = 0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _Response:
    """anthropic Message 형태의 최소 shim: .content[0].text / .usage / .stop_reason."""
    def __init__(self, text: str, usage: _Usage, stop_reason: str = "end_turn"):
        self.content = [_Block(text)]
        self.usage = usage
        self.stop_reason = stop_reason
        self.role = "assistant"


def _claude_bin() -> str:
    return os.getenv("CLAUDE_CLI_BIN") or shutil.which("claude") or "claude"


# claude -p 는 환경에 이 키들이 있으면 구독 로그인 대신 그걸(=프록시) 우선해 버린다.
# 서브프로세스 env 에서 제거해야 claude.ai 구독 인증을 쓴다. (폴백 프록시 클라이언트는
# 메인 프로세스 env 로 별도 구성되므로 영향 없음.)
_PROXY_ENV_KEYS = ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN",
                   "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL")


def _cli_env() -> dict:
    env = dict(os.environ)
    for k in _PROXY_ENV_KEYS:
        env.pop(k, None)
    return env


def _cli_timeout() -> int:
    try:
        return int(os.getenv("CLAUDE_CLI_TIMEOUT", "600"))
    except ValueError:
        return 600


def _content_to_text(content: Any) -> str:
    """messages content(str 또는 블록 리스트)를 평문으로."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for blk in content:
            if isinstance(blk, dict):
                parts.append(blk.get("text", "") or "")
            else:
                parts.append(getattr(blk, "text", "") or "")
        return "\n".join(p for p in parts if p)
    return str(content)


def _flatten(messages: list[dict], system: str | None) -> tuple[str, str | None]:
    """messages → 단일 프롬프트 문자열. system 은 별도 반환(--system-prompt 로)."""
    if len(messages) == 1 and messages[0].get("role") == "user":
        prompt = _content_to_text(messages[0].get("content", ""))
    else:
        lines = []
        for m in messages:
            role = m.get("role", "user")
            lines.append(f"[{role}]\n{_content_to_text(m.get('content', ''))}")
        prompt = "\n\n".join(lines)
    return prompt, system


def _build_cmd(prompt: str, model: str, system: str | None) -> list[str]:
    cmd = [_claude_bin(), "-p", prompt, "--model", model, "--output-format", "json"]
    # 기본 시스템 프롬프트를 대체해 순수 텍스트/JSON 변환기로 동작시킨다.
    cmd += ["--system-prompt", system or
            "You are a text/JSON transformation function. Output exactly what is asked, nothing else."]
    return cmd


def _parse_cli_json(stdout: str) -> tuple[str, _Usage]:
    data = json.loads(stdout)
    if data.get("is_error") or data.get("subtype") != "success":
        raise RuntimeError(
            f"claude -p error: subtype={data.get('subtype')} "
            f"result={str(data.get('result', ''))[:300]}"
        )
    usage = data.get("usage", {}) or {}
    return _strip_outer_fence(data.get("result", "")), _Usage(
        usage.get("input_tokens", 0) or 0,
        usage.get("output_tokens", 0) or 0,
    )


class _CLIMessages:
    def create(self, *, model: str, messages: list[dict], system: str | None = None,
               max_tokens: int | None = None, temperature: float | None = None,
               **_ignored: Any) -> _Response:
        prompt, sys_prompt = _flatten(messages, system)
        cmd = _build_cmd(prompt, model, sys_prompt)
        proc = subprocess.run(
            cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=_cli_timeout(), env=_cli_env(),
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"claude -p failed rc={proc.returncode}: {(proc.stderr or '')[:500]}"
            )
        text, usage = _parse_cli_json(proc.stdout)
        return _Response(text, usage)


def _log():
    import logging
    return logging.getLogger("llm_client")


def _wrap_proxy(resp: Any) -> _Response:
    """프록시(Anthropic SDK) 응답을 _Response 로 정규화 + 펜스 스트립(CLI 경로와 통일)."""
    text = resp.content[0].text if getattr(resp, "content", None) else ""
    u = getattr(resp, "usage", None)
    return _Response(
        _strip_outer_fence(text),
        _Usage(getattr(u, "input_tokens", 0) or 0, getattr(u, "output_tokens", 0) or 0),
        getattr(resp, "stop_reason", "end_turn") or "end_turn",
    )


def _proxy_kwargs(model: str, messages: list[dict], system, max_tokens, temperature) -> dict:
    """CLI 별칭 model 을 canonical 로 되돌려 프록시(Anthropic SDK) create kwargs 구성."""
    kwargs: dict[str, Any] = {
        "model": _CLI_TO_CANONICAL.get(model, model),
        "messages": messages,
    }
    if system is not None:
        kwargs["system"] = system
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if temperature is not None:
        kwargs["temperature"] = temperature
    return kwargs


class _FallbackMessages:
    """claude -p 우선, 실패 시 LiteLLM/Anthropic 프록시로 per-call 폴백 (sync)."""
    def __init__(self):
        self._cli = _CLIMessages()
        self._proxy = None

    def create(self, *, model, messages, system=None, max_tokens=None,
               temperature=None, **kw) -> Any:
        try:
            return self._cli.create(model=model, messages=messages, system=system,
                                    max_tokens=max_tokens, temperature=temperature, **kw)
        except Exception as e:
            if not _proxy_configured():
                raise
            _log().warning(f"claude -p 실패 → LiteLLM 프록시 폴백: {e}")
            if self._proxy is None:
                from anthropic import Anthropic
                self._proxy = Anthropic()
            return _wrap_proxy(self._proxy.messages.create(
                **_proxy_kwargs(model, messages, system, max_tokens, temperature)))


class _ClaudeCLIClient:
    def __init__(self):
        self.messages = _FallbackMessages()


class _AsyncCLIMessages:
    async def create(self, *, model: str, messages: list[dict], system: str | None = None,
                     max_tokens: int | None = None, temperature: float | None = None,
                     **_ignored: Any) -> _Response:
        import asyncio
        prompt, sys_prompt = _flatten(messages, system)
        cmd = _build_cmd(prompt, model, sys_prompt)
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=_cli_env(),
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=_cli_timeout())
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("claude -p timed out")
        if proc.returncode != 0:
            raise RuntimeError(
                f"claude -p failed rc={proc.returncode}: {(err.decode() if err else '')[:500]}"
            )
        text, usage = _parse_cli_json(out.decode())
        return _Response(text, usage)


class _AsyncFallbackMessages:
    """claude -p 우선, 실패 시 프록시로 per-call 폴백 (async)."""
    def __init__(self):
        self._cli = _AsyncCLIMessages()
        self._proxy = None

    async def create(self, *, model, messages, system=None, max_tokens=None,
                     temperature=None, **kw) -> Any:
        try:
            return await self._cli.create(model=model, messages=messages, system=system,
                                          max_tokens=max_tokens, temperature=temperature, **kw)
        except Exception as e:
            if not _proxy_configured():
                raise
            _log().warning(f"claude -p 실패 → LiteLLM 프록시 폴백: {e}")
            if self._proxy is None:
                from anthropic import AsyncAnthropic
                self._proxy = AsyncAnthropic()
            return _wrap_proxy(await self._proxy.messages.create(
                **_proxy_kwargs(model, messages, system, max_tokens, temperature)))


class _AsyncClaudeCLIClient:
    def __init__(self):
        self.messages = _AsyncFallbackMessages()


# ---------------------------------------------------------------------------
# 팩토리
# ---------------------------------------------------------------------------

def make_client() -> Any:
    """동기 클라이언트 반환 (백엔드에 따라 Anthropic / AnthropicBedrock / claude -p shim)."""
    b = backend()
    if b == "claude_cli":
        return _ClaudeCLIClient()
    if b == "bedrock":
        from anthropic import AnthropicBedrock
        kwargs: dict[str, Any] = {}
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        if region:
            kwargs["aws_region"] = region
        return AnthropicBedrock(**kwargs)
    from anthropic import Anthropic
    return Anthropic()


def make_async_client() -> Any:
    """비동기 클라이언트 반환."""
    b = backend()
    if b == "claude_cli":
        return _AsyncClaudeCLIClient()
    if b == "bedrock":
        from anthropic import AsyncAnthropicBedrock
        kwargs: dict[str, Any] = {}
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        if region:
            kwargs["aws_region"] = region
        return AsyncAnthropicBedrock(**kwargs)
    from anthropic import AsyncAnthropic
    return AsyncAnthropic()
