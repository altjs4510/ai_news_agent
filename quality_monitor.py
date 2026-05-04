"""Tier 4 — 품질 모니터.

매주 weekly.yml 직후 자동 실행. 이상 감지 시 Slack 알림.

검사 항목
─────────
1. vocabulary 미사용: 누적 0건인 카테고리 (엔트리 5개 이상인 경우에만)
2. 카테고리 집중: 전체 엔트리의 40%+ 가 단일 카테고리에 몰림 → 분리 신호
3. 미분류 엔트리: categories 필드 없거나 비어 있는 노트 수
4. 스팟라이트 URL 사망 여부: 최신 meta.json spotlight.url HEAD 요청
5. 중복 토픽 경보: 최신 meta.json keywords가 직전 스냅샷과 70%+ 겹침
   (reports-cache 브랜치 스냅샷이 있을 때만 / 없으면 스킵)

출력: 이상 항목이 있으면 Slack 웹훅으로 알림.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import aiohttp

from utils.logger import setup_logger

logger = setup_logger("quality_monitor")

# ── 환경변수 ────────────────────────────────────────────────────
SLACK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
BLOG_REPO = Path(
    os.getenv("BLOG_REPO_PATH", str(Path(__file__).resolve().parent.parent / "ai_news_blog"))
).resolve()
KNOWLEDGE_DIR = BLOG_REPO / "content" / "knowledge"

# 최신 reports 스냅샷 위치
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", str(Path(__file__).resolve().parent / "reports")))


# ── helpers ─────────────────────────────────────────────────────

def _find_latest_meta() -> dict | None:
    if not REPORTS_DIR.is_dir():
        return None
    candidates = sorted(
        (d for d in REPORTS_DIR.iterdir() if d.is_dir() and d.name.isdigit()),
        key=lambda p: p.name,
    )
    for d in reversed(candidates):
        meta_path = d / "meta.json"
        if meta_path.exists():
            try:
                return json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return None


def _find_prev_meta() -> dict | None:
    """두 번째로 최신 meta.json (중복 토픽 비교용)."""
    if not REPORTS_DIR.is_dir():
        return None
    candidates = sorted(
        (d for d in REPORTS_DIR.iterdir() if d.is_dir() and d.name.isdigit()),
        key=lambda p: p.name,
    )
    found = []
    for d in reversed(candidates):
        meta_path = d / "meta.json"
        if meta_path.exists():
            try:
                found.append(json.loads(meta_path.read_text(encoding="utf-8")))
            except Exception:
                continue
        if len(found) >= 2:
            break
    return found[1] if len(found) >= 2 else None


def _scan_knowledge() -> dict:
    """categories 분포 및 미분류 엔트리 스캔."""
    cat_counter: Counter[str] = Counter()
    uncategorized: list[str] = []
    total = 0
    if not KNOWLEDGE_DIR.is_dir():
        return {"cat_counter": {}, "uncategorized": [], "total": 0}
    for md in KNOWLEDGE_DIR.glob("*.md"):
        if md.name == "_index.md":
            continue
        total += 1
        text = md.read_text(encoding="utf-8")
        m = re.search(r"^categories:\s*\[(.+?)\]", text, re.M)
        if not m:
            uncategorized.append(md.stem)
            continue
        cats = [
            c.strip().strip('"').strip("'").strip()
            for c in m.group(1).split(",")
        ]
        cats = [c for c in cats if c]
        if not cats:
            uncategorized.append(md.stem)
            continue
        for c in cats:
            cat_counter[c] += 1
    return {"cat_counter": dict(cat_counter), "uncategorized": uncategorized, "total": total}


async def _check_url(session: aiohttp.ClientSession, url: str) -> bool:
    try:
        async with session.head(
            url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)
        ) as r:
            return r.status < 400
    except Exception:
        try:
            async with session.get(
                url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                return r.status < 400
        except Exception:
            return False


async def _run_checks() -> list[str]:
    issues: list[str] = []

    # ── 1-3. knowledge 분포 검사 ─────────────────────────────────
    dist = _scan_knowledge()
    total = dist["total"]
    cat_counter = dist["cat_counter"]
    uncategorized = dist["uncategorized"]

    if total >= 5:
        try:
            from main import CATEGORY_VOCABULARY
            unused = [v for v in CATEGORY_VOCABULARY if cat_counter.get(v, 0) == 0]
            if unused:
                issues.append(
                    f":ghost: *미사용 vocabulary* ({len(unused)}개): {', '.join(unused)}"
                )
        except ImportError:
            pass

        if cat_counter:
            top_cat, top_cnt = max(cat_counter.items(), key=lambda x: x[1])
            ratio = top_cnt / total
            if ratio >= 0.40:
                pct = int(ratio * 100)
                issues.append(
                    f":bar_chart: *카테고리 집중* — `{top_cat}` 에 {pct}% ({top_cnt}/{total}개) 몰림 → 분리 검토"
                )

    if uncategorized:
        issues.append(
            f":label: *미분류 엔트리* {len(uncategorized)}개: {', '.join(uncategorized[:5])}"
            + (f" (+{len(uncategorized)-5})" if len(uncategorized) > 5 else "")
        )

    # ── 4. spotlight URL 생존 확인 ───────────────────────────────
    meta = _find_latest_meta()
    dead_urls: list[str] = []
    if meta:
        spotlight_url = (meta.get("spotlight") or {}).get("url") or ""
        pick_urls = [p.get("url") or "" for p in (meta.get("additional_picks") or [])]
        all_urls = [u for u in [spotlight_url] + pick_urls if u.startswith("http")]
        if all_urls:
            headers = {"User-Agent": "Mozilla/5.0 (quality-monitor)"}
            async with aiohttp.ClientSession(headers=headers) as session:
                results = await asyncio.gather(*[_check_url(session, u) for u in all_urls])
            for url, ok in zip(all_urls, results):
                if not ok:
                    dead_urls.append(url)
        if dead_urls:
            issues.append(
                f":coffin: *죽은 링크* ({len(dead_urls)}개):\n"
                + "\n".join(f"  • {u}" for u in dead_urls)
            )

    # ── 5. 중복 토픽 감지 ────────────────────────────────────────
    prev_meta = _find_prev_meta()
    if meta and prev_meta:
        cur_kw = set((meta.get("keywords") or []))
        prev_kw = set((prev_meta.get("keywords") or []))
        if cur_kw and prev_kw:
            overlap = cur_kw & prev_kw
            ratio = len(overlap) / max(len(cur_kw), len(prev_kw))
            if ratio >= 0.70:
                pct = int(ratio * 100)
                issues.append(
                    f":repeat: *반복 토픽 경보* — 이번 호 키워드 {pct}%가 이전 호와 동일\n"
                    f"  겹침: {', '.join(sorted(overlap)[:8])}"
                )

    return issues


async def _notify_slack(issues: list[str]) -> None:
    if not SLACK_URL:
        logger.warning("SLACK_WEBHOOK_URL 미설정 — 콘솔 출력만")
        for i in issues:
            print(i)
        return
    total = len(issues)
    blocks = "\n".join(f"• {i}" for i in issues)
    text = (
        f":mag: *AI News 품질 모니터 — {total}개 이상 감지*\n\n{blocks}\n\n"
        "_자동 감지 — quality-monitor.yml_"
    )
    async with aiohttp.ClientSession() as session:
        async with session.post(
            SLACK_URL,
            json={"text": text},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status != 200:
                logger.error(f"Slack 알림 실패: HTTP {r.status}")


async def _async_main() -> int:
    logger.info("품질 모니터 시작")
    issues = await _run_checks()
    if issues:
        logger.warning(f"이상 {len(issues)}개 감지")
        await _notify_slack(issues)
    else:
        logger.info("이상 없음")
    return 0


def main() -> int:
    return asyncio.run(_async_main())


if __name__ == "__main__":
    sys.exit(main())
