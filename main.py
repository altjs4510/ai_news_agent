import asyncio
import os
from sources.aitimes import AITimesCrawler
from sources.youtube import YouTubeParser
from sources.reddit import RedditCollector
from sources.github_trending import GitHubTrendingCollector
from sources.ai_blogs import AIBlogCollector
from delivery.markdown_writer import MarkdownWriter
from delivery.notion_writer import NotionWriter
from delivery.email_sender import EmailSender
from delivery.blog_publisher import BlogPublisher
from utils.logger import setup_logger
from datetime import datetime
import anthropic
from anthropic import Anthropic, AsyncAnthropic
from utils.html_cleaner import clean_markdown_file
import re
import traceback
import json

logger = setup_logger('main')


def _read_or_empty(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _write_summary_markdown(report_path: str, date_str: str, headline, spotlight, summary, keywords) -> None:
    display_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
    keywords_line = " · ".join(f"`{k}`" for k in (keywords or []))
    lines = [
        "---",
        f'title: "{display_date} 요약"',
        f"date: {display_date}",
        "---",
        "",
    ]
    if headline:
        lines += [f"> [!tldr] TL;DR", f"> {headline}", ""]
    if spotlight and isinstance(spotlight, dict) and spotlight.get("title"):
        title = spotlight.get("title", "")
        url = spotlight.get("url", "")
        why = spotlight.get("why", "")
        application = spotlight.get("application", "")
        link = f"[{title}]({url})" if url else f"**{title}**"
        lines += [
            "> [!example] 🎯 이번 호 PoC/공부 추천",
            f"> **{link}**",
            ">",
            f"> **왜 주목** — {why}",
            ">",
            f"> **어떻게 접목** — {application}",
            "",
        ]
    if keywords_line:
        lines += [f"> [!info] 이번 호 키워드", f"> {keywords_line}", ""]
    os.makedirs(report_path, exist_ok=True)
    with open(f"{report_path}/summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


async def main():
    """메인 실행 함수"""
    try:
        logger.info("=== AI 뉴스 수집 시작 ===")
        
        # 수집기 활성화 설정
        ENABLE_AITIMES = False
        ENABLE_YOUTUBE = False
        ENABLE_REDDIT = True
        ENABLE_GITHUB_TRENDING = True
        ENABLE_AI_BLOGS = True

        # 출력 채널 활성화 설정
        ENABLE_BLOG = True
        ENABLE_NOTION = False
        ENABLE_EMAIL = False

        # 수집기 초기화
        collectors = []
        if ENABLE_AITIMES:
            aitimes = AITimesCrawler()
            collectors.append(('aitimes', aitimes.fetch_articles()))
        if ENABLE_YOUTUBE:
            youtube = YouTubeParser()
            collectors.append(('youtube', youtube.fetch_videos()))
        if ENABLE_REDDIT:
            reddit = RedditCollector()
            collectors.append(('reddit', reddit.fetch_posts()))
        if ENABLE_GITHUB_TRENDING:
            github = GitHubTrendingCollector(since="weekly", limit=25)
            collectors.append(('github_trending', github.fetch_repos()))
        if ENABLE_AI_BLOGS:
            ai_blogs = AIBlogCollector(days=7, per_source_limit=15)
            collectors.append(('ai_blogs', ai_blogs.fetch_posts()))

        writer = MarkdownWriter()

        # 병렬로 콘텐츠 수집
        if collectors:
            tasks = [collector[1] for collector in collectors]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            results = []

        # 수집 결과 처리
        articles = []
        videos = []
        reddit_posts = []
        github_repos = []
        ai_blog_posts = []

        for i, (source_name, _) in enumerate(collectors):
            result = results[i] if i < len(results) and not isinstance(results[i], Exception) else []
            if source_name == 'aitimes':
                articles = result
            elif source_name == 'youtube':
                videos = result
            elif source_name == 'reddit':
                reddit_posts = result
            elif source_name == 'github_trending':
                github_repos = result
            elif source_name == 'ai_blogs':
                ai_blog_posts = result

        # 마크다운 파일 저장
        markdown_writer = MarkdownWriter()
        markdown_writer.save_raw_contents(articles, videos, reddit_posts, github_repos, ai_blog_posts)
        
        # Reddit 포스트 관련성 평가 및 필터링
        logger.info("Reddit 포스트 관련성 평가 중...")
        relevant_posts = []
        for post in reddit_posts:
            logger.info(f"제목 평가 중: {post['title']}")
            if await evaluate_post_relevance(post['title']):
                relevant_posts.append(post)
        logger.info(f"관련성 높은 포스트: {len(relevant_posts)}개")
        
        # Reddit 포스트 번역
        logger.info("원본 데이터 저장 중...")
        markdown_writer.save_raw_contents(articles, videos, relevant_posts, github_repos, ai_blog_posts)
        
        logger.info("번역 시작...")
        translated_posts = await translate_contents_batch(relevant_posts)
        markdown_writer._save_reddit_contents(translated_posts)
        
        # 공통 컨텐츠 로드
        today = datetime.now()
        date_str = today.strftime("%Y%m%d")
        report_path = f"reports/{date_str}"

        aitimes_content = _read_or_empty(f"{report_path}/aitimes_raw.md")
        youtube_content = _read_or_empty(f"{report_path}/youtube_raw.md")
        reddit_translated_content = _read_or_empty(f"{report_path}/reddit_translated.md")
        github_content = _read_or_empty(f"{report_path}/github_raw.md")
        ai_blogs_content = _read_or_empty(f"{report_path}/ai_blogs_raw.md")

        # 통합 인사이트 (모든 소스 종합)
        logger.info("통합 인사이트 추출 중...")
        await summarize_combined_insights(ai_blogs_content, github_content, reddit_translated_content)
        combined_insights = _read_or_empty(f"{report_path}/combined_insights.md")

        summary, keywords = None, None
        headline = ""
        spotlight = None
        if ENABLE_BLOG or ENABLE_NOTION:
            try:
                headline, spotlight, summary, keywords = await generate_summary_and_keywords(
                    aitimes_content, youtube_content, combined_insights, github_content, ai_blogs_content
                )
                _write_summary_markdown(report_path, date_str, headline, spotlight, summary, keywords)
            except Exception as e:
                logger.error(f"요약/키워드 생성 실패: {e}")

        blog_url = None
        if ENABLE_BLOG:
            try:
                publisher = BlogPublisher()
                blog_url = publisher.publish(report_path, date_str)
                if blog_url:
                    logger.info(f"블로그 publish 완료: {blog_url}")
            except Exception as e:
                logger.error(f"블로그 publish 중 오류 발생: {str(e)}")

        page_id = None
        if ENABLE_NOTION:
            try:
                notion_writer = NotionWriter()
                page_id = notion_writer.create_ai_news_page(
                    date_str=date_str,
                    keywords=keywords or [],
                    summary=summary or [],
                    aitimes_content=aitimes_content,
                    youtube_content=youtube_content,
                    reddit_insights=reddit_insights
                )
                logger.info(f"Notion 페이지가 생성되었습니다. Page ID: {page_id}")
            except Exception as e:
                logger.error(f"Notion 페이지 생성 중 오류 발생: {str(e)}")

        if ENABLE_EMAIL and page_id:
            try:
                logger.info("이메일 알림 발송 중...")
                email_sender = EmailSender()
                email_sender.send_notion_page_notification(
                    date_str=date_str,
                    page_id=page_id,
                    summary=summary or [],
                    keywords=keywords or [],
                    reddit_url=blog_url,
                )
            except Exception as email_error:
                logger.error(f"이메일 발송 중 오류 발생: {str(email_error)}")

        logger.info("=== 작업 완료 ===")

    except Exception as e:
        logger.error(f"실행 중 오류 발생: {str(e)}")
        traceback.print_exc()

async def evaluate_post_relevance(title):
    """포스트 제목을 평가하여 AI 에이전트와의 관련성을 판단합니다."""
    try:
        # 제목에 중요 키워드가 있으면 바로 True 반환
        important_keywords = [
            'mcp', 'model context protocol', 'anthropic', 'claude',
            'agent', 'ai agent', 'workflow', 'automation', 'tutorial',
            'guide', 'how to', 'tips', 'best practices'
        ]
        if any(keyword.lower() in title.lower() for keyword in important_keywords):
            logger.info(f"✅ 중요 키워드 발견: {title}")
            return True

        # 명확한 제외 키워드가 있으면 바로 False 반환
        exclude_keywords = ['chat', 'daily', 'thread', 'megathread', 'news']
        if any(keyword.lower() in title.lower() for keyword in exclude_keywords):
            logger.info(f"❌ 제외 키워드 발견: {title}")
            return False

        # 키워드로 판단이 어려운 경우만 API 호출
        prompt = f"""다음 Reddit 포스트의 제목이 AI 에이전트 개발, 도구, 전략과 관련이 있는지 판단해주세요.

제목: {title}

다음 기준으로 가장 적합한 하나의 점수만 선택해주세요:

5: 매우 중요한 정보 (MCP, 에이전트 등 핵심 내용)
4: 유용한 정보/팁 (실용적인 구현 방법, 도구 소개 등)
3: 관련은 있으나 중요도 낮음
2: 홍보성 글이나 단순 소식
1: 단순 채팅/뉴스성 글

위 점수 중 하나만 숫자로 응답해주세요. 다른 텍스트나 설명은 포함하지 마세요."""

        client = AsyncAnthropic()
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip() if response.content else ""
        digits = re.findall(r"[1-5]", raw)
        score = int(digits[0]) if digits else 0
        is_relevant = score >= 4
        
        if is_relevant:
            logger.info(f"✅ 관련성 높음 (점수: {score}): {title}")
        else:
            logger.info(f"❌ 관련성 낮음 (점수: {score}): {title}")
            
        return is_relevant

    except Exception as e:
        logger.error(f"제목 평가 중 오류 발생 ({title}): {str(e)}")
        return False

async def translate_content(content):
    """Reddit 포스트의 영어 내용을 한글로 번역합니다."""
    try:
        title = content['title']
        logger.info(f"Reddit 포스트 번역 시작: {title[:30]}...")
        
        prompt = f"""다음 Reddit 포스트를 한국어로 번역해주세요:

제목: {title}
내용: {content['content']}

번역된 내용만 반환해주세요."""

        client = AsyncAnthropic()
        logger.info(f"Anthropic API 호출 중... ({title[:30]}...)")

        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )

        translated_text = response.content[0].text.strip() if response.content else ""
        logger.info(f"번역 완료: {title[:30]}...")
        
        return {
            'title': title,
            'url': content['url'],
            'content': translated_text,
            'original_content': content['content'],
            'source': content['source'],
            'published_at': content.get('published_at', '')
        }

    except Exception as e:
        logger.error(f"번역 실패 ({content.get('title', 'Unknown title')}): {str(e)}")
        return content

async def translate_contents_batch(contents, batch_size=3):
    """Reddit 포스트들을 배치로 번역합니다."""
    translated_contents = []
    total = len(contents)
    
    for i in range(0, total, batch_size):
        batch = contents[i:i + batch_size]
        logger.info(f"배치 번역 진행 중... ({i+1}-{min(i+batch_size, total)}/{total})")
        
        batch_results = await asyncio.gather(
            *[translate_content(content) for content in batch],
            return_exceptions=True
        )
        
        for result in batch_results:
            if isinstance(result, dict):
                translated_contents.append(result)
            elif isinstance(result, Exception):
                logger.error(f"배치 번역 중 오류 발생: {str(result)}")
        
        if i + batch_size < total:
            logger.info("다음 배치 처리를 위해 3초 대기...")
            await asyncio.sleep(3)
    
    return translated_contents

async def clean_textblock_from_file(filepath):
    """파일에서 TextBlock 메타데이터를 강제로 제거합니다."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 첫 4줄은 보존 (제목과 생성 시간)
        header_lines = content.split('\n')[:4]
        
        # TextBlock 찾기
        if '[TextBlock(' in content:
            # TextBlock의 text 부분만 추출
            text_content = content.split("text='", 1)[1].split("', type='text')]", 1)[0]
            
            # 이스케이프된 newline을 실제 newline으로 변환
            text_content = text_content.replace('\\n', '\n')
            
            # 최종 내용 조합
            final_content = '\n'.join(header_lines) + '\n' + text_content
            
            # 파일 다시 쓰기
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(final_content)
            logger.info(f"TextBlock 메타데이터 제거 완료: {filepath}")
            return True
        
        return False
    except Exception as e:
        logger.error(f"TextBlock 제거 중 오류 발생: {str(e)}")
        return False

async def summarize_combined_insights(ai_blogs_content: str, github_content: str, reddit_translated_content: str):
    """모든 수집 소스(AI 블로그·GitHub Trending·Reddit)를 종합한 인사이트 마크다운을 생성합니다."""
    try:
        logger.info("통합 인사이트 추출 시작")
        writer = MarkdownWriter()

        prompt = f"""다음은 이번 주 AI 관련 자료입니다. 모든 자료를 종합 분석해서 가독성 좋은 마크다운 인사이트 글을 작성해주세요.

==== AI 공식 블로그 (Anthropic / OpenAI / Google) ====
{ai_blogs_content[:6000]}

==== GitHub Trending (이번 주 인기 오픈소스) ====
{github_content[:3500]}

==== Reddit AI 커뮤니티 (한국어 번역본) ====
{reddit_translated_content[:9000]}

## 작성 규칙 (반드시 지키세요)

1. 자료에 등장한 마크다운 링크 [텍스트](URL)는 본문에 그대로 인용합니다. 자료에 없는 URL은 절대 만들지 마세요.
2. 각 단락은 **2~3문장**으로 짧게 끊습니다. 줄글이 길게 이어지면 안 됩니다.
3. 핵심 단어·제품명·회사명·개념은 **굵게** 강조합니다.
4. 단락 사이에는 빈 줄을 둡니다.
5. "이번 호", "수집된 자료" 같은 메타 멘트, 인사말, 결론 멘트는 금지합니다.
6. 출력은 순수 마크다운입니다. ```` ``` ```` 코드블록으로 감싸지 마세요.

## 출력 형식

# 전체 요약

(2~3 단락. 각 단락 2~3문장. 이번 주 AI 동향의 핵심 흐름을 명확하게 짚어줍니다.)

---

# 주제별 분석

## 1. (주제명을 한 줄로 명확하게)

**관련 자료**

- [제목](URL)
- [제목](URL)

**핵심 인사이트**

(2~3 단락. 각 단락 2~3문장. 단락 사이 빈 줄.)

## 2. (...)

(같은 구조)

(주제는 3~5개. 각 주제는 자료가 2개 이상 관련된 경우만 다룹니다. 출처는 모든 소스(AI 블로그·GitHub·Reddit)에서 자유롭게 인용합니다.)

---

# 주목할 만한 개별 발견

## (항목 제목 — 짧게)

- 출처: [링크](URL)

(1~2 단락의 독특한 인사이트. 주제별 분석에서 다루지 못한 단발성 정보만.)

(2~4개)"""

        client = Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=15000,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        # message.content는 list 형태일 수 있음
        if isinstance(message.content, list) and len(message.content) > 0:
            # 첫번째 TextBlock의 text 내용을 가져옴
            insights = message.content[0].text
        else:
            # 예상치 못한 형식이면 로그 남기고 빈 문자열 처리
            logger.warning(f"Unexpected Anthropic API response format: {type(message.content)}")
            insights = ""
        
        insights = insights.strip()
        # 코드 블록으로 감싸서 응답이 오면 제거
        insights = re.sub(r"^```[a-zA-Z]*\n", "", insights)
        insights = re.sub(r"\n```$", "", insights)

        filepath = writer.save_markdown(insights, "combined_insights.md")
        logger.info(f"통합 인사이트 저장 완료: {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"통합 인사이트 추출 실패: {str(e)}", exc_info=True)
        return None

async def generate_summary_and_keywords(aitimes_content, youtube_content, reddit_insights, github_content="", ai_blogs_content=""):
    """수집된 콘텐츠를 기반으로 전체 요약과 키워드를 생성합니다."""
    logger.info("요약 및 키워드 생성 시작")

    # 요약을 위한 프롬프트 생성
    prompt = f"""다음은 AI 관련 공식 블로그(Anthropic/OpenAI/Google), Reddit 인사이트, GitHub Trending, AI Times, YouTube 영상 자료입니다. 이를 바탕으로 아래 기준에 따라 정리해주세요.

자료의 각 항목에는 [텍스트](URL) 형태의 마크다운 링크가 포함되어 있으니, 인용할 때 그 URL을 그대로 본문에 가져다 쓰세요.

==== 공식 AI 블로그 ====
{ai_blogs_content[:3500]}

==== Reddit 인사이트 ====
{reddit_insights[:4000]}

==== GitHub Trending (이번 주) ====
{github_content[:3000]}

==== AI Times ====
{aitimes_content[:2000]}

==== YouTube ====
{youtube_content[:2000]}

## 사용자 프로젝트 컨텍스트 (Spotlight 작성 시 활용)
사용자는 ai_news_agent를 운영합니다:
- Python 기반 AI 동향 자동 수집·번역·요약·블로그 발행 파이프라인
- 수집 소스: Reddit (AI 서브레딧), GitHub Trending, Anthropic/OpenAI/Google 공식 블로그
- LLM: Anthropic Claude (Haiku 4.5 평가/번역, Sonnet 4.6 요약)
- 출력: Quartz 정적 블로그로 GitHub Pages에 자동 발행

## 작성 규칙 (반드시 지키세요)

1. **headline (1줄, 80자 내외)** — 이번 호를 관통하는 핵심 흐름.

2. **spotlight (1개만)** — 자료 중에서 사용자가 직접 PoC하거나 공부하면 가장 도움이 될 항목 1개를 선정하세요. 가능하면 ai_news_agent에 접목 가능성이 높거나 AI 에이전트 운영 학습 가치가 큰 것을 우선합니다.
   - title: 항목 이름 (저장소·제품·기능·블로그 글 제목 등)
   - url: 자료에 등장한 URL (절대 임의 생성 금지)
   - why: 왜 주목할 만한지 1~2문장
   - application: ai_news_agent의 어떤 부분(수집기, 번역, 요약, 발행, 운영)에 어떻게 접목할지 구체적 제안 1~2문장

3. **keywords 5개** — 이번 호 핵심 주제 (각 2~3 단어).

4. 인사말·결론 멘트 금지.

## 응답 형식 (JSON, 다른 텍스트 금지)
{{
  "headline": "...",
  "spotlight": {{
    "title": "...",
    "url": "https://...",
    "why": "...",
    "application": "..."
  }},
  "keywords": ["...", "...", "...", "...", "..."]
}}"""

    try:
        # Claude API 호출
        client = Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=6000,
            temperature=0.2,
            system="너는 AI 뉴스 분석과 요약을 전문으로 하는 Assistant입니다. 주어진 콘텐츠에서 핵심 내용을 파악하고 출처 링크를 포함해 정확하게 요약합니다. 응답은 항상 단일 JSON 객체여야 합니다.",
            messages=[{"role": "user", "content": prompt}]
        )

        # 응답에서 JSON 형식 추출 (코드 블록 제거 후 첫 { ~ 마지막 })
        result_text = response.content[0].text
        logger.info(f"응답 길이: {len(result_text)}")
        cleaned = re.sub(r"^```(?:json)?\s*", "", result_text.strip())
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            json_str = cleaned[start : end + 1]
            result_json = json.loads(json_str)
            headline = result_json.get('headline', '')
            spotlight = result_json.get('spotlight') or None
            summary = result_json.get('summary', [])  # legacy, 더 이상 사용 안 함
            keywords = result_json.get('keywords', [])

            if not headline and not spotlight:
                raise ValueError("헤드라인/스포트라이트가 생성되지 않았습니다.")
            if not keywords or len(keywords) < 5:
                raise ValueError("키워드가 충분히 생성되지 않았습니다.")

            logger.info(f"헤드라인: {headline}")
            if spotlight:
                logger.info(f"Spotlight: {spotlight.get('title')}")
            logger.info(f"요약 생성 완료: {len(summary)}개 카테고리")
            logger.info(f"키워드 생성 완료: {keywords}")
            return headline, spotlight, summary, keywords
        raise ValueError("JSON 형식으로 응답이 오지 않았습니다.")
    
    except Exception as e:
        logger.error(f"요약 및 키워드 생성 중 오류 발생: {str(e)}")
        raise e  # 예외를 다시 발생시켜서 상위에서 처리하도록 함

if __name__ == "__main__":
    asyncio.run(main())
