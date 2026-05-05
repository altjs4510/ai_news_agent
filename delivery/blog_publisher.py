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


def _demote_headings(text: str) -> str:
    """본문 내 모든 ATX 헤딩을 한 단계씩 강등.
    페이지 hero가 이미 h1을 가지므로 본문은 h2부터 시작해야 한다 (H1 중복 방지).
    h6는 그대로 둔다(더 내릴 수 없음).
    """
    def _bump(m: re.Match) -> str:
        hashes = m.group(1)
        rest = m.group(2)
        if len(hashes) >= 6:
            return m.group(0)
        return "#" * (len(hashes) + 1) + rest
    return re.sub(r"(?m)^(#{1,5})(\s+\S)", _bump, text)


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
    def _build_spotlight_html(
        spotlight: dict | None,
        detail_url: str | None = None,
    ) -> str:
        """spotlight 카드. detail_url이 주어지면 카드 하단에 '자세히 보기 →' CTA 버튼을
        그려서 사이트 내 상세(knowledge note)로 바로 점프할 수 있게 한다."""
        if not (spotlight and isinstance(spotlight, dict) and spotlight.get("title")):
            return ""
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

        detail_cta = (
            '  <p class="ai-spotlight-cta">'
            f'<a class="ai-spotlight-detail" href="{detail_url}">'
            '자세히 보기 <span class="ai-spotlight-detail-arrow" aria-hidden="true">→</span>'
            "</a></p>\n"
            if detail_url
            else ""
        )

        return (
            '<aside class="ai-spotlight">\n'
            '  <p class="ai-eyebrow ai-spotlight-eyebrow">✦ TODAY\'S PICK</p>\n'
            f"  {title_block}\n"
            f'  <p class="ai-spotlight-why">{sp_why_html}</p>\n'
            '  <p class="ai-spotlight-app">'
            '<span class="ai-spotlight-app-label">접목 →</span> '
            f"{sp_app_html}</p>\n"
            + detail_cta
            + "</aside>\n\n"
        )

    @staticmethod
    def _build_additional_picks_html(additional_picks: list[dict] | None) -> str:
        if not additional_picks:
            return ""
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
        if not cards:
            return ""
        return (
            '<section class="ai-additional">\n'
            '  <p class="ai-eyebrow">ALSO WORTH READING · 꼭 읽어보세요</p>\n'
            '  <div class="ai-pick-list">\n  '
            + "\n  ".join(cards) + "\n"
            "  </div>\n"
            "</section>\n\n"
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

    def _scan_knowledge_entries(self) -> dict[str, dict]:
        """모든 content/knowledge/<date>.md를 스캔해 {date_str: {title, tags, categories}} 반환."""
        knowledge_dir = self.blog_repo / "content" / "knowledge"
        entries: dict[str, dict] = {}
        if not knowledge_dir.is_dir():
            return entries
        for md in sorted(knowledge_dir.glob("*.md")):
            if md.name == "_index.md":
                continue
            date = md.stem
            try:
                text = md.read_text(encoding="utf-8")
            except Exception:
                continue
            title_m = re.search(r'^title:\s*"(.+?)"', text, re.M)
            tags_m = re.search(r'^tags:\s*\[(.+?)\]', text, re.M)
            cats_m = re.search(r'^categories:\s*\[(.+?)\]', text, re.M)
            title = title_m.group(1) if title_m else date
            tags = []
            if tags_m:
                for raw in tags_m.group(1).split(","):
                    t = raw.strip().strip('"').strip("'").strip()
                    if t:
                        tags.append(t)
            cats = []
            if cats_m:
                for raw in cats_m.group(1).split(","):
                    c = raw.strip().strip('"').strip("'").strip()
                    if c:
                        cats.append(c)
            entries[date] = {"title": title, "tags": tags, "categories": cats}
        return entries

    def _build_knowledge_sidebar_html(self, current_date_str: str | None = None) -> str:
        """카테고리 트리 사이드바. categories(고정 vocabulary) 기준 그룹핑.
        categories가 비어 있는 구버전 엔트리는 그 엔트리의 첫 tag로 fallback.
        """
        entries = self._scan_knowledge_entries()
        if not entries:
            return ""

        # 카테고리 → 엔트리 그룹핑 (날짜 desc)
        by_cat: dict[str, list[tuple[str, str]]] = {}
        for date, info in entries.items():
            cats = info.get("categories") or []
            if not cats:
                # categories 누락된 구버전 엔트리는 첫 tag로 (있으면) 또는 "기타"로
                cats = [info["tags"][0]] if info.get("tags") else ["기타"]
            for cat in cats:
                by_cat.setdefault(cat, []).append((date, info["title"]))
        for cat in by_cat:
            by_cat[cat].sort(key=lambda x: x[0], reverse=True)

        # vocabulary 순서 우선 + 그 외(레거시)는 카운트 desc로 뒤에
        sorted_cats = []
        seen = set()
        # vocabulary 정의 순서대로 먼저
        from main import CATEGORY_VOCABULARY  # 지연 import: vocabulary는 main.py 단일 출처
        for v in CATEGORY_VOCABULARY:
            if v in by_cat:
                sorted_cats.append((v, by_cat[v]))
                seen.add(v)
        # vocabulary 밖 (레거시 fallback) 카테고리는 뒤에 카운트 desc
        leftovers = [(c, items) for c, items in by_cat.items() if c not in seen]
        leftovers.sort(key=lambda x: (-len(x[1]), x[0]))
        sorted_cats.extend(leftovers)

        blocks = []
        for cat, items in sorted_cats:
            cat_e = cat.replace("&", "&amp;").replace("<", "&lt;")
            is_open = any(d == current_date_str for d, _ in items) or len(by_cat) <= 8
            open_attr = " open" if is_open else ""
            li_html = []
            for date, title in items:
                display_date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
                t = title.replace("&", "&amp;").replace("<", "&lt;")
                short_t = t[:48] + ("…" if len(t) > 48 else "")
                cls = ' class="current"' if date == current_date_str else ""
                li_html.append(
                    f'<li><a href="{self.site_url}/knowledge/{date}/"{cls}>'
                    f'<span class="kdate">{display_date}</span>'
                    f'<span class="ktitle">{short_t}</span>'
                    f"</a></li>"
                )
            blocks.append(
                f'<details class="ai-cat"{open_attr}>'
                f'<summary><span class="catname">{cat_e}</span>'
                f'<span class="catcount">{len(items)}</span></summary>'
                f'<ul>{"".join(li_html)}</ul>'
                f"</details>"
            )

        return (
            '<aside class="ai-knowledge-sidebar">\n'
            '  <p class="ai-eyebrow">CATEGORIES</p>\n'
            '  <nav class="ai-cat-tree">'
            + "".join(blocks)
            + "</nav>\n"
            "</aside>"
        )

    def refresh_all_knowledge_sidebars(self) -> int:
        """모든 content/knowledge/<date>.md의 사이드바 HTML 블록 갱신.

        curate.py가 frontmatter categories를 변경한 뒤 호출.
        index와 detail 모두 같은 사이드바 빌더를 씀.
        반환: 갱신된 파일 수.
        """
        knowledge_dir = self.blog_repo / "content" / "knowledge"
        if not knowledge_dir.is_dir():
            return 0
        updated = 0
        sidebar_re = re.compile(
            r'<aside class="ai-knowledge-sidebar">.*?</aside>', re.S
        )
        for md in knowledge_dir.glob("*.md"):
            if md.name == "_index.md":
                continue
            text = md.read_text(encoding="utf-8")
            date_str = md.stem
            new_sidebar = self._build_knowledge_sidebar_html(current_date_str=date_str)
            if not new_sidebar:
                continue
            new_text, count = sidebar_re.subn(new_sidebar, text, count=1)
            if count and new_text != text:
                md.write_text(new_text, encoding="utf-8")
                updated += 1
        # /knowledge/_index.md도 같이 갱신
        self._refresh_knowledge_index()
        logger.info(f"사이드바 갱신: {updated}건")
        return updated

    def _refresh_knowledge_index(self) -> None:
        """/knowledge/ 인덱스 페이지에 좌측 카테고리 사이드바를 emit.
        Hextra가 자동 출력하는 글 카드들과 CSS Grid로 좌-우 배치된다.
        """
        knowledge_dir = self.blog_repo / "content" / "knowledge"
        if not knowledge_dir.is_dir():
            return

        sidebar_html = self._build_knowledge_sidebar_html(current_date_str=None)
        base = self._section_index_text("Knowledge")
        if not sidebar_html:
            (knowledge_dir / "_index.md").write_text(base, encoding="utf-8")
            return

        # 사이드바만 본문에 두고, Hextra가 자체 emit하는 카드 그리드는 CSS로 우측 컬럼 배치.
        # main 그리드에서 사이드바와 카드가 함께 보이도록 .content는 display:contents로 흐려짐.
        (knowledge_dir / "_index.md").write_text(base + "\n" + sidebar_html + "\n", encoding="utf-8")

    def publish(
        self,
        report_dir: str,
        date_str: str,
        keywords: list[str] | None = None,
        headline: str | None = None,
        spotlight: dict | None = None,
        additional_picks: list[dict] | None = None,
        categories: list[str] | None = None,
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

        # 메인 인사이트 본문 (combined_insights) — 홈/포스트 공통 body
        combined_path = src / "combined_insights.md"
        combined_body = ""
        if combined_path.exists():
            text = combined_path.read_text(encoding="utf-8")
            text = _strip_existing_frontmatter(text)
            combined_body = text.strip()

        # 학습 브리프 — 별도 /knowledge/<date>/에 발행. 홈/포스트 hero의 보조 CTA로 링크.
        study_src = src / "study.md"
        study_body = ""
        if has_study and study_src.exists():
            study_body = study_src.read_text(encoding="utf-8").strip()
        # study_url_path는 knowledge 페이지가 실제 발행될 때만 set — 홈/포스트의 보조 CTA를
        # 미리 가리킬 수 있도록 study_body 존재로 선판단.
        study_url_path: str | None = (
            f"knowledge/{date_str}/" if study_body else None
        )

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

        cats_yaml = ""
        if categories:
            quoted = ", ".join(f'"{c}"' for c in categories)
            cats_yaml = f"categories: [{quoted}]\n"

        post_h1 = (headline or f"{display_date} AI 동향").strip()

        # Posts 상세 페이지는 그날의 홈 컨텐츠(spotlight/추천/태그/본문/푸터)를
        # 그대로 아카이브하되, hero만 post 전용 디자인으로 — 좌상단 ← POSTS 백링크
        # 가 자연스럽게 목록(/posts/)으로 돌아가는 진입점이 된다. 홈은 자기 hero
        # (ai-home-hero) 그대로 유지.
        post_hero = self._detail_hero_html(
            "POSTS", display_date, "일간 요약", post_h1
        )
        home_body_for_post = self._build_home_body(
            date_str=date_str,
            display_date=display_date,
            body_text=combined_body,
            headline=headline,
            spotlight=spotlight,
            keywords=clean_tags,
            study_url_path=study_url_path,
            additional_picks=additional_picks,
            hero_html=post_hero,
        )
        raw_link_block = (
            '\n<p class="ai-post-raw">'
            '<a href="raw">📂 원본 수집 데이터 펼쳐보기 →</a>'
            "</p>\n"
        )

        if combined_body:
            index_md = (
                "---\n"
                f'title: "{post_h1}"\n'
                f"date: {display_date}\n"
                "toc: true\n"
                "customHero: true\n"
                + tags_yaml
                + cats_yaml
                + "---\n\n"
                + home_body_for_post
                + raw_link_block
            )
        else:
            index_md = (
                "---\n"
                f'title: "{post_h1}"\n'
                f"date: {display_date}\n"
                "toc: true\n"
                "customHero: true\n"
                + tags_yaml
                + cats_yaml
                + "---\n\n"
                + home_body_for_post
                + "\n이번 호는 요약 생성에 실패했습니다. 원본 수집 데이터는 [raw](raw) 페이지에서 확인할 수 있습니다.\n"
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
        # study_url_path는 publish 상단에서 study_body 존재로 미리 set됨.
        if study_body:
            sp_title = (spotlight or {}).get("title", "").strip() if isinstance(spotlight, dict) else ""
            sp_url = (spotlight or {}).get("url", "").strip() if isinstance(spotlight, dict) else ""
            sp_title_yaml = sp_title.replace('"', "'")

            # _ensure_blog_section()이 publish 시작부에서 이미 _index.md 작성 완료.
            knowledge_dir = self.blog_repo / "content" / "knowledge"

            # 본문 상단 — 원문 + 출처 호 백링크.
            # 두 줄을 같은 인용 블록 안에서 단락 분리되게 ">" 빈 줄을 사이에 둠.
            # (단순 "\n"으로 잇기만 하면 markdown이 한 단락으로 합쳐 한 줄로 렌더됨)
            origin_block_parts = []
            if sp_url:
                origin_block_parts.append(f"> 원문: [{sp_title or sp_url}]({sp_url})")
            origin_block_parts.append(
                f"> ↩ 출처 호: [{display_date} AI 동향 요약]"
                f"({{{{< relref \"posts/{date_str}\" >}}}})"
            )
            origin_block = "\n>\n".join(origin_block_parts) + "\n\n"

            tags_yaml_k = ""
            if clean_tags:
                quoted = ", ".join(f'"{t}"' for t in clean_tags)
                tags_yaml_k = f"tags: [{quoted}]\n"

            cats_yaml_k = ""
            if categories:
                quoted = ", ".join(f'"{c}"' for c in categories)
                cats_yaml_k = f"categories: [{quoted}]\n"

            # 상세 페이지 hero — 홈/포스트와 같은 결.
            knowledge_h1 = sp_title or display_date
            knowledge_hero = self._detail_hero_html(
                "KNOWLEDGE", display_date, "학습 노트", knowledge_h1
            )

            # ▶ 새 entry를 디렉토리에 먼저 (빈 placeholder로) 두면 스캔 시 자기 자신도 포함.
            placeholder = (
                "---\n"
                f'title: "{sp_title_yaml or display_date}"\n'
                f"date: {display_date}\n"
                + tags_yaml_k
                + cats_yaml_k
                + "---\n"
            )
            (knowledge_dir / f"{date_str}.md").write_text(placeholder, encoding="utf-8")

            sidebar_html = self._build_knowledge_sidebar_html(current_date_str=date_str)

            # 본문을 shell로 감싸 좌측 카테고리 트리 + 우측 article 레이아웃 구성.
            # goldmark는 raw HTML 블록 안의 markdown을 처리하지 않으므로
            # 태그 주변에 빈 줄을 두어 markdown 모드를 다시 활성화한다.
            knowledge_md = (
                "---\n"
                f'title: "{sp_title_yaml or display_date}"\n'
                f"date: {display_date}\n"
                + (f'source_url: "{sp_url}"\n' if sp_url else "")
                + tags_yaml_k
                + cats_yaml_k
                + "---\n\n"
                '<div class="ai-knowledge-shell">\n\n'
                + sidebar_html
                + "\n\n"
                '<article class="ai-knowledge-article">\n\n'
                + knowledge_hero
                + origin_block
                + study_body
                + "\n\n"
                "</article>\n\n"
                "</div>\n"
            )
            (knowledge_dir / f"{date_str}.md").write_text(knowledge_md, encoding="utf-8")

            # /knowledge/ 인덱스 상단 카테고리 칩 strip 갱신 (누적 태그 집계)
            self._refresh_knowledge_index()

        # 3) 홈 (content/_index.md) = 최신 summary + 아카이브 안내
        self._update_home(
            date_str, display_date, combined_body, headline, spotlight, clean_tags,
            study_url_path=study_url_path,
            additional_picks=additional_picks,
        )

        if not self._git_commit_and_push(date_str):
            return None

        return f"{self.site_url}/posts/{date_str}/"

    def _build_home_body(
        self,
        date_str: str,
        display_date: str,
        body_text: str,
        headline: str | None = None,
        spotlight: dict | None = None,
        keywords: list[str] | None = None,
        study_url_path: str | None = None,
        additional_picks: list[dict] | None = None,
        hero_html: str | None = None,
    ) -> str:
        """홈/포스트 상세 공용 본문(프론트매터 제외) 생성. 모든 내부 링크는 site_url
        절대 경로로 — / 와 /posts/<date>/ 양쪽에서 동일하게 동작하기 위함.
        hero_html이 주어지면 그것을 사용 (포스트 상세는 _detail_hero_html("POSTS"…)
        를 넘겨 자기만의 hero를 갖는다). 미지정 시 홈 hero를 자동 생성."""
        site = self.site_url
        headline_text = (headline or f"{display_date} AI 동향").strip()
        headline_html = headline_text.replace("&", "&amp;").replace("<", "&lt;")

        secondary_cta = (
            f'    <a class="ai-cta ai-cta-secondary" href="{site}/{study_url_path}">\n'
            '      <span class="ai-cta-label">📚 오늘의 학습</span>\n'
            '      <span class="ai-cta-arrow" aria-hidden="true">→</span>\n'
            "    </a>\n"
            if study_url_path
            else ""
        )

        if hero_html is None:
            hero_html = (
                '<section class="ai-home-hero">\n'
                '  <p class="ai-eyebrow">AI NEWS · DAILY DIGEST</p>\n'
                f'  <h1 class="ai-headline">{headline_html}</h1>\n'
                f'  <p class="ai-meta">{display_date} · 매일 자동 발행</p>\n'
                '  <div class="ai-cta-row">\n'
                f'    <a class="ai-cta" href="{site}/posts/{date_str}/">\n'
                '      <span class="ai-cta-label">최신 호 전체 보기</span>\n'
                '      <span class="ai-cta-arrow" aria-hidden="true">→</span>\n'
                "    </a>\n"
                + secondary_cta
                + "  </div>\n"
                "</section>\n\n"
            )

        # spotlight pick의 사이트 내 상세 페이지 = 그날의 knowledge note.
        # study_url_path가 있으면 absolute URL로 변환해 spotlight CTA에 연결.
        spotlight_detail_url = (
            f"{site}/{study_url_path}" if study_url_path else None
        )
        spotlight_html = self._build_spotlight_html(
            spotlight, detail_url=spotlight_detail_url
        )
        additional_html = self._build_additional_picks_html(additional_picks)

        tags_html = ""
        if keywords:
            chips = "".join(
                f'<a class="ai-chip" href="{site}/tags/{k}/">#{k}</a>'
                for k in keywords
            )
            tags_html = f'<nav class="ai-chips">{chips}</nav>\n\n'

        body = body_text.strip() if body_text else ""
        if body:
            # hero가 이미 h1이므로 본문 마크다운 헤딩을 한 단계씩 강등 (H1 중복 방지)
            body = _demote_headings(body)
        body_block = (
            (
                '<section class="ai-home-body">\n\n'
                f"{body}\n\n"
                "</section>\n\n"
            )
            if body
            else ""
        )

        footer = (
            '<footer class="ai-home-footer">\n'
            '  <p class="ai-eyebrow">SOURCES</p>\n'
            '  <p class="ai-source-list">'
            "Anthropic · OpenAI · Google · DeepMind · "
            "Simon Willison · Latent Space · LangChain · LlamaIndex · "
            "AutoGen · CrewAI · Cursor · Cline · Aider · "
            "Karpathy · Lilian Weng · Hamel Husain · Matt Pocock (AI Hero) · "
            "TLDR AI · The Rundown · AlphaSignal · Ben's Bites · The Batch · "
            "Reddit · Hacker News · Product Hunt · TechCrunch AI · "
            "arxiv · HuggingFace Papers · GitHub Trending · Bluesky"
            "</p>\n"
            '  <p class="ai-home-links">'
            f'<a href="{site}/posts/">📰 일간 요약</a>'
            '<span class="ai-dot">·</span>'
            f'<a href="{site}/knowledge/">📚 학습 노트</a>'
            '<span class="ai-dot">·</span>'
            f'<a href="{site}/tags/">🏷 태그</a>'
            '<span class="ai-dot">·</span>'
            f'<a href="{site}/posts/index.xml">🛰 RSS</a>'
            '<span class="ai-dot">·</span>'
            f'<a href="{site}/about/">📓 소개</a>'
            "</p>\n"
            "</footer>\n"
        )

        return (
            hero_html
            + spotlight_html
            + additional_html
            + tags_html
            + body_block
            + footer
        )

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
        body = self._build_home_body(
            date_str=date_str,
            display_date=display_date,
            body_text=body_text,
            headline=headline,
            spotlight=spotlight,
            keywords=keywords,
            study_url_path=study_url_path,
            additional_picks=additional_picks,
        )
        page = (
            "---\n"
            'title: "AI News Digest"\n'
            "toc: false\n"
            "---\n\n"
            + body
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
