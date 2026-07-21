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
            timeout=_cli_timeout(),
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"claude -p failed rc={proc.returncode}: {(proc.stderr or '')[:500]}"
            )
        text, usage = _parse_cli_json(proc.stdout)
        return _Response(text, usage)


class _ClaudeCLIClient:
    def __init__(self):
        self.messages = _CLIMessages()


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


class _AsyncClaudeCLIClient:
    def __init__(self):
        self.messages = _AsyncCLIMessages()


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
