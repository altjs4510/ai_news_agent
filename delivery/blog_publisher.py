import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from utils.logger import setup_logger

logger = setup_logger('blog_publisher')

RAW_SOURCES = [
    ("AI 공식 블로그 (Anthropic / OpenAI / Google)", "ai_blogs_raw.md"),
    ("GitHub Trending (이번 주 인기 오픈소스)", "github_raw.md"),
    ("Reddit 원문 목록", "reddit_raw.md"),
    ("Reddit 번역본 (전문)", "reddit_translated.md"),
    ("AI Times", "aitimes_raw.md"),
    ("YouTube", "youtube_raw.md"),
]


def _strip_existing_frontmatter(text: str) -> str:
    if text.lstrip().startswith("---"):
        return re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL).lstrip()
    return text


def _strip_leading_h1(text: str) -> str:
    text = re.sub(r"^#\s+[^\n]*\n", "", text, count=1).lstrip()
    text = re.sub(r"^수집 시간:[^\n]*\n", "", text, count=1).lstrip()
    return text


def _is_meaningful(text: str) -> bool:
    body = _strip_existing_frontmatter(text)
    body = _strip_leading_h1(body)
    body = body.strip()
    if not body:
        return False
    # 표 헤더만 있고 행이 없는 경우 제외
    lines = [l for l in body.splitlines() if l.strip()]
    if all(l.startswith("|") and ("---" in l or l.replace("|", "").replace(" ", "") == "출처제목링크작성일") for l in lines):
        return False
    return len(body) > 80


class BlogPublisher:
    """수집·요약 결과를 별도 ai_news_blog 레포(Quartz)에 publish."""

    def __init__(self):
        default_path = str(Path(__file__).resolve().parent.parent.parent / "ai_news_blog")
        self.blog_repo = Path(os.getenv("BLOG_REPO_PATH", default_path)).resolve()
        self.posts_dir = self.blog_repo / "content" / "posts"
        self.site_url = os.getenv(
            "BLOG_SITE_URL", "https://altjs4510.github.io/ai_news_blog"
        ).rstrip("/")

    def publish(self, report_dir: str, date_str: str) -> str | None:
        if not self.blog_repo.is_dir():
            logger.error(f"블로그 레포를 찾을 수 없습니다: {self.blog_repo}")
            return None

        src = Path(report_dir)
        if not src.is_dir():
            logger.error(f"리포트 디렉토리가 없습니다: {report_dir}")
            return None

        target = self.posts_dir / date_str
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)

        display_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")

        # 1) 메인 페이지 = summary 본문 + Reddit 깊이 분석
        summary_path = src / "summary.md"
        summary_body = ""
        if summary_path.exists():
            summary_body = _strip_existing_frontmatter(
                summary_path.read_text(encoding="utf-8")
            ).strip()

        combined_path = src / "combined_insights.md"
        combined_body = ""
        if combined_path.exists():
            text = combined_path.read_text(encoding="utf-8")
            text = _strip_existing_frontmatter(text)
            combined_body = text.strip()

        sections = []
        if summary_body:
            sections.append(summary_body)
        if combined_body:
            sections.append(combined_body)
        sections.append("---\n\n📂 [원본 수집 데이터 펼쳐보기](raw)")

        if sections:
            index_md = (
                "---\n"
                f'title: "{display_date} AI 동향 요약"\n'
                f"date: {display_date}\n"
                "---\n\n"
                + "\n\n---\n\n".join(sections)
                + "\n"
            )
        else:
            index_md = (
                "---\n"
                f'title: "{display_date} AI 동향"\n'
                f"date: {display_date}\n"
                "---\n\n"
                "이번 호는 요약 생성에 실패했습니다. 원본 수집 데이터는 [raw](raw) 페이지에서 확인할 수 있습니다.\n"
            )
        (target / "index.md").write_text(index_md, encoding="utf-8")

        # 2) 모든 raw 데이터를 단일 페이지로 묶음
        raw_sections = []
        for label, fname in RAW_SOURCES:
            fpath = src / fname
            if not fpath.exists():
                continue
            content = fpath.read_text(encoding="utf-8")
            if not _is_meaningful(content):
                continue
            body = _strip_existing_frontmatter(content)
            body = _strip_leading_h1(body)
            raw_sections.append(f"## {label}\n\n{body.strip()}")

        if raw_sections:
            raw_md = (
                "---\n"
                f'title: "{display_date} 원본 수집 데이터"\n'
                f"date: {display_date}\n"
                "---\n\n"
                "수집된 원본 데이터를 한곳에 모았습니다. 요약은 [메인 페이지](.)에서 보실 수 있습니다.\n\n"
                + "\n\n---\n\n".join(raw_sections)
            )
            (target / "raw.md").write_text(raw_md, encoding="utf-8")

        # 3) 홈 (content/index.md) = 최신 summary + 아카이브 안내
        self._update_home(date_str, display_date, summary_body)

        if not self._git_commit_and_push(date_str):
            return None

        return f"{self.site_url}/posts/{date_str}/"

    def _update_home(self, date_str: str, display_date: str, summary_body: str) -> None:
        intro = (
            "---\n"
            'title: "AI News Digest"\n'
            "---\n\n"
            "AI 동향을 자동 수집·요약해 매주 발행하는 블로그입니다.\n"
            "수집 소스: Anthropic / OpenAI / Google AI 공식 블로그, GitHub Trending, Reddit (AI 서브레딧).\n"
            "수집·번역·요약은 Anthropic Claude 모델이 담당합니다.\n\n"
            f"## 가장 최근 발행: [{display_date}](posts/{date_str}/)\n\n"
        )
        body = summary_body.strip() if summary_body else "_(이번 호는 요약 생성에 실패했습니다.)_"
        archive = (
            "\n\n---\n\n"
            "[📚 발행 아카이브 전체 보기](posts/)\n"
        )
        (self.blog_repo / "content" / "index.md").write_text(intro + body + archive, encoding="utf-8")

    def _git_commit_and_push(self, date_str: str) -> bool:
        try:
            subprocess.run(
                ["git", "-C", str(self.blog_repo), "add", "content/"],
                check=True,
                capture_output=True,
            )
            staged = subprocess.run(
                ["git", "-C", str(self.blog_repo), "diff", "--cached", "--quiet"]
            )
            if staged.returncode == 0:
                logger.info("블로그에 변경 사항이 없어 commit을 건너뜁니다.")
                return True
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.blog_repo),
                    "commit",
                    "-m",
                    f"chore: publish {date_str} digest",
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(self.blog_repo), "push"],
                check=True,
                capture_output=True,
            )
            logger.info(f"블로그 publish 완료: {date_str}")
            return True
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            logger.error(f"git 동작 실패: {e} / {stderr}")
            return False
