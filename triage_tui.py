"""triage_tui.py — 하루치 raw 수집물(reports/{date}/*_raw.md)을 좌측 폴더에서 훑으며
skip / queue(나중에) / one-off / reference 4가지로만 트리아지하는 개인용 터미널 UI.

카테고리(main.py CATEGORY_VOCABULARY 8종)는 curate.py 가 발행 후 자동으로 붙여주므로
지정은 **선택 사항**이다(2026-08-20 (4) 피드백: "왜 아예 제거했냐, 필요하면 수정할 수도
있는건데" — 필수→선택으로 정정). 우측 하단 액션 바의 드롭다운(또는 숫자 1~8)으로 아무 때나
고를 수 있고, 비워두면(blank) curate.py 판단에 맡겨진다.

우측 하단 액션 바 = 실제 클릭 가능한 버튼(2026-08-31 피드백: "버튼 만들어달라니까는" —
키보드 단축키만으로는 부족했음): [읽음 토글] [카테고리 드롭다운] [Skip] [나중에] [One-off]
[Reference]. 키보드 s/q/o/r/m 과 완전히 동등하게 동작하며 서로 상태를 공유한다.

핵심 모델: 좌측 상단 폴더 = "미분류"(아직 안 본 것) + "나중에"(queue) + "건너뜀"(skip) +
"one-off(발행대기)" + "reference(발행대기)". 판정하면 해당 폴더로 이동. **114건을 오늘
안에 0으로 만들어야 하는 할 일 목록이 아니다** — 훑다가 눈에 띄는 것만 처리하고, 나머지는
그냥 미분류에 남겨둔 채 종료해도 된다(아무 판정 안 한 항목은 아무 데도 안 감).

배경: LLM이 하루 수집물 중 spotlight 1개만 골라 블로그로 보내는 현재 파이프라인은
(1) 나머지가 전부 버려지고 (2) "1회성 vs 레퍼런스" 성격 구분이 아예 없다는 문제가 있었음.
여기서 나온 결정이 나중에 (a) one-off/reference 둘 다 → 블로그 지식노트로 발행,
(b) reference 는 발행 후 curate.py 가 붙인 카테고리를 그대로 물려받아 ai-news.okf concept
으로도 미러링(아직 미연동, 이 스크립트는 트리아지 결정을 state/triage/{date}.jsonl 에
기록하는 데까지만).

사용법:
    uv run python triage_tui.py [YYYYMMDD]   # 생략 시 오늘(KST). 같은 날 재실행하면
                                              # 이전 판정이 각자 폴더에 복원된 채로 이어짐.

조작:
    Tab           폴더 목록 ↔ 항목 목록 포커스 전환
    j/k, ↓/↑      포커스된 목록에서 이동
    s/q/o/r       현재 항목 판정(skip/queue/one-off/reference) — 그 시점 카테고리 드롭다운
                  값을 그대로 붙여 저장(버튼 클릭과 동일 동작)
    1~8           카테고리 드롭다운 값만 설정(판정은 별개 — s/q/o/r 나 버튼으로)
    m             읽음/안읽음 토글(판정과 별개 축 — state/read_status.json, 2026-08-31 추가)
    Ctrl+Q        종료(그때까지 판정은 이미 저장됨)

카테고리 폴더(하단 8개)는 사람이 트리아지에서 지정한 카테고리가 없으면, Medium 자동화처럼
항목 자체에 이미 붙어있는 카테고리를 그대로 보여준다 — 굳이 재분류 안 해도 바로 걸러 보인다.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, ListView, ListItem, Label, Static, Button, Select, Markdown

from delivery.study_brief import fetch_article_text  # 이미 spotlight 1건에만 쓰던 본문 fetch를 재사용

REPORTS = Path(__file__).parent / "reports"
STATE_DIR = Path(__file__).parent / "state" / "triage"
MEDIUM_DIR = Path(__file__).parent / "state" / "medium_digest"
BLOG_REPO = Path(os.getenv("BLOG_REPO_PATH", str(Path(__file__).resolve().parent.parent / "ai_news_blog")))

LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)]+)\)")
FRONTMATTER_URL_RE = re.compile(r'^source_url:\s*"([^"]*)"', re.M)
FRONTMATTER_TITLE_RE = re.compile(r'^title:\s*"([^"]*)"', re.M)
ARTICLE_RE = re.compile(r'<article class="ai-knowledge-article">(.*?)</article>', re.S)
HERO_RE = re.compile(r'<header class="ai-post-hero">.*?</header>', re.S)
TAG_RE = re.compile(r"<[^>]+>")


def build_blog_index() -> dict[str, tuple[str, str]]:
    """이미 발행된 지식노트를 source_url 로 색인화 — {url: (title, body)}. 우리 자체
    글이라 저작권 문제 없이 전문 표시 가능(2026-08-24 (2) 피드백: "블로그 글도 같이
    보고 싶다"). content/knowledge/*.md 를 훑는다(daily 자동 발행 + 수기 노트 공용 스키마)."""
    index: dict[str, tuple[str, str]] = {}
    kdir = BLOG_REPO / "content" / "knowledge"
    if not kdir.is_dir():
        return index
    for md in kdir.glob("*.md"):
        if md.name == "_index.md":
            continue
        text = md.read_text(encoding="utf-8")
        m_url = FRONTMATTER_URL_RE.search(text)
        if not m_url or not m_url.group(1):
            continue
        m_title = FRONTMATTER_TITLE_RE.search(text)
        title = m_title.group(1) if m_title else md.stem
        m_article = ARTICLE_RE.search(text)
        body = m_article.group(1) if m_article else text
        body = HERO_RE.sub("", body)
        body = TAG_RE.sub("", body)
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        index[m_url.group(1)] = (title, body)
    return index


FRONTMATTER_DATE_RE = re.compile(r"^date:\s*(\S+)", re.M)
FRONTMATTER_CATEGORIES_RE = re.compile(r"^categories:\s*\[(.*?)\]", re.M)
PUBLISHED = "발행됨"


def load_published_items() -> list[Item]:
    """이미 발행된 지식노트(content/knowledge/*.md)를 TUI에서 훑어볼 수 있게 로드한다
    (2026-09-02 피드백: "발행한 글은 tui에서 어떻게 보냐"). build_blog_index()가 하는
    파싱(ARTICLE_RE로 본문만 추출, 사이드바는 article 밖이라 자동 제외)을 그대로 따라 쓴다.
    이미 끝난 항목이라 트리아지 판정이 필요 없으므로 미분류엔 안 넣는다 — 카테고리 폴더에서만
    보인다(카테고리는 curate.py가 발행 후 붙인 최신 값을 그대로 씀)."""
    items: list[Item] = []
    kdir = BLOG_REPO / "content" / "knowledge"
    if not kdir.is_dir():
        return items
    for md in sorted(kdir.glob("*.md")):
        if md.name == "_index.md":
            continue
        text = md.read_text(encoding="utf-8")
        m_url = FRONTMATTER_URL_RE.search(text)
        if not m_url or not m_url.group(1):
            continue
        m_title = FRONTMATTER_TITLE_RE.search(text)
        title = m_title.group(1) if m_title else md.stem
        m_date = FRONTMATTER_DATE_RE.search(text)
        raw_date = m_date.group(1) if m_date else ""
        category = ""
        m_cats = FRONTMATTER_CATEGORIES_RE.search(text)
        if m_cats:
            first = m_cats.group(1).split(",")[0].strip().strip('"').strip("'")
            category = first
        m_article = ARTICLE_RE.search(text)
        body = m_article.group(1) if m_article else text
        body = HERO_RE.sub("", body)
        body = TAG_RE.sub("", body)
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        items.append(Item(
            source=PUBLISHED, title=title, content=body,
            url=m_url.group(1), raw_date=raw_date, category=category,
        ))
    return items


FILE_LABELS = {
    "news_raw.md": "News",
    "ai_blogs_raw.md": "Blog",
    "research_raw.md": "Research",
    "youtube_raw.md": "YouTube",
    "reddit_raw.md": "Reddit",
    "bluesky_raw.md": "Social",
    "github_raw.md": "GitHub",
}

UNSORTED = "미분류"
LATER = "나중에"
SKIPPED = "건너뜀"
ONEOFF = "one-off(발행대기)"
REFERENCE = "reference(발행대기)"
STATUS_FOLDERS = [UNSORTED, LATER, SKIPPED, ONEOFF, REFERENCE]
FOLDER_ICON = {UNSORTED: "📥", LATER: "⏳", SKIPPED: "✗", ONEOFF: "📰", REFERENCE: "📌"}
DECISION_TO_FOLDER = {"queue": LATER, "skip": SKIPPED, "one-off": ONEOFF, "reference": REFERENCE}

# ai_news_agent/main.py:802-811 의 CATEGORY_VOCABULARY 를 미러링(publish_note.py 와 같은
# 이미 알려진 패턴 — main.py 를 직접 import 하면 playwright/notion 등 무거운 소스 모듈이
# 줄줄이 딸려와 이 가벼운 TUI 스크립트엔 안 맞음. 8종이 바뀌면 여기도 손으로 맞출 것).
# reference 판정에서 "선택 사항"으로만 쓰인다 — 안 고르면 curate.py가 발행 후 알아서 붙임.
CATEGORY_VOCABULARY = [
    "에이전트 오케스트레이션",
    "MCP & 도구 통합",
    "코딩 에이전트",
    "모델 & 연구",
    "인프라 & 컴퓨트",
    "보안 & 거버넌스",
    "응용 사례",
    "산업 동향",
]

# 폴더 목록 = 상태 5개(트리아지 판정 단계용) + 카테고리 8개(순수 조회 필터 — one-off/reference
# 로 확정되면서 붙은 카테고리를 "코딩 에이전트만 모아보기" 식으로 훑어보는 용도. 여기서
# 카테고리를 고르는 게 아니라, 이미 붙어있는 카테고리로 걸러 볼 뿐이다. 2026-08-24 (2) 피드백:
# "카테고리별로는 어디서 확인해" — 트리아지 단계에서 카테고리를 강제로 안 묻는 것과, 이미
# 붙은 카테고리를 훑어보는 뷰가 있는 것은 별개라 둘 다 필요했다).
FOLDER_NAMES = STATUS_FOLDERS + CATEGORY_VOCABULARY


@dataclass
class Item:
    source: str
    title: str
    content: str  # 요약/설명/본문 — 없으면 빈 문자열
    url: str
    raw_date: str
    category: str = ""  # 항목 자체에 이미 붙어있는 카테고리(예: Medium 자동화가 매긴 것) —
                         # 사람이 트리아지에서 별도로 지정 안 해도 카테고리 폴더에 잡히게 함.

    @property
    def key(self) -> str:
        return self.url or f"{self.source}:{self.title}"


def parse_markdown_table(text: str) -> list[dict[str, str]]:
    """헤더 행의 컬럼명으로 각 데이터 행을 dict화. 컬럼 순서/개수가 파일마다 달라도,
    또 구버전(요약 컬럼 없음)이어도 안 깨지게 이름 기반으로 찾는다."""
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= {"-", ":"} for c in cells if c):
            continue  # 구분선(|---|---|)
        if header is None:
            header = cells
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def extract_link(cell: str) -> tuple[str, str]:
    m = LINK_RE.search(cell)
    if m:
        return m.group(1), m.group(2)
    return cell, ""


