import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from utils.logger import setup_logger

logger = setup_logger('blog_publisher')

RAW_SOURCES = [
    ("AI 블로그 (공식·엔지니어링·에이전트·큐레이션)", "ai_blogs_raw.md"),
    ("Bluesky 와글와글 (주요 AI 인물 단문 — X 대체)", "bluesky_raw.md"),
    ("GitHub (Trending + MCP/Agent 토픽)", "github_raw.md"),
    ("Hacker News · Product Hunt · TechCrunch AI", "news_raw.md"),
    ("arxiv · HuggingFace Papers (학술/연구)", "research_raw.md"),
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

    def publish(
        self,
        report_dir: str,
        date_str: str,
        keywords: list[str] | None = None,
        headline: str | None = None,
        spotlight: dict | None = None,
        has_study: bool = False,
    ) -> str | None:
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

        # 학습 브리프 입력
        study_src = src / "study.md"
        study_body = ""
        if has_study and study_src.exists():
            study_body = study_src.read_text(encoding="utf-8").strip()

        sections = []
        if summary_body:
            sections.append(summary_body)
        # 포스트 상단에 학습 브리프 진입 배너
        if study_body:
            sections.append(
                "{{< callout emoji=\"📚\" >}}\n"
                "**오늘의 학습 — Spotlight 자료 한 건을 한국어로 정리** "
                "→ [학습 브리프 열기](study)\n"
                "{{< /callout >}}"
            )
        if combined_body:
            sections.append(combined_body)
        sections.append("---\n\n📂 [원본 수집 데이터 펼쳐보기](raw)")

        # 키워드를 Hugo taxonomy(tags)에 노출 → /tags/<keyword>/ 자동 생성
        # 백틱(`...`)이 붙은 키워드는 벗기고, 양옆 공백 정리
        clean_tags = []
        for k in (keywords or []):
            if not k:
                continue
            t = str(k).strip().strip("`").strip()
            if t and t not in clean_tags:
                clean_tags.append(t)
        tags_yaml = ""
        if clean_tags:
            quoted = ", ".join(f'"{t}"' for t in clean_tags)
            tags_yaml = f"tags: [{quoted}]\n"

        if sections:
            index_md = (
                "---\n"
                f'title: "{display_date} AI 동향 요약"\n'
                f"date: {display_date}\n"
                + tags_yaml
                + "---\n\n"
                + "\n\n---\n\n".join(sections)
                + "\n"
            )
        else:
            index_md = (
                "---\n"
                f'title: "{display_date} AI 동향"\n'
                f"date: {display_date}\n"
                + tags_yaml
                + "---\n\n"
                "이번 호는 요약 생성에 실패했습니다. 원본 수집 데이터는 [raw](raw) 페이지에서 확인할 수 있습니다.\n"
            )
        (target / "_index.md").write_text(index_md, encoding="utf-8")

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

        # 2.5) 학습 브리프 — Spotlight 자료 1건 한국어 정리
        study_url_path: str | None = None
        if study_body:
            sp_title = (spotlight or {}).get("title", "").strip() if isinstance(spotlight, dict) else ""
            sp_url = (spotlight or {}).get("url", "").strip() if isinstance(spotlight, dict) else ""
            sp_title_yaml = sp_title.replace('"', "'")
            origin_block = (
                f"> 원문: [{sp_title or sp_url}]({sp_url})\n\n"
                if sp_url
                else ""
            )
            study_md = (
                "---\n"
                f'title: "📚 오늘의 학습 — {sp_title_yaml or display_date}"\n'
                f"date: {display_date}\n"
                "---\n\n"
                + origin_block
                + study_body
                + "\n"
            )
            (target / "study.md").write_text(study_md, encoding="utf-8")
            study_url_path = f"posts/{date_str}/study/"

        # 3) 홈 (content/_index.md) = 최신 summary + 아카이브 안내
        self._update_home(
            date_str, display_date, combined_body, headline, spotlight, clean_tags,
            study_url_path=study_url_path,
        )

        if not self._git_commit_and_push(date_str):
            return None

        return f"{self.site_url}/posts/{date_str}/"

    def _update_home(
        self,
        date_str: str,
        display_date: str,
        body_text: str,
        headline: str | None = None,
        spotlight: dict | None = None,
        keywords: list[str] | None = None,
        study_url_path: str | None = None,
    ) -> None:
        """홈 _index.md 작성. body_text는 combined_insights 본문(요약 callout 중복 회피)."""
        # ─ Hero ────────────────────────────────────────────────────────────
        # Apple 톤: 작은 eyebrow + 거대한 헤드라인 + 무거운 메타.
        # goldmark unsafe=true 가 켜져 있어 raw HTML 통과.
        headline_text = (headline or f"{display_date} AI 동향").strip()
        # HTML escape 최소만 — 본문 큐레이션은 Claude가 만들어 신뢰 가능 텍스트.
        headline_html = headline_text.replace("&", "&amp;").replace("<", "&lt;")

        # 보조 CTA — 학습 브리프가 있을 때만 노출
        secondary_cta = (
            f'    <a class="ai-cta ai-cta-secondary" href="{study_url_path}">\n'
            '      <span class="ai-cta-label">📚 오늘의 학습</span>\n'
            '      <span class="ai-cta-arrow" aria-hidden="true">→</span>\n'
            "    </a>\n"
            if study_url_path
            else ""
        )

        hero_html = (
            '<section class="ai-home-hero">\n'
            '  <p class="ai-eyebrow">AI NEWS · WEEKLY DIGEST</p>\n'
            f'  <h1 class="ai-headline">{headline_html}</h1>\n'
            f'  <p class="ai-meta">{display_date} · 매주 월요일 자동 발행</p>\n'
            '  <div class="ai-cta-row">\n'
            f'    <a class="ai-cta" href="posts/{date_str}/">\n'
            '      <span class="ai-cta-label">최신 호 전체 보기</span>\n'
            '      <span class="ai-cta-arrow" aria-hidden="true">→</span>\n'
            "    </a>\n"
            + secondary_cta
            + "  </div>\n"
            "</section>\n\n"
        )

        # ─ Spotlight 카드 ─────────────────────────────────────────────────
        spotlight_html = ""
        if spotlight and isinstance(spotlight, dict) and spotlight.get("title"):
            sp_title = (spotlight.get("title") or "").strip()
            sp_url = (spotlight.get("url") or "").strip()
            sp_why = (spotlight.get("why") or "").strip()
            sp_app = (spotlight.get("application") or "").strip()
            sp_title_html = sp_title.replace("&", "&amp;").replace("<", "&lt;")
            sp_why_html = sp_why.replace("&", "&amp;").replace("<", "&lt;")
            sp_app_html = sp_app.replace("&", "&amp;").replace("<", "&lt;")

            title_block = (
                f'<a class="ai-spotlight-title" href="{sp_url}" '
                f'target="_blank" rel="noopener">{sp_title_html}<span class="ai-spotlight-arrow">↗</span></a>'
                if sp_url
                else f'<span class="ai-spotlight-title">{sp_title_html}</span>'
            )

            spotlight_html = (
                '<aside class="ai-spotlight">\n'
                '  <p class="ai-eyebrow ai-spotlight-eyebrow">✦ THIS WEEK\'S PICK</p>\n'
                f"  {title_block}\n"
                f'  <p class="ai-spotlight-why">{sp_why_html}</p>\n'
                '  <p class="ai-spotlight-app">'
                '<span class="ai-spotlight-app-label">접목 →</span> '
                f"{sp_app_html}</p>\n"
                "</aside>\n\n"
            )

        # ─ Tag chips ──────────────────────────────────────────────────────
        tags_html = ""
        if keywords:
            chips = "".join(
                f'<a class="ai-chip" href="tags/{k}/">#{k}</a>'
                for k in keywords
            )
            tags_html = f'<nav class="ai-chips">{chips}</nav>\n\n'

        # ─ Body (통합 인사이트 본문) ────────────────────────────────────
        body = body_text.strip() if body_text else ""
        body_block = (
            (
                '<section class="ai-home-body">\n\n'
                f"{body}\n\n"
                "</section>\n\n"
            )
            if body
            else ""
        )

        # ─ Footer (소스·아카이브) ─────────────────────────────────────────
        footer = (
            '<footer class="ai-home-footer">\n'
            '  <p class="ai-eyebrow">SOURCES</p>\n'
            '  <p class="ai-source-list">'
            "Anthropic · OpenAI · Google · DeepMind · "
            "Simon Willison · Latent Space · LangChain · LlamaIndex · "
            "AutoGen · CrewAI · Cursor · Cline · Aider · "
            "Karpathy · Lilian Weng · Hamel Husain · "
            "TLDR AI · The Rundown · AlphaSignal · Ben's Bites · The Batch · "
            "Reddit · Hacker News · Product Hunt · TechCrunch AI · "
            "arxiv · HuggingFace Papers · GitHub Trending · Bluesky"
            "</p>\n"
            '  <p class="ai-home-links">'
            '<a href="posts/">📚 발행 아카이브</a>'
            '<span class="ai-dot">·</span>'
            '<a href="tags/">🏷 태그</a>'
            '<span class="ai-dot">·</span>'
            '<a href="posts/index.xml">🛰 RSS</a>'
            '<span class="ai-dot">·</span>'
            '<a href="about/">📓 소개</a>'
            "</p>\n"
            "</footer>\n"
        )

        page = (
            "---\n"
            'title: "AI News Digest"\n'
            "toc: false\n"
            "---\n\n"
            + hero_html
            + spotlight_html
            + tags_html
            + body_block
            + footer
        )
        (self.blog_repo / "content" / "_index.md").write_text(page, encoding="utf-8")

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
