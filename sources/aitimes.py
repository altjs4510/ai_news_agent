import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
import re
from utils.logger import setup_logger

logger = setup_logger('aitimes')

class AITimesCrawler:
    def __init__(self):
        self.base_url = "https://www.aitimes.com"
        self.list_url = f"{self.base_url}/news/articleList.html?sc_sub_section_code=S2N110&view_type=sm"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        logger.info("AITimesCrawler 초기화 완료")

    async def fetch_articles(self):
        articles = []
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                logger.info(f"뉴스 수집 시작: {self.list_url}")
                async with session.get(self.list_url) as response:
                    if response.status != 200:
                        logger.error(f"뉴스 브리핑 페이지 접근 실패: {response.status}")
                        return articles

                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    # 뉴스 브리핑 기사 목록 찾기
                    article_items = soup.select("#section-list > ul > li")
                    logger.info(f"발견된 기사 수: {len(article_items)}")
                    
                    if not article_items:
                        logger.error("기사를 찾을 수 없습니다.")
                        return articles

                    # 병렬 처리를 위한 작업 목록 생성
                    tasks = []
                    for item in article_items[:7]:  # 최근 7개만
                        try:
                            # 제목과 링크 추출
                            title_tag = item.select_one("h4.titles a")
                            if not title_tag:
                                logger.debug(f"제목 태그 없음. HTML: {item}")
                                continue

                            title = title_tag.get_text(strip=True)
                            relative_url = title_tag.get("href", "")
                            
                            if not relative_url:
                                logger.warning(f"URL 없음: {title}")
                                continue

                            # URL 정규화
                            article_url = self.base_url + relative_url if relative_url.startswith("/") else relative_url
                            
                            # 날짜 정보 추출
                            date_tag = item.select_one("span.byline")
                            published_at = date_tag.get_text(strip=True) if date_tag else datetime.now().strftime("%Y-%m-%d %H:%M")
                            
                            # 작업 추가
                            task = self._process_article(session, title, article_url, published_at)
                            tasks.append(task)

                        except Exception as e:
                            logger.error(f"개별 기사 처리 실패: {str(e)}", exc_info=True)
                            continue

                    # 모든 기사 병렬 처리
                    if tasks:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        for result in results:
                            if isinstance(result, dict):  # 성공적으로 처리된 기사
                                articles.append(result)
                            elif isinstance(result, Exception):  # 에러 발생
                                logger.error(f"기사 처리 중 에러 발생: {str(result)}")

            except Exception as e:
                logger.error(f"AI Times 크롤링 실패: {str(e)}", exc_info=True)

        logger.info(f"총 {len(articles)}개의 기사가 수집되었습니다.")
        return articles

    async def _process_article(self, session, title, url, published_at):
        """개별 기사를 처리합니다."""
        content = await self._fetch_article_content(session, url)
        if not content:
            raise ValueError(f"내용을 가져올 수 없음: {title}")

        logger.info(f"기사 추가: {title}")
        return {
            "source": "AI타임스",
            "title": title,
            "url": url,
            "content": content,
            "published_at": published_at
        }

    async def _fetch_article_content(self, session, url):
        """기사 본문을 가져옵니다."""
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"기사 접근 실패: {url} - {response.status}")
                    return ""

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                # 본문 영역 찾기
                content_div = soup.select_one("#article-view-content-div")
                if not content_div:
                    logger.warning(f"본문 영역을 찾을 수 없음: {url}")
                    return ""

                # 불필요한 요소 제거
                for tag in content_div.select("script, style, iframe"):
                    tag.decompose()

                # 텍스트 추출 및 정리
                text = content_div.get_text(strip=True)
                text = re.sub(r'\s+', ' ', text)  # 연속된 공백 제거
                return text

        except Exception as e:
            logger.error(f"기사 본문 가져오기 실패 ({url}): {str(e)}", exc_info=True)
            return ""

if __name__ == "__main__":
    import asyncio
    import json

    async def test():
        crawler = AITimesCrawler()
        articles = await crawler.fetch_articles()
        logger.info("\n=== 수집된 기사 목록 ===")
        logger.info(json.dumps(articles, indent=2, ensure_ascii=False))
        logger.info(f"\n총 {len(articles)}개의 기사가 수집되었습니다.")

    asyncio.run(test())