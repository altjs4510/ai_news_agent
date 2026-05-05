import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import asyncio
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import aiohttp
from bs4 import BeautifulSoup

from utils.logger import setup_logger

logger = setup_logger('ai_blogs')

UA = "Mozilla/5.0 (compatible; ai-news-agent/0.1)"


def _strip_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def _local(tag: str) -> str:
    """ElementTree tag → namespace 제거한 local name."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


# 에이전트·MCP·코딩 에이전트·멀티에이전트 프레임워크 피드.
# (사용자 메인 프로젝트 DCSAI / Team Agent 키워드 매칭용)
DEV_AGENT_FEEDS = [
    # MCP·agent 본진
    ("https://simonwillison.net/atom/everything/", "Simon Willison"),
    ("https://www.latent.space/feed", "Latent Space"),
    ("https://blog.langchain.com/rss/", "LangChain Blog"),
    ("https://medium.com/feed/llamaindex-blog", "LlamaIndex Blog"),
    # 코딩 에이전트 비교 (Claude Code plugin/skill/hook 학습)
    ("https://github.com/getcursor/cursor/releases.atom", "Cursor Releases"),
    ("https://github.com/cline/cline/releases.atom", "Cline Releases"),
    ("https://github.com/Aider-AI/aider/releases.atom", "Aider Releases"),
    # 멀티에이전트 프레임워크
    ("https://devblogs.microsoft.com/autogen/feed/", "Microsoft AutoGen"),
    ("https://github.com/crewAIInc/crewAI/releases.atom", "CrewAI Releases"),
    ("https://github.com/google/adk-python/releases.atom", "Google ADK Releases"),
    ("https://github.com/openai/openai-agents-python/releases.atom", "OpenAI Agents SDK Releases"),
    # X 대체 — 큐레이션 뉴스레터 (트위터 담론 압축본)
    ("https://tldr.tech/api/rss/ai", "TLDR AI"),
    ("https://www.therundown.ai/feed", "The Rundown AI"),
    ("https://alphasignal.ai/feed", "AlphaSignal"),
    ("https://www.bensbites.com/feed", "Ben's Bites"),
    ("https://www.deeplearning.ai/the-batch/feed/", "Andrew Ng — The Batch"),
    # 개인 엔지니어링 블로그 (고신호)
    ("https://karpathy.bearblog.dev/feed/", "Karpathy"),
    ("https://lilianweng.github.io/index.xml", "Lilian Weng"),
    ("https://eugeneyan.com/rss/", "Eugene Yan"),
    ("https://huyenchip.com/feed.xml", "Chip Huyen"),
    ("https://hamel.dev/index.xml", "Hamel Husain"),
    # AI 엔지니어링 워크샵 (TS·에이전트·evals 실습 톤 — 다른 소스에 없는 결).
    # cutoff(7일) 필터로 evergreen 글이 매번 등장하는 건 자동 차단.
    ("https://www.aihero.dev/rss.xml", "Matt Pocock — AI Hero"),
]


class AIBlogCollector:
    """AI 블로그 통합 수집기 — 공식 회사 블로그 + 에이전트/MCP 엔지니어링 블로그.

    state_file이 주어지면 cross-run URL dedup 적용 — 한 번 fetch_posts에서
    수집된 URL은 그 이후 run에선 제외. aihero.dev처럼 RSS pubDate가 모든
    아이템에 동일한 build time으로 박혀서 7일 cutoff가 무력한 소스를 위한
    안전망. 일반 RSS도 부수효과로 같은 글 중복 노출 방지."""

    SEEN_URL_CAP = 1500  # 무한 증가 방지용 롤링 cap

    def __init__(
        self,
        days: int = 7,
        per_source_limit: int = 15,
        per_extra_limit: int = 5,
        state_file: Path | str | None = None,
    ):
        self.cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        self.per_source_limit = per_source_limit
        # 에이전트/엔지니어링 피드는 노이즈가 많아 별도 더 작은 cap 적용
        self.per_extra_limit = per_extra_limit
        self.state_file = Path(state_file) if state_file else None
        self._seen_urls: set[str] = self._load_seen()

    def _load_seen(self) -> set[str]:
        if not self.state_file or not self.state_file.exists():
            return set()
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return set(data.get("urls", []))
        except Exception as e:
            logger.warning(f"seen-URL state 로드 실패, 빈 셋으로 시작: {e}")
            return set()

    def _save_seen(self, fresh_urls: set[str]) -> None:
        if not self.state_file:
            return
        merged = self._seen_urls | fresh_urls
        # 롤링 cap — 너무 오래된 URL은 자연 만료
        urls_sorted = sorted(merged)
        if len(urls_sorted) > self.SEEN_URL_CAP:
            urls_sorted = urls_sorted[-self.SEEN_URL_CAP:]
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(
                json.dumps({"urls": urls_sorted}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"seen-URL state 저장 실패: {e}")

    async def fetch_posts(self):
        # Meta AI 블로그는 SPA로 server HTML에서 제목 추출이 어려워 임시 보류.
        official_tasks = [
            self._fetch_anthropic(),
            self._fetch_openai(),
            self._fetch_google(),
            self._fetch_deepmind(),
        ]
        extra_tasks = [
            self._fetch_feed(url, name, limit=self.per_extra_limit)
            for url, name in DEV_AGENT_FEEDS
        ]
        results = await asyncio.gather(*official_tasks, *extra_tasks, return_exceptions=True)
        all_posts = []
        for r in results:
            if isinstance(r, list):
                all_posts.extend(r)
            elif isinstance(r, Exception):
                logger.error(f"AI 블로그 수집 부분 실패: {r}")

        # cross-run dedup: state_file이 설정되어 있을 때만.
        # 이전 run에서 이미 등장한 URL은 제외 — aihero.dev처럼 pubDate가 망가진
        # 소스가 같은 워크샵을 매번 떠넘기는 걸 차단.
        all_urls = {p["url"] for p in all_posts if p.get("url")}
        if self.state_file:
            fresh_posts = [p for p in all_posts if p.get("url") not in self._seen_urls]
            self._save_seen(all_urls)
            logger.info(
                f"AI 블로그 총 {len(all_posts)}개 수집 → "
                f"신규 {len(fresh_posts)}개 (dedup {len(all_posts) - len(fresh_posts)}개 제외)"
            )
            return fresh_posts

        logger.info(f"AI 블로그 총 {len(all_posts)}개 수집")
        return all_posts

    async def _get(self, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={"User-Agent": UA}, timeout=30) as resp:
                resp.raise_for_status()
                return await resp.text()

    async def _fetch_rss(self, url: str, source_name: str):
        # 기존 호출자(공식 RSS)는 self.per_source_limit 사용
        return await self._fetch_feed(url, source_name, limit=self.per_source_limit)

    async def _fetch_feed(self, url: str, source_name: str, limit: int | None = None):
        """RSS 2.0과 Atom 1.0 모두 처리하는 범용 피드 파서."""
        cap = limit if limit is not None else self.per_source_limit
        try:
            text = await self._get(url)
        except Exception as e:
            logger.error(f"{source_name} 피드 요청 실패: {e}")
            return []

        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            logger.error(f"{source_name} 피드 파싱 실패: {e}")
            return []

        posts = []
        for el in root.iter():
            if _local(el.tag) not in ("item", "entry"):
                continue

            title = ""
            link = ""
            desc = ""
            pub_str = ""

            for child in el:
                ltag = _local(child.tag)
                if ltag == "title" and not title:
                    title = (child.text or "").strip()
                elif ltag == "link":
                    # Atom: <link href=".."/>; RSS: <link>..</link>
                    href = child.get("href")
                    if href and not link:
                        link = href.strip()
                    elif (child.text or "").strip() and not link:
                        link = child.text.strip()
                elif ltag in ("pubDate", "published", "updated") and not pub_str:
                    pub_str = (child.text or "").strip()
                elif ltag in ("description", "summary", "content") and not desc:
                    desc = (child.text or "").strip()

            dt = None
            if pub_str:
                try:
                    dt = parsedate_to_datetime(pub_str)
                except (TypeError, ValueError):
                    dt = None
                if dt is None:
                    # ISO 8601 (Atom)
                    try:
                        s = pub_str.replace("Z", "+00:00")
                        dt = datetime.fromisoformat(s)
                    except ValueError:
                        dt = None
                if dt and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)

            if dt and dt < self.cutoff:
                continue
            if not title or not link:
                continue

            posts.append({
                "source": source_name,
                "title": title,
                "url": link,
                "published_at": dt.isoformat() if dt else "",
                "content": _strip_html(desc) or title,
            })
            if len(posts) >= cap:
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

            # 날짜 추출 실패하거나 cutoff보다 오래된 글은 제외 (cutoff 정확성 보장)
            if dt is None or dt < self.cutoff:
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


    async def _fetch_deepmind(self):
        """DeepMind blog (HTML 스크래핑, 날짜 정보 부재 → 최근 게시물 한정)."""
        url = "https://deepmind.google/discover/blog/"
        try:
            text = await self._get(url)
        except Exception as e:
            logger.error(f"DeepMind Blog 요청 실패: {e}")
            return []

        soup = BeautifulSoup(text, "html.parser")
        seen = set()
        posts = []
        for a in soup.select("article a[href*='/blog/']"):
            href = a.get("href", "")
            if not href or href in seen:
                continue
            if "/blog/" not in href or href.rstrip("/").endswith("/blog"):
                continue
            seen.add(href)
            title = a.get_text(separator=" ", strip=True)
            if not title or len(title) < 8 or title.lower() in {"learn more", "read more"}:
                continue
            full_url = href if href.startswith("http") else f"https://deepmind.google{href}"
            posts.append({
                "source": "DeepMind Blog",
                "title": title[:200],
                "url": full_url,
                "published_at": "",
                "content": title[:200],
            })
            if len(posts) >= self.per_source_limit:
                break

        logger.info(f"DeepMind Blog 수집 완료: {len(posts)}개")
        return posts

    async def _fetch_meta_ai(self):
        """Meta AI blog (HTML 스크래핑, 날짜 정보 부재 → 최근 게시물 한정)."""
        url = "https://ai.meta.com/blog/"
        try:
            text = await self._get(url)
        except Exception as e:
            logger.error(f"Meta AI Blog 요청 실패: {e}")
            return []

        soup = BeautifulSoup(text, "html.parser")
        seen = set()
        posts = []
        for a in soup.select("a[href*='ai.meta.com/blog/']"):
            href = a.get("href", "")
            if not href or href in seen:
                continue
            if href.rstrip("/").endswith("/blog"):
                continue
            seen.add(href)
            title = a.get_text(separator=" ", strip=True)
            if not title or len(title) < 8 or title.lower() in {"featured", "learn more", "read more"}:
                # 부모 element에서 다른 텍스트 시도
                parent_text = a.find_parent().get_text(separator=" ", strip=True) if a.find_parent() else ""
                title = parent_text[:200] if parent_text else title
            if not title:
                continue
            posts.append({
                "source": "Meta AI Blog",
                "title": title[:200],
                "url": href,
                "published_at": "",
                "content": title[:200],
            })
            if len(posts) >= self.per_source_limit:
                break

        logger.info(f"Meta AI Blog 수집 완료: {len(posts)}개")
        return posts


if __name__ == "__main__":
    import json

    async def test():
        collector = AIBlogCollector(days=14)
        posts = await collector.fetch_posts()
        print(json.dumps(posts, indent=2, ensure_ascii=False))

    asyncio.run(test())
