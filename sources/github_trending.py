import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import asyncio
from datetime import datetime

import aiohttp
from bs4 import BeautifulSoup

from utils.logger import setup_logger

logger = setup_logger('github_trending')


class GitHubTrendingCollector:
    """github.com/trending 스크래퍼 (공식 API 없음)."""

    BASE_URL = "https://github.com/trending"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (compatible; ai-news-agent/0.1)",
        "Accept": "text/html",
    }

    def __init__(self, since: str = "weekly", language: str = "", limit: int = 25):
        self.since = since
        self.language = language
        self.limit = limit

    async def fetch_repos(self):
        url = f"{self.BASE_URL}/{self.language}" if self.language else self.BASE_URL
        params = {"since": self.since}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=self.HEADERS, timeout=30) as resp:
                    if resp.status != 200:
                        logger.error(f"GitHub Trending HTTP {resp.status}")
                        return []
                    html = await resp.text()
        except Exception as e:
            logger.error(f"GitHub Trending 페이지 요청 실패: {e}", exc_info=True)
            return []

        soup = BeautifulSoup(html, "html.parser")
        articles = soup.select("article.Box-row")

        repos = []
        for article in articles[: self.limit]:
            link = article.select_one("h2 a")
            if not link:
                continue

            href = link.get("href", "").strip()
            full_name = "".join(link.get_text().split())
            repo_url = f"https://github.com{href}"

            desc_el = article.select_one("p")
            description = desc_el.get_text(strip=True) if desc_el else ""

            lang_el = article.select_one('span[itemprop="programmingLanguage"]')
            language = lang_el.get_text(strip=True) if lang_el else ""

            stars_period = ""
            for span in article.select("span.d-inline-block.float-sm-right"):
                stars_period = span.get_text(strip=True)
                break

            star_links = article.select("a.Link--muted")
            total_stars = star_links[0].get_text(strip=True) if star_links else ""

            repos.append({
                "source": f"GitHub Trending ({self.since})",
                "title": full_name,
                "url": repo_url,
                "published_at": datetime.now().isoformat(),
                "description": description,
                "language": language,
                "stars_period": stars_period,
                "total_stars": total_stars,
                "content": (
                    f"{full_name}\n"
                    f"{description}\n"
                    f"language: {language} | stars this {self.since}: {stars_period} | total: {total_stars}"
                ),
            })

        logger.info(f"GitHub Trending {self.since} 수집 완료: {len(repos)}개")
        return repos


if __name__ == "__main__":
    import json

    async def test():
        collector = GitHubTrendingCollector(since="weekly", limit=15)
        repos = await collector.fetch_repos()
        print(json.dumps(repos, indent=2, ensure_ascii=False))

    asyncio.run(test())
