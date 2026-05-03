import os
from datetime import datetime
from pathlib import Path

class MarkdownWriter:
    def __init__(self):
        self.base_dir = self._create_report_directory()

    def _create_report_directory(self):
        """오늘 날짜의 리포트 디렉토리를 생성합니다."""
        today = datetime.now().strftime('%Y%m%d')
        base_dir = Path('reports') / today
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    def save_raw_contents(self, aitimes_posts, youtube_posts, reddit_posts):
        """수집된 원본 데이터를 마크다운 형식으로 저장합니다."""
        # AI Times 저장
        aitimes_file = self._save_table_contents(aitimes_posts, "aitimes")
        
        # YouTube 저장
        youtube_file = self._save_table_contents(youtube_posts, "youtube")
        
        # Reddit 저장 (원문 테이블과 번역본)
        reddit_files = self._save_reddit_contents(reddit_posts)
        
        return aitimes_file, youtube_file, reddit_files

    def _save_table_contents(self, contents, source_type):
        """테이블 형식으로 콘텐츠를 저장합니다."""
        filename = f"{source_type}_raw.md"
        filepath = self.base_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {source_type} 수집 데이터\n")
            f.write(f"수집 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # 테이블 헤더
            f.write("| 출처 | 제목 | 링크 | 작성일 |\n")
            f.write("|------|------|------|--------|\n")
            
            # 각 콘텐츠를 테이블 행으로 추가
            for content in contents:
                title = content['title'].replace('|', '\\|')  # 파이프 문자 이스케이프
                source = content['source'].replace('|', '\\|')
                url = content['url']
                published_at = content.get('published_at', '-')
                
                f.write(f"| {source} | {title} | [링크]({url}) | {published_at} |\n")
        
        return filepath

    def _save_reddit_contents(self, contents):
        """Reddit 포스트를 원문 테이블과 번역본으로 저장합니다."""
        # 1. 원문 테이블 저장 (제목 중심)
        raw_filepath = self.base_dir / "reddit_raw.md"
        with open(raw_filepath, 'w', encoding='utf-8') as f:
            f.write("# Reddit 수집 데이터 (원문)\n")
            f.write(f"수집 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # 테이블 헤더
            f.write("| 서브레딧 | 제목 | 링크 | 작성일 |\n")
            f.write("|----------|------|------|--------|\n")
            
            for content in contents:
                title = content['title'].replace('|', '\\|')
                subreddit = content['source'].split(' - ')[1]  # "Reddit - r/artificial" -> "r/artificial"
                url = content['url']
                published_at = content.get('published_at', '-')
                
                f.write(f"| {subreddit} | {title} | [링크]({url}) | {published_at} |\n")

        # 2. 번역본 상세 저장
        translated_filepath = self.base_dir / "reddit_translated.md"
        with open(translated_filepath, 'w', encoding='utf-8') as f:
            f.write("# Reddit 수집 데이터 (번역본)\n")
            f.write(f"수집 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for content in contents:
                f.write(f"## [{content['source'].split(' - ')[1]}] {content['title']}\n\n")
                
                if 'original_content' in content:  # 번역이 있는 경우
                    translated_text = content['content'].split('[한글 번역]')[-1].strip()
                    f.write(f"{translated_text}\n\n")
                else:  # 번역 실패 등의 이유로 원본만 있는 경우
                    f.write("(번역 없음)\n\n")
                
                f.write(f"원문 링크: {content['url']}\n")
                f.write("\n---\n\n")
        
        return raw_filepath, translated_filepath

    def save_markdown(self, content, filename):
        """마크다운 내용을 파일로 저장합니다."""
        filepath = self.base_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath

    def get_report_path(self):
        """현재 리포트 디렉토리 경로를 반환합니다."""
        return self.base_dir

def save_markdown_text(markdown_text: str, output_dir="outputs"):
    today_str = datetime.now().strftime("%Y%m%d")
    filename = f"{today_str}_AI_동향_요약.md"
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown_text)

    print(f"✅ 마크다운 저장 완료: {filepath}")
    return filepath


if __name__ == "__main__":
    dummy_text = """
# 📅 2025년 04월 22일 AI 동향 요약

## 🔹 주요 요약

| 출처 | 제목 | 핵심 요약 |
|------|------|-----------|
| AI타임스 | LLAMA 3 공개 | Meta가 LLAMA 3를 공개함. 400B 파라미터와 오픈소스 라이선스. |
| YouTube - 조코딩 | AI로 1인 개발하는 방법 | ChatGPT와 Python을 활용한 사이드 프로젝트 실습 영상. |

---

## 📌 키워드 모음
- LLM, Meta, LLAMA, ChatGPT, 사이드 프로젝트

## 📎 전체 콘텐츠 목록
- [LLAMA 3 공개](https://example.com/llama3)
- [AI로 1인 개발하는 방법](https://youtube.com/ai-solo)
"""
    save_markdown_text(dummy_text)
