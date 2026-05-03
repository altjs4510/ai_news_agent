import logging
import sys
from datetime import datetime
import os

def setup_logger(name):
    """애플리케이션 전반에서 사용할 로거를 설정합니다."""
    
    # 로그 디렉토리 생성
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 로거 생성
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # 이미 핸들러가 설정되어 있다면 추가하지 않음
    if logger.handlers:
        return logger
    
    # 파일 핸들러 설정 (매일 새로운 로그 파일)
    today = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(
        filename=f"{log_dir}/ai_news_{today}.log",
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 포맷터 설정
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 핸들러 추가
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger 