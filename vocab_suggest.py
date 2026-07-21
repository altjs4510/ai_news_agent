"""Tier 2 — Vocabulary 진화 제안.

축적된 학습 노트 분포를 LLM(Opus)이 분석해 CATEGORY_VOCABULARY 진화안을 제안한다.
출력: GitHub Issue (사용자가 검토 후 main.py 편집).
실행: 매월 1일 자동 + 수동 트리거.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from main import CATEGORY_VOCABULARY
from utils.llm_client import make_client, resolve_model
from utils.logger import setup_logger

logger = setup_logger("vocab_suggest")


def _knowledge_dir() -> Path:
    base = Path(os.getenv("BLOG_REPO_PATH", str(Path(__file__).resolve().parent.parent / "ai_news_blog"))).resolve()
    return base / "content" / "knowledge"


def _collect_distribution() -> dict:
    knowledge_dir = _knowledge_dir()
    cat_counter: Counter[str] = Counter()
    tag_counter: Counter[str] = Counter()
    entries: list[dict] = []
    if not knowledge_dir.is_dir():
        return {"entries": [], "cat_counter": {}, "tag_counter": {}}

    for md in sorted(knowledge_dir.glob("*.md")):
        if md.name == "_index.md":
            continue
        text = md.read_text(encoding="utf-8")
        title_m = re.search(r'^title:\s*"(.+?)"', text, re.M)
        cats_m = re.search(r'^categories:\s*\[(.+?)\]', text, re.M)
        tags_m = re.search(r'^tags:\s*\[(.+?)\]', text, re.M)
        title = title_m.group(1) if title_m else md.stem
        cats = []
        if cats_m:
            for raw in cats_m.group(1).split(","):
                c = raw.strip().strip('"').strip("'").strip()
                if c:
                    cats.append(c)
                    cat_counter[c] += 1
        tags = []
        if tags_m:
            for raw in tags_m.group(1).split(","):
                t = raw.strip().strip('"').strip("'").strip()
                if t:
                    tags.append(t)
                    tag_counter[t] += 1
        entries.append({"date": md.stem, "title": title, "categories": cats, "tags": tags})
    return {"entries": entries, "cat_counter": dict(cat_counter), "tag_counter": dict(tag_counter)}


def _build_prompt(dist: dict) -> str:
    vocab_block = "\n".join(f"- {c}: {dist['cat_counter'].get(c, 0)} entries" for c in CATEGORY_VOCABULARY)
    top_tags = sorted(dist["tag_counter"].items(), key=lambda x: -x[1])[:30]
    tags_block = "\n".join(f"- {t} ×{n}" for t, n in top_tags)
    entries_block = "\n".join(
        f"- {e['date']} {e['title'][:60]} [cats={e['categories']} tags={e['tags']}]"
        for e in dist["entries"][-30:]
    )
    return f"""다음은 AI 동향 학습 노트 아카이브의 누적 분포입니다.
현재 vocabulary 8개가 충분한지 검토하고 **진화안**을 제안하세요.

## 현재 CATEGORY_VOCABULARY 8개와 누적 사용량
{vocab_block}

## 자유 태그 상위 30개 (LLM이 매주 자유 생성한 keywords 누적)
{tags_block}

## 최근 학습 노트 30개 (날짜·제목·카테고리·태그)
{entries_block}

## 작성 규칙

