"""Study brief generator — spotlight 자료 1개를 한국어 학습 브리프로 만든다.

큐레이션이 '무엇을 볼지' 정해주는 단계라면, study brief는
그 자료를 '오늘 바로 공부할 수 있게' 다듬는 단계다.
DCSAI / Team Agent 컨텍스트와 함께 Claude에 던져
정의·핵심 개념·구조·접목 방향·핵심 단락 번역까지 정리한다.
"""

import re
import aiohttp
from bs4 import BeautifulSoup
from utils.llm_client import make_client, resolve_model
from utils.logger import setup_logger

logger = setup_logger("study_brief")

UA = "Mozilla/5.0 (compatible; ai-news-agent/0.1)"

# 사용자 메인 프로젝트 컨텍스트 — 접목 섹션에서 구체 모듈명을 짚도록.
# main.py의 spotlight 컨텍스트와 같은 결.
USER_CONTEXT = """\
사용자(쿠키, F&F)는 두 메인 프로젝트를 진행 중.

A. DCSAI (`dcs-ai-project`) — Next.js 15(Turbopack) + NestJS + PostgreSQL/Snowflake/Neo4j.
   Anthropic SDK 직통합으로 agent loop · HITL · HTTP chunked streaming, MCP host server 자체 구현.
   Frontend FSD, Microsoft SSO + JWT. 부속군: dcs-ai-cli(Rust), dcs-ai-plugin(Claude Code), ff-claude-manager(Tauri 2).

B. Team Agent (`gtm-agent-poc`) — F&F Discovery 사업부 GTM AI 에이전트 플랫폼.
   Goal 2축: Build(업무·기술 하네스) + Operate(사람 전환·가치 회수).
   `discovery-core-agent`(브랜드) ↔ `platform-core-agent`(크로스 브랜드) 계층, dcsai KG MCP 직연결,
   브랜드별 yaml 주입(brand.yaml), Activity Log/Observer 피드백 루프(L1~L4),
   Quest 3계층(전체·파티·플레이어). Next.js 15 App Router · FSD · server-only.
"""


async def fetch_article_text(url: str, max_chars: int = 30000) -> str:
    """원문 페이지를 가져와 가독 가능한 본문 텍스트를 반환."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={"User-Agent": UA}, timeout=40) as resp:
                if resp.status != 200:
                    logger.error(f"Study fetch HTTP {resp.status}: {url}")
                    return ""
                html = await resp.text()
    except Exception as e:
        logger.error(f"Study fetch 실패: {e}", exc_info=True)
        return ""

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "iframe"]):
        tag.decompose()

    container = soup.select_one("article") or soup.select_one("main") or soup.body
    if container is None:
        return ""

    text = container.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars]


async def _generate_structured_brief(spotlight: dict, raw_text: str) -> str | None:
    """Opus로 정리(구조화) 부분만 생성 — 분석·접목·핵심 개념표 등."""
    title = (spotlight.get("title") or "").strip()
    url = (spotlight.get("url") or "").strip()
    why = (spotlight.get("why") or "").strip()
    application = (spotlight.get("application") or "").strip()

    prompt = f"""다음은 사용자 쿠키가 이번 주에 깊이 공부할 단 하나의 자료입니다.
**정리(structured brief)** 부분만 작성하세요. 원문 전체 번역은 다른 단계에서 별도로 진행됩니다.

## 큐레이션 메모
- 제목: {title}
- 원문 URL: {url}
- 왜 주목: {why}
- 접목 방향: {application}

## 사용자 컨텍스트
{USER_CONTEXT}

## 원문 본문 (HTML 정제 후, 최대 30K자)
{raw_text}

## 작성 규칙
1. 출력은 순수 마크다운. ``` 코드블록으로 전체를 감싸지 마세요.
2. 본문에 등장한 [텍스트](URL) 링크는 그대로 인용. 자료에 없는 URL은 절대 만들지 마세요.
3. 단락은 2~3문장. 핵심 단어·제품명·개념은 **굵게**.
4. 인사말·결론 멘트 금지. **번역 섹션 만들지 마세요(다른 단계에서 처리).**
5. 다음 섹션 순서를 그대로 사용:

### 1. 한 줄 정의
한 문장으로.

### 2. 왜 지금 중요한가
3~5개 bullet. AI 동향 흐름 안에서 어떤 결을 건드리는지.

### 3. 핵심 개념
표 형식. | 용어 | 정의 | 비고/관련 키워드 |

### 4. 작동 원리 / 구조
필요시 mermaid 다이어그램(```mermaid 코드 블록은 허용). 다이어그램이 어색하면 글로.

### 5. 실제 사용법 / 예시
원문에 코드·명령·API 호출이 있으면 그대로 인용. 없으면 가상 예시 만들지 말고 "원문에 코드 예시 없음"이라고 적기.

### 6. 사용자 프로젝트 접목
구체 모듈/단계명 짚어 2~4 bullet.
- DCSAI 측: agent loop · HITL 분기 · MCP host · Anthropic SDK · plugins · Tauri 매니저 중 어디에 어떻게.
- Team Agent 측: discovery-core-agent · platform-core-agent · brand.yaml · Activity Log/Observer · Quest 3계층 · FSD/server-only 중 어디에 어떻게.

