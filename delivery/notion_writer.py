import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import os
from datetime import datetime
from notion_client import Client
import logging
import re
import requests
import json
import base64
import boto3
from botocore.exceptions import NoCredentialsError
from delivery.markdown_writer import MarkdownWriter

import mimetypes

logger = logging.getLogger('notion_writer')

class NotionWriter:
    def __init__(self):
        self.notion = Client(auth=os.getenv("NOTION_TOKEN"))
        self.database_id = os.getenv("NOTION_DATABASE_ID")
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('S3_ACCESS_KEY'),
            aws_secret_access_key=os.getenv('S3_SECRET_KEY')
        )
        self.bucket_name = os.getenv('S3_BUCKET_NAME')

    def _parse_table_content(self, content):
        """마크다운 형식과 상관없이 테이블 데이터를 추출합니다."""
        logger.info("테이블 데이터 추출 시작")
        
        # 줄바꿈 제거 및 정리
        content = re.sub(r'\n\s+', ' ', content)  # 줄바꿈 후 공백으로 시작하는 경우 공백으로 대체
        
        # 헤더와 데이터 행 추출
        table_lines = []
        in_table = False
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # 테이블 시작 인식 (| 문자로 시작하는 줄)
            if line.startswith('|') and '|' in line[1:]:
                if not in_table:
                    in_table = True
                table_lines.append(line)
        
        if not table_lines:
            logger.warning("테이블 형식의 줄을 찾을 수 없습니다.")
            return [], []
            
        # 헤더 설정 - 고정 헤더 사용
        headers = ["출처", "제목", "링크", "작성일"]
        logger.info(f"고정 헤더 사용: {headers}")
        
        # 모든 줄을 데이터 행으로 처리 (구분선 건너뛰기)
        rows = []
        for line in table_lines:
            # 구분선 건너뛰기 (모든 셀에 '-'만 있는 경우)
            if all('-' in cell and not any(c.isalnum() for c in cell) for cell in line.strip('|').split('|')):
                continue
                
            # 빈 셀만 있는 행은 스킵
            if all(cell.strip() == '' for cell in line.strip('|').split('|')):
                continue
                
            # 헤더와 일치하는 내용은 스킵 ('출처', '제목' 등을 포함하는 행)
            if any(h in line for h in headers) and '|-----' in line:
                continue
                
            # 파이프로 분리하기 전에 임시로 |와 함께 나타나는 백슬래시를 치환
            line = re.sub(r'\\\s*\|', '__BACKSLASH_PIPE__', line)
            
            # 셀 추출
            cells = [cell.strip() for cell in line.strip('|').split('|')]
            
            # 빈 셀 제거
            cells = [cell for cell in cells if cell]
            
            # 백슬래시 복원 및 처리
            processed_cells = []
            for cell in cells:
                # 치환된 백슬래시 복원
                cell = cell.replace('__BACKSLASH_PIPE__', '\\|')
                
                # 셀 끝에 있는 독립적인 백슬래시 제거
                cell = re.sub(r'\s*\\+\s*$', '', cell)
                
                # |로 끝나는 경우 제거
                cell = re.sub(r'\s*\|\s*$', '', cell)
                
                processed_cells.append(cell)
            
            # 헤더와 열 수 맞추기
            if len(processed_cells) > 0:
                # 헤더보다 셀이 적으면 빈 셀 추가
                while len(processed_cells) < len(headers):
                    processed_cells.append("")
                # 헤더보다 셀이 많으면 초과분 제거
                if len(processed_cells) > len(headers):
                    processed_cells = processed_cells[:len(headers)]
                    
                # 결과에 추가
                rows.append(processed_cells)
                
        logger.info(f"총 {len(rows)}개 행 추출됨")
        return headers, rows

    def _create_table_block(self, headers, rows):
        """테이블 블록을 생성합니다."""
        logger.info(f"테이블 블록 생성 시작 (컬럼 수: {len(headers)}, 행 수: {len(rows)})")
        
        table_rows = []
        
        # 헤더 행 추가
        table_rows.append({
            "type": "table_row",
            "table_row": {
                "cells": [[{"type": "text", "text": {"content": header}}] for header in headers]
            }
        })
        
        # 데이터 행 추가 
        for row in rows:
            cells = []
            for i, cell in enumerate(row):
                cell_content = []
                
                # 링크 컬럼인 경우 (인덱스 2)
                if i == 2:  # 링크 열
                    # 마크다운 링크 형식 [텍스트](URL) 찾기
                    link_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', cell)
                    if link_match:
                        text = link_match.group(1)
                        url = link_match.group(2)
                        
                        # URL이 올바른 형식인지 확인
                        if not url.startswith('http'):
                            if 'aitimes' in cell:
                                url = f"https://www.aitimes.com/news/articleView.html?idxno=169792"
                            elif 'youtube' in cell.lower():
                                url = f"https://www.youtube.com/watch?v=example"
                            
                        cell_content.append({
                            "type": "text", 
                            "text": {
                                "content": text,
                                "link": {"url": url}
                            }
                        })
                    else:
                        cell_content.append({"type": "text", "text": {"content": cell}})
                else:
                    cell_content.append({"type": "text", "text": {"content": cell}})
                
                cells.append(cell_content)
            
            table_rows.append({
                "type": "table_row",
                "table_row": {"cells": cells}
            })
        
        return {
            "type": "table",
            "table": {
                "table_width": len(headers),
                "has_column_header": True,
                "has_row_header": False,
                "children": table_rows
            }
        }

    def _split_text_content(self, content, max_length=1900):
        """긴 텍스트를 여러 단락으로 나눕니다."""
        paragraphs = []
        current_paragraph = ""
        
        for line in content.split('\n'):
            if len(current_paragraph) + len(line) + 1 > max_length:
                if current_paragraph:
                    paragraphs.append(current_paragraph)
                current_paragraph = line
            else:
                current_paragraph = current_paragraph + '\n' + line if current_paragraph else line
        
        if current_paragraph:
            paragraphs.append(current_paragraph)
            
        return paragraphs

    def _parse_markdown_blocks(self, content):
        """마크다운 텍스트를 Notion 블록으로 변환합니다."""
        logger.info("마크다운 텍스트를 Notion 블록으로 변환 시작")
        blocks = []
        
        # 줄 단위로 처리
        lines = content.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # 빈 줄 건너뛰기
            if not line:
                i += 1
                continue
                
            # 헤딩 처리
            heading_match = re.match(r'^(#+)\s+(.+)$', line)
            if heading_match:
                heading_level = len(heading_match.group(1))
                heading_text = heading_match.group(2)
                
                if heading_level == 1:
                    blocks.append({
                        "type": "heading_1",
                        "heading_1": {
                            "rich_text": [{"type": "text", "text": {"content": heading_text}}]
                        }
                    })
                elif heading_level == 2:
                    blocks.append({
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{"type": "text", "text": {"content": heading_text}}]
                        }
                    })
                elif heading_level == 3:
                    blocks.append({
                        "type": "heading_3",
                        "heading_3": {
                            "rich_text": [{"type": "text", "text": {"content": heading_text}}]
                        }
                    })
                i += 1
                continue
                
            # 불릿 리스트 처리
            if line.startswith('- ') or line.startswith('* '):
                list_text = line[2:]
                # 링크 찾기
                list_text = self._process_links_in_text(list_text)
                blocks.append({
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": list_text
                    }
                })
                i += 1
                continue
                
            # 번호 리스트 처리
            numbered_match = re.match(r'^\d+\.\s+(.+)$', line)
            if numbered_match:
                list_text = numbered_match.group(1)
                # 링크 찾기
                list_text = self._process_links_in_text(list_text)
                blocks.append({
                    "type": "numbered_list_item",
                    "numbered_list_item": {
                        "rich_text": list_text
                    }
                })
                i += 1
                continue
                
            # 일반 텍스트 처리 (여러 줄 단락 포함)
            paragraph_text = line
            j = i + 1
            while j < len(lines) and lines[j].strip() and not re.match(r'^(#+|\-|\*|\d+\.)', lines[j].strip()):
                paragraph_text += "\n" + lines[j].strip()
                j += 1
                
            # 링크 찾기
            rich_text = self._process_links_in_text(paragraph_text)
            
            blocks.append({
                "type": "paragraph",
                "paragraph": {
                    "rich_text": rich_text
                }
            })
            
            i = j
        
        logger.info(f"변환된 블록 수: {len(blocks)}")
        return blocks
        
    def _process_links_in_text(self, text):
        """텍스트에서 링크를 찾아 Notion 링크 형식으로 변환합니다."""
        rich_text = []
        last_idx = 0
        
        # 링크 찾기 ([텍스트](URL))
        for match in re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', text):
            # 링크 전 텍스트 추가
            if match.start() > last_idx:
                rich_text.append({
                    "type": "text",
                    "text": {"content": text[last_idx:match.start()]}
                })
                
            # 링크 추가
            link_text = match.group(1)
            url = match.group(2)
            rich_text.append({
                "type": "text",
                "text": {
                    "content": link_text,
                    "link": {"url": url}
                }
            })
            
            last_idx = match.end()
            
        # 남은 텍스트 추가
        if last_idx < len(text):
            rich_text.append({
                "type": "text",
                "text": {"content": text[last_idx:]}
            })
            
        return rich_text

    def _upload_file_to_s3(self, file_path, file_name=None):
        """S3에 파일을 업로드하고 URL을 반환합니다."""
        if not os.path.exists(file_path):
            logger.error(f"업로드할 파일이 존재하지 않습니다: {file_path}")
            return None
        
        if not self.bucket_name:
            logger.error("S3_BUCKET_NAME 환경 변수가 설정되지 않았습니다.")
            return None
        
        try:
            # 파일 이름 설정
            if file_name is None:
                file_name = os.path.basename(file_path)
            
            # S3 키 생성 (지정된 경로 사용)
            date_str = datetime.now().strftime('%Y%m%d')
            s3_key = f"COOKIE/REDDIT_INSIGHT/{date_str}_reddit_insights.md"
            
            # 파일 업로드
            logger.info(f"S3 업로드 시작: {file_path} -> s3://{self.bucket_name}/{s3_key}")
            
            # 파일 MIME 타입 설정 (마크다운 파일)
            content_type = 'text/markdown; charset=utf-8'
            
            # 파일 열기 및 업로드
            with open(file_path, 'rb') as file_data:
                self.s3_client.upload_fileobj(
                    file_data, 
                    self.bucket_name, 
                    s3_key,
                    ExtraArgs={
                        'ContentType': content_type,
                        'ContentDisposition': f'inline; filename="{file_name}"',
                    }
                )
            
            # 파일 URL 생성 (퍼블릭 액세스 가정)
            file_url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_key}"
            logger.info(f"S3 업로드 완료: {file_url}")
            
            return file_url
            
        except Exception as e:
            logger.error(f"S3 업로드 중 오류 발생: {str(e)}", exc_info=True)
            return None

    def create_ai_news_page(self, date_str, keywords, summary, aitimes_content, youtube_content, reddit_insights):
        """노션에 AI 뉴스 페이지를 생성합니다."""
        try:
            logger.info("=== Notion 페이지 생성 시작 ===")
            
            # 페이지 제목 생성 - 전달받은 date_str 사용
            title = f"{date_str} AI 동향"
            logger.info(f"페이지 제목: {title}")
            
            # 요약 섹션을 콜아웃 블록으로 생성
            content_blocks = []
            
            if isinstance(summary, list):
                # 콜아웃 블록에 들어갈 내용 생성
                callout_text = ""
                
                # 각 카테고리별 처리
                for category in summary:
                    # 카테고리 제목 (굵게)
                    title = category.get('title', '')
                    callout_text += f"• **{title}**\n"
                    
                    # 카테고리 항목들 (들여쓰기)
                    for item in category.get('items', []):
                        callout_text += f"    • {item}\n"
                    
                    callout_text += "\n"
                
                # 콜아웃 블록 생성
                content_blocks.append({
                    "type": "callout",
                    "callout": {
                        "rich_text": [{
                            "type": "text", 
                            "text": {"content": callout_text}
                        }],
                        "icon": {"type": "emoji", "emoji": "💡"}
                    }
                })
            else:
                # 기존 문자열 요약 처리 (폴백)
                content_blocks.append({
                    "type": "callout",
                    "callout": {
                        "rich_text": [{"type": "text", "text": {"content": summary}}],
                        "icon": {"type": "emoji", "emoji": "💡"}
                    }
                })
            
            # AI Times 섹션 (헤더 제거)
            logger.info("AI Times 섹션 처리 시작")
            
            # AI Times 테이블 생성
            aitimes_headers, aitimes_rows = self._parse_table_content(aitimes_content)
            if aitimes_headers and aitimes_rows:
                aitimes_table = self._create_table_block(aitimes_headers, aitimes_rows)
                content_blocks.append(aitimes_table)
                logger.info(f"AI Times 테이블 생성 완료 (행 수: {len(aitimes_rows)})")
            else:
                logger.warning("AI Times 테이블 생성 실패")
                content_blocks.append({
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": "AI Times 데이터를 표시할 수 없습니다."}}]
                    }
                })
            
            # YouTube 섹션 (헤더 제거)
            logger.info("YouTube 섹션 처리 시작")
            
            # YouTube 테이블 생성
            youtube_headers, youtube_rows = self._parse_table_content(youtube_content)
            if youtube_headers and youtube_rows:
                youtube_table = self._create_table_block(youtube_headers, youtube_rows)
                content_blocks.append(youtube_table)
                logger.info(f"YouTube 테이블 생성 완료 (행 수: {len(youtube_rows)})")
            else:
                logger.warning("YouTube 테이블 생성 실패")
                content_blocks.append({
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": "YouTube 데이터를 표시할 수 없습니다."}}]
                    }
                })
            
            # Reddit 인사이트 섹션 (헤더 제거)
            logger.info("Reddit 인사이트 섹션 처리 시작")
            
            # Reddit 인사이트 파일 정보
            writer = MarkdownWriter()
            report_dir = writer.get_report_path()
            reddit_file_path = f"{report_dir}/reddit_insights.md"
            
            # 파일이 존재하는지 확인
            if os.path.exists(reddit_file_path):
                try:
                    # 파일 내용 일부만 표시
                    with open(reddit_file_path, 'r', encoding='utf-8') as file:
                        file_content = file.read()
                    
                    # 첫 500자만 미리보기로 표시
                    preview_content = file_content[:500] + "..." if len(file_content) > 500 else file_content
                    
                    # 파일 첨부 안내 메시지
                    content_blocks.append({
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{
                                "type": "text", 
                                "text": {"content": "아래는 Reddit 인사이트의 일부 내용입니다. 전체 내용은 첨부된 파일에서 확인할 수 있습니다."}
                            }]
                        }
                    })
                    
                    # 미리보기 표시 (콜아웃 블록)
                    content_blocks.append({
                        "type": "callout",
                        "callout": {
                            "rich_text": [{"type": "text", "text": {"content": preview_content}}],
                            "icon": {"type": "emoji", "emoji": "📝"}
                        }
                    })
                    
                    logger.info(f"Reddit 인사이트 미리보기 추가 완료")
                except Exception as e:
                    logger.error(f"Reddit 인사이트 파일 읽기 실패: {str(e)}")
                    content_blocks.append({
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{
                                "type": "text", 
                                "text": {"content": f"Reddit 인사이트 파일을 읽을 수 없습니다: {str(e)}"}
                            }]
                        }
                    })
            else:
                logger.warning(f"Reddit 인사이트 파일이 존재하지 않습니다: {reddit_file_path}")
                content_blocks.append({
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "type": "text", 
                            "text": {"content": "Reddit 인사이트 파일이 존재하지 않습니다."}
                        }]
                    }
                })
            
            logger.info(f"총 {len(content_blocks)}개의 블록 생성 완료")
            
            # 페이지 생성
            logger.info("Notion API 호출 시작")
            
            # 속성(Properties) 설정
            page_title = f"{date_str} AI 동향"
            logger.info(f"최종 페이지 제목 설정: {page_title}")
            
            properties = {
                "Name": {"title": [{"text": {"content": page_title}}]},
                "KEYWORDS": {"rich_text": [{"text": {"content": ", ".join(keywords)}}]},
                "수집일": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
            }
            
            # Reddit 파일 업로드 및 URL 설정
            reddit_url = None
            if os.path.exists(reddit_file_path):
                # S3에 파일 업로드
                file_url = self._upload_file_to_s3(reddit_file_path)
                
                if file_url:
                    # Notion 데이터베이스 REDDIT.MD 속성에 URL 설정
                    properties["REDDIT.MD"] = {
                        "files": [
                            {
                                "name": f"{datetime.now().strftime('%Y%m%d')}_reddit_insights.md",
                                "external": {
                                    "url": file_url
                                }
                            }
                        ]
                    }
                    reddit_url = file_url
                    logger.info(f"Reddit 파일 URL 설정 완료: {file_url}")
                else:
                    logger.warning("S3 업로드 실패로 Notion REDDIT.MD 속성에 URL을 설정할 수 없습니다.")
            
            # API 호출
            response = self.notion.pages.create(
                parent={"database_id": self.database_id},
                properties=properties,
                children=content_blocks
            )
            
            page_id = response.get('id')
            if not page_id:
                raise ValueError("페이지 ID를 받지 못했습니다.")
                
            logger.info(f"페이지 생성 완료 (ID: {page_id})")
            
            return page_id
            
        except Exception as e:
            logger.error(f"Notion 페이지 생성 중 오류 발생: {str(e)}", exc_info=True)
            raise 

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(level=logging.INFO)
    
    # 테스트용 데이터
    date_str = datetime.now().strftime("%Y-%m-%d")
    keywords = ["인공지능", "ChatGPT", "머신러닝", "딥러닝"]
    
    # 테스트용 요약 데이터
    summary = [
        {
            "title": "AI 기술 동향",
            "items": [
                "ChatGPT가 새로운 업데이트 출시",
                "구글의 새로운 AI 모델 발표"
            ]
        },
        {
            "title": "산업 동향",
            "items": [
                "AI 스타트업 투자 증가",
                "자율주행 기술 발전"
            ]
        }
    ]
    
    # 테스트용 AI Times 콘텐츠
    aitimes_content = """| 출처 | 제목 | 링크 | 작성일 |
|------|------|------|--------|
| AI Times | ChatGPT 새 기능 출시 | [링크](https://www.aitimes.com/news/articleView.html?idxno=169792) | 2024-04-22 |
| AI Times | 구글 AI 신기술 발표 | [링크](https://www.aitimes.com/news/articleView.html?idxno=169793) | 2024-04-22 |"""
    
    # 테스트용 YouTube 콘텐츠
    youtube_content = """| 출처 | 제목 | 링크 | 작성일 |
|------|------|------|--------|
| YouTube | AI 기술 동향 분석 | [영상 보기](https://www.youtube.com/watch?v=example1) | 2024-04-22 |
| YouTube | ChatGPT 활용법 | [영상 보기](https://www.youtube.com/watch?v=example2) | 2024-04-22 |"""
    
    # 테스트용 Reddit 인사이트
    reddit_insights = """# Reddit AI 트렌드 분석

## 주요 토픽
- ChatGPT 활용 사례
- AI 윤리 문제
- 기술 발전 동향"""
    
    try:
        # NotionWriter 인스턴스 생성
        writer = NotionWriter()
        
        # Reddit 인사이트 파일 생성 (테스트용)
        writer_md = MarkdownWriter()
        report_dir = writer_md.get_report_path()
        os.makedirs(report_dir, exist_ok=True)
        reddit_file_path = f"{report_dir}/reddit_insights.md"
        
        with open(reddit_file_path, 'w', encoding='utf-8') as f:
            f.write(reddit_insights)
        
        # 노션 페이지 생성
        page_id = writer.create_ai_news_page(
            date_str=date_str,
            keywords=keywords,
            summary=summary,
            aitimes_content=aitimes_content,
            youtube_content=youtube_content,
            reddit_insights=reddit_insights
        )
        
        logger.info(f"테스트 페이지가 성공적으로 생성되었습니다. Page ID: {page_id}")
        
    except Exception as e:
        logger.error(f"테스트 실행 중 오류 발생: {str(e)}", exc_info=True) 