1. 출력은 순수 마크다운. ``` 코드 블록으로 전체 감싸지 마세요.
2. 다음 4개 섹션 그대로 사용:

### ① 추가 후보
자유 태그에서 자주 등장하지만 현재 vocabulary가 잘 흡수하지 못하는 토픽이 있으면 새 카테고리 후보 1~3개를 제안.
근거(어떤 태그/엔트리들이 모이는지)와 함께 작성. 없으면 "없음".

### ② 제거/병합 후보
0~1 entries만 갖는 vocabulary, 또는 의미가 중복돼 다른 vocab에 흡수해도 되는 항목.
"X → Y로 흡수" 형식 또는 "X 제거" 형식. 없으면 "없음".

### ③ 분리 후보
하나의 vocab에 30%+ entries가 몰려 너무 광범위해진 경우, 2개 sub-카테고리로 분리 제안.
없으면 "없음".

### ④ 권장 vocabulary (개정안)
위 ①②③ 반영한 새 vocabulary를 정확히 코드 블록으로 출력:

```python
CATEGORY_VOCABULARY = [
    "...",
    "...",
]
```

변경이 없으면 현재 vocabulary 그대로 복사.
"""


def _generate_suggestion(dist: dict) -> str:
    if not dist["entries"]:
        return "## ℹ️ 학습 노트가 아직 없어 vocabulary 진화 제안을 생성하지 않습니다."
    client = make_client()
    response = client.messages.create(
        model=resolve_model("claude-opus-4-8"),
        max_tokens=4000,
        system=(
            "너는 정보 아키텍처 전문가다. 콘텐츠 분포를 보고 카테고리 vocabulary가 "
            "충분히 토픽을 분리·통합하는지 비판적으로 검토하고 구체적 진화안을 제시한다. "
            "보수적으로 — 변경 근거가 약하면 변경 없음을 권장한다."
        ),
        messages=[{"role": "user", "content": _build_prompt(dist)}],
    )
    if not response.content:
        return ""
    text = response.content[0].text.strip()
    text = re.sub(r"^```(?:markdown)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    return text


def _open_github_issue(body: str, dist: dict) -> bool:
    """gh CLI로 Issue 생성. GH 워크플로 안에서는 GITHUB_TOKEN 자동 인증."""
    repo = os.getenv("GITHUB_REPOSITORY", "altjs4510/ai_news_agent")
    n_entries = len(dist["entries"])
    title = f"Vocabulary 진화 제안 ({n_entries} entries 누적)"
    full_body = (
        f"누적 학습 노트 **{n_entries}건** 분포를 LLM이 분석한 진화안입니다. "
        "검토 후 동의하면 `main.py`의 `CATEGORY_VOCABULARY`를 편집하고 "
        "`gh workflow run curate.yml`로 일괄 재분류하세요.\n\n"
        "---\n\n" + body + "\n\n---\n\n"
        "_자동 생성 — vocab-suggest.yml_"
    )
    try:
        subprocess.run(
            ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", full_body, "--label", "vocabulary"],
            check=True,
            capture_output=True,
        )
        logger.info(f"Issue 생성 완료: {repo}")
        return True
    except FileNotFoundError:
        # gh CLI 없으면 stdout에 출력
        print("=== Vocabulary Suggestion ===")
        print(f"Title: {title}\n")
        print(full_body)
        return False
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
        # label이 없으면 label 빼고 재시도
        if "could not add label" in stderr.lower() or "label" in stderr.lower():
            try:
                subprocess.run(
                    ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", full_body],
                    check=True,
                    capture_output=True,
                )
                logger.info(f"Issue 생성 완료(라벨 없이): {repo}")
                return True
            except subprocess.CalledProcessError as e2:
                logger.error(f"Issue 생성 실패: {e2.stderr.decode('utf-8', errors='replace') if e2.stderr else e2}")
        else:
            logger.error(f"Issue 생성 실패: {stderr}")
        return False


def main() -> int:
    dist = _collect_distribution()
    logger.info(f"누적 entries: {len(dist['entries'])}, cats: {len(dist['cat_counter'])}, tags: {len(dist['tag_counter'])}")
    if len(dist["entries"]) < 3:
        logger.info("학습 노트 3건 미만 — 진화 제안 스킵")
        return 0
    suggestion = _generate_suggestion(dist)
    if not suggestion:
        logger.error("LLM 응답이 비어 있습니다.")
        return 1
    _open_github_issue(suggestion, dist)
    return 0


if __name__ == "__main__":
    sys.exit(main())
