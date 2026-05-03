import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

logger = logging.getLogger('email_sender')

class EmailSender:
    def __init__(self):
        # 이메일 설정
        self.smtp_server = os.getenv("SMTP_SERVER")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = os.getenv("SMTP_USER")
        self.sender_password = os.getenv("SMTP_PASSWORD")
        self.recipient_emails = os.getenv("SMTP_TO", "").split(',')
        
        # 환경 변수 확인을 위한 디버그 로깅
        logger.info(f"SMTP 서버: {self.smtp_server}")
        logger.info(f"SMTP 포트: {self.smtp_port}")
        logger.info(f"보내는 사람(SMTP_USER): {self.sender_email}")
        logger.info(f"비밀번호 설정: {'있음' if self.sender_password else '없음'}")
        logger.info(f"받는 사람: {self.recipient_emails}")
        
    def send_notion_page_notification(self, date_str, page_id, summary, keywords, reddit_url=None):
        """노션 페이지 생성 알림을 이메일로 발송합니다."""
        if not all([self.smtp_server, self.sender_email, self.sender_password, self.recipient_emails]):
            logger.warning("이메일 설정이 완료되지 않아 알림을 발송할 수 없습니다.")
            return False
            
        try:
            # 이메일 제목 설정
            subject = f"[AI 동향] {date_str} 업데이트 알림"
            
            # 노션 페이지 URL 생성
            notion_url = f"https://www.notion.so/{page_id.replace('-', '')}"
            
            # 이메일 본문 생성
            email_content = f"""
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #f5f5f5; padding: 10px; border-radius: 5px; margin-bottom: 20px; }}
        .footer {{ background-color: #f5f5f5; padding: 10px; border-radius: 5px; margin-top: 20px; font-size: 12px; color: #777; }}
        h1 {{ color: #2c3e50; }}
        h2 {{ color: #3498db; }}
        .button {{ display: inline-block; padding: 10px 20px; background-color: #3498db; color: white; text-decoration: none; border-radius: 5px; }}
        .keywords {{ background-color: #eaf7ff; padding: 10px; border-radius: 5px; margin-bottom: 20px; }}
        .tag {{ display: inline-block; background-color: #e1f0fa; padding: 3px 8px; margin-right: 5px; border-radius: 3px; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AI 동향 업데이트</h1>
            <p>날짜: {date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}</p>
        </div>
        
        <p>안녕하세요,</p>
        <p>오늘의 AI 동향이 업데이트되었습니다. 아래 링크를 통해 자세한 내용을 확인하세요.</p>
        
        <p style="text-align: center; margin: 30px 0;">
            <a href="{notion_url}" class="button">노션 페이지 보기</a>
        </p>
        
        <h2>주요 키워드</h2>
        <div class="keywords">
"""
            
            # 키워드 추가
            for keyword in keywords:
                email_content += f'            <span class="tag">{keyword}</span>\n'
                
            email_content += """
        </div>
        
        <h2>요약</h2>
"""
            
            # 요약 내용 추가
            if isinstance(summary, list):
                for category in summary:
                    title = category.get('title', '')
                    items = category.get('items', [])
                    
                    email_content += f"        <h3>{title}</h3>\n        <ul>\n"
                    for item in items:
                        email_content += f"            <li>{item}</li>\n"
                    email_content += "        </ul>\n"
            else:
                email_content += f"        <p>{summary}</p>\n"
            
            # Reddit 인사이트 파일 링크가 있으면 추가
            if reddit_url:
                email_content += f"""
        <h2>Reddit 인사이트</h2>
        <p><a href="{reddit_url}">Reddit 인사이트 파일 다운로드</a></p>
"""
                
            email_content += """
        <div class="footer">
            <p>이 이메일은 자동으로 생성되었습니다. © AI 뉴스 에이전트 {current_year}</p>
        </div>
    </div>
</body>
</html>
""".format(current_year=datetime.now().year)
            
            # 이메일 메시지 생성
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = ", ".join(self.recipient_emails)
            
            # HTML 메시지 추가
            html_part = MIMEText(email_content, "html")
            message.attach(html_part)
            
            # SMTP 서버 연결 및 이메일 발송
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                logger.info("SMTP 서버에 연결 중...")
                server.starttls()  # TLS 보안 연결
                logger.info(f"SMTP 로그인 시도 (사용자: {self.sender_email})")
                server.login(self.sender_email, self.sender_password)
                logger.info("SMTP 로그인 성공")
                server.send_message(message)
                logger.info("이메일 발송 완료")
                
            logger.info(f"알림 이메일이 {len(self.recipient_emails)}명의 수신자에게 발송되었습니다.")
            return True
            
        except Exception as e:
            logger.error(f"이메일 발송 중 오류 발생: {str(e)}")
            if "Username and Password not accepted" in str(e):
                logger.error("Gmail 앱 비밀번호가 올바르지 않습니다. 새로운 앱 비밀번호를 생성해주세요.")
            return False 

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    import json
    
    # 오늘 날짜의 데이터 파일 경로 설정
    date_str = datetime.now().strftime("%Y%m%d")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    reports_dir = os.path.join(base_dir, "reports", date_str)
    
    try:
        # 키워드와 요약 데이터 읽기
        summary_file = os.path.join(reports_dir, "summary.json")
        if os.path.exists(summary_file):
            with open(summary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                keywords = data.get('keywords', [])
                summary = data.get('summary', [])
        else:
            logger.warning(f"요약 파일을 찾을 수 없습니다: {summary_file}")
            keywords = ["AI", "테스트"]
            summary = [{"title": "테스트", "items": ["테스트 데이터입니다."]}]
        
        # Reddit 인사이트 파일 URL (테스트 시에는 별도 호스팅 URL 미사용)
        reddit_url = None
        
        # 테스트용 페이지 ID (실제로는 노션에서 생성된 ID를 사용)
        test_page_id = "test-page-id"
        
        # 이메일 발송 테스트
        sender = EmailSender()
        result = sender.send_notion_page_notification(
            date_str=date_str,
            page_id=test_page_id,
            summary=summary,
            keywords=keywords,
            reddit_url=reddit_url
        )
        
        if result:
            logger.info("테스트 이메일 발송 성공")
        else:
            logger.error("테스트 이메일 발송 실패")
            
    except Exception as e:
        logger.error(f"테스트 실행 중 오류 발생: {str(e)}") 