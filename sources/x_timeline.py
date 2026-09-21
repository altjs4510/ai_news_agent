"""X(Twitter) 수집 — 개인 계정 로그인 세션 기반.

공식 API가 아니라 Playwright로 실제 로그인 세션을 통해 X를 읽는다. 두 가지 모드:
- XTimelineCollector: Following 홈 타임라인(팔로우 계정 한정, 핸들 화이트리스트로 재필터)
- XSearchCollector: 키워드 검색 — 팔로우 여부와 무관하게 바이럴/트렌드 게시물 탐지

X 이용약관상 자동 스크래핑은 금지 행위이며, 계정 정지 리스크를 감수하고 쓰는 경로다.
그래서 하루 1회(파이프라인 배치) 수준의 저빈도로만 호출할 것 — 그 이상 자주 돌리지 말 것.

전제: sources/x_login.py 를 먼저 1회 수동 실행해 로그인 세션을 state 파일에 저장해둬야 한다.
세션이 없거나 만료되면 조용히 스킵한다(다른 소스에 영향 없음) — main.py가 존재 여부를 확인한다.

X 웹앱 DOM은 예고 없이 바뀐다. 파싱 실패는 전체 실행을 죽이지 않고 해당 트윗만 건너뛴다.
"""

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from utils.logger import setup_logger

logger = setup_logger('x_timeline')

HOME_URL = "https://x.com/home"
SEARCH_URL = "https://x.com/search"


class XTimelineCollector:
    """개인 X 계정의 Following 홈 타임라인에서 최근 게시물을 수집."""

    def __init__(self, state_path: str, days: int = 1, limit: int = 20, max_scrolls: int = 8, handles: list[str] | None = None):
        self.state_path = state_path
        self.cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        self.limit = limit
        self.max_scrolls = max_scrolls
        # 개인 계정 Following 피드엔 AI와 무관한 기존 팔로우가 섞여 있어 화이트리스트로 거른다.
        # None/빈 리스트면 필터 없이 전부 통과(테스트용).
        self.handles = {h.lower() for h in handles} if handles else None

    async def fetch_posts(self):
        if not os.path.exists(self.state_path):
            logger.warning(f"X 로그인 세션 파일 없음({self.state_path}) — sources/x_login.py 로 1회 로그인 필요. 스킵")
            return []

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("playwright 미설치 — `uv add playwright && uv run playwright install chromium` 필요. 스킵")
            return []

        posts = []
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(storage_state=self.state_path)
                page = await context.new_page()
                try:
                    await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=30000)

                    if "/login" in page.url or "/i/flow/login" in page.url:
                        logger.error("X 로그인 세션 만료 — sources/x_login.py 로 재로그인 필요. 스킵")
                        return []

                    # "Following" 탭(팔로우 계정만 시간순) 우선 — 없으면 기본 탭(For you)으로 진행
                    try:
                        following_tab = page.get_by_role("tab", name=re.compile("Following|팔로우 중"))
                        await following_tab.click(timeout=5000)
                        await page.wait_for_timeout(1500)
                    except Exception:
                        logger.debug("Following 탭을 찾지 못함 — 기본 타임라인으로 진행")

                    # 화이트리스트 필터링 전 raw article 수로는 매칭 개수를 예측할 수 없으니
                    # (팔로우 중인 비-AI 계정이 섞여 있음) 스크롤 횟수를 그대로 다 채운다.
                    for _ in range(self.max_scrolls):
                        await page.mouse.wheel(0, 2400)
                        await page.wait_for_timeout(1500)

                    articles = await page.locator('article[data-testid="tweet"]').all()
                    for article in articles:
                        post = await _parse_tweet_article(article, self.cutoff)
                        if not post:
                            continue
                        if self.handles is not None and post["_handle"].lower() not in self.handles:
                            continue
                        posts.append(_finalize_post(post))
                        if len(posts) >= self.limit:
                            break
                finally:
                    await browser.close()
        except Exception as e:
            logger.error(f"X 타임라인 수집 실패: {e}", exc_info=True)
            return []

        logger.info(f"X 타임라인 수집 완료: {len(posts)}개")
        return posts


