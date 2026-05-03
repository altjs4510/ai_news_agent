import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from datetime import datetime, timedelta, timezone
from config import YOUTUBE_API_KEY, YOUTUBE_CHANNELS
from utils.logger import setup_logger
import asyncio
import re
import time
import random
from datetime import datetime

logger = setup_logger('youtube')

class YouTubeParser:
    def __init__(self):
        self.youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        self.week_ago = self._get_week_ago()

    def _get_week_ago(self):
        """현재 시간으로부터 7일 전 시간을 반환합니다."""
        return datetime.now(timezone.utc) - timedelta(days=7)

    def _parse_duration(self, duration):
        """YouTube API의 duration 문자열을 파싱하여 초 단위로 변환합니다."""
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if not match:
            return 0
        
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        
        return hours * 3600 + minutes * 60 + seconds

    async def fetch_videos(self):
        videos = []
        
        for channel_name, channel_id in YOUTUBE_CHANNELS.items():
            try:
                response = await self._fetch_channel_videos(channel_id)
                
                # 채널 간 대기 시간 추가
                await asyncio.sleep(1)
                
                for item in response["items"]:
                    video_id = item["id"]["videoId"]
                    title = item["snippet"]["title"]
                    published_at_str = item["snippet"]["publishedAt"]
                    published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))

                    if published_at < self.week_ago:
                        logger.info(f"오래된 영상 제외: {title} ({published_at_str})")
                        continue

                    url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    # 영상 상세 정보 가져오기
                    video_info = await self._get_video_info(video_id)
                    if not video_info:
                        continue

                    # 라이브 스트리밍 체크
                    if video_info.get("live_streaming"):
                        logger.info(f"라이브 스트리밍 영상 제외: {title}")
                        continue

                    # 영상 길이 체크
                    if video_info.get("duration_seconds", 0) > 3600:  # 1시간 초과
                        logger.info(f"1시간 이상 긴 영상 감지: {title}")
                        videos.append({
                            "source": f"YouTube - {channel_name}",
                            "title": title,
                            "url": url,
                            "published_at": published_at_str,
                            "content": f"[제목] {title}\n\n[설명]\n{video_info.get('description', '')}"
                        })
                        continue

                    # 일반 영상은 자막 시도 (재시도 로직 포함)
                    transcript = await self._get_transcript_with_retry(video_id)
                    content = transcript if transcript else video_info.get('description', '')

                    logger.info(f"영상 추가: {title} ({published_at_str})")
                    videos.append({
                        "source": f"YouTube - {channel_name}",
                        "title": title,
                        "url": url,
                        "published_at": published_at_str,
                        "content": content
                    })
                    
                    # 영상 처리 간 대기 시간 추가 (더 긴 대기)
                    await asyncio.sleep(random.uniform(3, 5))
                    
            except Exception as e:
                logger.error(f"유튜브 영상 수집 실패 ({channel_name}): {str(e)}", exc_info=True)

        return videos

    async def _get_video_info(self, video_id):
        """영상의 상세 정보를 가져옵니다."""
        try:
            loop = asyncio.get_event_loop()
            request = self.youtube.videos().list(
                part="contentDetails,snippet,liveStreamingDetails",
                id=video_id
            )
            response = await loop.run_in_executor(None, request.execute)
            
            if not response.get("items"):
                return None
                
            video_info = response["items"][0]
            duration = video_info["contentDetails"]["duration"]
            
            return {
                "duration_seconds": self._parse_duration(duration),
                "description": video_info["snippet"]["description"],
                "live_streaming": "liveStreamingDetails" in video_info
            }
        except Exception as e:
            logger.error(f"영상 정보 가져오기 실패 ({video_id}): {str(e)}")
            return None

    async def _fetch_channel_videos(self, channel_id):
        """채널의 동영상 목록을 비동기적으로 가져옵니다."""
        loop = asyncio.get_event_loop()
        request = self.youtube.search().list(
            part="snippet",
            channelId=channel_id,
            order="date",
            maxResults=10,
            type="video",
            publishedAfter=(self.week_ago.strftime('%Y-%m-%dT%H:%M:%SZ'))
        )
        return await loop.run_in_executor(None, request.execute)

    async def _get_transcript(self, video_id):
        """자막을 비동기적으로 가져옵니다."""
        try:
            loop = asyncio.get_event_loop()
            transcript = await loop.run_in_executor(
                None,
                lambda: YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
            )
            return " ".join([seg['text'] for seg in transcript])
        except TranscriptsDisabled:
            logger.info(f"자막 없음: {video_id}")
            return ""
        except Exception as e:
            logger.error(f"자막 수집 실패 ({video_id}): {str(e)}")
            return ""
    
    async def _get_transcript_with_retry(self, video_id, max_retries=2):
        """재시도 로직이 포함된 자막 가져오기"""
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_event_loop()
                transcript = await loop.run_in_executor(
                    None,
                    lambda: YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
                )
                return " ".join([seg['text'] for seg in transcript])
            except TranscriptsDisabled:
                logger.info(f"자막 없음: {video_id}")
                return ""
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    # 첫 번째 실패도 로그에 기록
                    logger.warning(f"Rate limit 에러 발생 ({video_id}) - 시도: {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:  # 마지막 시도가 아닐 때만 재시도
                        # 더 긴 대기 시간으로 조정
                        wait_time = (5 ** attempt) + random.uniform(10, 20)  # 5초, 35초 정도
                        logger.warning(f"{wait_time:.1f}초 후 재시도")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # 마지막 시도도 실패한 경우, 자막 없이 진행
                        logger.warning(f"Rate limit으로 자막 수집 실패 ({video_id}), 설명으로 대체")
                        return ""
                else:
                    # 다른 에러는 즉시 실패 처리
                    logger.error(f"자막 수집 실패 ({video_id}): {error_msg}")
                    return ""
        
        # 모든 재시도 실패
        logger.warning(f"자막 수집 최종 실패 ({video_id}): Rate limit 지속, 설명으로 대체")
        return ""

if __name__ == "__main__":
    import json

    async def main():
        parser = YouTubeParser()
        videos = await parser.fetch_videos()
        logger.info("\n=== 수집된 영상 목록 ===")
        logger.info(json.dumps(videos, indent=2, ensure_ascii=False))
        logger.info(f"\n총 {len(videos)}개의 영상이 수집되었습니다.")

    asyncio.run(main())
