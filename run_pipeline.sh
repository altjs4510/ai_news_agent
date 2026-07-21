#!/bin/bash
# AI News 파이프라인 로컬 실행 래퍼 — launchd 가 호출한다.
#   usage: run_pipeline.sh daily|weekly|vocab
#
# 배경: LLM 백엔드가 F&F LiteLLM 프록시(사내망 전용)라 GitHub Actions(공용 러너)에선
# 안 닿아 로컬 실행으로 이관했다. Actions 에서 daily 완료→curate→link-related,
# quality-monitor 로 물려 있던 체인을 여기서 순차 재현한다. (weekly 는 발행만, vocab 은 월1회 독립.)
# 백엔드 자격증명·설정은 .env (git-ignore) 에서 온다. → CLAUDE.md 참조.

set -uo pipefail
cd "$(dirname "$0")" || exit 1

MODE="${1:-}"
case "$MODE" in
    daily|weekly|vocab) ;;
    *) echo "usage: $0 daily|weekly|vocab" >&2; exit 2 ;;
esac

# .env 로드(셸 레벨) — SLACK_WEBHOOK_URL 등 셸에서 필요한 값. python 은 별도로 load_dotenv 함.
set -a
[ -f .env ] && . ./.env
set +a

UV="/Users/ac1158/.local/bin/uv"
LOG="logs/pipeline_${MODE}.log"
mkdir -p logs

log()   { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
notify_fail() {
    # 실패 시 Slack 알림(웹훅이 .env 에 있을 때만). Actions 의 실패 알림 대체.
    local step="$1"
    [ -n "${SLACK_WEBHOOK_URL:-}" ] || return 0
    local text=":x: *AI News 로컬 파이프라인 실패* — mode=\`${MODE}\`, step=\`${step}\`\n호스트: $(hostname)  로그: ${LOG}"
    curl -sS -m 10 -X POST -H 'Content-Type: application/json' \
         --data "$(python3 -c 'import json,sys; print(json.dumps({"text": sys.argv[1]}))' "$text")" \
         "$SLACK_WEBHOOK_URL" >/dev/null 2>&1 || true
}

# step <label> <script...> : 실행하고 실패해도 다음 단계로(경고만). 반환코드 전파.
run_step() {
    local label="$1"; shift
    log "▶ ${label} 시작: $*"
    if "$UV" run python "$@" >>"$LOG" 2>&1; then
        log "✔ ${label} 완료"
        return 0
    else
        local rc=$?
        log "✘ ${label} 실패 (exit=$rc)"
        notify_fail "$label"
        return $rc
    fi
}

log "===== 파이프라인 시작 (mode=${MODE}) ====="

case "$MODE" in
    daily)
        # main 이 실패하면 후속 단계는 의미 없음 → 중단.
        if ! run_step "collect+publish (daily)" main.py --mode daily; then
            log "main.py 실패 — 후속 단계 스킵, 종료"
            exit 1
        fi
        # 후속 체인: 하나 실패해도 나머지는 시도(각자 독립 발행/모니터).
        run_step "curate (사이드바 전파)" curate.py || true
        run_step "link-related (관련 링크)" link_related.py || true
        run_step "quality-monitor (링크 검사)" quality_monitor.py || true
        ;;
    weekly)
        if ! run_step "collect+publish (weekly)" main.py --mode weekly; then
            exit 1
        fi
        ;;
    vocab)
        run_step "vocabulary 제안" vocab_suggest.py || exit 1
        ;;
esac

log "===== 파이프라인 종료 (mode=${MODE}) ====="