def clean(text: str) -> str:
    return text.replace("\\|", "|").strip()


def load_items(date: str) -> list[Item]:
    day_dir = REPORTS / date
    if not day_dir.is_dir():
        sys.exit(f"reports/{date}/ 없음")
    items: list[Item] = []
    for fname, label in FILE_LABELS.items():
        fpath = day_dir / fname
        if not fpath.is_file():
            continue
        for row in parse_markdown_table(fpath.read_text(encoding="utf-8")):
            if fname == "github_raw.md":
                title, url = extract_link(row.get("저장소", ""))
                lang = row.get("언어", "")
                stars = row.get("총 별", "")
                content = clean(row.get("설명", ""))
                extra_bits = " · ".join(x for x in (lang, stars) if x)
                if extra_bits:
                    content = f"{content}\n\n({extra_bits})" if content else f"({extra_bits})"
                raw_date = ""
            elif fname == "bluesky_raw.md":
                title = clean(row.get("본문", ""))
                _, url = extract_link(row.get("링크", ""))
                content = row.get("인게이지먼트", "")
                raw_date = row.get("작성일", "")
            else:
                title = clean(row.get("제목", ""))
                _, url = extract_link(row.get("링크", ""))
                content = clean(row.get("요약", ""))
                raw_date = row.get("작성일", "")
            if title:
                items.append(Item(source=label, title=title, content=content, url=url, raw_date=raw_date))
    return items


