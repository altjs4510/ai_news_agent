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

**대체 백엔드 — Claude Code 구독 (`claude -p`)**: `.env` 에 `USE_CLAUDE_CLI=1` 넣으면 LLM 을 LiteLLM 대신 구독으로 라우팅(`llm_client.py` 의 `_ClaudeCLIClient` 어댑터가 `messages.create` 흉내). **공용망 어디서든 동작** → WFH/VPN 미접속 대비책. 단 콜당 ~35k 베이스라인 토큰 + 프로세스 spin-up 으로 LiteLLM 보다 느리고 구독 5시간 롤링 한도를 더 먹음. 백엔드 우선순위: `USE_CLAUDE_CLI` > `USE_BEDROCK` > 기본(프록시). 어댑터는 응답이 단일 ```` ``` ```` 펜스로 감싸이면 언랩(내부 펜스 있으면 미변경)해 `json.loads` 안전.

creds 는 로컬 `.env`(git-ignore) 에 둔다. Reddit 등 선택 소스 키가 없으면 해당 소스만 스킵(main.py 가드).

## 재실행 (daily/weekly 다시 돌리기) — 로컬

```bash
uv run python main.py --mode daily     # .env 에 ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN 필요
uv run python main.py --mode weekly
```
→ 크롤→요약(LiteLLM)→`../ai_news_blog` 에 commit + **SSH push**(github-personal). Pages 빌드는 blog 레포 Actions 가 함.

> gh 계정 참고: 워크플로우 트리거/secret 관리가 필요하면 `gh auth switch --user altjs4510` (위 §GitHub 계정). 단 위 이유로 Actions 실행 자체는 현재 로컬로 대체 중.
