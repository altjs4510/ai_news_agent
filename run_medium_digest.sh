#!/bin/bash
# Medium Daily Digest 자동 요약 — launchd 가 매일 새벽 호출한다.
#
# 배경: 이 작업은 main.py 파이프라인(run_pipeline.sh)과 달리 순수 LLM API 호출이 아니라
# Claude Code 에이전트 세션이 필요하다 — Outlook 메일 검색(mcp__claude_ai_Microsoft_365__*)과
# 브라우저 조작(mcp__claude-in-chrome__*)이 claude 세션 안에서만 붙는 도구라서다. 그래서
# `claude -p`(헤드리스) 로 automation/medium_digest_prompt.md 를 통째로 프롬프트로 넘긴다.
#
# 크롬 연동 — `--chrome` 플래그(2026-08-28 확인)로 헤드리스 세션에도 claude-in-chrome
# 확장이 그대로 붙는다. **평소 쓰는 크롬을 전혀 건드리지 않는다** — 재시작도, 디버깅
# 포트도 필요 없다. (처음엔 chrome-devtools MCP 로 크롬을 강제 재시작하는 방식을 시도했다가
# 로그인 세션이 있는 기본 프로필에선 원격 디버깅 자체가 막혀 있어서 실패했고, 크롬을 잘못
# 껐다 켜는 사고까지 났다 — `--chrome` 플래그로 완전히 대체함.)

set -uo pipefail
cd "$(dirname "$0")" || exit 1

LOG="logs/medium_digest.log"
mkdir -p logs

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# 실행 동안 idle-sleep 억제.
command -v caffeinate >/dev/null && caffeinate -i -w "$$" &

log "===== Medium Digest 자동화 시작 ====="

CLAUDE="/Users/ac1158/.local/bin/claude"
PROMPT_FILE="automation/medium_digest_prompt.md"

ALLOWED_TOOLS="mcp__claude_ai_Microsoft_365__outlook_email_search mcp__claude_ai_Microsoft_365__read_resource mcp__claude-in-chrome__tabs_context_mcp mcp__claude-in-chrome__navigate mcp__claude-in-chrome__get_page_text mcp__claude-in-chrome__tabs_close_mcp Write Read Glob Bash(mkdir -p *) Bash(grep *)"

log "claude -p --chrome 실행…"
if "$CLAUDE" -p --chrome "$(cat "$PROMPT_FILE")" \
    --allowedTools $ALLOWED_TOOLS \
    >>"$LOG" 2>&1; then
    log "✔ Medium Digest 완료"
else
    rc=$?
    log "✘ Medium Digest 실패 (exit=$rc)"
fi

log "===== Medium Digest 자동화 종료 ====="
