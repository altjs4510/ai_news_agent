import asyncio
import os
from sources.aitimes import AITimesCrawler
from sources.youtube import YouTubeParser
from sources.reddit import RedditCollector
from delivery.markdown_writer import MarkdownWriter
from delivery.notion_writer import NotionWriter
from delivery.email_sender import EmailSender
from utils.logger import setup_logger
import openai
from datetime import datetime
import anthropic
from anthropic import Anthropic
from utils.html_cleaner import clean_markdown_file
import re
import traceback
import json

logger = setup_logger('main')

async def main():
    """메인 실행 함수"""
    try:
        logger.info("=== AI 뉴스 수집 시작 ===")
        
        # 수집기 활성화 설정
        ENABLE_AITIMES = False
        ENABLE_YOUTUBE = True
        ENABLE_REDDIT = True
        
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
        
        for i, (source_name, _) in enumerate(collectors):
            result = results[i] if i < len(results) and not isinstance(results[i], Exception) else []
            if source_name == 'aitimes':
                articles = result
            elif source_name == 'youtube':
                videos = result
            elif source_name == 'reddit':
                reddit_posts = result

        # 마크다운 파일 저장
        markdown_writer = MarkdownWriter()
        markdown_writer.save_raw_contents(articles, videos, reddit_posts)
        
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
        markdown_writer.save_raw_contents(articles, videos, relevant_posts)
        
        logger.info("번역 시작...")
        translated_posts = await translate_contents_batch(relevant_posts)
        markdown_writer._save_reddit_contents(translated_posts)
        
        # Reddit 인사이트 생성
        logger.info("인사이트 추출 중...")
        reddit_insights_path = await summarize_reddit_insights()
        
        # Notion 페이지 생성
        try:
            notion_writer = NotionWriter()
            
            # 날짜 문자열 생성
            today = datetime.now()
            date_str = today.strftime("%Y%m%d")
            report_path = f"reports/{date_str}"
            
            # 각 컨텐츠 읽기
            with open(f"{report_path}/aitimes_raw.md", "r", encoding="utf-8") as f:
                aitimes_content = f.read()
            with open(f"{report_path}/youtube_raw.md", "r", encoding="utf-8") as f:
                youtube_content = f.read()
            with open(f"{report_path}/reddit_insights.md", "r", encoding="utf-8") as f:
                reddit_insights = f.read()
                
            # 요약 및 키워드 자동 생성
            summary, keywords = await generate_summary_and_keywords(aitimes_content, youtube_content, reddit_insights)
            
            # Notion 페이지 생성
            page_id = notion_writer.create_ai_news_page(
                date_str=date_str,
                keywords=keywords,
                summary=summary,
                aitimes_content=aitimes_content,
                youtube_content=youtube_content,
                reddit_insights=reddit_insights
            )
            logger.info(f"Notion 페이지가 생성되었습니다. Page ID: {page_id}")
            
            # 이메일 발송
            try:
                logger.info("이메일 알림 발송 중...")
                email_sender = EmailSender()
                
                # Reddit 인사이트 파일 URL (S3 업로드)
                reddit_url = None
                reddit_file_path = f"{report_path}/reddit_insights.md"
                if os.path.exists(reddit_file_path):
                    # NotionWriter의 S3 업로드 메서드 사용
                    file_url = notion_writer._upload_file_to_s3(reddit_file_path)
                    if file_url:
                        reddit_url = file_url
                        logger.info(f"Reddit 파일 S3 업로드 완료: {file_url}")
                    else:
                        logger.warning("S3 업로드 실패, 로컬 파일 경로 사용")
                        reddit_url = f"file://{reddit_file_path}"
                
                email_result = email_sender.send_notion_page_notification(
                    date_str=date_str,
                    page_id=page_id,
                    summary=summary,
                    keywords=keywords,
                    reddit_url=reddit_url
                )
                
                if email_result:
                    logger.info("✅ 이메일 알림 발송 완료!")
                else:
                    logger.warning("⚠️ 이메일 알림 발송 실패 (설정 확인 필요)")
                    
            except Exception as email_error:
                logger.error(f"❌ 이메일 발송 중 오류 발생: {str(email_error)}")
            
        except Exception as e:
            logger.error(f"Notion 페이지 생성 중 오류 발생: {str(e)}")

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

        client = openai.AsyncOpenAI()
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        score = int(response.choices[0].message.content.strip())
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

        client = openai.AsyncOpenAI()
        logger.info(f"OpenAI API 호출 중... ({title[:30]}...)")
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        translated_text = response.choices[0].message.content.strip()
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

