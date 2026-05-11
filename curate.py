"""축적된 학습 노트 카테고리를 LLM으로 재분류하는 curation 루프.

매일 daily.yml 직후 자동 실행되어:
1. content/knowledge/*.md 의 frontmatter + 본문 일부를 읽음
2. CATEGORY_VOCABULARY 8개 중 정확히 1개를 Sonnet에 골라달라고 요청
3. 기존 categories와 다르면 frontmatter 업데이트
4. 모든 detail 사이드바 + index 사이드바 일괄 갱신
5. 변경 내역을 git commit message로 요약 + 블로그 push

블로그 자체를 AI가 관리하는 첫 사이클.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from main import CATEGORY_VOCABULARY
from delivery.blog_publisher import BlogPublisher
from utils.llm_client import make_client, resolve_model
from utils.logger import setup_logger

logger = setup_logger("curate")


def _blog_repo() -> Path:
    return Path(os.getenv("BLOG_REPO_PATH", str(Path(__file__).resolve().parent.parent / "ai_news_blog"))).resolve()


def _knowledge_dir() -> Path:
    return _blog_repo() / "content" / "knowledge"


def _parse_categories(text: str) -> list[str]:
    m = re.search(r"^categories:\s*\[(.+?)\]", text, re.M)
    if not m:
        return []
    cats = []
    for raw in m.group(1).split(","):
        c = raw.strip().strip('"').strip("'").strip()
        if c:
            cats.append(c)
    return cats


def _parse_title(text: str) -> str:
    m = re.search(r'^title:\s*"(.+?)"', text, re.M)
    return m.group(1) if m else ""


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end < 0:
        return text
    return text[end + 4 :].lstrip()


async def _classify(client, title: str, body_excerpt: str) -> list[str]:
    vocab_block = "\n".join(f"- {c}" for c in CATEGORY_VOCABULARY)
    prompt = f"""다음 학습 노트를 아래 vocabulary에서 정확히 1개 카테고리로 분류하세요.
새 단어 만들지 말고 vocabulary에서 정확히 그대로 옮겨 적으세요.

## 학습 노트
제목: {title}

본문 발췌:
{body_excerpt[:2500]}

## Vocabulary (이 8개 중에서만 선택)
{vocab_block}