### 7. 더 파고들 거리
원문에 등장한 관련 링크/논문/저장소 2~5개. 본문에 없으면 이 섹션 생략.
"""

    try:
        client = make_client()
        response = client.messages.create(
            model=resolve_model("claude-opus-4-7"),
            max_tokens=6000,
            system=(
                "너는 단 한 자료를 깊이 학습하도록 돕는 한국어 학습 큐레이터다. "
                "원문 텍스트에 등장한 정보만 사용하고 환각하지 않는다. "
                "사용자의 두 메인 프로젝트(DCSAI / Team Agent) 결에 맞춰 접목 방안을 구체적으로 제시한다. "
                "원문 전체 번역은 별도 단계에서 처리하므로 이 응답에 포함하지 않는다."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        if not response.content:
            return None
        text = response.content[0].text.strip()
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
        logger.info(f"구조화 브리프 생성 완료: {len(text)}자")
        return text
    except Exception as e:
        logger.error(f"Structured brief Claude 호출 실패: {e}", exc_info=True)
        return None


async def _generate_full_translation(spotlight: dict, raw_text: str) -> str | None:
    """Sonnet 4.6로 원문 전체를 한국어로 번역 — 정독용. 의역 최소화."""
    title = (spotlight.get("title") or "").strip()
    url = (spotlight.get("url") or "").strip()

    prompt = f"""다음 영문 자료(혹은 비한국어 자료)를 정독용으로 한국어 번역하세요.

## 자료 정보
- 제목: {title}
- 원문 URL: {url}

## 원문 본문 (HTML 정제 후)
{raw_text}

## 번역 규칙
1. **빠짐 없이 전체 번역** — 단락을 통째로 생략하지 마세요. 광고/푸터처럼 명백한 잡음만 빼세요.
2. 의역 최소화. 문장 구조와 톤을 가급적 보존하되 한국어로 자연스럽게.
3. 고유명사·제품명·전문용어는 영문 그대로 두거나 "한글 (영문)" 형태. 통일성 유지.
4. 코드 블록·표·수식·링크는 형식을 그대로 유지. 코드 안의 식별자는 번역하지 마세요.
5. 원문 마크다운 헤더 구조가 있으면 그 위계를 그대로 한국어로 옮기세요(`#` `##` `###`).
6. 출력은 순수 마크다운. 인사말/머리말/메타 코멘트 금지. 본문만.
7. 첫 줄 위에 다음 헤더 한 줄을 두세요: `### 원문 전체 번역 (정독용)`
"""

    try:
        client = make_client()
        response = client.messages.create(
            model=resolve_model("claude-sonnet-4-6"),
            max_tokens=12000,
            system=(
                "너는 정확한 한국어 기술 번역가다. 영문 기술 자료를 한 문단도 빠뜨리지 않고 "
                "한국어로 옮긴다. 의역하지 않고 원문 의미를 보존한다."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        if not response.content:
            return None
        text = response.content[0].text.strip()
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
        logger.info(f"전체 번역 생성 완료: {len(text)}자")
        return text
    except Exception as e:
        logger.error(f"Full translation Claude 호출 실패: {e}", exc_info=True)
        return None


async def generate_study_brief(spotlight: dict) -> str | None:
    """Spotlight 1건을 학습 가능한 페이지로 만든다.

    - 정리(structured brief)  ─ Opus 4.7로 구조화·접목·핵심 개념표
    - 원문 전체 번역(verbatim) ─ Sonnet 4.6로 정독용 한국어 번역

    두 결과를 한 페이지에 묶어 반환. 둘 중 하나만 성공해도 페이지는 만든다.
    """
    title = (spotlight.get("title") or "").strip()
    url = (spotlight.get("url") or "").strip()

    if not url:
        logger.info("Spotlight에 URL이 없어 학습 브리프를 건너뜁니다.")
        return None

    logger.info(f"학습 브리프 생성 시작: {title} ({url})")
    raw_text = await fetch_article_text(url)
    if not raw_text or len(raw_text) < 300:
        logger.warning(f"본문 텍스트 부족({len(raw_text)}자) — 학습 브리프 생략: {url}")
        return None

    # 두 단계 병렬 실행 — Opus(정리) + Sonnet(번역)
    import asyncio

    brief_task = asyncio.create_task(_generate_structured_brief(spotlight, raw_text))
    trans_task = asyncio.create_task(_generate_full_translation(spotlight, raw_text))
    brief_md, translation_md = await asyncio.gather(
        brief_task, trans_task, return_exceptions=True
    )

    brief_part = brief_md if isinstance(brief_md, str) and brief_md else None
    trans_part = translation_md if isinstance(translation_md, str) and translation_md else None

    if not brief_part and not trans_part:
        logger.warning("정리·번역 모두 실패 — 학습 브리프 생략")
        return None

    sections = []
    sections.append("## 📌 학습 정리")
    sections.append(brief_part if brief_part else "_(정리 생성 실패)_")
    sections.append("---")
    sections.append("## 📖 원문 전체 번역 (정독용)")
    sections.append(
        "> 의역 최소화한 전체 번역입니다. 큰 흐름은 위 정리에서 잡고, 정확한 워딩이 필요할 땐 이 섹션에서 정독하세요."
    )
    if trans_part:
        # `_generate_full_translation`이 자체 헤더 한 줄을 붙일 수도 있으니 중복 헤더 제거
        cleaned = re.sub(r"^#{1,6}\s*원문 전체 번역[^\n]*\n", "", trans_part).strip()
        sections.append(cleaned)
    else:
        sections.append("_(번역 생성에 실패했습니다. 원문 URL을 직접 참고하세요.)_")

    return "\n\n".join(sections)


if __name__ == "__main__":
    import asyncio
    import json

    async def test():
        spotlight = {
            "title": "An open-source spec for orchestration: Symphony",
            "url": "https://openai.com/index/open-source-codex-orchestration-symphony/",
            "why": "agent 협업 표준",
            "application": "Team Agent 멀티에이전트 계층",
        }
        out = await generate_study_brief(spotlight)
        print(out or "(none)")

    asyncio.run(test())