def load_medium_items() -> list[Item]:
    """개인 Medium Daily Digest 아카이브(state/medium_digest/{date}/*.md — 별도 워크플로우가
    이메일에서 골라 한글 요약까지 만들어 저장해둔 것)를 TUI에서도 훑어볼 수 있게 로드한다
    (2026-08-27 피드백: "TUI에도 보여"). 파이프라인 raw 항목과 달리 "그날의 수집물"이 아니라
    계속 쌓이는 개인 서재라서 특정 날짜에 가두지 않고 저장된 날짜 폴더를 전부 훑는다
    (2026-08-27 피드백: "굳이 날짜별로 폴더링할 필요 없을거같은데"). 이미 완성된 한글 요약이
    파일 안에 있으므로 본문을 다시 fetch하지 않는다 — _auto_fetch_if_needed 의 Medium
    예외 처리 참조."""
    items: list[Item] = []
    if not MEDIUM_DIR.is_dir():
        return items
    for day_dir in sorted(MEDIUM_DIR.iterdir()):
        if not day_dir.is_dir():
            continue
        for md in sorted(day_dir.glob("*.md")):
            text = md.read_text(encoding="utf-8")
            m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
            if not m:
                continue
            fm_text, body = m.groups()
            fm: dict[str, str] = {}
            for line in fm_text.splitlines():
                if ":" not in line:
                    continue
                key, _, val = line.partition(":")
                val = val.strip().strip('"')
                if val.startswith("["):  # tags: [a, b] 같은 리스트 값은 여기선 안 씀
                    continue
                fm[key.strip()] = val
            items.append(Item(
                source="Medium", title=fm.get("title", md.stem), content=body.strip(),
                url=fm.get("url", ""), raw_date=fm.get("published", "") or fm.get("fetched", ""),
                category=fm.get("category", ""),
            ))
    return items