async def summarize_reddit_insights():
    """Reddit 번역본에서 실용적인 인사이트를 추출합니다."""
    try:
        logger.info("Reddit 포스트 인사이트 추출 중...")
        
        writer = MarkdownWriter()
        report_dir = writer.get_report_path()
        
        # 원본 포스트와 번역본 읽기
        with open(f"{report_dir}/reddit_translated.md", 'r', encoding='utf-8') as f:
            translated_content = f.read()

        # 번역된 포스트 분리
        posts = [post.strip() for post in translated_content.split("---") if post.strip()]
        logger.info(f"총 {len(posts)}개의 포스트 분석 시작...")

        prompt = f"""다음은 Reddit에서 수집한 AI 관련 포스트들입니다. 포스트들을 분석하여 주요 주제별로 실용적인 인사이트를 추출해주세요.

특히 다음과 같은 주제들을 중심으로 분석해주세요:
1. 구현 기술과 방법론
2. 성능 최적화와 문제 해결
3. 도구와 리소스
4. 실제 사용 사례와 경험
5. 주의사항과 제한사항

포스트들:
{translated_content}

다음 형식으로 작성해주세요:

# 전체 요약
(수집된 포스트들의 전반적인 트렌드와 핵심 인사이트를 3-4줄로 요약)

# 주제별 상세 분석
## [주제 1]
- 관련 포스트:
  - [포스트 제목 1](출처 URL)
  - [포스트 제목 2](출처 URL)
- 핵심 인사이트:
  (이 주제와 관련된 포스트들의 내용을 종합적으로 분석한 인사이트)

## [주제 2]
...

(각 주제는 2개 이상의 포스트가 관련되어 있을 때만 포함하고, 
개별 포스트의 독특한 인사이트는 별도 섹션에서 다루어주세요)

# 개별 포스트 주요 발견
## [포스트 제목]
- 출처: [원본 링크]
- 주요 발견: (다른 포스트에서 다루지 않은 독특한 인사이트나 중요한 정보)

(이 섹션은 주제별 분석에서 충분히 다루지 못한 중요한 개별 인사이트가 있는 경우에만 포함)"""

        client = Anthropic()
        message = client.messages.create(
            model="claude-3-7-sonnet-latest",
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
        
        # 응답에서 TextBlock 형식이 있는지 확인 (이제 insights는 문자열)
        # TextBlock 메타데이터 제거 (이제 필요 없을 수 있지만 안전하게 남겨둠)
        insights = insights.replace("[TextBlock(citations=None, text='", "")
        insights = insights.replace("', type='text')]", "")
        insights = insights.replace('\\n', '\n')  # 이중 이스케이프된 줄바꿈 처리
        insights = insights.replace('\n', '\n')    # 단일 이스케이프된 줄바꿈 처리
        
        # 최종 마크다운 생성
        final_content = f"""# Reddit AI 개발 인사이트 모음
생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{insights.strip()}"""
        
        # 파일 저장
        filepath = writer.save_markdown(final_content, "reddit_insights.md")
        
        # 저장된 파일 확인 및 TextBlock 재확인
        with open(filepath, 'r', encoding='utf-8') as f:
            saved_content = f.read()
            if '[TextBlock(' in saved_content:
                # TextBlock이 여전히 있다면 다시 한번 정리
                cleaned_content = saved_content.replace('[TextBlock(citations=None, text=\'', '')
                cleaned_content = cleaned_content.replace('\', type=\'text\')]', '')
                cleaned_content = cleaned_content.replace('\\\\n', '\n')
                cleaned_content = cleaned_content.replace('\\n', '\n')
                
                # 깨끗한 내용으로 다시 저장
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(cleaned_content)
        
        logger.info(f"Reddit 인사이트 저장 완료: {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"Reddit 인사이트 추출 실패: {str(e)}", exc_info=True)
        return None

async def generate_summary_and_keywords(aitimes_content, youtube_content, reddit_insights):
    """수집된 콘텐츠를 기반으로 전체 요약과 키워드를 생성합니다."""
    logger.info("요약 및 키워드 생성 시작")
    
    # 요약을 위한 프롬프트 생성
    prompt = f"""다음은 AI 관련 뉴스, YouTube 영상, Reddit 인사이트입니다. 이를 바탕으로 아래 기준에 따라 정리하고 주요 키워드 5개를 추출해주세요.

AI Times 뉴스:
{aitimes_content[:3000]}  # 너무 길지 않게 앞부분만 사용

YouTube 영상:
{youtube_content[:3000]}  # 너무 길지 않게 앞부분만 사용

Reddit 인사이트:
{reddit_insights[:4000]}  # 너무 길지 않게 앞부분만 사용

## 요약 목표
- AI 트렌드를 빠르게 파악하고, 실행 가능한 인사이트를 뽑아내는 것

## 요약 분류 기준
- 다음 세 가지 범주 중 하나로 분류하고 각 범주별로 2~4개의 핵심 포인트를 불릿 포인트로 작성하세요:
    1. 지금 바로 실험해볼만한 도구/기능
        - 신기능, API, 공개된 툴 등
        - 실무에 적용하거나 데모해볼 수 있는 아이디어
    2. 전략적으로 중요한 흐름
        - 산업 변화, 기업 정책, 기술 방향성
        - 향후 AI 관련 결정에 영향을 줄 수 있는 트렌드
    3. 나중에 참고할만한 아이디어
        - 흥미롭지만 당장 실행하긴 어려운 개념, 이론, 논쟁
        - 장기적으로 체크하거나 기록해두면 좋을 정보
        
다음 JSON 형식으로 응답해주세요:
{{
    "summary": [
        {{
            "title": "주요 카테고리 제목1", 
            "items": [
                "상세 내용 포인트 1", 
                "상세 내용 포인트 2", 
                "상세 내용 포인트 3"
            ]
        }},
        {{
            "title": "주요 카테고리 제목2", 
            "items": [
                "상세 내용 포인트 1", 
                "상세 내용 포인트 2"
            ]
        }},
        {{
            "title": "주요 카테고리 제목3", 
            "items": [
                "상세 내용 포인트 1", 
                "상세 내용 포인트 2", 
                "상세 내용 포인트 3", 
                "상세 내용 포인트 4"
            ]
        }}
    ],
    "keywords": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"]
}}

요약은 4~5개의 주요 카테고리로 나누고, 각 카테고리별로 2~4개의 핵심 포인트를 불릿 포인트로 작성하세요.
주요 카테고리는 AI 모델 발전, 에이전트 플랫폼, AI 활용 사례, 안전성/윤리, 기술 동향 등이 될 수 있습니다.
키워드는 현재 가장 주목받는 기술, 제품, 이슈 등을 나타내는 짧은 단어나 구문(최대 2-3단어)이어야 합니다."""

    try:
        # Claude API 호출
        client = Anthropic()
        response = client.messages.create(
            model="claude-3-7-sonnet-latest",
            max_tokens=2000,
            temperature=0.2,
            system="너는 AI 뉴스 분석과 요약을 전문으로 하는 Assistant입니다. 주어진 콘텐츠에서 핵심 내용을 파악하고 간결하게 요약합니다.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        # 응답에서 JSON 형식 추출
        result_text = response.content[0].text
        logger.info(f"응답: {result_text}")
        # JSON 형식 찾기
        json_match = re.search(r'({.*})', result_text.replace('\n', ''))
        if json_match:
            result_json = json.loads(json_match.group(1))
            summary = result_json.get('summary', [])
            keywords = result_json.get('keywords', [])
            
            if not summary:
                raise ValueError("요약이 생성되지 않았습니다.")
            if not keywords or len(keywords) < 5:
                raise ValueError("키워드가 충분히 생성되지 않았습니다.")
                
            logger.info(f"요약 생성 완료: {len(summary)}개 카테고리")
            logger.info(f"키워드 생성 완료: {keywords}")
            return summary, keywords
        else:
            raise ValueError("JSON 형식으로 응답이 오지 않았습니다.")
    
    except Exception as e:
        logger.error(f"요약 및 키워드 생성 중 오류 발생: {str(e)}")
        raise e  # 예외를 다시 발생시켜서 상위에서 처리하도록 함

if __name__ == "__main__":
    asyncio.run(main())
