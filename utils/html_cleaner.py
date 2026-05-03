from bs4 import BeautifulSoup
import html2text
import re
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger('html_cleaner')

class HTMLCleaner:
    @staticmethod
    def clean_html(html_content):
        """HTML 콘텐츠를 정리된 텍스트로 변환합니다."""
        try:
            # BeautifulSoup으로 HTML 파싱
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 불필요한 요소 제거
            for tag in soup(['script', 'style', 'iframe', 'nav', 'footer']):
                tag.decompose()
            
            # HTML을 텍스트로 변환
            h = html2text.HTML2Text()
            h.ignore_links = True
            h.ignore_images = True
            h.ignore_tables = True
            
            clean_text = h.handle(str(soup))
            
            # 여러 줄의 공백 제거
            clean_text = '\n'.join(line.strip() for line in clean_text.split('\n') if line.strip())
            
            return clean_text
            
        except Exception as e:
            print(f"Error cleaning HTML: {e}")
            return ""
            
    @staticmethod
    def extract_main_content(html_content):
        """메인 콘텐츠 영역만 추출합니다."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 일반적인 메인 콘텐츠 영역 선택자
            main_content_selectors = [
                'article',
                'main',
                '.content',
                '.article-content',
                '#main-content'
            ]
            
            for selector in main_content_selectors:
                content = soup.select_one(selector)
                if content:
                    return HTMLCleaner.clean_html(str(content))
                    
            # 선택자로 찾지 못한 경우 전체 내용 반환
            return HTMLCleaner.clean_html(str(soup))
            
        except Exception as e:
            print(f"Error extracting main content: {e}")
            return ""

def clean_textblock(content: str) -> Optional[str]:
    """TextBlock 메타데이터에서 실제 텍스트 내용만 추출합니다.
    
    Args:
        content (str): TextBlock을 포함한 원본 문자열
        
    Returns:
        Optional[str]: 정리된 텍스트 내용. 실패 시 None 반환
    """
    try:
        # TextBlock이 없으면 원본 반환
        if '[TextBlock(' not in content:
            return content
            
        # 헤더 부분 (처음 4줄) 추출
        header_lines = content.split('\n')[:4]
        
        # TextBlock 시작 위치 찾기
        start_idx = content.find('[TextBlock(')
        if start_idx == -1:
            return content
            
        # text=' 다음부터 마지막 ' 이전까지 추출
        text_start = content.find("text='", start_idx)
        if text_start == -1:
            return content
            
        text_start += 6  # len("text='")
        text_end = content.rfind("', type='text')]")
        if text_end == -1:
            return content
            
        # 실제 내용 추출
        text_content = content[text_start:text_end]
        
        # 이스케이프된 문자 처리
        text_content = text_content.replace('\\n', '\n')
        text_content = text_content.replace('\\"', '"')
        text_content = text_content.replace("\\'", "'")
        
        # 헤더와 내용 합치기
        final_content = '\n'.join(header_lines) + '\n' + text_content
        
        return final_content
        
    except Exception as e:
        logger.error(f"TextBlock 정리 중 오류 발생: {str(e)}")
        return None

def clean_html_tags(content: str) -> str:
    """HTML 태그를 제거하고 텍스트만 추출합니다.
    
    Args:
        content (str): HTML 태그를 포함한 문자열
        
    Returns:
        str: HTML 태그가 제거된 순수 텍스트
    """
    # HTML 태그 제거
    clean_text = re.sub(r'<[^>]+>', '', content)
    # 연속된 공백 정리
    clean_text = ' '.join(clean_text.split())
    return clean_text.strip()

def clean_markdown_file(filepath: str, preserve_header_lines: int = 0) -> bool:
    """마크다운 파일에서 메타데이터를 제거하고 정리합니다.
    
    Args:
        filepath (str): 처리할 마크다운 파일 경로
        preserve_header_lines (int): 보존할 헤더 라인 수
        
    Returns:
        bool: 성공 여부
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 헤더 라인 보존
        header_lines = []
        if preserve_header_lines > 0:
            header_lines = content.split('\n')[:preserve_header_lines]
            
        # 본문 정리
        cleaned_content = clean_textblock(content)
        if cleaned_content is None:
            return False
            
        # 최종 내용 조합
        if header_lines:
            final_content = '\n'.join(header_lines) + '\n' + cleaned_content
        else:
            final_content = cleaned_content
            
        # 파일 다시 쓰기
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(final_content)
            
        logger.info(f"파일 정리 완료: {filepath}")
        return True
        
    except Exception as e:
        logger.error(f"파일 정리 중 오류 발생: {str(e)}")
        return False 