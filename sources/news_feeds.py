import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import asyncio
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import aiohttp

from utils.logger import setup_logger

logger = setup_logger('news_feeds')

UA = "Mozilla/5.0 (compatible; ai-news-agent/0.1)"


def _strip_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


class NewsFeedCollector:
    """Hacker News, Product Hunt, TechCrunch AI 카테고리 통합 수집기."""

    AI_KEYWORDS = re.compile(
        r"\b(AI|LLM|GPT|Claude|Gemini|Anthropic|OpenAI|agent|MCP|RAG|"
        r"diffusion|transformer|inference|fine-tun|prompt|hugging\s*face|"
        r"deepmind|mistral|cohere|perplexity|copilot|"
        # 오픈소스 LLM/agent 진영 — Anthropic 외 사각지대 보완
        r"hermes|nous\s*research|llama|qwen|deepseek|grok|cursor|"
        r"openrouter|together|groq|fireworks)\b",
        re.IGNORECASE,
    )

    def __init__(self, days: int = 7, per_source_limit: int = 12, hn_min_points: int = 50):
        self.cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        self.cutoff_ts = int(self.cutoff.timestamp())
        self.per_source_limit = per_source_limit
        self.hn_min_points = hn_min_points

    async def fetch_posts(self):
        results = await asyncio.gather(
            self._fetch_hacker_news(),
            self._fetch_product_hunt(),
            self._fetch_techcrunch_ai(),
            return_exceptions=True,
        )
        all_posts = []
        for r in results:
            if isinstance(r, list):
                all_posts.extend(r)
            elif isinstance(r, Exception):
                logger.error(f"news feed 부분 실패: {r}")
        logger.info(f"News Feeds 총 {len(all_posts)}개 수집")
        return all_posts

    async def _get(self, url: str, params=None) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={"User-Agent": UA}, params=params, timeout=30) as resp:
                resp.raise_for_status()
                return await resp.text()

    async def _fetch_hacker_news(self):
        """HN Algolia search: AI/agent/LLM 관련 일주일 내 인기 글.

        query="AI" 단일 키워드는 "Hermes Agent #1 on OpenRouter" 같은 화제글이
        본문은 AI인데 제목에 "AI"가 없으면 통째로 누락됨. OR 확장으로 사각지대 차단.
        Algolia HN search는 query에 multi-term 입력 시 자동 OR 처리.
        """
        url = "https://hn.algolia.com/api/v1/search"
        params = {
            "query": "AI agent LLM",
            "tags": "story",
            "numericFilters": f"created_at_i>{self.cutoff_ts},points>{self.hn_min_points}",
            "hitsPerPage": str(self.per_source_limit * 5),  # OR 확장으로 후보 늘어남, 필터 여유
        }
        try:
            text = await self._get(url, params=params)
            data = json.loads(text)
        except Exception as e:
            logger.error(f"Hacker News 요청 실패: {e}")
            return []

        posts = []
        for hit in data.get("hits", []):
            title = (hit.get("title") or "").strip()
            if not title:
                continue
            # AI 관련 글만 (제목 기준)
            if not self.AI_KEYWORDS.search(title):
                continue
            url_target = (hit.get("url") or "").strip() or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            comments_url = f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            points = hit.get("points") or 0
            ncomments = hit.get("num_comments") or 0
            created = hit.get("created_at") or ""
            posts.append({
                "source": "Hacker News",
                "title": title,
                "url": url_target,
                "published_at": created,
                "content": (
                    f"{title}\n"
                    f"points: {points} · comments: {ncomments} · "
                    f"discussion: {comments_url}"
                ),
            })
            if len(posts) >= self.per_source_limit:
                break

        logger.info(f"Hacker News 수집 완료: {len(posts)}개 (≥{self.hn_min_points}점, AI 키워드)")
        return posts

    async def _fetch_product_hunt(self):
        """Product Hunt — Atom feed, AI 카테고리."""
        url = "https://www.producthunt.com/feed?category=artificial-intelligence"
        try:
            text = await self._get(url)
            root = ET.fromstring(text)
        except Exception as e:
            logger.error(f"Product Hunt 요청/파싱 실패: {e}")
            return []

        ns = "{http://www.w3.org/2005/Atom}"
        posts = []
        for entry in root.findall(f"{ns}entry"):
            title = (entry.findtext(f"{ns}title") or "").strip()
            link_el = entry.find(f"{ns}link")
            link = link_el.get("href") if link_el is not None else ""
            published = entry.findtext(f"{ns}published") or ""
            content = entry.findtext(f"{ns}content") or entry.findtext(f"{ns}summary") or ""

            try:
                dt = datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None
                if dt and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                dt = None
            if not dt or dt < self.cutoff:
                continue

            posts.append({
                "source": "Product Hunt (AI)",
                "title": title,
                "url": link,
                "published_at": dt.isoformat() if dt else "",
                "content": _strip_html(content)[:500] or title,
            })
            if len(posts) >= self.per_source_limit:
                break

        logger.info(f"Product Hunt 수집 완료: {len(posts)}개")
        return posts

    async def _fetch_techcrunch_ai(self):
        """TechCrunch AI 카테고리 RSS."""
        url = "https://techcrunch.com/category/artificial-intelligence/feed/"
        try:
            text = await self._get(url)
            root = ET.fromstring(text)
        except Exception as e:
            logger.error(f"TechCrunch 요청/파싱 실패: {e}")
            return []

        posts = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = item.findtext("pubDate")
            description = (item.findtext("description") or "").strip()

            try:
                dt = parsedate_to_datetime(pub) if pub else None
                if dt and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                dt = None
            if not dt or dt < self.cutoff:
                continue

            posts.append({
                "source": "TechCrunch AI",
                "title": title,
                "url": link,
                "published_at": dt.isoformat() if dt else "",
                "content": _strip_html(description)[:500] or title,
            })
            if len(posts) >= self.per_source_limit:
                break

        logger.info(f"TechCrunch AI 수집 완료: {len(posts)}개")
        return posts


if __name__ == "__main__":
    async def test():
        c = NewsFeedCollector()
        posts = await c.fetch_posts()
        for p in posts[:5]:
            print(p["source"], "|", p["title"][:80])
        print(f"총 {len(posts)}개")

    asyncio.run(test())