## 응답 형식 (JSON only)
{{"categories": ["..."]}}
"""
    response = client.messages.create(
        model=resolve_model("claude-sonnet-4-6"),
        max_tokens=200,
        system=(
            "너는 기술 콘텐츠 분류 전문가다. 주어진 학습 노트를 고정된 카테고리 vocabulary에서 "
            "가장 적합한 1개 카테고리에 매핑한다. vocabulary 밖 단어는 만들지 않는다."
        ),
        messages=[{"role": "user", "content": prompt}],
    )
    if not response.content:
        return []
    text = response.content[0].text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    m = re.search(r"\{.*?\}", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    cats = data.get("categories") or []
    if not isinstance(cats, list):
        return []
    return [c for c in cats if isinstance(c, str) and c in CATEGORY_VOCABULARY][:1]


def _replace_categories(text: str, new_cats: list[str]) -> str:
    """frontmatter의 categories 라인을 갱신. 없으면 tags 다음/끝에 추가."""
    new_line = "categories: [" + ", ".join(f'"{c}"' for c in new_cats) + "]"
    if re.search(r"^categories:\s*\[.+?\]", text, re.M):
        return re.sub(r"^categories:\s*\[.+?\]", new_line, text, count=1, flags=re.M)
    # 추가: tags 다음 줄, 없으면 frontmatter 끝(\n---\n) 직전.
    tags_m = re.search(r"^tags:\s*\[.+?\]\n", text, re.M)
    if tags_m:
        idx = tags_m.end()
        return text[:idx] + new_line + "\n" + text[idx:]
    fm_end = text.find("\n---\n", 3)
    if fm_end < 0:
        return text
    return text[: fm_end + 1] + new_line + "\n" + text[fm_end + 1 :]


async def main() -> int:
    knowledge_dir = _knowledge_dir()
    if not knowledge_dir.is_dir():
        logger.error(f"{knowledge_dir} 없음 — 블로그 레포 체크아웃 확인")
        return 1

    md_files = sorted(p for p in knowledge_dir.glob("*.md") if p.name != "_index.md")
    if not md_files:
        logger.info("학습 노트가 없어 curation 스킵")
        return 0

    client = make_client()
    changes: list[dict] = []
    cat_counter: dict[str, int] = {}

    for md in md_files:
        text = md.read_text(encoding="utf-8")
        title = _parse_title(text)
        body = _strip_frontmatter(text)
        # body 안 사이드바 제거 후 article 본문 발췌
        body = re.sub(
            r'<aside class="ai-knowledge-sidebar">.*?</aside>', "", body, count=1, flags=re.S
        )
        excerpt = re.sub(r"<[^>]+>", " ", body)
        excerpt = re.sub(r"\s+", " ", excerpt).strip()[:2500]

        cur_cats = _parse_categories(text)

        try:
            new_cats = await _classify(client, title, excerpt)
        except Exception as e:
            logger.error(f"{md.name} 분류 실패: {e}")
            continue

        if not new_cats:
            logger.warning(f"{md.name}: 분류 결과 없음 (vocabulary 매칭 실패)")
            continue

        for c in new_cats:
            cat_counter[c] = cat_counter.get(c, 0) + 1

        if set(new_cats) == set(cur_cats):
            logger.info(f"{md.name}: {cur_cats} (변경 없음)")
            continue

        new_text = _replace_categories(text, new_cats)
        if new_text == text:
            continue
        md.write_text(new_text, encoding="utf-8")
        changes.append(
            {"file": md.name, "title": title, "before": cur_cats, "after": new_cats}
        )
        logger.info(f"{md.name}: {cur_cats} → {new_cats}")

    # vocabulary 사용 분포
    logger.info("=== Vocabulary 사용 분포 ===")
    for vocab in CATEGORY_VOCABULARY:
        cnt = cat_counter.get(vocab, 0)
        logger.info(f"  {vocab}: {cnt}")
    unused = [v for v in CATEGORY_VOCABULARY if cat_counter.get(v, 0) == 0]
    if unused:
        logger.warning(f"미사용 카테고리({len(unused)}): {unused}")

    if not changes:
        logger.info("Curation 변경 없음 — 블로그 push 스킵")
        return 0

    # 사이드바 일괄 갱신 (frontmatter categories 반영)
    publisher = BlogPublisher()
    publisher.refresh_all_knowledge_sidebars()

    # commit + push
    blog = _blog_repo()
    try:
        subprocess.run(["git", "-C", str(blog), "add", "content/knowledge/"], check=True, capture_output=True)
        staged = subprocess.run(["git", "-C", str(blog), "diff", "--cached", "--quiet"])
        if staged.returncode == 0:
            logger.info("Curation: staged 변경 없음 — 커밋 스킵")
            return 0
        msg_lines = [
            f"chore: curate categories ({len(changes)} changes)",
            "",
        ]
        for c in changes[:10]:
            msg_lines.append(f"- {c['title'][:60]}: {c['before']} → {c['after']}")
        if len(changes) > 10:
            msg_lines.append(f"- (+{len(changes) - 10} more)")
        msg = "\n".join(msg_lines)
        subprocess.run(["git", "-C", str(blog), "commit", "-m", msg], check=True, capture_output=True)
        # push (race 대비 pull --rebase 한 번)
        try:
            subprocess.run(["git", "-C", str(blog), "push"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            subprocess.run(["git", "-C", str(blog), "pull", "--rebase", "origin", "main"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(blog), "push"], check=True, capture_output=True)
        logger.info(f"Curation 완료: {len(changes)}건 변경 push")
    except subprocess.CalledProcessError as e:
        logger.error(f"git 동작 실패: {e.stderr.decode('utf-8', errors='replace') if e.stderr else e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
