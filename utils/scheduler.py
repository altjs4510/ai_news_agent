import os
import time
import logging
import asyncio
import schedule
from datetime import datetime
import subprocess
import sys

logger = logging.getLogger('scheduler')

class NewsScheduler:
    def __init__(self):
        self.run_time = os.getenv("SCHEDULER_RUN_TIME", "08:00")  # 기본값: 매일 오전 8시
        
    def _run_news_collection(self):
        """AI 뉴스 수집 및 노션 페이지 생성 스크립트를 실행합니다."""
        try:
            logger.info(f"=== 정기 뉴스 수집 시작 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
            
            # 현재 스크립트의 경로 기준으로 main.py 위치 확인
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            main_script = os.path.join(current_dir, "main.py")
            
            # Python 프로세스를 별도로 실행
            python_executable = sys.executable
            result = subprocess.run(
                [python_executable, main_script],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info("뉴스 수집 및 노션 페이지 생성 성공")
                logger.debug(f"출력: {result.stdout}")
            else:
                logger.error(f"뉴스 수집 실패 (코드: {result.returncode})")
                logger.error(f"오류: {result.stderr}")
                
        except Exception as e:
            logger.error(f"뉴스 수집 실행 중 오류 발생: {str(e)}")
    
    def start(self):
        """스케줄러를 시작합니다."""
        logger.info(f"AI 뉴스 스케줄러 시작 (매일 {self.run_time}에 실행)")
        
        # 매일 지정된 시간에 실행
        schedule.every().day.at(self.run_time).do(self._run_news_collection)
        
        # 시작 시 한 번 실행 (테스트용)
        logger.info("초기 실행 (테스트용)")
        self._run_news_collection()
        
        # 스케줄러 실행
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # 1분마다 스케줄 확인
            except KeyboardInterrupt:
                logger.info("스케줄러 중지됨")
                break
            except Exception as e:
                logger.error(f"스케줄러 실행 중 오류 발생: {str(e)}")
                time.sleep(300)  # 오류 발생 시 5분 대기 후 재시도

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("scheduler.log")
        ]
    )
    
    # 스케줄러 시작
    scheduler = NewsScheduler()
    scheduler.start() 