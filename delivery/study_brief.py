"""Study brief generator — spotlight 자료 1개를 한국어 학습 브리프로 만든다.

큐레이션이 '무엇을 볼지' 정해주는 단계라면, study brief는
그 자료를 '오늘 바로 공부할 수 있게' 다듬는 단계다.
한 페이지에 두 결을 함께 싣는다:
  - 입문 가이드(풀어쓴 정리) — 비전공자·기획자도 이해할 수 있게 비유와 일상어 위주.
  - 원문 전체 번역(정독용) — 정확한 워딩이 필요할 때 보는 용도.
"""

import re
import aiohttp
from bs4 import BeautifulSoup
from utils.llm_client import make_client, resolve_model
from utils.logger import setup_logger

logger = setup_logger("study_brief")

UA = "Mozilla/5.0 (compatible; ai-news-agent/0.1)"


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
    """Opus로 입문 가이드(풀어쓴 정리)를 생성한다.

    번역본이 '정확한 워딩' 담당이라면, 이 섹션은 정반대 결 —
    비전공자·기획자도 이해할 수 있도록 비유와 일상어로 풀어쓴다.
    """
    title = (spotlight.get("title") or "").strip()
    url = (spotlight.get("url") or "").strip()
    why = (spotlight.get("why") or "").strip()

    prompt = f"""다음 자료를 처음 보는 사람(비전공자·기획자 포함)도 이해할 수 있도록 한국어로 풀어쓴 **입문 가이드**를 작성하세요.
이 응답의 목적은 입문 가이드이지 원문 번역이 아닙니다. 원문 전체 번역은 다른 단계에서 별도로 진행됩니다.

## 큐레이션 메모 (글의 결을 잡는 참고용 — 본문에 그대로 인용하지 마세요)
- 제목: {title}
- 원문 URL: {url}
- 왜 주목: {why}

## 원문 본문 (HTML 정제 후, 최대 30K자)
{raw_text}

## 작성 규칙
1. 출력은 순수 마크다운. ``` 코드블록으로 전체를 감싸지 마세요.
2. 본문에 등장한 [텍스트](URL) 링크는 그대로 인용. 자료에 없는 URL은 절대 만들지 마세요.
3. **톤** — 친한 동료에게 차근차근 설명하는 결. "전문가가 강의하는" 결 금지. 단정·과시 톤 금지.
4. **용어** — 영문 기술 용어가 나오면 반드시 한국어로 먼저 풀어 설명한 뒤 괄호로 영문을 병기. 첫 등장 한 번만. 예: "지식 그래프(knowledge graph)". 풀어쓰기 어려운 고유명사·제품명은 그대로 두되 한 줄 설명을 붙이세요.
5. **밀도** — 한 단락은 2~4문장. dense한 표·항목 나열 금지(섹션 5의 용어 풀이만 예외). 풀어쓴 문장을 우선하세요.
6. 인사말·결론 멘트·"오늘은 ~을 살펴보겠습니다" 같은 머리말 금지. 사용자 개인 프로젝트나 사내 컨텍스트는 본문에 언급하지 마세요.
7. 다음 6개 섹션 순서를 그대로 사용:

### 1. 한 줄로 말하면
한두 문장. 비유 또는 일상어로. 영문 용어는 가능한 한 배제.

### 2. 왜 이게 만들어졌어요?
어떤 문제·불편이 있어서 이 도구/기법/개념이 등장했는지 배경을 한 단락(3~5문장)으로. "원래는 이렇게 했는데, 이런 문제가 있어서…" 식으로 풀어쓰세요.

### 3. 비유로 풀면
"이건 마치 ○○ 같은 거예요" 형식의 비유 1~2개. 동떨어진 비유 말고, 실제 작동 방식의 핵심을 짚는 비유로. 비유 다음에 "그래서 결국…" 한 줄로 비유와 실제를 연결.

### 4. 어떻게 작동하는지 (그림으로)
mermaid 다이어그램(```mermaid 코드 블록 허용)으로 흐름을 그리되, **노드 레이블은 한국어 풀어쓰기**로. 영문 식별자만 늘어놓지 마세요. 다이어그램 아래에 흐름을 2~3문장으로 풀이. 다이어그램이 어색한 주제면 글로 흐름을 설명해도 됩니다.

### 5. 처음 보는 용어 풀이
원문의 핵심 용어 중 입문자가 막힐 만한 것 5~7개. 다음 형식:
- **한국어로 풀어쓴 이름 (영문)** — 한두 문장 설명. 무엇을 하는지·왜 필요한지 위주. 더 어려운 용어로 설명하지 마세요.

### 6. 한 발 더 들어가고 싶다면
원문에 등장한 관련 링크/논문/저장소 2~5개. 각 항목 옆에 "이걸 보면 ○○을 알 수 있어요" 식으로 한 줄 안내를 붙이세요. 원문에 그런 링크가 없으면 이 섹션 자체를 생략.
"""

    try:
        client = make_client()
        response = client.messages.create(
            model=resolve_model("claude-opus-4-7"),
            max_tokens=6000,
            system=(
                "너는 비전공자·기획자도 한 번에 이해할 수 있도록 풀어 쓰는 한국어 입문 가이드 작성자다. "
                "원문 텍스트에 등장한 정보만 사용하고 환각하지 않는다. "
                "영문 기술 용어는 반드시 한국어로 먼저 풀어 설명한 뒤 (영문)을 병기한다. "
                "단정·과시 톤을 피하고, 친한 동료에게 차근차근 설명하는 결을 유지한다. "
                "원문 전체 번역은 별도 단계에서 처리하므로 이 응답에 포함하지 않는다. "
                "사용자 개인 프로젝트나 사내 컨텍스트는 본문에 언급하지 않는다."
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
