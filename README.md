# AI 뉴스 수집 에이전트

AI 동향을 다양한 소스에서 자동 수집·번역·요약·인사이트화하고, 결과를 [ai_news_blog](https://github.com/altjs4510/ai_news_blog) (Quartz / GitHub Pages) 로 자동 발행하는 도구입니다.

게시 사이트: https://altjs4510.github.io/ai_news_blog

## 주요 기능

- **다중 소스 크롤링**: 공식 AI 블로그(Anthropic news + claude.com/blog · OpenAI · Google), Reddit, GitHub Trending, Hacker News, arxiv, Bluesky 등에서 자동 수집
- **번역 및 요약**: 영어 콘텐츠를 한글로 번역하고 핵심 내용 요약
- **2-tier 발행 모드**:
  - **Daily** (화~일 23:30 KST): 24h raw → spotlight 1개 + 학습 노트 1편을 `/knowledge/YYYYMMDD/`에 발행
  - **Weekly** (월요일 06:00 KST): 지난주 월~일 7일치 → 헤드라인+전체요약+spotlight+picks를 `/posts/YYYYMMDD/`에 발행
- **Weekly ↔ Daily knowledge 매칭**: weekly LLM 프롬프트에 같은 주 daily picks를 컨텍스트로 주고, `spotlight.related_daily`(매칭된 daily date_str 또는 null)로 응답받아 TODAY'S PICK "자세히 보기 →" CTA를 그 daily knowledge 페이지로 연결. 매칭이 없으면(`related_daily=null`) weekly 픽 자체의 학습 브리프를 생성해 `/posts/YYYYMMDD/study/`에 발행하고 CTA를 그쪽으로 연결 — 어느 주든 "자세히 보기" 진입로가 비지 않도록 보장
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

# --- LLM 백엔드 전환: Anthropic API 대신 AWS Bedrock 사용 (옵션) ---
# USE_BEDROCK=1                                # 1이면 AnthropicBedrock 클라이언트로 라우팅, 비우면 기본 Anthropic API
# AWS_REGION=ap-northeast-2                    # Bedrock 리전 (또는 us-east-1 등)
# AWS_BEARER_TOKEN_BEDROCK=ABSKxxxxx           # Bedrock API key (또는 표준 AWS 자격 증명 사용)
# BEDROCK_MODEL_OPUS_4_7=global.anthropic.claude-opus-4-7-v1:0       # 기본값 오버라이드 시
# BEDROCK_MODEL_SONNET_4_6=global.anthropic.claude-sonnet-4-6-v1:0
# BEDROCK_MODEL_HAIKU_4_5=global.anthropic.claude-haiku-4-5-v1:0

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

### 자동 스케줄링 (로컬 launchd)

> **2026-07 이관**: LLM 백엔드를 F&F PRCS **LiteLLM 프록시**로 바꿨는데 이 프록시가 사내망 전용(`10.91.x.x`)이라 GitHub 공용 러너에서 못 닿는다. 그래서 스케줄 발행을 **로컬 launchd** 로 옮겼고, `.github/workflows/*.yml` 의 `schedule`/`workflow_run` 자동 트리거는 모두 비활성(주석)했다 — `workflow_dispatch`(수동)만 남김. 상세·재실행법은 `CLAUDE.md` 참조.

발행은 이 맥의 launchd 3개(`~/Library/LaunchAgents/com.cookie.ainews.{daily,weekly,vocab}.plist`)가 담당하며, 모두 래퍼 **`run_pipeline.sh <mode>`** 를 호출한다:

- **daily** — 03:00 KST 화~일. `main.py --mode daily`(→ `/knowledge/YYYYMMDD/`) 후 `curate.py`→`link_related.py`→`quality_monitor.py` 순차 실행.
- **weekly** — 03:00 KST 월. `main.py --mode weekly` → `/posts/YYYYMMDD/`.
- **vocab** — 매월 1일 11:00 KST. `vocab_suggest.py`.

> **⚠️ 새벽 실행 = wake 필요.** launchd `StartCalendarInterval` 은 맥이 자고 있으면 그 시각에 안 돌고 *다음에 깰 때* 밀린 실행을 한다(= 아침 근무 시작 시각 → 구독 토큰 한도 경합). 그래서 03:00 실행 전에 맥을 깨우도록 **반복 wake** 를 걸어둔다:
> ```bash
> sudo pmset repeat wake MTWRFSU 02:58:00     # 매일 02:58 wake → 03:00 launchd 실행
> pmset -g sched                              # 확인
> ```
> 확실히 깨려면 밤새 **AC 전원 연결**(뚜껑 닫혀도 대개 OK) 권장. 실행 중 재수면은 래퍼의 `caffeinate -i` 가 막는다. 03:00 실행이면 ~08:00 에 5h 롤링 한도가 리셋돼 근무(09:00)와 안 겹친다.

launchd 관리:
```bash
launchctl list | grep ainews                                   # 상태
launchctl kickstart -k gui/$(id -u)/com.cookie.ainews.daily    # 즉시 1회 실행(테스트)
# plist 수정 후: launchctl bootout … && launchctl bootstrap gui/$(id -u) <plist>
```

발행 결과·블로그 push(SSH `github-personal`)는 로컬에서 이뤄진다. LLM 은 claude -p(구독) 우선이라 공용망에서도 되지만, LiteLLM 폴백은 F&F 망이 있어야 동작. 맥이 켜져 있어야 함. 로그: `logs/pipeline_{daily,weekly,vocab}.log`, `logs/launchd_*.{out,err}.log`.

**설정(.env, git-ignore)** — `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`(LiteLLM `sk-…`), 선택 `REDDIT_*`, `SLACK_WEBHOOK_URL`(실패 알림). `USE_BEDROCK` 은 넣지 않음. 백엔드 분기는 `utils/llm_client.py`, 상세는 `CLAUDE.md`.

### 로컬 수동 실행 (디버깅용)
```bash
uv run python main.py --mode daily     # .env 필요
uv run python main.py --mode weekly
./run_pipeline.sh daily                # 후속 체인(curate/link/quality)까지 한 번에
```

GitHub Actions 는 이제 수동 전용 — `gh workflow run <name> --repo altjs4510/ai_news_agent` (단 위 사내망 제약으로 LLM 단계는 실패). Actions secrets 는 레거시.

## 결과 확인

- **홈**: https://altjs4510.github.io/ai_news_blog/ — 좌측 main(weekly digest) + 우측 aside(this week / last week daily picks)
- **주간**: https://altjs4510.github.io/ai_news_blog/posts/YYYYMMDD/
- **일간 (학습 노트)**: https://altjs4510.github.io/ai_news_blog/knowledge/YYYYMMDD/
- **로그**: `logs/scheduled_run_{daily,weekly}_*.log`
- **보고서**: `reports/YYYYMMDD/` 에서 생성된 raw 데이터 + meta.json
- **상태**: `state/home_state.json` (weekly + daily_picks 누적)

## 수기 리서치 노트 (`publish_note.py`)

자동 수집과 별개로, **링크 하나를 직접 골라 리서치한 다이제스트**(논문·툴·아티클·릴리스 무엇이든)를
같은 knowledge 베이스에 누적한다. 자동 데일리 픽과 파일명이 겹치지 않도록 stem 을
`YYYYMMDD-<slug>` 로 쓴다(순수 `YYYYMMDD` stem 은 자동 픽 전용).

```bash
python publish_note.py --slug proprag \
  --title "제목" --source-url https://... \
  --category "모델 & 연구" --tags "a,b,c" --body-file /tmp/digest.md
```

- 이 스크립트는 **knowledge md 파일만 쓴다**(git 안 함). 발행은 **review-first** — 본문 확인 후
  OK 면 별도로 `git commit && push`.
- push 후 다음 **curate** 실행이 전체 사이드바에 이 항목을 자동 전파한다.
- `--category` 는 8종 vocabulary(`CATEGORY_VOCABULARY`) 중 하나 권장 — 그래야 curate 가 안 건드림.
- 사이드바 빌더는 `delivery/blog_publisher.py` 를 미러링(stdlib 자립). vocabulary 변경 시
  `main.CATEGORY_VOCABULARY` 와 `publish_note.py:VOCAB` 를 함께 맞춘다.

## 문제 해결

- **API 한도 초과**: OpenAI 또는 Anthropic API 요청 제한에 도달한 경우, 로그를 확인하고 일정 시간 후 다시 시도
- **소스 변경**: 크롤링 소스 사이트의 구조가 바뀐 경우 해당 모듈 업데이트 필요

## 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다.
