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

    @staticmethod
    def _detail_hero_html(kind: str, display_date: str, meta: str, title: str) -> str:
        """상세 페이지 hero — 홈 hero와 같은 결.
        kind 텍스트는 섹션 인덱스로 돌아가는 클릭 가능한 백링크가 된다."""
        t = (title or "").strip().replace("&", "&amp;").replace("<", "&lt;")
        return (
            '<header class="ai-post-hero">\n'
            f'  <p class="ai-eyebrow"><a class="ai-back" href="../">{kind}</a> · {display_date} · {meta}</p>\n'
            f'  <h1 class="ai-post-title">{t}</h1>\n'
            "</header>\n\n"
        )

    @staticmethod
    def _section_index_text(title: str) -> str:
        """Hextra 'blog' 레이아웃을 cascade로 강제 — 좌측 docs sidebar 제거.
        섹션 페이지 본문은 비워둔다(h1·intro CSS hide와 짝). title은 브라우저 탭용."""
        return (
            "---\n"
            f'title: "{title}"\n'
            "type: blog\n"
            "cascade:\n"
            "  type: blog\n"
            "  toc: false\n"
            "toc: false\n"
            "---\n"
        )

    def _ensure_blog_section(self, section_dir: Path, title: str) -> None:
        section_dir.mkdir(parents=True, exist_ok=True)
        idx = section_dir / "_index.md"
        desired = self._section_index_text(title)
        if not idx.exists() or idx.read_text(encoding="utf-8") != desired:
            idx.write_text(desired, encoding="utf-8")

    def publish(
        self,
        report_dir: str,
        date_str: str,
        keywords: list[str] | None = None,
        headline: str | None = None,
        spotlight: dict | None = None,
        additional_picks: list[dict] | None = None,
        has_study: bool = False,
    ) -> str | None:
        if not self.blog_repo.is_dir():
            logger.error(f"블로그 레포를 찾을 수 없습니다: {self.blog_repo}")
            return None

        src = Path(report_dir)
        if not src.is_dir():
            logger.error(f"리포트 디렉토리가 없습니다: {report_dir}")
            return None

        # 두 섹션의 _index.md를 항상 'blog' 레이아웃으로 정규화 — Hextra 좌측
        # docs 사이드바 제거. 사용자가 본 "Knowledge가 사라지고 지식이 요약 하위에"
        # 인상은 docs 트리가 두 섹션을 한 사이드바에 펼친 결과였음.
        self._ensure_blog_section(self.posts_dir, "Posts")
        self._ensure_blog_section(self.blog_repo / "content" / "knowledge", "Knowledge")

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
        # 포스트 상단에 학습 노트 진입 배너 (별도 knowledge 섹션의 자식 글로 링크)
        if study_body:
            sections.append(
                "{{< callout emoji=\"📚\" >}}\n"
                f"[학습 노트 열기 →]({{{{< relref \"knowledge/{date_str}\" >}}}})\n"
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

        # 상세 페이지 hero — 홈 hero와 같은 톤. headline이 비어 있으면 일자 fallback.
        post_h1 = (headline or f"{display_date} AI 동향").strip()
        post_hero = self._detail_hero_html("POSTS", display_date, "주간 요약", post_h1)

        if sections:
            index_md = (
                "---\n"
                f'title: "{post_h1}"\n'   # frontmatter title = headline (브라우저 탭 + 카드)
                f"date: {display_date}\n"
                + tags_yaml
                + "---\n\n"
                + post_hero
                + "\n\n---\n\n".join(sections)
                + "\n"
            )
        else:
            index_md = (
                "---\n"
                f'title: "{post_h1}"\n'
                f"date: {display_date}\n"
                + tags_yaml
                + "---\n\n"
                + post_hero
                + "이번 호는 요약 생성에 실패했습니다. 원본 수집 데이터는 [raw](raw) 페이지에서 확인할 수 있습니다.\n"
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

        # 2.5) 학습 브리프 — 별도 'knowledge' 섹션에 누적 (블로그형 아카이브).
        # posts/<date>/study/ 자식 페이지가 아니라 /knowledge/<date>/ 독립 글로 발행.
        study_url_path: str | None = None
        if study_body:
            sp_title = (spotlight or {}).get("title", "").strip() if isinstance(spotlight, dict) else ""
            sp_url = (spotlight or {}).get("url", "").strip() if isinstance(spotlight, dict) else ""
            sp_title_yaml = sp_title.replace('"', "'")

            # _ensure_blog_section()이 publish 시작부에서 이미 _index.md 작성 완료.
            knowledge_dir = self.blog_repo / "content" / "knowledge"

            # 본문 상단 — 원문 + 출처 호 백링크
            origin_block_parts = []
            if sp_url:
                origin_block_parts.append(f"> 원문: [{sp_title or sp_url}]({sp_url})")
            origin_block_parts.append(
                f"> ↩ 출처 호: [{display_date} AI 동향 요약]"
                f"({{{{< relref \"posts/{date_str}\" >}}}})"
            )
            origin_block = "\n".join(origin_block_parts) + "\n\n"

            tags_yaml_k = ""
            if clean_tags:
                quoted = ", ".join(f'"{t}"' for t in clean_tags)
                tags_yaml_k = f"tags: [{quoted}]\n"

            # 상세 페이지 hero — 홈/포스트와 같은 결.
            knowledge_h1 = sp_title or display_date
            knowledge_hero = self._detail_hero_html(
                "KNOWLEDGE", display_date, "학습 노트", knowledge_h1
            )

            knowledge_md = (
                "---\n"
                f'title: "{sp_title_yaml or display_date}"\n'
                f"date: {display_date}\n"
                + (f'source_url: "{sp_url}"\n' if sp_url else "")
                + tags_yaml_k
                + "---\n\n"
                + knowledge_hero
                + origin_block
                + study_body
                + "\n"
            )
            (knowledge_dir / f"{date_str}.md").write_text(knowledge_md, encoding="utf-8")
            study_url_path = f"knowledge/{date_str}/"

        # 3) 홈 (content/_index.md) = 최신 summary + 아카이브 안내
        self._update_home(
            date_str, display_date, combined_body, headline, spotlight, clean_tags,
            study_url_path=study_url_path,
            additional_picks=additional_picks,
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
        additional_picks: list[dict] | None = None,
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

        # ─ Additional picks — "꼭 읽어보세요" 보조 카드 0~2개 ───────────────
        additional_html = ""
        if additional_picks:
            cards = []
            for pick in additional_picks:
                p_title = (pick.get("title") or "").strip()
                p_url = (pick.get("url") or "").strip()
                p_summary = (pick.get("summary") or "").strip()
                if not p_title or not p_summary:
                    continue
                p_title_e = p_title.replace("&", "&amp;").replace("<", "&lt;")
                p_sum_e = p_summary.replace("&", "&amp;").replace("<", "&lt;")
                title_block = (
                    f'<a class="ai-pick-title" href="{p_url}" target="_blank" rel="noopener">'
                    f'{p_title_e}<span class="ai-pick-arrow">↗</span></a>'
                    if p_url
                    else f'<span class="ai-pick-title">{p_title_e}</span>'
                )
                cards.append(
                    f'<article class="ai-pick">\n'
                    f'  {title_block}\n'
                    f'  <p class="ai-pick-summary">{p_sum_e}</p>\n'
                    f'</article>'
                )
            if cards:
                additional_html = (
                    '<section class="ai-additional">\n'
                    '  <p class="ai-eyebrow">ALSO WORTH READING · 꼭 읽어보세요</p>\n'
                    '  <div class="ai-pick-list">\n  '
                    + "\n  ".join(cards) + "\n"
                    "  </div>\n"
                    "</section>\n\n"
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
            '<a href="posts/">📰 주간 요약</a>'
            '<span class="ai-dot">·</span>'
            '<a href="knowledge/">📚 학습 노트</a>'
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
            + additional_html
            + tags_html
            + body_block
            + footer
        )
        (self.blog_repo / "content" / "_index.md").write_text(page, encoding="utf-8")

    def _git_commit_and_push(self, date_str: str) -> bool:
        """블로그 레포에 commit 후 push. push race가 흔해서 rebase 재시도 포함."""

        def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
            return subprocess.run(
                ["git", "-C", str(self.blog_repo), *args],
                check=check,
                capture_output=True,
            )

        try:
            _run(["add", "content/"])
            staged = _run(["diff", "--cached", "--quiet"], check=False)
            if staged.returncode == 0:
                logger.info("블로그에 변경 사항이 없어 commit을 건너뜁니다.")
                return True
            _run(["commit", "-m", f"chore: publish {date_str} digest"])
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            logger.error(f"git 커밋 실패: {e} / {stderr}")
            return False

        # 푸시 race 대비. 최대 3회 시도: push 실패 시 pull --rebase 후 재시도.
        # 동시에 다른 사용자가 같은 ref에 push했어도 자동 회복.
        for attempt in range(3):
            try:
                _run(["push"])
                logger.info(f"블로그 publish 완료: {date_str}")
                return True
            except subprocess.CalledProcessError as e:
                stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
                logger.warning(
                    f"git push 실패 (시도 {attempt + 1}/3): {stderr.strip()[:200]}"
                )
                # 마지막 시도 실패는 그대로 종료
                if attempt == 2:
                    logger.error(f"git push 최종 실패: {stderr}")
                    return False
                # pull --rebase로 원격 변경 흡수 후 재시도
                try:
                    _run(["pull", "--rebase", "origin", "main"])
                    logger.info("pull --rebase 완료, push 재시도")
                except subprocess.CalledProcessError as pe:
                    pe_stderr = pe.stderr.decode("utf-8", errors="replace") if pe.stderr else ""
                    logger.error(f"pull --rebase 실패: {pe_stderr}")
                    return False
        return False
