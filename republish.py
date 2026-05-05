"""마지막 수집 결과(reports/<latest>/)로만 블로그를 재발행한다.

LLM/크롤 없이 publisher 템플릿·블로그 CSS·Hugo 설정 변경을
빠르게 적용하기 위한 가벼운 진입점.
daily.yml 스냅샷이 reports-cache 브랜치에 올려둔 데이터를 기반으로 한다.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from delivery.blog_publisher import BlogPublisher
from main import _write_summary_markdown
from utils.logger import setup_logger

logger = setup_logger("republish")


def find_latest_report() -> Path | None:
    base = Path("reports")
    if not base.is_dir():
        return None
    candidates = [d for d in base.iterdir() if d.is_dir() and d.name.isdigit()]
    return max(candidates, key=lambda d: d.name) if candidates else None


async def main() -> int:
    latest = find_latest_report()
    if not latest:
        logger.error("reports/<date>/ 디렉토리를 찾지 못했습니다 (reports-cache 브랜치 누락?)")
        return 1

    date_str = latest.name
    logger.info(f"Republish 대상: {latest}")

    meta_path = latest / "meta.json"
    meta: dict = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"meta.json 파싱 실패, 빈 메타로 진행: {e}")
    else:
        logger.warning(f"{meta_path} 없음 — headline/spotlight 메타 없이 진행")

    # publisher 템플릿이 바뀌면 summary.md도 같이 재생성해야 변경이 반영됨.
    # (publisher는 summary.md를 그대로 읽어서 post에 끼워 넣기 때문)
    headline = meta.get("headline") or ""
    deck = meta.get("deck") or ""
    spotlight = meta.get("spotlight") or None
    keywords = meta.get("keywords") or []
    additional_picks = meta.get("additional_picks") or []
    categories = meta.get("categories") or []
    try:
        _write_summary_markdown(
            str(latest), date_str, headline, spotlight, [], keywords,
            additional_picks=additional_picks,
        )
        logger.info("summary.md 재생성 완료 (현재 publisher 템플릿 기준)")
    except Exception as e:
        logger.warning(f"summary.md 재생성 실패, 기존 파일 그대로 사용: {e}")

    publisher = BlogPublisher()
    blog_url = publisher.publish(
        report_dir=str(latest),
        date_str=date_str,
        keywords=keywords,
        headline=headline,
        deck=deck,
        spotlight=spotlight,
        additional_picks=additional_picks,
        categories=categories,
        has_study=meta.get("has_study", (latest / "study.md").exists()),
    )
    if blog_url:
        logger.info(f"Republish 완료: {blog_url}")
        return 0
    logger.error("Republish 실패")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
