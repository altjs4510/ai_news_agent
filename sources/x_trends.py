"""X 키워드 트렌드 분석 — 수집된 X 게시물에서 화제 키워드를 LLM으로 추출하고
일별 카운트를 누적해 "요즘 뜨는 키워드"를 뽑아낸다.

LLM 호출은 utils.llm_client.make_async_client() 그대로 사용 — 프로젝트 기본 백엔드
우선순위(claude -p 구독 → LiteLLM 폴백)를 별도 설정 없이 그대로 물려받는다.

URL은 LLM에게 만들게 하지 않는다 — LLM은 term/count만 추출하고, 각 키워드의
예시 링크는 원본 posts 리스트에서 문자열 매칭으로 직접 뽑는다(할루시네이션 방지,
"자료에 없는 URL은 절대 만들지 마세요" 규칙과 동일한 원칙).
"""

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import json
import re
from datetime import datetime, timedelta

from utils.llm_client import make_async_client, resolve_model
from utils.logger import setup_logger

logger = setup_logger('x_trends')

MAX_POSTS_FOR_EXTRACTION = 60
HISTORY_RETENTION_DAYS = 30
BASELINE_WINDOW_DAYS = 7
MAX_EXAMPLES_PER_KEYWORD = 2


async def extract_keywords(posts: list[dict], max_keywords: int = 20) -> list[dict]:
    """오늘 수집된 X 게시물에서 급상승 키워드를 LLM으로 추출.

    제품/모델명뿐 아니라 새로 뜨는 개념·기법 용어("context engineering",
    "그래프 엔지니어링" 류)도 대상 — 다만 거대 랩/회사 이름(Anthropic, OpenAI, Meta 등)
    자체는 거의 매일 등장해서 "화제"라는 신호가 없으니 제외한다.
    """
    if not posts:
        return []

    lines = []
    for p in posts[:MAX_POSTS_FOR_EXTRACTION]:
        content = (p.get("content") or "").replace("\n", " ")[:200]
        if content:
            lines.append(f"- {content}")
    if not lines:
        return []
    posts_block = "\n".join(lines)

    prompt = f"""다음은 오늘 X(트위터)에서 수집된 AI 관련 게시물입니다.
지금 급부상하는 화제 키워드를 최대 {max_keywords}개 추출하고,
각 키워드가 몇 개 게시물에서 언급됐는지 세어주세요.

**포함 대상 (둘 다):**
1. 구체적인 제품명·모델명·프로젝트명·이벤트명 (예: "Prime Agent", "Kimi K3", "ARC-AGI-3")
2. 새로 뜨거나 화제가 되는 개념·기법·방법론 용어 (예: "context engineering",
   "그래프 엔지니어링", "agentic RL", "vibe coding" 처럼 아직 굳어지지 않은 신조어/용어)

**제외 규칙 (중요):**
- "AI", "LLM"처럼 이미 널리 쓰이는 너무 일반적인 단어는 제외.
- **거대 AI 랩/회사 이름 자체는 키워드로 뽑지 마세요** — Anthropic, OpenAI, Google,
  Google DeepMind, Meta, Microsoft, NVIDIA, Amazon, Apple, Alibaba, ByteDance 등은
  거의 매일 언급되는 배경 잡음이라 "화제"가 아닙니다. 회사 이름이 언급됐어도
  그 회사가 **오늘 낸 구체적인 제품·모델·논문·이벤트명**만 뽑으세요.
  예: "Meta released Muse Spark 1.2" → "Meta"가 아니라 "Muse Spark 1.2"를 뽑을 것.
  예: "OpenAI's GPT-5.6 scored..." → "OpenAI"가 아니라 "GPT-5.6"을 뽑을 것.
- 표기가 다른 동의어(예: "Claude Code"와 "claude code")는 하나로 합치세요.

## 게시물
{posts_block}

## 응답 (JSON만, 다른 텍스트 없이)
{{"keywords": [{{"term": "정확한 표기", "count": N}}, ...]}}
회사명 제외 후 남는 구체적 화제가 없으면 {{"keywords": []}}
"""
    try:
        client = make_async_client()
        response = await client.messages.create(
            model=resolve_model("claude-haiku-4-5"),
            max_tokens=1000,
            system="AI 업계 동향 분석가. 게시물에서 화제가 되는 고유명사 키워드만 정확히 추출한다.",
            messages=[{"role": "user", "content": prompt}],
        )
        if not response.content:
            return []
        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return []
        data = json.loads(m.group(0))
        keywords = data.get("keywords") or []
        return [
            {"term": str(k["term"]).strip(), "count": int(k["count"])}
            for k in keywords if k.get("term")
        ]
    except Exception as e:
        logger.error(f"키워드 추출 실패: {e}", exc_info=True)
        return []


