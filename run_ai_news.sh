#!/bin/bash

# AI News Agent 실행 스크립트
# 작성일: $(date '+%Y-%m-%d')

# 스크립트 디렉토리로 이동
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# 로그 파일 설정
LOG_FILE="logs/scheduled_run_$(date +%Y%m%d_%H%M%S).log"

# 로그 디렉토리 생성
mkdir -p logs

echo "=== AI News Agent 시작 ===" | tee -a "$LOG_FILE"
echo "시작 시간: $(date)" | tee -a "$LOG_FILE"
echo "작업 디렉토리: $SCRIPT_DIR" | tee -a "$LOG_FILE"

# uv 설치 확인
if command -v uv &> /dev/null; then
    echo "uv 사용 가능" | tee -a "$LOG_FILE"
    echo "uv 버전: $(uv --version)" | tee -a "$LOG_FILE"
else
    echo "경고: uv를 찾을 수 없습니다. 시스템 Python을 사용합니다." | tee -a "$LOG_FILE"
fi

# 환경 변수 확인
if [ ! -f ".env" ]; then
    echo "경고: .env 파일을 찾을 수 없습니다." | tee -a "$LOG_FILE"
fi

# 메인 스크립트 실행
echo "AI News Agent 실행 중..." | tee -a "$LOG_FILE"
if command -v uv &> /dev/null; then
    echo "uv run으로 실행..." | tee -a "$LOG_FILE"
    uv run main.py >> "$LOG_FILE" 2>&1
else
    echo "Python으로 직접 실행..." | tee -a "$LOG_FILE"
    python main.py >> "$LOG_FILE" 2>&1
fi

# 실행 결과 확인
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "=== AI News Agent 완료 ===" | tee -a "$LOG_FILE"
    echo "종료 시간: $(date)" | tee -a "$LOG_FILE"
    echo "상태: 성공" | tee -a "$LOG_FILE"
else
    echo "=== AI News Agent 실패 ===" | tee -a "$LOG_FILE"
    echo "종료 시간: $(date)" | tee -a "$LOG_FILE"
    echo "상태: 실패 (종료 코드: $EXIT_CODE)" | tee -a "$LOG_FILE"
fi

# uv run은 자동으로 가상환경을 관리하므로 별도 정리 불필요

exit $EXIT_CODE
