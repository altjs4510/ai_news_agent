import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import aiohttp
from bs4 import BeautifulSoup

from utils.logger import setup_logger

logger = setup_logger('research_feeds')

UA = "Mozilla/5.0 (compatible; ai-news-agent/0.1)"


class ResearchFeedCollector:
    """학술/연구 피드: arxiv (cs.AI/cs.CL), HuggingFace Papers."""

    def __init__(self, days: int = 7, per_source_limit: int = 10):
        self.cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        self.per_source_limit = per_source_limit

    async def fetch_posts(self):
        results = await asyncio.gather(
            self._fetch_arxiv(),
            self._fetch_hf_papers(),
            return_exceptions=True,
        )
        all_posts = []
        for r in results:
            if isinstance(r, list):
                all_posts.extend(r)
            elif isinstance(r, Exception):
                logger.error(f"research feed 부분 실패: {r}")
        logger.info(f"Research Feeds 총 {len(all_posts)}개 수집")
        return all_posts

    async def _get(self, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={"User-Agent": UA}, timeout=30) as resp:
                resp.raise_for_status()
                return await resp.text()

    async def _fetch_arxiv(self):
        """arxiv API (cs.AI + cs.CL 카테고리, 최신순)."""
        url = (
            "http://export.arxiv.org/api/query"
            "?search_query=cat:cs.AI+OR+cat:cs.CL"
            "&sortBy=submittedDate&sortOrder=descending"
            f"&max_results={self.per_source_limit * 2}"
        )
        try:
            text = await self._get(url)
            root = ET.fromstring(text)
        except Exception as e:
            logger.error(f"arxiv 요청/파싱 실패: {e}")
            return []

        ns = {"a": "http://www.w3.org/2005/Atom"}
        posts = []
        for entry in root.findall("a:entry", ns):
            title = (entry.findtext("a:title", namespaces=ns) or "").strip()
            published = entry.findtext("a:published", namespaces=ns)
            link_el = entry.find("a:id", ns)
            url_target = link_el.text.strip() if link_el is not None else ""
            summary = (entry.findtext("a:summary", namespaces=ns) or "").strip()

            try:
                dt = datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None
                if dt and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                dt = None
            if not dt or dt < self.cutoff:
                continue

            posts.append({
                "source": "arxiv (cs.AI/cs.CL)",
                "title": re.sub(r"\s+", " ", title)[:240],
                "url": url_target,
                "published_at": dt.isoformat() if dt else "",
                "content": re.sub(r"\s+", " ", summary)[:600] or title,
            })
            if len(posts) >= self.per_source_limit:
                break

        logger.info(f"arxiv 수집 완료: {len(posts)}개")
        return posts

    async def _fetch_hf_papers(self):
        """Hugging Face Papers (오늘의 인기 논문 큐레이션)."""
        url = "https://huggingface.co/papers"
        try:
            text = await self._get(url)
        except Exception as e:
            logger.error(f"HF Papers 요청 실패: {e}")
            return []

        soup = BeautifulSoup(text, "html.parser")
        posts = []
        seen = set()
        for h3 in soup.find_all("h3"):
            title = h3.get_text(separator=" ", strip=True)
            if not title or len(title) < 10:
                continue
            link = h3.find("a", href=True) or h3.find_parent().find("a", href=True) if h3.find_parent() else None
            href = ""
            if link:
                href = link.get("href", "")
            if not href:
                continue
            if href.startswith("/papers/"):
                href = f"https://huggingface.co{href.split('#')[0]}"
            if href in seen:
                continue
            seen.add(href)
            posts.append({
                "source": "HuggingFace Papers",
                "title": title[:240],
                "url": href,
                "published_at": "",
                "content": title[:240],
            })
            if len(posts) >= self.per_source_limit:
                break

        logger.info(f"HF Papers 수집 완료: {len(posts)}개")
        return posts


if __name__ == "__main__":
    async def test():
        c = ResearchFeedCollector()
        posts = await c.fetch_posts()
        for p in posts[:5]:
            print(p["source"], "|", p["title"][:80])
        print(f"총 {len(posts)}개")

    asyncio.run(test())