def _find_examples(term: str, posts: list[dict], limit: int = MAX_EXAMPLES_PER_KEYWORD) -> list[dict]:
    """term이 실제로 등장하는 원본 게시물을 문자열 매칭으로 찾는다 (URL 할루시네이션 방지)."""
    term_lower = term.lower()
    examples = []
    seen_urls = set()
    for p in posts:
        content = p.get("content") or ""
        url = p.get("url") or ""
        if not url or url in seen_urls:
            continue
        if term_lower in content.lower():
            title = (p.get("title") or content[:80]).replace("\n", " ").strip()
            examples.append({"title": title, "url": url})
            seen_urls.add(url)
        if len(examples) >= limit:
            break
    return examples


def _load_state(state_path: str) -> dict:
    if not os.path.exists(state_path):
        return {}
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state_path: str, state: dict):
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def update_trends(keywords: list[dict], posts: list[dict], state_path: str, date_str: str) -> dict:
    """오늘 추출 결과를 state에 반영하고, 최근 이력 대비 추세 + 예시 링크를 계산해 반환."""
    state = _load_state(state_path)
    state[date_str] = {k["term"]: k["count"] for k in keywords}

    cutoff_date = (datetime.strptime(date_str, "%Y%m%d") - timedelta(days=HISTORY_RETENTION_DAYS)).strftime("%Y%m%d")
    state = {d: v for d, v in state.items() if d >= cutoff_date}
    _save_state(state_path, state)

    prior_dates = sorted(d for d in state if d < date_str)[-BASELINE_WINDOW_DAYS:]
    trends = []
    for term, count in state[date_str].items():
        prior_counts = [state[d].get(term, 0) for d in prior_dates]
        baseline = sum(prior_counts) / len(prior_dates) if prior_dates else 0
        is_new = baseline == 0
        delta = count - baseline
        trends.append({
            "term": term,
            "count": count,
            "baseline": round(baseline, 1),
            "delta": round(delta, 1),
            "is_new": is_new,
            "examples": _find_examples(term, posts),
        })

    trends.sort(key=lambda t: (not t["is_new"], -t["delta"]))
    return {"date": date_str, "trends": trends}


def render_markdown(result: dict) -> str:
    trends = result.get("trends") or []
    # 원본 링크를 못 찾은 키워드는 본문에서 인용할 근거가 없으니 제외한다
    # ("자료에 없는 URL은 절대 만들지 마세요" 규칙을 지키려면 애초에 링크 있는 것만 넘겨야 함).
    # 단발 언급(1건)은 "화제"로 보기 어려우니 같이 거른다.
    trends_with_links = [t for t in trends if t["examples"] and t["count"] >= 2]

    if not trends_with_links:
        return ""

    # H1은 페이지 hero가 이미 쓰므로(daily knowledge / weekly combined_insights 공통 관례)
    # 여기 삽입될 걸 감안해 H2부터 시작.
    lines = [
        "## X 화제 키워드",
        "",
    ]
    for t in trends_with_links:
        if t["is_new"]:
            trend_label = "🆕 신규"
        elif t["delta"] > 0:
            trend_label = f"🔺 +{t['delta']} (최근 7일 평균 {t['baseline']}건 → 오늘 {t['count']}건)"
        else:
            trend_label = f"▫️ {t['delta']} (최근 7일 평균 {t['baseline']}건 → 오늘 {t['count']}건)"
        lines.append(f"### {t['term']} ({trend_label}, 오늘 {t['count']}개 게시물)")
        for ex in t["examples"]:
            lines.append(f"- [{ex['title']}]({ex['url']})")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


async def analyze(posts: list[dict], state_path: str, date_str: str) -> str:
    keywords = await extract_keywords(posts)
    result = update_trends(keywords, posts, state_path, date_str)
    return render_markdown(result)


if __name__ == "__main__":
    import asyncio

    async def test():
        sample = [
            {"content": "Meta launches Muse Code, a new coding agent", "title": "Meta launches Muse Code", "url": "https://x.com/a/status/1"},
            {"content": "Muse Code pricing undercuts Claude Code", "title": "Muse Code pricing", "url": "https://x.com/b/status/2"},
            {"content": "MCP protocol adoption is growing fast", "title": "MCP protocol adoption", "url": "https://x.com/c/status/3"},
        ]
        md = await analyze(sample, "state/x_keyword_trends.json", "20260806")
        print(md)

    asyncio.run(test())
