#!/bin/bash

# AI News Agent 스케줄러 설치/제거 스크립트
# 작성일: $(date '+%Y-%m-%d')

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CRON_FILE="$SCRIPT_DIR/ai_news_cron"
RUN_SCRIPT="$SCRIPT_DIR/run_ai_news.sh"

show_help() {
    echo "AI News Agent 스케줄러 관리 도구"
    echo ""
    echo "사용법:"
    echo "  ./setup_scheduler.sh install   - cron 작업 설치"
    echo "  ./setup_scheduler.sh remove    - cron 작업 제거"
    echo "  ./setup_scheduler.sh status    - 현재 cron 작업 상태 확인"
    echo "  ./setup_scheduler.sh test      - 스크립트 테스트 실행"
    echo "  ./setup_scheduler.sh help      - 도움말 표시"
    echo ""
}

install_cron() {
    echo "=== AI News Agent 스케줄러 설치 ==="
    
    # 실행 스크립트 권한 확인
    if [ ! -f "$RUN_SCRIPT" ]; then
        echo "오류: run_ai_news.sh 파일을 찾을 수 없습니다."
        exit 1
    fi
    
    # 실행 권한 부여
    chmod +x "$RUN_SCRIPT"
    echo "✓ run_ai_news.sh 실행 권한 설정 완료"
    
    # cron 파일 확인
    if [ ! -f "$CRON_FILE" ]; then
        echo "오류: ai_news_cron 파일을 찾을 수 없습니다."
        exit 1
    fi
    
    # 현재 cron 백업
    crontab -l > current_cron 2>/dev/null || echo "# 기존 cron 작업 없음" > current_cron
    echo "✓ 현재 cron 작업 백업 완료 (current_cron)"
    
    # 새 cron 작업 추가
    (crontab -l 2>/dev/null; echo ""; cat "$CRON_FILE") | crontab -
    echo "✓ cron 작업 등록 완료"
    
    echo ""
    echo "설치 완료! 다음 명령으로 확인할 수 있습니다:"
    echo "  crontab -l"
    echo ""
    echo "매주 월요일 오전 6시에 AI News Agent가 자동 실행됩니다."
}

remove_cron() {
    echo "=== AI News Agent 스케줄러 제거 ==="
    
    # AI News Agent 관련 cron 작업 제거
    crontab -l 2>/dev/null | grep -v "run_ai_news.sh" | crontab -
    echo "✓ AI News Agent cron 작업 제거 완료"
    
    # 백업 파일 업데이트
    crontab -l > current_cron 2>/dev/null || echo "# cron 작업 없음" > current_cron
    echo "✓ 현재 cron 상태 업데이트 완료"
    
    echo ""
    echo "제거 완료!"
}

check_status() {
    echo "=== AI News Agent 스케줄러 상태 ==="
    echo ""
    echo "현재 등록된 cron 작업:"
    crontab -l 2>/dev/null || echo "등록된 cron 작업이 없습니다."
    echo ""
    
    echo "AI News Agent 관련 작업:"
    if crontab -l 2>/dev/null | grep -q "run_ai_news.sh"; then
        echo "✓ AI News Agent 스케줄러가 등록되어 있습니다."
        crontab -l 2>/dev/null | grep "run_ai_news.sh"
    else
        echo "✗ AI News Agent 스케줄러가 등록되어 있지 않습니다."
    fi
    echo ""
    
    echo "파일 상태:"
    [ -f "$RUN_SCRIPT" ] && echo "✓ run_ai_news.sh 존재" || echo "✗ run_ai_news.sh 없음"
    [ -x "$RUN_SCRIPT" ] && echo "✓ run_ai_news.sh 실행 가능" || echo "✗ run_ai_news.sh 실행 권한 없음"
    [ -f "$CRON_FILE" ] && echo "✓ ai_news_cron 존재" || echo "✗ ai_news_cron 없음"
}

test_run() {
    echo "=== AI News Agent 테스트 실행 ==="
    echo ""
    
    if [ ! -f "$RUN_SCRIPT" ]; then
        echo "오류: run_ai_news.sh 파일을 찾을 수 없습니다."
        exit 1
    fi
    
    if [ ! -x "$RUN_SCRIPT" ]; then
        echo "실행 권한 부여 중..."
        chmod +x "$RUN_SCRIPT"
    fi
    
    echo "AI News Agent를 테스트 실행합니다..."
    echo "로그는 logs/ 디렉토리에서 확인할 수 있습니다."
    echo ""
    
    "$RUN_SCRIPT"
}

# 메인 로직
case "$1" in
    install)
        install_cron
        ;;
    remove)
        remove_cron
        ;;
    status)
        check_status
        ;;
    test)
        test_run
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "오류: 잘못된 명령입니다."
        echo ""
        show_help
        exit 1
        ;;
esac
