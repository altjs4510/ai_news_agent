# ai_news_agent — 프로젝트 컨텍스트

AI 동향 수집·요약·발행 파이프라인. 상세는 `README.md` 참조. 이 파일은 **재실행/운영 시 반드시 알아야 할 것**만.

## ⚠️ GitHub 계정 정체성 (매번 걸리는 지점)

이 파이프라인 레포(`altjs4510/ai_news_agent`)와 블로그(`altjs4510/ai_news_blog`)는 **altjs4510**(쿠키 개인 GitHub) 소유. 회사 계정 topseon23 이 아님.

**중요: 이 머신 gh keyring 에 두 계정이 다 로그인돼 있다** — topseon23(active 기본) + altjs4510. altjs4510 은 이 레포 admin 이라 워크플로우 트리거·secret 관리 다 됨. 작업 전 **계정 전환만 하면 됨**:

```bash
gh auth switch --user altjs4510        # 작업 시작 시 1회
gh auth switch --user topseon23        # 끝나면 원복(선택)
```

topseon23 active 상태로는 이 레포에 `gh workflow run` → 403("Must have admin rights"), `gh secret list` → 403. **막히면 401/403 을 곧이곧대로 "권한 없음"으로 보고하지 말고 계정부터 전환.**

- git push: origin 이 `git@github-personal:altjs4510/…` (SSH, `~/.ssh/config` 의 `github-personal` = `id_ed25519_personal`)라 **push 는 계정 전환 없이 SSH 로 됨.** 블로그(`../ai_news_blog`)도 동일. (memory `blog-repo-push-ssh`.)
- 워크플로우 트리거·secret 은 **git 이 아니라 GitHub REST API** → SSH 가 아니라 gh 토큰을 씀 → 위 `gh auth switch` 필요.

## 실행 모드

- **Daily** (화~일 06:00 KST): `--mode daily` → `/knowledge/YYYYMMDD/`
- **Weekly** (월 06:00 KST): `--mode weekly` → `/posts/YYYYMMDD/`
- 스케줄: `.github/workflows/daily.yml`(cron `0 21 * * 1-6` UTC) · `weekly.yml`(일 21:00 UTC)

## LLM 백엔드 — F&F LiteLLM 프록시 (현행)

`make_client()`(`utils/llm_client.py`)는 인자 없는 `Anthropic()` 를 쓰므로 SDK 가 env 를 자동 인식:
- `ANTHROPIC_BASE_URL=https://litellm.int-prcs-dev.fnf.co.kr` — F&F PRCS LiteLLM 프록시 (Anthropic 호환)
- `ANTHROPIC_AUTH_TOKEN=sk-nW-…` — cloud-portal 발급 가상 키 (`general-models` 그룹). Bearer 로 전송됨.
- `USE_BEDROCK` 은 **넣지 않음** (넣으면 `AnthropicBedrock` 경로로 빠짐 — 현재 미사용).

> ⚠️ **이 프록시는 사내망 전용** — `litellm.int-prcs-dev.fnf.co.kr` 이 `10.91.x.x`(사설 IP)로 풀림. F&F 망의 이 맥에선 닿지만 **GitHub Actions 공용 러너에선 안 닿음.** 따라서 daily/weekly 는 현재 **로컬 실행만** 가능. (`.github/workflows/*.yml` 은 아직 `ANTHROPIC_API_KEY`/`USE_BEDROCK`/Bedrock secrets 기준 — Anthropic 크레딧 소진 상태라 그대로는 실패. Actions 자동화하려면 self-hosted 러너 or 공용 도달 가능한 LLM 필요 — 미해결.)

**사용 모델** (2026-07 업그레이드, 프록시 `/v1/models` 와 일치해야 함): `claude-opus-4-8` · `claude-sonnet-5` · `claude-haiku-4-5`. 프록시 모델 목록 변경 시 코드의 `resolve_model("…")` 인자도 맞춰야 함 (non-Bedrock 경로는 canonical 이름을 그대로 프록시에 넘김).

