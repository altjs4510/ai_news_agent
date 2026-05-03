import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import asyncio
from datetime import datetime, timedelta

import aiohttp
from bs4 import BeautifulSoup

from utils.logger import setup_logger

logger = setup_logger('github_trending')

# DCSAI / Team Agent 키워드 매칭용 GitHub 토픽 (Search API).
# github.com/trending 스크래핑은 언어별 인기에만 의존하므로 MCP/agent 생태계 흐름을
# 놓치기 쉬워, topic 기반 Search API 결과를 함께 수집한다.
GITHUB_TOPICS = ["mcp-server", "agent", "multi-agent"]


class GitHubTrendingCollector:
    """github.com/trending 스크래퍼 + GitHub Search API(topic) 보조 수집."""

    BASE_URL = "https://github.com/trending"
    SEARCH_URL = "https://api.github.com/search/repositories"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (compatible; ai-news-agent/0.1)",
        "Accept": "text/html",
    }
    SEARCH_HEADERS = {
        "User-Agent": "Mozilla/5.0 (compatible; ai-news-agent/0.1)",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    def __init__(self, since: str = "weekly", language: str = "", limit: int = 25, topic_limit: int = 8, days: int = 7):
        self.since = since
        self.language = language
        self.limit = limit
        self.topic_limit = topic_limit
        self.days = days

    async def fetch_repos(self):
        """언어별 트렌딩 + 토픽별 검색을 모두 수집해 합쳐 반환 (URL 기준 중복 제거)."""
        trending = await self._fetch_trending_html()
        topical = await self._fetch_topics()

        merged = []
        seen_urls = set()
        for item in trending + topical:
            url = item.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            merged.append(item)

        logger.info(
            f"GitHub 수집 통합: trending {len(trending)} + topics {len(topical)} → {len(merged)} (중복 제거 후)"
        )
        return merged

    async def _fetch_trending_html(self):
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

    async def _fetch_topics(self):
        """GitHub Search API로 topic + 최근 push 기준 인기 저장소 수집.

        unauth rate limit: 10 req/min. 토픽 3개라 단일 실행 안에서 안전.
        토큰이 있으면 ``GITHUB_TOKEN`` 환경변수로 30 req/min 적용.
        """
        since_date = (datetime.now() - timedelta(days=self.days)).strftime("%Y-%m-%d")
        token = os.getenv("GITHUB_TOKEN")
        headers = dict(self.SEARCH_HEADERS)
        if token:
            headers["Authorization"] = f"Bearer {token}"

        all_items = []
        try:
            async with aiohttp.ClientSession() as session:
                for topic in GITHUB_TOPICS:
                    q = f"topic:{topic} pushed:>{since_date}"
                    params = {
                        "q": q,
                        "sort": "stars",
                        "order": "desc",
                        "per_page": str(self.topic_limit),
                    }
                    try:
                        async with session.get(
                            self.SEARCH_URL, params=params, headers=headers, timeout=30
                        ) as resp:
                            if resp.status != 200:
                                body = (await resp.text())[:200]
                                logger.error(
                                    f"GitHub Search topic={topic} HTTP {resp.status}: {body}"
                                )
                                continue
                            data = await resp.json()
                    except Exception as e:
                        logger.error(
                            f"GitHub Search topic={topic} 실패: {e}", exc_info=True
                        )
                        continue

                    for item in data.get("items", []):
                        full_name = item.get("full_name", "")
                        repo_url = item.get("html_url", "")
                        if not full_name or not repo_url:
                            continue
                        description = item.get("description") or ""
                        language = item.get("language") or ""
                        total_stars = item.get("stargazers_count", 0)
                        pushed_at = item.get("pushed_at") or ""
                        all_items.append({
                            "source": f"GitHub Topic ({topic})",
                            "title": full_name,
                            "url": repo_url,
                            "published_at": pushed_at or datetime.now().isoformat(),
                            "description": description,
                            "language": language,
                            "stars_period": "",  # API에는 기간별 별 증가 정보 없음
                            "total_stars": str(total_stars),
                            "content": (
                                f"{full_name}\n"
                                f"{description}\n"
                                f"language: {language} | total stars: {total_stars} | "
                                f"topic: {topic} | last push: {pushed_at}"
                            ),
                        })
        except Exception as e:
            logger.error(f"GitHub Topic 수집 전체 실패: {e}", exc_info=True)
            return []

        logger.info(f"GitHub Topic 수집 완료: {len(all_items)}개 ({len(GITHUB_TOPICS)} topics)")
        return all_items


if __name__ == "__main__":
    import json

    async def test():
        collector = GitHubTrendingCollector(since="weekly", limit=15)
        repos = await collector.fetch_repos()
        print(json.dumps(repos, indent=2, ensure_ascii=False))

    asyncio.run(test())
