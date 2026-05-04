"""Tier 3 — 관련 학습 자동 링크.

related 블록이 없는 knowledge 노트마다 Sonnet이 전체 노트 목록에서
가장 유사한 2~3개를 골라 <!-- ai-related-links --> 블록으로 파일 말미에 삽입.
curate.py 의 refresh_all_knowledge_sidebars()는 <aside class="ai-knowledge-sidebar">만
교체하므로 이 블록과 충돌 없음.

실행: link-related.yml (curate.yml 완료 후 자동) + 수동.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from anthropic import Anthropic

from utils.logger import setup_logger

logger = setup_logger("link_related")

RELATED_START = "<!-- ai-related-links -->"
RELATED_END = "<!-- /ai-related-links -->"


def _blog_repo() -> Path:
    return Path(
        os.getenv("BLOG_REPO_PATH", str(Path(__file__).resolve().parent.parent / "ai_news_blog"))
    ).resolve()


def _knowledge_dir() -> Path:
    return _blog_repo() / "content" / "knowledge"


def _site_url() -> str:
    return os.getenv("BLOG_SITE_URL", "https://altjs4510.github.io/ai_news_blog").rstrip("/")


def _parse_title(text: str) -> str:
    m = re.search(r'^title:\s*"(.+?)"', text, re.M)
    return m.group(1) if m else ""


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    return text[end + 4 :].lstrip() if end >= 0 else text


def _get_excerpt(text: str, max_chars: int = 600) -> str:
    body = _strip_frontmatter(text)
    body = re.sub(r"<[^>]+>", " ", body)
    body = re.sub(r"\s+", " ", body).strip()
    return body[:max_chars]


def _find_related(
    client: Anthropic,
    target_date: str,
    target_title: str,
    target_excerpt: str,
    others: dict[str, dict],
) -> list[dict]:
    if not others:
        return []
    candidates = [
        f"id={d} | {info['title'][:70]} — {info['excerpt'][:250]}"
        for d, info in others.items()
    ][:80]
    candidates_block = "\n".join(candidates)
    prompt = f"""다음 학습 노트와 개념·주제·기술 측면에서 가장 밀접한 노트를 2~3개 고르세요.

## 대상
id={target_date}
제목: {target_title}
발췌: {target_excerpt[:400]}

## 후보 (id | 제목 — 발췌)
{candidates_block}

## 응답 (JSON only)
{{"related": ["id1", "id2"]}}
관련 노트가 없으면 {{"related": []}}
"""
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        system=(
            "기술 문서 유사도 전문가. 개념적으로 가장 관련 깊은 노트 id를 2~3개 골라 "
            "JSON으로 반환. 관련성이 낮으면 적게 선택. id 외 텍스트 출력 금지."
        ),
        messages=[{"role": "user", "content": prompt}],
    )
    if not resp.content:
        return []
    text = resp.content[0].text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    m = re.search(r"\{.*?\}", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    ids = data.get("related") or []
    result = []
    for rid in ids[:3]:
        if rid in others:
            result.append({"date": rid, "title": others[rid]["title"]})
    return result


def _build_related_block(related: list[dict]) -> str:
    if not related:
        return ""
    items = []
    for r in related:
        d = r["date"]
        title = r["title"].replace("&", "&amp;").replace("<", "&lt;")
        display = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        short = title[:48] + ("…" if len(title) > 48 else "")
        items.append(
            f'<li><a href="{_site_url()}/knowledge/{d}/">'
            f'<span class="kdate">{display}</span>'
            f'<span class="ktitle">{short}</span>'
            f"</a></li>"
        )
    return (
        f"\n{RELATED_START}\n"
        f'<aside class="ai-related-links">\n'
        f'  <p class="ai-eyebrow">관련 학습</p>\n'
        f'  <ul>{"".join(items)}</ul>\n'
        f"</aside>\n"
        f"{RELATED_END}\n"
    )


def _inject_block(text: str, block: str) -> str:
    if RELATED_START in text:
        return re.sub(
            re.escape(RELATED_START) + r".*?" + re.escape(RELATED_END),
            block.strip(),
            text,
            count=1,
            flags=re.S,
        )
    return text.rstrip() + "\n" + block


def main() -> int:
    knowledge_dir = _knowledge_dir()
    if not knowledge_dir.is_dir():
        logger.error(f"{knowledge_dir} 없음 — BLOG_REPO_PATH 확인")
        return 1

    md_files = sorted(p for p in knowledge_dir.glob("*.md") if p.name != "_index.md")
    if len(md_files) < 2:
        logger.info("노트 2개 미만 — 링크 불필요")
        return 0

    # 전체 인덱스 빌드
    index: dict[str, dict] = {}
    for md in md_files:
        text = md.read_text(encoding="utf-8")
        index[md.stem] = {
            "title": _parse_title(text) or md.stem,
            "excerpt": _get_excerpt(text),
            "text": text,
            "path": md,
        }

    client = Anthropic()
    changes = 0

    for date, info in index.items():
        if RELATED_START in info["text"]:
            logger.info(f"{date}: related 블록 존재 — 스킵")
            continue

        logger.info(f"{date}: 관련 노트 탐색 중...")
        others = {d: v for d, v in index.items() if d != date}
        try:
            related = _find_related(
                client, date, info["title"], info["excerpt"], others
            )
        except Exception as e:
            logger.error(f"{date}: LLM 실패 — {e}")
            continue

        if not related:
            logger.info(f"{date}: 관련 노트 없음")
            continue

        block = _build_related_block(related)
        new_text = _inject_block(info["text"], block)
        if new_text == info["text"]:
            continue
        info["path"].write_text(new_text, encoding="utf-8")
        titles = [r["title"][:30] for r in related]
        logger.info(f"{date}: 관련 {len(related)}개 링크 → {titles}")
        changes += 1

    if not changes:
        logger.info("관련 링크 변경 없음 — push 스킵")
        return 0

    blog = _blog_repo()
    try:
        subprocess.run(
            ["git", "-C", str(blog), "add", "content/knowledge/"],
            check=True,
            capture_output=True,
        )
        staged = subprocess.run(
            ["git", "-C", str(blog), "diff", "--cached", "--quiet"]
        )
        if staged.returncode == 0:
            logger.info("staged 변경 없음 — 커밋 스킵")
            return 0
        subprocess.run(
            [
                "git",
                "-C",
                str(blog),
                "commit",
                "-m",
                f"chore: link related notes ({changes} updated)",
            ],
            check=True,
            capture_output=True,
        )
        try:
            subprocess.run(
                ["git", "-C", str(blog), "push"], check=True, capture_output=True
            )
        except subprocess.CalledProcessError:
            subprocess.run(
                ["git", "-C", str(blog), "pull", "--rebase", "origin", "main"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(blog), "push"], check=True, capture_output=True
            )
        logger.info(f"관련 링크 {changes}건 push 완료")
    except subprocess.CalledProcessError as e:
        logger.error(
            f"git 실패: {e.stderr.decode('utf-8', errors='replace') if e.stderr else e}"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
