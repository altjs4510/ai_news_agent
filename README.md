# AI 뉴스 수집 에이전트

AI 동향을 다양한 소스에서 자동 수집·번역·요약·인사이트화하고, 결과를 [ai_news_blog](https://github.com/altjs4510/ai_news_blog) (Quartz / GitHub Pages) 로 자동 발행하는 도구입니다.

게시 사이트: https://altjs4510.github.io/ai_news_blog

## 주요 기능

- **다중 소스 크롤링**: AITimes, Reddit, YouTube 등 다양한 소스에서 AI 관련 뉴스를 수집
- **번역 및 요약**: 영어 콘텐츠를 한글로 번역하고, 핵심 내용 요약
- **인사이트 추출**: Reddit 포스트에서 주제별로 실용적인 인사이트 추출
- **자동 키워드 생성**: 수집된 콘텐츠에서 중요 키워드 추출
- **블로그 자동 발행**: 결과 마크다운을 별도 블로그 레포에 commit·push → GitHub Actions가 Quartz로 빌드해 Pages에 배포
- **Notion / 이메일 알림**: 옵션으로 활성화 가능 (`main.py`의 `ENABLE_NOTION`, `ENABLE_EMAIL`)
- **스케줄링**: cron 또는 launchd를 통한 정기적인 자동 실행

## 디렉토리 구조

```
ai_news_agent/
├── main.py             # 메인 실행 파일
├── config.py           # 설정 파일
├── sources/            # 데이터 소스 관련 모듈
│   ├── aitimes.py      # AI 타임즈 크롤러
│   ├── reddit.py       # Reddit 수집기
│   └── youtube.py      # YouTube 파싱 모듈
├── delivery/           # 데이터 전달/저장 관련 모듈
│   ├── markdown_writer.py  # 마크다운 파일 생성
│   └── notion_writer.py    # Notion 페이지 생성
├── utils/              # 유틸리티 모듈
│   ├── logger.py       # 로깅 설정
│   └── html_cleaner.py # HTML 정리 유틸리티
├── reports/            # 수집된 데이터 저장 (날짜별)
├── logs/               # 로그 파일 저장
└── requirements.txt    # 의존성 패키지 목록
```

## 설치 방법

1. 저장소 클론
```bash
git clone [저장소 URL]
cd ai-news
```

2. 가상 환경 설정 (uv 사용)
```bash
uv venv
source .venv/bin/activate  # Linux/Mac
# 또는
.venv\Scripts\activate  # Windows
```

3. 의존성 설치
```bash
uv pip install -r requirements.txt
```

4. 환경 변수 설정
프로젝트 루트에 `.env` 파일을 만들고 다음 항목들을 설정합니다:
```
# --- LLM / 소스 API ---
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
YOUTUBE_API_KEY=your_youtube_api_key
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=your_reddit_user_agent

# --- 블로그 발행 (필수, ai_news_blog 레포가 같은 부모 디렉토리에 clone되어 있다고 가정) ---
# BLOG_REPO_PATH=/absolute/path/to/ai_news_blog   # 기본값: ../ai_news_blog
# BLOG_SITE_URL=https://altjs4510.github.io/ai_news_blog

# --- Notion (옵션, ENABLE_NOTION=True 일 때만) ---
# NOTION_TOKEN=your_notion_integration_token
# NOTION_DATABASE_ID=your_notion_database_id

# --- S3 / S3 호환 객체 저장소 (옵션, NotionWriter가 reddit_insights 업로드에 사용) ---
# S3_ACCESS_KEY=your_access_key
# S3_SECRET_KEY=your_secret_key
# S3_BUCKET_NAME=your_bucket_name

# --- 이메일 알림 (옵션, ENABLE_EMAIL=True 일 때만) ---
# SMTP_SERVER=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your@email.com
# SMTP_PASSWORD=your_app_password
# SMTP_TO=recipient1@example.com,recipient2@example.com
```

5. 블로그 레포 준비
```bash
cd ..
git clone git@github-personal:altjs4510/ai_news_blog.git
cd ai_news_agent
```

## 사용 방법

### 수동 실행
```bash
uv run main.py
```

### 자동 스케줄링 설정
매주 월요일 오전 6시에 자동으로 실행되도록 설정할 수 있습니다:

방법 1. 스케줄러 설치:
```bash
./setup_scheduler.sh install
```

방법 2. 수동 설정
(1) Cron 사용
```bash
chmod +x run_ai_news.sh
crontab ai_news_cron
```

현재 설정된 cron 작업 확인:
```bash
crontab -l
```

(2) launchd 사용
1. ~/Library/LaunchAgents/com.ai-news.plist 생성
(예시 plist 파일은 ./com.ai-news.plist 참고)

2. 설치:
```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ai-news.plist
```

3. 강제로 즉시 실행 (테스트용):
```bash
launchctl kickstart -k gui/$(id -u)/com.ai-news
```

4. 해제:
```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.ai-news.plist

```


## 결과 확인

- **블로그**: https://altjs4510.github.io/ai_news_blog/posts/YYYYMMDD/
- **로그**: `logs/` 디렉토리에서 실행 로그 확인
- **보고서**: `reports/날짜/` 디렉토리에서 생성된 마크다운 파일 확인

## 문제 해결

- **API 한도 초과**: OpenAI 또는 Anthropic API 요청 제한에 도달한 경우, 로그를 확인하고 일정 시간 후 다시 시도
- **소스 변경**: 크롤링 소스 사이트의 구조가 바뀐 경우 해당 모듈 업데이트 필요

## 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다.
