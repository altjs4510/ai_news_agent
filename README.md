# AI 뉴스 수집 에이전트

AI 동향을 다양한 소스에서 자동 수집·번역·요약·인사이트화하고, 결과를 [ai_news_blog](https://github.com/altjs4510/ai_news_blog) (Quartz / GitHub Pages) 로 자동 발행하는 도구입니다.

게시 사이트: https://altjs4510.github.io/ai_news_blog

## 주요 기능

- **다중 소스 크롤링**: 공식 AI 블로그(Anthropic·OpenAI·Google), Reddit, GitHub Trending, Hacker News, arxiv, Bluesky 등에서 자동 수집
- **번역 및 요약**: 영어 콘텐츠를 한글로 번역하고 핵심 내용 요약
- **2-tier 발행 모드**:
  - **Daily** (화~일 23:30 KST): 24h raw → spotlight 1개 + 학습 노트 1편을 `/knowledge/YYYYMMDD/`에 발행
  - **Weekly** (월요일 06:00 KST): 지난주 월~일 7일치 → 헤드라인+전체요약+spotlight+picks를 `/posts/YYYYMMDD/`에 발행
- **자동 URL 검증**: LLM이 생성한 spotlight/additional_picks URL을 HEAD 요청으로 사전 검증 (404 제거)
- **자동 키워드 생성**: 수집된 콘텐츠에서 중요 키워드 추출
- **블로그 자동 발행**: 결과 마크다운을 별도 ai_news_blog 레포에 commit·push → GitHub Actions가 Hugo로 빌드해 Pages에 배포
- **Notion / 이메일 알림**: 옵션으로 활성화 가능 (`main.py`의 `ENABLE_NOTION`, `ENABLE_EMAIL`)
- **스케줄링**: launchd plist 2개 (daily / weekly) 분리 실행

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

### 자동 스케줄링 (GitHub Actions)

발행은 GitHub Actions의 두 워크플로가 담당:

- **`.github/workflows/daily.yml`** — 매일 21:00 UTC (= 06:00 KST), 단 UTC 일요일 제외 (월요일은 weekly 담당). `--mode daily` 실행 → `/knowledge/YYYYMMDD/`에 그날의 픽 1개 발행.
- **`.github/workflows/weekly.yml`** — 매주 일요일 21:00 UTC (= 월요일 06:00 KST). `--mode weekly` 실행 → `/posts/YYYYMMDD/`에 지난 7일 종합 발행.

수동 트리거: GitHub Actions 탭에서 workflow_dispatch 또는 `gh workflow run`.

필요한 secrets (Repo Settings → Secrets and variables → Actions):

- `ANTHROPIC_API_KEY`
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`
- `BLOG_PUSH_TOKEN` — ai_news_blog 레포에 push 권한이 있는 PAT
- `SLACK_WEBHOOK_URL` (옵션, 실패 알림)
- `ANTHROPIC_ADMIN_KEY` (옵션, sk-ant-admin01-… — 설정하면 Slack 실패 알림에 오늘/이번달 Anthropic 사용 비용을 함께 표시)

### 로컬 수동 실행 (디버깅용)
```bash
# .env 필요 (위 secrets와 동일 키)
uv run main.py --mode daily
uv run main.py --mode weekly
```

## 결과 확인

- **홈**: https://altjs4510.github.io/ai_news_blog/ — 좌측 main(weekly digest) + 우측 aside(this week / last week daily picks)
- **주간**: https://altjs4510.github.io/ai_news_blog/posts/YYYYMMDD/
- **일간 (학습 노트)**: https://altjs4510.github.io/ai_news_blog/knowledge/YYYYMMDD/
- **로그**: `logs/scheduled_run_{daily,weekly}_*.log`
- **보고서**: `reports/YYYYMMDD/` 에서 생성된 raw 데이터 + meta.json
- **상태**: `state/home_state.json` (weekly + daily_picks 누적)

## 문제 해결

- **API 한도 초과**: OpenAI 또는 Anthropic API 요청 제한에 도달한 경우, 로그를 확인하고 일정 시간 후 다시 시도
- **소스 변경**: 크롤링 소스 사이트의 구조가 바뀐 경우 해당 모듈 업데이트 필요

## 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다.