**현행 백엔드 — Claude Code 구독(`claude -p`) 우선 + LiteLLM 폴백** (`.env` 에 `USE_CLAUDE_CLI=1`):
- **비용 근거**: 구독은 정액(한계비용 ~0), LiteLLM 은 회사 쿼터 소모 → 구독 먼저 쓰고 실패/한도소진 시에만 프록시로 흘림.
- `llm_client.py` 의 `_ClaudeCLIClient`(sync)/`_AsyncClaudeCLIClient`(async) 가 `messages.create` 를 흉내내 call-site 무변경. per-call try(claude -p)→except(프록시) 폴백.
- **공용망 어디서든 동작**(구독) → WFH/VPN 미접속에도 primary 성공. 폴백만 사내망 필요.
- 트레이드오프: claude -p 는 콜당 ~35k 베이스라인 토큰 + 프로세스 spin-up 으로 느리고 구독 5h 롤링 한도를 먹음(6시 배치라 무방).
- ⚠️ **claude -p 서브프로세스엔 `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_API_KEY` 를 제거**해서 띄운다(`_cli_env`). 안 그러면 claude 가 그 env(프록시)를 구독보다 우선해 구독 인증이 무시됨.
- 두 경로 응답 모두 단일 ```` ``` ```` 펜스면 언랩(`_strip_outer_fence`; 내부 펜스 있으면 미변경) → `json.loads` 안전.
- 백엔드 우선순위: `USE_CLAUDE_CLI` > `USE_BEDROCK` > 기본(프록시 직결). `USE_CLAUDE_CLI` 끄면 LiteLLM 직결로 되돌아감.

creds 는 로컬 `.env`(git-ignore) 에 둔다. Reddit 등 선택 소스 키가 없으면 해당 소스만 스킵(main.py 가드).

## X(Twitter) 소스 — 개인 계정 로그인 세션 (2026-08 추가)

`sources/x_timeline.py` 가 개인 X 계정의 **Following 홈 타임라인**을 Playwright 로 읽는다. 공식 API가 아니다 — X 이용약관상 자동 스크래핑은 금지 행위라 **계정 정지 리스크를 감수하는 경로**로 의도적으로 선택함(공식 API Basic 플랜 $200/월~ 이 비용상 안 맞아서 대안으로 채택). 리스크를 낮추려고 하루 1회(파이프라인 배치) 수준의 저빈도 호출로만 쓴다 — 그 이상 자주 돌리거나 탐지 회피 기법(핑거프린트 위장 등)을 추가하지 않는다.

- **1회 수동 로그인 필요**: `uv run python sources/x_login.py` — 브라우저 창이 뜨면 본인 X 계정으로 로그인 후 터미널에서 Enter. 세션이 `state/x_auth_state.json` 에 저장됨(git-ignore, 쿠키 포함 — 절대 커밋 금지).
- 세션 없거나 만료되면 `main.py` 가 경고 로그만 남기고 X 소스를 조용히 스킵(다른 소스엔 영향 없음). 만료 시 `x_login.py` 재실행.
- `uv run playwright install chromium` 브라우저 바이너리 설치 필요(최초 1회, `uv sync` 후).
- X 게시물은 Bluesky 게시물과 같은 버킷(`bluesky_posts` 변수, `social_raw.md` 성격의 `bluesky_raw.md` 파일)에 합쳐져 프롬프트에 "소셜 버즈(Bluesky + X)"로 들어간다.
- X 웹앱 DOM은 예고 없이 바뀐다 — 파싱 실패 시 해당 트윗만 스킵하고 전체 실행은 죽지 않는다(`sources/x_timeline.py` 의 `_parse_tweet_article`).
- `XTimelineCollector`(Following 홈, `config.X_HANDLES` 화이트리스트로 팔로우 중인 비-AI 계정 걸러냄)와 `XSearchCollector`(키워드 검색 — 팔로우 무관 바이럴 탐지, `config.X_SEARCH_KEYWORDS`) 둘 다 같은 세션을 쓴다. 검색은 X 연산자(`since:`/`until:`/`min_faves:`)를 쿼리에 직접 박아 서버 사이드에서 날짜·인게이지먼트 범위를 좁힘 — 정렬은 기본(Top/인게이지먼트 기준), 시간순(Latest)이 아님.
- 개인 계정 Following 피드는 팔로우 수가 적으면 X가 "Following" 탭 자체를 숨긴다 — 화이트리스트가 실질적 필터이니 탭 클릭 성공 여부에 의존하지 않음.
- `sources/x_trends.py` — 그날 수집된 X 게시물(timeline+search)에서 LLM(haiku, `extract_keywords`)이 화제 키워드(term+count)만 추출하고, 각 키워드의 예시 링크는 **LLM이 아니라 코드가 원본 posts 리스트에서 문자열 매칭으로 직접**(`_find_examples`) 찾는다(URL 할루시네이션 방지). `state/x_keyword_trends.json`에 일별 카운트를 누적해 최근 7일 평균 대비 추세(🆕신규/🔺상승)를 `update_trends`가 계산하고, 원본 링크가 실제로 붙은 키워드만 남긴다(링크 없으면 통째로 버림).
- **기사 본문엔 넣지 않는다** — 처음엔 daily/weekly 본문에 직접 섹션을 삽입했지만, daily는 spotlight 1개짜리 글이라 그날의 spotlight 주제와 무관한 키워드가 끼어드는 게 어색해서 **별도 데이터 + 홈 화면 작은 위젯**으로 설계 변경(2026-08). `main.py`가 계산한 `x_trends_items`(최대 6개, term/url/title/is_new/count)를 `publish_daily`/`publish_weekly` 양쪽에 전달 → `home_state.json`의 `state["x_trends"]`에 저장(매 실행마다 최신 스냅샷으로 덮어씀, daily/weekly 어느 쪽이 마지막이든 반영) → 홈 우측 aside 맨 위에 "🔥 X 화제 키워드" 미니 리스트로 렌더(`BlogPublisher._build_x_trends_section_html`). 항목이 없으면 위젯 자체가 사라짐. `sources/x_trends.py`의 `render_markdown`/`analyze()`는 로컬 리포트 파일(`reports/{date}/x_trends.md`) 기록용으로만 남아 있고 프롬프트에는 안 들어간다.
- LLM 호출(`extract_keywords`)은 `make_async_client()`를 그대로 써서 별도 설정 없이 `USE_CLAUDE_CLI` 백엔드 우선순위(claude -p 구독 → LiteLLM 폴백)를 물려받는다 — 로컬 배치 특성상 구독 정액 비용만 든다.

## 재실행 (daily/weekly 다시 돌리기) — 로컬

```bash
uv run python main.py --mode daily     # .env 에 ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN 필요
uv run python main.py --mode weekly
```
→ 크롤→요약(LiteLLM)→`../ai_news_blog` 에 commit + **SSH push**(github-personal). Pages 빌드는 blog 레포 Actions 가 함.

> gh 계정 참고: 워크플로우 트리거/secret 관리가 필요하면 `gh auth switch --user altjs4510` (위 §GitHub 계정). 단 위 이유로 Actions 실행 자체는 현재 로컬로 대체 중.
