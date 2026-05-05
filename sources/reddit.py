import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import praw
from datetime import datetime, timedelta
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, REDDIT_SUBREDDITS
import asyncio
from utils.logger import setup_logger

logger = setup_logger('reddit')

class RedditCollector:
    def __init__(self, days: int = 1):
        self.reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )
        self.since = datetime.utcnow() - timedelta(days=days)
        logger.info("RedditCollector 초기화 완료")

    async def fetch_posts(self):
        """Reddit 게시물을 비동기적으로 수집합니다."""
        posts = []
        loop = asyncio.get_event_loop()

        for subreddit_name in REDDIT_SUBREDDITS:
            try:
                logger.info(f"서브레딧 수집 시작: r/{subreddit_name}")
                # Reddit API 호출을 비동기적으로 처리
                subreddit = self.reddit.subreddit(subreddit_name)
                
                # 비동기 실행을 위해 run_in_executor 사용
                async def fetch_subreddit_posts():
                    return [post for post in subreddit.top(time_filter="week", limit=10)]
                
                subreddit_posts = await loop.run_in_executor(None, lambda: list(subreddit.top(time_filter="week", limit=10)))
                
                for post in subreddit_posts:
                    created = datetime.utcfromtimestamp(post.created_utc)
                    if created < self.since:
                        logger.debug(f"오래된 게시물 제외: {post.title}")
                        continue

                    logger.info(f"게시물 추가: {post.title}")
                    posts.append({
                        "source": f"Reddit - r/{subreddit_name}",
                        "title": post.title,
                        "url": f"https://www.reddit.com{post.permalink}",
                        "published_at": created.isoformat(),
                        "content": post.selftext or post.title
                    })
            except Exception as e:
                logger.error(f"Reddit 수집 실패: r/{subreddit_name} - {str(e)}", exc_info=True)

        logger.info(f"총 {len(posts)}개의 Reddit 게시물이 수집되었습니다.")
        return posts

if __name__ == "__main__":
    import json

    async def test():
        collector = RedditCollector()
        posts = await collector.fetch_posts()
        logger.info("\n=== 수집된 Reddit 게시물 목록 ===")
        logger.info(json.dumps(posts, indent=2, ensure_ascii=False))

    asyncio.run(test())