class XSearchCollector:
    """키워드 검색으로 팔로우 여부와 무관한 바이럴/트렌드 게시물을 수집.

    X 검색 연산자(since:/until:/min_faves:)를 그대로 쿼리에 박아 서버 사이드에서
    날짜·인게이지먼트 범위를 먼저 좁힌다. 정렬은 기본(Top, 인게이지먼트 기준) —
    "최신"이 아니라 "바이럴"이 목적이라 시간순(Latest) 대신 이걸 쓴다.
    """

    def __init__(
        self,
        state_path: str,
        keywords: list[str],
        days: int = 1,
        limit_per_keyword: int = 10,
        max_scrolls: int = 4,
        min_faves: int = 200,
    ):
        self.state_path = state_path
        self.keywords = keywords
        self.days = days
        self.limit_per_keyword = limit_per_keyword
        self.max_scrolls = max_scrolls
        self.min_faves = min_faves
        self.cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async def fetch_posts(self):
        if not os.path.exists(self.state_path):
            logger.warning(f"X 로그인 세션 파일 없음({self.state_path}) — sources/x_login.py 로 1회 로그인 필요. 스킵")
            return []
        if not self.keywords:
            return []

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("playwright 미설치 — `uv add playwright && uv run playwright install chromium` 필요. 스킵")
            return []

        posts = []
        seen_urls = set()
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(storage_state=self.state_path)
                page = await context.new_page()
                try:
                    for keyword in self.keywords:
                        try:
                            found = await self._search_keyword(page, keyword)
                        except Exception as e:
                            logger.error(f"X 검색 실패 (\"{keyword}\"): {e}", exc_info=True)
                            continue
                        for post in found:
                            if post["url"] in seen_urls:
                                continue
                            seen_urls.add(post["url"])
                            posts.append(post)
                        await page.wait_for_timeout(1500)
                finally:
                    await browser.close()
        except Exception as e:
            logger.error(f"X 검색 수집 실패: {e}", exc_info=True)
            return []

        logger.info(f"X 검색 수집 완료: {len(posts)}개 ({len(self.keywords)}개 키워드)")
        return posts

    async def _search_keyword(self, page, keyword: str):
        since = self.cutoff.strftime("%Y-%m-%d")
        until = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
        query = f'{keyword} min_faves:{self.min_faves} since:{since} until:{until}'
        url = f"{SEARCH_URL}?q={quote(query)}&src=typed_query"

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        if "/login" in page.url or "/i/flow/login" in page.url:
            logger.error("X 로그인 세션 만료 — sources/x_login.py 로 재로그인 필요. 스킵")
            return []

        await page.wait_for_timeout(2000)
        for _ in range(self.max_scrolls):
            await page.mouse.wheel(0, 2400)
            await page.wait_for_timeout(1500)

        found = []
        articles = await page.locator('article[data-testid="tweet"]').all()
        for article in articles:
            post = await _parse_tweet_article(article, self.cutoff)
            if not post:
                continue
            final = _finalize_post(post, matched_keyword=keyword)
            found.append(final)
            if len(found) >= self.limit_per_keyword:
                break

        logger.info(f"X 검색 \"{keyword}\": {len(found)}개")
        return found


async def _parse_tweet_article(article, cutoff):
    """공통 트윗 파싱. cutoff 이전이거나 필수 필드가 없으면 None."""
    try:
        time_el = article.locator("time").first
        datetime_attr = await time_el.get_attribute("datetime")
        if not datetime_attr:
            return None
        dt = datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
        if dt < cutoff:
            return None

        permalink = ""
        link = time_el.locator("xpath=..")
        href = await link.get_attribute("href")
        if href:
            permalink = f"https://x.com{href}"

        handle = ""
        user_name_text = await article.locator('div[data-testid="User-Name"]').first.inner_text()
        handle_match = re.search(r"@(\w+)", user_name_text or "")
        if handle_match:
            handle = handle_match.group(1)

        text = ""
        text_locator = article.locator('div[data-testid="tweetText"]').first
        if await text_locator.count() > 0:
            text = (await text_locator.inner_text()).strip()
        if not text or not permalink:
            return None

        is_repost = await article.locator('div[data-testid="socialContext"]').count() > 0

        engagement = "-"
        group = article.locator('div[role="group"][aria-label]').first
        if await group.count() > 0:
            aria_label = await group.get_attribute("aria-label") or ""
            replies = _extract_count(aria_label, r"(\d[\d,]*)\s*repl")
            reposts = _extract_count(aria_label, r"(\d[\d,]*)\s*repost")
            likes = _extract_count(aria_label, r"(\d[\d,]*)\s*like")
            engagement = f"❤ {likes} · 🔁 {reposts} · 💬 {replies}"

        return {
            "_handle": handle,
            "_text": text,
            "_permalink": permalink,
            "_dt": dt,
            "_is_repost": is_repost,
            "_engagement": engagement,
        }
    except Exception as e:
        logger.debug(f"X 트윗 파싱 스킵: {e}")
        return None


def _finalize_post(parsed: dict, matched_keyword: str | None = None) -> dict:
    handle = parsed["_handle"]
    text = parsed["_text"]
    tag = "🔁 repost" if parsed["_is_repost"] else "post"
    title = (text[:80] + "…") if len(text) > 80 else text
    source = f"X - @{handle}" if handle else "X"
    if matched_keyword:
        source = f'{source} (검색: "{matched_keyword}")'
    return {
        "source": source,
        "title": title.replace("\n", " "),
        "url": parsed["_permalink"],
        "published_at": parsed["_dt"].isoformat(),
        "tag": tag,
        "engagement": parsed["_engagement"],
        "content": text,
    }


def _extract_count(aria_label: str, pattern: str) -> str:
    m = re.search(pattern, aria_label, re.IGNORECASE)
    return m.group(1) if m else "0"


if __name__ == "__main__":
    import asyncio
    import json

    async def test():
        c = XTimelineCollector(state_path="state/x_auth_state.json", days=1, limit=10)
        posts = await c.fetch_posts()
        print(json.dumps(posts, indent=2, ensure_ascii=False))

    asyncio.run(test())
