"""Bluesky AT Protocol public reader.

X 대체 — 인증 없이 공개 피드를 읽어 'X 와글와글' 성격의 짧은 버즈를 수집한다.
HTTP only, 별도 인프라(서버·쿠키) 불필요. 레이트리밋은 미인증 ~3,000/5min.
"""

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import asyncio
from datetime import datetime, timedelta, timezone

import aiohttp

from utils.logger import setup_logger

logger = setup_logger('bluesky')

API_BASE = "https://public.api.bsky.app/xrpc"
USER_AGENT = "ai-news-agent/0.1 (+https://github.com/altjs4510/ai_news_agent)"


class BlueskyCollector:
    """Bluesky 공개 AuthorFeed에서 최근 게시물을 수집."""

    def __init__(self, handles: list[str], days: int = 7, per_handle_limit: int = 8):
        self.handles = handles
        self.cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        self.per_handle_limit = per_handle_limit

    async def fetch_posts(self):
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
            tasks = [self._fetch_handle(session, h) for h in self.handles]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_posts = []
        for r in results:
            if isinstance(r, list):
                all_posts.extend(r)
            elif isinstance(r, Exception):
                logger.error(f"Bluesky 수집 부분 실패: {r}")
        logger.info(f"Bluesky 총 {len(all_posts)}개 수집 ({len(self.handles)} handles)")
        return all_posts

    async def _fetch_handle(self, session: aiohttp.ClientSession, handle: str):
        url = f"{API_BASE}/app.bsky.feed.getAuthorFeed"
        params = {
            "actor": handle,
            "limit": str(min(max(self.per_handle_limit * 2, 10), 50)),
            "filter": "posts_no_replies",
        }
        try:
            async with session.get(url, params=params, timeout=30) as resp:
                if resp.status != 200:
                    body = (await resp.text())[:200]
                    logger.error(f"Bluesky {handle} HTTP {resp.status}: {body}")
                    return []
                data = await resp.json()
        except Exception as e:
            logger.error(f"Bluesky {handle} 요청 실패: {e}", exc_info=True)
            return []

        posts = []
        for entry in data.get("feed", []):
            post = entry.get("post") or {}
            record = post.get("record") or {}
            text = (record.get("text") or "").strip()
            created = record.get("createdAt") or ""
            uri = post.get("uri") or ""
            cid = post.get("cid") or ""
            author = post.get("author") or {}
            author_handle = author.get("handle") or handle

            if not text or not uri:
                continue

            # ISO8601 → datetime
            dt = None
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except ValueError:
                    dt = None
            if dt is None or dt < self.cutoff:
                continue

            # 리포스트(reason 포함)는 reason 표시
            reason = entry.get("reason") or {}
            is_repost = reason.get("$type") == "app.bsky.feed.defs#reasonRepost"
            tag = "🔁 repost" if is_repost else "post"

            # at:// uri를 사람이 볼 수 있는 https URL로 변환
            web_url = _at_uri_to_web(uri, author_handle) or post.get("uri", "")

            engagement = (
                f"❤ {post.get('likeCount', 0)} · "
                f"🔁 {post.get('repostCount', 0)} · "
                f"💬 {post.get('replyCount', 0)}"
            )

            # 요약 prompt에는 본문 + handle + 인게이지먼트만 의미 있음.
            # title은 헤더 가독성용 — 첫 80자 발췌.
            title = (text[:80] + "…") if len(text) > 80 else text
            posts.append({
                "source": f"Bluesky - @{author_handle}",
                "title": title.replace("\n", " "),
                "url": web_url,
                "published_at": dt.isoformat() if dt else "",
                "tag": tag,
                "engagement": engagement,
                "content": text,
            })
            if len(posts) >= self.per_handle_limit:
                break

        logger.info(f"Bluesky @{handle} 수집 완료: {len(posts)}개")
        return posts


def _at_uri_to_web(at_uri: str, handle: str) -> str:
    """at://did:plc:xxx/app.bsky.feed.post/3l...id → https://bsky.app/profile/<handle>/post/<rkey>"""
    if not at_uri.startswith("at://"):
        return ""
    parts = at_uri[len("at://"):].split("/")
    if len(parts) < 3:
        return ""
    rkey = parts[-1]
    return f"https://bsky.app/profile/{handle}/post/{rkey}"


if __name__ == "__main__":
    import json

    async def test():
        c = BlueskyCollector(handles=[
            "karpathy.bsky.social",
            "swyx.io",
            "simonwillison.net",
        ])
        posts = await c.fetch_posts()
        print(json.dumps(posts[:5], indent=2, ensure_ascii=False))

    asyncio.run(test())