READ_STATUS_PATH = Path(__file__).parent / "state" / "read_status.json"


def load_read_keys() -> set[str]:
    """읽음 표시된 item.key 집합 — 날짜/판정과 무관한 별도 상태(2026-08-31 피드백:
    "읽었는지 체크되게"). 트리아지 판정(skip/queue/one-off/reference)과는 축이 달라서
    state/triage/*.jsonl 이 아니라 별도 flat 파일에 둔다."""
    if not READ_STATUS_PATH.is_file():
        return set()
    try:
        return set(json.loads(READ_STATUS_PATH.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return set()


def save_read_keys(keys: set[str]) -> None:
    READ_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    READ_STATUS_PATH.write_text(json.dumps(sorted(keys), ensure_ascii=False, indent=2), encoding="utf-8")


def load_seen_keys(exclude_date: str) -> set[str]:
    """다른 날짜의 트리아지 기록에서 판정된 key 를 모은다(오늘 자신의 기록은 제외 —
    오늘 이미 내린 판정은 재실행 시 각 폴더에 복원돼야지 아예 숨겨지면 안 되므로)."""
    seen = set()
    if not STATE_DIR.is_dir():
        return seen
    for f in STATE_DIR.glob("*.jsonl"):
        if f.stem == exclude_date:
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            seen.add(rec.get("key", ""))
    return seen


def load_today_decisions(date: str) -> dict[str, tuple[str, str, str]]:
    """key -> (decision, category, by). by 는 "llm-auto"(auto_classify.py) 또는
    "human"(이 TUI에서 직접 누른 것) — 자동분류 결과인지 사람이 확정한 건지 구분."""
    path = STATE_DIR / f"{date}.jsonl"
    decisions: dict[str, tuple[str, str, str]] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            decisions[rec["key"]] = (rec.get("decision", ""), rec.get("category", ""), rec.get("by", "human"))
    return decisions


DECISION_LABEL = {"skip": "Skip", "queue": "Queue(나중에)", "one-off": "One-off", "reference": "Reference"}


class TriageApp(App):
    CSS = """
    Screen { layout: vertical; }
    #body { height: 1fr; width: 1fr; }
    #left { width: 38%; height: 1fr; border-right: solid $accent; }
    #folders { height: 30%; border-bottom: solid $accent-darken-1; }
    #itemslist { height: 1fr; }
    #right { width: 1fr; height: 1fr; }
    #detail { height: 1fr; padding: 1 2; overflow-y: auto; }
    #actions { height: 7; padding: 0 1; border-top: solid $accent-darken-1; }
    #actions_row1, #actions_row2 { height: 3; align: left middle; }
    #actions Button { margin-right: 1; min-width: 8; }
    #select_category { width: 22; margin-right: 1; }
    #progress { dock: bottom; height: 1; background: $panel; color: $text; padding: 0 1; }
    """

    BINDINGS = [
        Binding("s", "decide('skip')", "Skip"),
        Binding("q", "decide('queue')", "Queue"),
        Binding("o", "decide('one-off')", "One-off"),
        Binding("r", "decide('reference')", "Reference"),
        Binding("m", "toggle_read", "읽음 체크"),
        Binding("f", "fetch_full", "본문 재요청"),
        Binding("pagedown", "scroll_detail_down", "본문 스크롤↓", show=False),
        Binding("pageup", "scroll_detail_up", "본문 스크롤↑", show=False),
        Binding("tab", "toggle_focus", "폴더⇄목록", show=False),
        Binding("j,down", "cursor_down", "↓", show=False),
        Binding("k,up", "cursor_up", "↑", show=False),
        Binding("ctrl+q", "quit", "종료"),
    ] + [Binding(str(n), f"pick_category({n})", show=False) for n in range(1, 9)]

    def __init__(self, date: str, all_items: list[Item], decisions: dict[str, tuple[str, str, str]]):
        super().__init__()
        self.date = date
        self.all_items = all_items
        self.decisions = dict(decisions)  # key -> (decision, category, by)
        self.out_path = STATE_DIR / f"{date}.jsonl"
        self.current_folder = UNSORTED
        self.current_items: list[Item] = []
        # 전문(全文) fetch 캐시 — 세션 메모리에만 보관, 디스크에 저장 안 함(원문 통째 복제
        # 방지 — study_brief.py 가 spotlight 1건에 하던 걸 여기선 "보는 중인 항목"에 on-demand로).
        self.fetched_content: dict[str, str] = {}
        self.fetching: set[str] = set()
        self.blog_index = build_blog_index()  # url -> (title, body) — 이미 발행된 우리 글
        self.read_keys = load_read_keys()
        self._detail_key: str | None = None  # 마지막으로 상세 패널에 띄운 항목의 key —
            # 카테고리 드롭다운을 "항목이 바뀔 때만" 동기화하기 위함. 안 그러면 배경에서
            # 자동 본문 fetch가 끝나 _refresh_detail 이 다시 불릴 때마다 드롭다운이 초기값으로
            # 리셋되면서, 사용자가 방금 고른 카테고리가 조용히 날아가는 버그가 있었다(2026-08-31).

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield ListView(*[ListItem(Label(self._folder_label(n))) for n in FOLDER_NAMES], id="folders")
                yield ListView(id="itemslist")
            with Vertical(id="right"):
                with VerticalScroll(id="detail"):
                    yield Static(id="detail_header")
                    yield Markdown(id="detail_body")
                with Vertical(id="actions"):
                    with Horizontal(id="actions_row1"):
                        yield Button("· 안읽음", id="btn_read")
                        yield Select[str](
                            [(c, c) for c in CATEGORY_VOCABULARY], id="select_category",
                            prompt="카테고리", allow_blank=True,
                        )
                    with Horizontal(id="actions_row2"):
                        yield Button("Skip", id="btn_skip")
                        yield Button("나중에", id="btn_queue")
                        yield Button("One-off", id="btn_oneoff", variant="primary")
                        yield Button("Reference", id="btn_reference", variant="success")
        yield Static(id="progress")

    def _items_in_folder(self, name: str) -> list[Item]:
        if name == UNSORTED:
            # 이미 발행된 글(PUBLISHED)은 트리아지할 게 없는 완결 항목이라 미분류엔 안 넣는다
            # — 카테고리 폴더에서만 훑어본다(2026-09-02).
            return [i for i in self.all_items if i.key not in self.decisions and i.source != PUBLISHED]
        if name in CATEGORY_VOCABULARY:
            # 카테고리 폴더 = 조회 전용 필터. 사람이 트리아지에서 지정한 카테고리(decisions)가
            # 있으면 그걸 우선, 없으면 항목 자체에 이미 붙어있던 카테고리(예: Medium 자동화가
            # 매긴 것)를 쓴다 — 수동 재분류 없이도 카테고리 폴더에서 바로 보이게(2026-08-31).
            def _cat(i: Item) -> str:
                return self.decisions.get(i.key, ("", "", ""))[1] or i.category
            return [i for i in self.all_items if _cat(i) == name]
        return [i for i in self.all_items
                if DECISION_TO_FOLDER.get(self.decisions.get(i.key, ("", "", ""))[0]) == name]

    def _folder_label(self, name: str) -> Text:
        count = len(self._items_in_folder(name))
        t = Text(f"{FOLDER_ICON.get(name, '📁')} ")
        t.append(name, style="bold" if name == UNSORTED else "")
        t.append(f"  ({count})", style="dim")
        return t

    def _item_label(self, item: Item) -> Text:
        # Rich 마크업 파싱을 아예 안 태우게 Text() 로 조립 — title/content 안에 대괄호가
        # 있어도 안전(예전 f-string 버전은 "[GitHub]" 같은 접두를 Rich 가 스타일 태그로
        # 오인해 내용이 사라지는 버그가 있었음, 2026-08-20).
        rec = self.decisions.get(item.key)
        t = Text()
        t.append("✓ " if item.key in self.read_keys else "· ", style="green" if item.key in self.read_keys else "dim")
        if rec and len(rec) > 2 and rec[2] == "llm-auto":
            t.append("🤖 ", style="yellow")
        source_tag = f"[{item.source}]"
        if item.source in ("Medium", PUBLISHED) and item.raw_date:
            source_tag = f"[{item.source} {item.raw_date}]"
        t.append(f"{source_tag} ", style="bold cyan")
        t.append(item.title[:70])
        return t

    def on_mount(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.query_one("#folders", ListView).index = 0
        self._select_folder(UNSORTED)

    def _select_folder(self, name: str) -> None:
        self.current_folder = name
        self.current_items = self._items_in_folder(name)
        items_lv = self.query_one("#itemslist", ListView)
        items_lv.clear()
        for i in self.current_items:
            items_lv.append(ListItem(Label(self._item_label(i))))
        if self.current_items:
            items_lv.index = 0
        self._refresh_detail()

    def _refresh_folders(self) -> None:
        lv = self.query_one("#folders", ListView)
        for idx, name in enumerate(FOLDER_NAMES):
            lv._nodes[idx].query_one(Label).update(self._folder_label(name))  # noqa: SLF001

    def on_list_view_highlighted(self, event) -> None:
        if event.list_view.id == "folders" and event.list_view.index is not None:
            name = FOLDER_NAMES[event.list_view.index]
            if name != self.current_folder:
                self._select_folder(name)
        elif event.list_view.id == "itemslist":
            self._refresh_detail()

    def action_toggle_focus(self) -> None:
        folders = self.query_one("#folders", ListView)
        items = self.query_one("#itemslist", ListView)
        (folders if self.focused is items else items).focus()

    def action_cursor_down(self) -> None:
        if isinstance(self.focused, ListView):
            self.focused.action_cursor_down()

    def action_cursor_up(self) -> None:
        if isinstance(self.focused, ListView):
            self.focused.action_cursor_up()

    def _current(self) -> Item | None:
        lv = self.query_one("#itemslist", ListView)
        if lv.index is None or not self.current_items or lv.index >= len(self.current_items):
            return None
        return self.current_items[lv.index]

    def _refresh_detail(self) -> None:
        item = self._current()
        header = self.query_one("#detail_header", Static)
        body_widget = self.query_one("#detail_body", Markdown)
        if not item:
            header.update(Text(f"({self.current_folder} 폴더에 항목 없음)"))
            body_widget.update("")
            return
        # 카테고리 드롭다운을 이 항목의 현재 카테고리로 동기화하되, **항목이 실제로 바뀔
        # 때만** — 같은 항목을 보는 중에 배경 fetch 완료 등으로 _refresh_detail 이 다시
        # 불려도, 사용자가 방금 고른(아직 확정 전) 드롭다운 값을 덮어쓰지 않는다.
        if item.key != self._detail_key:
            self._detail_key = item.key
            current_category = self.decisions.get(item.key, ("", "", ""))[1] or item.category
            select = self.query_one("#select_category", Select)
            select.value = current_category or Select.NULL
        read_btn = self.query_one("#btn_read", Button)
        read_btn.label = "✓ 읽음" if item.key in self.read_keys else "· 안읽음"

        # 상단 메타데이터는 계속 Rich Text() 로 조립 — 마크다운 특수문자(제목·URL 안의
        # `[`,`*`,`_` 등)가 엉뚱하게 렌더될 위험이 없는 안전한 경로(2026-08-20 마크업
        # 인젝션 버그의 교훈). 실제 본문(마크다운 형태로 이미 쓰인 Medium 요약·우리 발행글,
        # 또는 그냥 평문 요약)만 아래 Markdown 위젯으로 렌더한다(2026-09-02 피드백:
        # "마크다운 뷰어로 보게 할 수는 없나").
        t = Text()
        t.append(item.title, style="bold")
        t.append(f"\n\n출처: {item.source}")
        if item.raw_date:
            t.append(f"   날짜: {item.raw_date}")
        if item.category:
            t.append(f"   카테고리: {item.category}")
        t.append(f"\n{item.url}\n")
        t.append(f"\n{'✓ 읽음' if item.key in self.read_keys else '· 안읽음'}\n",
                 style="green" if item.key in self.read_keys else "dim")
        rec = self.decisions.get(item.key)
        if rec:
            cat_str = f" · {rec[1]}" if rec[1] else ""
            by_str = " (자동분류, 확인 필요)" if len(rec) > 2 and rec[2] == "llm-auto" else ""
            t.append(f"→ 판정됨: {DECISION_LABEL.get(rec[0], rec[0])}{cat_str}{by_str}\n",
                     style="yellow" if by_str else "green")
        t.append("아래 버튼 또는 s/q/o/r 키, 카테고리는 드롭다운 또는 1~8  ·  "
                 "f=본문재요청  PgUp/PgDn=스크롤  Tab=폴더목록", style="dim")
        header.update(t)

        body_md_parts: list[str] = []
        full = self.fetched_content.get(item.key)
        if full:
            shown = full[:5000]
            body_md_parts.append(shown)
            if len(full) > 5000:
                body_md_parts.append(f"\n\n*(총 {len(full)}자 중 5000자만 표시 — PgUp/PgDn 스크롤, f로 다시 받기)*")
        elif item.key in self.fetching:
            if item.content:
                body_md_parts.append(item.content)
            body_md_parts.append("\n\n*(전문 불러오는 중…)*")
        elif item.content:
            body_md_parts.append(item.content)
        else:
            body_md_parts.append("*(요약 없음 — 전문을 불러오는 중…)*")
        blog = self.blog_index.get(item.url)
        if blog:
            blog_title, blog_body = blog
            shown_blog = blog_body[:4000]
            body_md_parts.append(f"\n\n---\n\n### 📝 이미 블로그에 발행됨: {blog_title}\n\n{shown_blog}")
            if len(blog_body) > 4000:
                body_md_parts.append(f"\n\n*(총 {len(blog_body)}자 중 4000자만 표시)*")
        body_widget.update("".join(body_md_parts))
        self._auto_fetch_if_needed(item)

    def _refresh_progress(self) -> None:
        done = len(self.decisions)
        total = len(self.all_items)
        self.query_one("#progress", Static).update(
            f" [{self.current_folder}] {done}/{total} 판정 완료 — {self.out_path}"
        )

    def _auto_fetch_if_needed(self, item: Item) -> None:
        """항목을 볼 때마다 자동으로 전문을 가져온다(2026-08-24 피드백: "f 없이 항상 본문이
        떴으면 좋겠다") — 이미 캐시됐거나 fetch 중이면 아무것도 안 함."""
        if item.source in ("Medium", PUBLISHED):
            return  # 이미 완성된 본문이 content 에 있음(Medium=한글요약, 발행글=우리 원문)
        if not item.url or item.key in self.fetched_content or item.key in self.fetching:
            return
        self.run_worker(self._fetch_and_cache(item), exclusive=False)

    async def _fetch_and_cache(self, item: Item) -> None:
        self.fetching.add(item.key)
        if self._current() is item:
            self._refresh_detail()
        try:
            text = await fetch_article_text(item.url)
        except Exception as e:  # 네트워크/파싱 실패 — 조용히 실패 표시만(트리아지 흐름 안 막음)
            text = f"(본문 가져오기 실패: {e})"
        finally:
            self.fetching.discard(item.key)
        self.fetched_content[item.key] = text or "(본문 없음)"
        if self._current() is item:
            self._refresh_detail()

    def action_fetch_full(self) -> None:
        """f = 강제 재시도(캐시 무시) — 자동 fetch가 실패했거나 다시 받고 싶을 때."""
        item = self._current()
        if not item or not item.url:
            return
        self.fetched_content.pop(item.key, None)
        self._auto_fetch_if_needed(item)

    def action_scroll_detail_down(self) -> None:
        self.query_one("#detail", VerticalScroll).scroll_page_down()

    def action_scroll_detail_up(self) -> None:
        self.query_one("#detail", VerticalScroll).scroll_page_up()

    def _selected_category(self) -> str:
        value = self.query_one("#select_category", Select).value
        return "" if value == Select.NULL else value

    def action_decide(self, decision: str) -> None:
        item = self._current()
        if not item:
            return
        self._finalize(item, decision, self._selected_category())

    def action_pick_category(self, n: int) -> None:
        # 키보드로 카테고리 드롭다운만 설정(1~8) — 결정은 별도로 s/q/o/r 나 버튼으로.
        # 이미 판정된 항목이면 on_select_changed 가 그 자리에서 카테고리를 갱신해준다.
        if not (1 <= n <= len(CATEGORY_VOCABULARY)):
            return
        self.query_one("#select_category", Select).value = CATEGORY_VOCABULARY[n - 1]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        item = self._current()
        if not item:
            return
        if event.button.id == "btn_read":
            self.action_toggle_read()
            return
        decision = {
            "btn_skip": "skip", "btn_queue": "queue",
            "btn_oneoff": "one-off", "btn_reference": "reference",
        }.get(event.button.id or "")
        if decision:
            self._finalize(item, decision, self._selected_category())

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "select_category":
            return
        item = self._current()
        if not item or item.key not in self.decisions:
            return  # 아직 판정 전이면 다음 결정 때 쓰일 값으로만 대기(바로 저장하지 않음)
        decision, current_category, _by = self.decisions[item.key]
        category = "" if event.value == Select.NULL else event.value
        if category == current_category:
            # 실제 변경이 없다 — _refresh_detail 이 항목 전환 시 드롭다운 표시값을 동기화하며
            # 쏘는 Changed 이벤트(비동기라 타이밍상 걸러내기 어려움)가 같은 판정을 매번
            # jsonl 에 중복 기록하던 버그를 여기서 막는다(2026-09-02 발견).
            return
        self._finalize(item, decision, category)

    def action_toggle_read(self) -> None:
        item = self._current()
        if not item:
            return
        if item.key in self.read_keys:
            self.read_keys.discard(item.key)
        else:
            self.read_keys.add(item.key)
        save_read_keys(self.read_keys)
        # 현재 목록의 라벨(체크마크)과 상세 패널을 즉시 갱신.
        lv = self.query_one("#itemslist", ListView)
        if lv.index is not None:
            lv._nodes[lv.index].query_one(Label).update(self._item_label(item))  # noqa: SLF001
        self._refresh_detail()

    def _finalize(self, item: Item, decision: str, category: str) -> None:
        self.decisions[item.key] = (decision, category, "human")
        with self.out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "key": item.key, "source": item.source, "title": item.title,
                "url": item.url, "date": item.raw_date, "decision": decision,
                "category": category, "by": "human",
                "ts": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
            }, ensure_ascii=False) + "\n")
        # 판정된 항목은 현재(미분류) 목록에서 사라지고 해당 폴더로 이동한다.
        self._refresh_folders()
        self._select_folder(self.current_folder)
        self._refresh_progress()


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")
    raw_items = load_items(date)
    seen = load_seen_keys(exclude_date=date)
    all_items = [i for i in raw_items if i.key not in seen] + load_medium_items() + load_published_items()
    decisions = load_today_decisions(date)
    if not all_items:
        print(f"{date}: 항목 없음 (전체 {len(raw_items)}건, 전부 다른 날짜에 이미 판정됨 또는 raw 없음)")
        return
    unsorted_count = len([i for i in all_items if i.key not in decisions])
    print(f"{date}: 전체 {len(all_items)}건 (미분류 {unsorted_count}건, 기존 판정 {len(decisions)}건 복원) "
          f"— 다 훑을 필요 없음, 눈에 띄는 것만 처리하고 나머진 그냥 두면 됨")
    TriageApp(date, all_items, decisions).run()


if __name__ == "__main__":
    main()
