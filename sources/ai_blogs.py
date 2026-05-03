import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import aiohttp
from bs4 import BeautifulSoup

from utils.logger import setup_logger

logger = setup_logger('ai_blogs')

UA = "Mozilla/5.0 (compatible; ai-news-agent/0.1)"


def _strip_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


class AIBlogCollector:
    """공식 AI 회사 블로그 통합 수집기 (Anthropic / OpenAI / Google AI)."""

    def __init__(self, days: int = 7, per_source_limit: int = 15):
        self.cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        self.per_source_limit = per_source_limit

    async def fetch_posts(self):
        results = await asyncio.gather(
            self._fetch_anthropic(),
            self._fetch_openai(),
            self._fetch_google(),
            return_exceptions=True,
        )
        all_posts = []
        for r in results:
            if isinstance(r, list):
                all_posts.extend(r)
            elif isinstance(r, Exception):
                logger.error(f"AI 블로그 수집 부분 실패: {r}")
        logger.info(f"AI 블로그 총 {len(all_posts)}개 수집")
        return all_posts

    async def _get(self, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={"User-Agent": UA}, timeout=30) as resp:
                resp.raise_for_status()
                return await resp.text()

    async def _fetch_rss(self, url: str, source_name: str):
        try:
            text = await self._get(url)
        except Exception as e:
            logger.error(f"{source_name} RSS 요청 실패: {e}")
            return []

        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            logger.error(f"{source_name} RSS 파싱 실패: {e}")
            return []

        posts = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = item.findtext("pubDate")
            description = (item.findtext("description") or "").strip()

            dt = None
            if pub_date:
                try:
                    dt = parsedate_to_datetime(pub_date)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    dt = None

            if dt and dt < self.cutoff:
                continue

            posts.append({
                "source": source_name,
                "title": title,
                "url": link,
                "published_at": dt.isoformat() if dt else "",
                "content": _strip_html(description) or title,
            })
            if len(posts) >= self.per_source_limit:
                break

        logger.info(f"{source_name} 수집 완료: {len(posts)}개")
        return posts

    async def _fetch_openai(self):
        return await self._fetch_rss("https://openai.com/news/rss.xml", "OpenAI Blog")

    async def _fetch_google(self):
        return await self._fetch_rss(
            "https://blog.google/technology/ai/rss/", "Google AI Blog"
        )

    async def _fetch_anthropic(self):
        url = "https://www.anthropic.com/news"
        try:
            text = await self._get(url)
        except Exception as e:
            logger.error(f"Anthropic Blog 요청 실패: {e}")
            return []

        soup = BeautifulSoup(text, "html.parser")
        date_pat = re.compile(
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4})"
        )
        category_words = ["Product", "Announcements", "Research", "Policy", "Society"]

        posts = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not (href.startswith("/news/") and href != "/news/" and href.count("/") >= 2):
                continue
            if href in seen:
                continue
            seen.add(href)

            blob = a.get_text(separator=" ", strip=True)
            if not blob:
                continue

            m = date_pat.search(blob)
            dt = None
            if m:
                try:
                    dt = datetime.strptime(m.group(1), "%b %d, %Y").replace(tzinfo=timezone.utc)
                except ValueError:
                    dt = None

            if dt and dt < self.cutoff:
                continue

            title = blob
            if m:
                title = title.replace(m.group(1), " ")
            for word in category_words:
                title = re.sub(rf"\b{word}\b", " ", title)
            title = re.sub(r"\s+", " ", title).strip()

            posts.append({
                "source": "Anthropic Blog",
                "title": title,
                "url": f"https://www.anthropic.com{href}",
                "published_at": dt.isoformat() if dt else "",
                "content": title,
            })
            if len(posts) >= self.per_source_limit:
                break

        logger.info(f"Anthropic Blog 수집 완료: {len(posts)}개")
        return posts


if __name__ == "__main__":
    import json

    async def test():
        collector = AIBlogCollector(days=14)
        posts = await collector.fetch_posts()
        print(json.dumps(posts, indent=2, ensure_ascii=False))

    asyncio.run(test())
