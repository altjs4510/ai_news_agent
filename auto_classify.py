"""auto_classify.py — 누적된 raw 수집물(reports/{date}/*_raw.md)을 LLM으로 일괄
1차 자동분류한다: skip/queue/one-off/reference 판정 + (one-off·reference인 경우) 카테고리
8종까지 한 번에. 결과는 state/triage/{date}.jsonl 에 사람이 트리아지한 것과 동일한 스키마로
기록되며 "by": "llm-auto" 로 출처를 구분한다.

배경(2026-08-24 피드백): "이미 쌓여왔던 애들을 알아서 최초 자동분류 해달라고 하는건데
왜 자꾸 코드[TUI]만 수정하냐" — TUI는 사람이 처음부터 하나씩 판정하는 도구가 아니라,
이 스크립트가 미리 채워둔 결과를 훑어보고 틀린 것만 고치는 **검토 도구**여야 했다.

curate.py 는 이미 발행된 지식노트 1건씩 LLM 1회 호출로 카테고리를 매기는데(항목 수가
하루 1~3건이라 충분), 여기는 한 번에 수백 건이라 그 방식은 claude -p 서브프로세스 기동
비용(콜당 ~35k 베이스라인 토큰) 때문에 너무 느리다 — 대신 BATCH_SIZE개씩 묶어 한 번의
LLM 호출로 여러 항목을 동시에 분류한다.

사용법:
    uv run python auto_classify.py 20260824             # 하루만
    uv run python auto_classify.py 20260819 20260824    # 범위(양끝 포함)

이미 state/triage/*.jsonl 에 판정(사람이든 LLM이든)이 있는 항목은 건너뛴다 — 재실행해도
중복 분류 안 됨.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# config.py 가 import 시점에 load_dotenv() 를 해주는데, 이 스크립트는 main.py/config.py 를
# 안 거치므로(무거운 소스 모듈 회피 목적) 직접 로드해야 한다 — 안 그러면 make_client() 가
# ANTHROPIC_AUTH_TOKEN 등을 못 찾아 인증 에러로 즉시 죽는다(2026-08-24 최초 실행에서 발견).
load_dotenv()

from triage_tui import CATEGORY_VOCABULARY, REPORTS, STATE_DIR, Item, load_items  # noqa: E402
from utils.llm_client import make_client, resolve_model  # noqa: E402

BATCH_SIZE = 20
VALID_DECISIONS = ("skip", "queue", "one-off", "reference")


def date_range(start: str, end: str) -> list[str]:
    d0, d1 = datetime.strptime(start, "%Y%m%d"), datetime.strptime(end, "%Y%m%d")
    out, d = [], d0
    while d <= d1:
        out.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return out


def load_all_decided_keys() -> set[str]:
    seen = set()
    if not STATE_DIR.is_dir():
        return seen
    for f in STATE_DIR.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            seen.add(rec.get("key", ""))
    return seen


def build_prompt(batch: list[Item]) -> str:
    vocab_block = "\n".join(f"- {c}" for c in CATEGORY_VOCABULARY)
    lines = []
    for idx, item in enumerate(batch):
        snippet = (item.content or "").replace("\n", " ").strip()[:200]
        lines.append(f"[{idx}] 출처={item.source} | 제목={item.title[:100]} | 요약={snippet or '(없음)'}")
    items_block = "\n".join(lines)
    return f"""다음은 AI 뉴스 수집 파이프라인이 그날 모은 원본 후보들이다. 각 항목마다
decision 과 category 를 정하라.

## decision (정확히 1개, 아래 4가지 중에서만)
- "skip": 흥미롭지 않음 / AI·기술과 무관 / 저품질·광고성 / 중복적인 뉴스 — 대다수가 여기 해당되는 게 정상
- "queue": 흥미로울 수도 있으나 애매해서 사람이 나중에 직접 봐야 함
- "one-off": 오늘의 AI 뉴스 블로그에 실을 만한, 시의성 있고 흥미로운 뉴스
- "reference": 두고두고 참고할 근본적인 논문·기법·개념 — 아주 드물게만 부여(하루에 있어야 0~1건)

## category (decision 이 one-off 또는 reference 일 때만 지정, 그 외엔 빈 문자열 "")
{vocab_block}

## 항목들
{items_block}

## 응답 형식 (JSON 배열만, 다른 텍스트·설명 없이)
[{{"index": 0, "decision": "skip", "category": ""}}, {{"index": 1, "decision": "one-off", "category": "코딩 에이전트"}}, ...]
항목 수만큼 전부 포함할 것.
"""


def classify_batch(client, batch: list[Item]) -> dict[int, tuple[str, str]]:
    response = client.messages.create(
        model=resolve_model("claude-sonnet-5"),
        max_tokens=2000,
        system=(
            "너는 AI 뉴스 큐레이터다. 주어진 항목들을 지정된 decision/category 로 정확히 "
            "분류해 JSON 배열만 응답한다. 설명이나 다른 텍스트를 덧붙이지 않는다."
        ),
        messages=[{"role": "user", "content": build_prompt(batch)}],
    )
    text = response.content[0].text.strip() if response.content else ""
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    result: dict[int, tuple[str, str]] = {}
    for row in data:
        try:
            idx = int(row["index"])
        except (KeyError, TypeError, ValueError):
            continue
        decision = row.get("decision", "")
        if decision not in VALID_DECISIONS:
            continue
        category = row.get("category") or ""
        if category and category not in CATEGORY_VOCABULARY:
            category = ""
        result[idx] = (decision, category)
    return result


def main() -> None:
    if len(sys.argv) == 3:
        dates = date_range(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        dates = [sys.argv[1]]
    else:
        sys.exit("usage: auto_classify.py <YYYYMMDD> [YYYYMMDD_end]")

    already = load_all_decided_keys()
    seen_this_run: set[str] = set()
    per_date_items: dict[str, list[Item]] = {}
    for d in dates:
        if not (REPORTS / d).is_dir():
            print(f"  {d}: reports 없음, 스킵")
            continue
        fresh = []
        for item in load_items(d):
            if item.key in already or item.key in seen_this_run:
                continue
            seen_this_run.add(item.key)
            fresh.append(item)
        per_date_items[d] = fresh

    total = sum(len(v) for v in per_date_items.values())
    print(f"분류 대상: {total}건 (이미 판정된 것 제외, 날짜 간 중복 제거 완료)")
    if total == 0:
        return

    client = make_client()
    done = 0
    for d, items in per_date_items.items():
        if not items:
            continue
        out_path = STATE_DIR / f"{d}.jsonl"
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i : i + BATCH_SIZE]
            results = classify_batch(client, batch)
            with out_path.open("a", encoding="utf-8") as f:
                for idx, item in enumerate(batch):
                    decision, category = results.get(idx, ("queue", ""))  # 파싱 실패 시 안전하게 queue
                    f.write(json.dumps({
                        "key": item.key, "source": item.source, "title": item.title,
                        "url": item.url, "date": item.raw_date, "decision": decision,
                        "category": category, "by": "llm-auto",
                        "ts": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
                    }, ensure_ascii=False) + "\n")
            done += len(batch)
            print(f"  {d}: {done}/{total} 처리...")
    print("완료 — triage_tui.py 로 열어서 훑어보고 틀린 것만 고치면 됨")


if __name__ == "__main__":
    main()
