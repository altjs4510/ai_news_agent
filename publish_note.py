"""수기 리서치 노트를 ai_news_blog knowledge 베이스에 추가한다.

용도: Cookie 가 링크를 주고 "이거 서치해줘" 하면 — 논문/툴/아티클/릴리스 무엇이든 —
그 공개 다이제스트를 content/knowledge/ 에 knowledge 항목으로 누적한다.
데일리 자동 픽과 파일명이 겹치지 않도록 stem 을 'YYYYMMDD-<slug>' 로 쓴다.

이 스크립트는 **파일만 쓴다**(git 안 함). 발행 게이트는 review-first:
  1) 이 스크립트로 노트 작성 → 2) 사람이 본문 확인 → 3) OK 면 별도로 git commit/push.
push 후 다음 curate 실행이 전체 사이드바에 이 항목을 자동 전파한다.

사이드바 빌더 로직은 delivery/blog_publisher.py 의 _build_knowledge_sidebar_html /
_scan_knowledge_entries 를 그대로 미러링한다(무거운 main import 를 피하려 stdlib 자립).
카테고리 vocabulary 가 바뀌면 그쪽(main.CATEGORY_VOCABULARY)과 여기 VOCAB 를 함께 맞춘다.

예:
  python publish_note.py --slug proprag \
    --title "PropRAG — 프로포지션 경로 위 beam search로 멀티홉 검색 안내" \
    --source-url https://arxiv.org/abs/2504.18070 \
    --category "모델 & 연구" --tags "멀티홉 RAG,proposition,beam search" \
    --body-file /tmp/digest.md --date 20260716
"""
from __future__ import annotations

import argparse
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_BLOG = Path(__file__).resolve().parent.parent / "ai_news_blog"
SITE = os.getenv("BLOG_SITE_URL", "https://altjs4510.github.io/ai_news_blog").rstrip("/")

# main.CATEGORY_VOCABULARY 미러 (단일 출처는 main.py; 여기 값이 어긋나면 curate 가 교정).
VOCAB = [
    "에이전트 오케스트레이션",
    "MCP & 도구 통합",
    "코딩 에이전트",
    "모델 & 연구",
    "인프라 & 컴퓨트",
    "보안 & 거버넌스",
    "응용 사례",
    "산업 동향",
]


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;")


def _scan(kdir: Path) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    for md in sorted(kdir.glob("*.md")):
        if md.name == "_index.md":
            continue
        t = md.read_text(encoding="utf-8")
        tm = re.search(r'^title:\s*"(.+?)"', t, re.M)
        gm = re.search(r"^tags:\s*\[(.+?)\]", t, re.M)
        cm = re.search(r"^categories:\s*\[(.+?)\]", t, re.M)
        title = tm.group(1) if tm else md.stem

        def _split(m):
            if not m:
                return []
            out = []
            for raw in m.group(1).split(","):
                v = raw.strip().strip('"').strip("'").strip()
                if v:
                    out.append(v)
            return out

        entries[md.stem] = {"title": title, "tags": _split(gm), "categories": _split(cm)}
    return entries


def _build_sidebar(entries: dict[str, dict], current: str) -> str:
    by_cat: dict[str, list[tuple[str, str]]] = {}
    for date, info in entries.items():
        cats = info.get("categories") or (
            [info["tags"][0]] if info.get("tags") else ["기타"]
        )
        for c in cats:
            by_cat.setdefault(c, []).append((date, info["title"]))
    for c in by_cat:
        by_cat[c].sort(key=lambda x: x[0], reverse=True)

    ordered: list[tuple[str, list]] = []
    seen: set[str] = set()
    for v in VOCAB:
        if v in by_cat:
            ordered.append((v, by_cat[v]))
            seen.add(v)
    left = [(c, i) for c, i in by_cat.items() if c not in seen]
    left.sort(key=lambda x: (-len(x[1]), x[0]))
    ordered.extend(left)

    blocks = []
    for cat, items in ordered:
        is_open = any(d == current for d, _ in items) or len(by_cat) <= 8
        oa = " open" if is_open else ""
        lis = []
        for date, title in items:
            dk = date[:8]
            dd = f"{dk[:4]}-{dk[4:6]}-{dk[6:8]}" if dk.isdigit() else date
            t = _esc(title)
            st = t[:48] + ("…" if len(t) > 48 else "")
            cls = ' class="current"' if date == current else ""
            lis.append(
                f'<li><a href="{SITE}/knowledge/{date}/"{cls}>'
                f'<span class="kdate">{dd}</span>'
                f'<span class="ktitle">{st}</span></a></li>'
            )
        blocks.append(
            f'<details class="ai-cat"{oa}><summary>'
            f'<span class="catname">{_esc(cat)}</span>'
            f'<span class="catcount">{len(items)}</span></summary>'
            f'<ul>{"".join(lis)}</ul></details>'
        )
    return (
        '<aside class="ai-knowledge-sidebar">\n'
        '  <p class="ai-eyebrow">CATEGORIES</p>\n'
        '  <nav class="ai-cat-tree">' + "".join(blocks) + "</nav>\n"
        "</aside>"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="ai_news_blog 에 수기 knowledge 노트 추가")
    ap.add_argument("--slug", required=True, help="파일 slug (stem = YYYYMMDD-<slug>)")
    ap.add_argument("--title", required=True)
    ap.add_argument("--source-url", default="")
    ap.add_argument("--category", required=True, help="8종 vocabulary 중 하나 권장")
    ap.add_argument("--tags", default="", help="콤마 구분")
    ap.add_argument("--body-file", required=True, help="본문 마크다운 파일 경로")
    ap.add_argument("--date", default="", help="YYYYMMDD (기본: 오늘 KST)")
    ap.add_argument("--meta", default="리서치 노트", help="hero eyebrow 라벨")
    args = ap.parse_args()

    blog = Path(os.getenv("BLOG_REPO_PATH", str(DEFAULT_BLOG))).resolve()
    kdir = blog / "content" / "knowledge"
    if not kdir.is_dir():
        print(f"[에러] knowledge 디렉토리 없음: {kdir}")
        return 1

    date = args.date or datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")
    if not re.fullmatch(r"\d{8}", date):
        print(f"[에러] --date 는 YYYYMMDD 형식: {date!r}")
        return 1
    slug = re.sub(r"[^a-z0-9-]", "-", args.slug.strip().lower()).strip("-")
    stem = f"{date}-{slug}"
    display_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"

    if args.category not in VOCAB:
        print(f"[경고] '{args.category}' 는 8종 vocabulary 밖 — curate 가 재분류할 수 있음.")

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    body = Path(args.body_file).read_text(encoding="utf-8").strip()

    entries = _scan(kdir)
    entries[stem] = {"title": args.title, "tags": tags, "categories": [args.category]}
    sidebar = _build_sidebar(entries, stem)

    hero = (
        '<header class="ai-post-hero">\n'
        f'  <p class="ai-eyebrow"><a class="ai-back" href="../">KNOWLEDGE</a> · {display_date} · {args.meta}</p>\n'
        f'  <h2 class="ai-post-title">{_esc(args.title)}</h2>\n'
        "</header>\n\n"
    )
    tags_yaml = ", ".join(f'"{t}"' for t in tags)
    fm = (
        "---\n"
        f'title: "{args.title}"\n'
        f"date: {display_date}\n"
        + (f'source_url: "{args.source_url}"\n' if args.source_url else "")
        + (f"tags: [{tags_yaml}]\n" if tags else "")
        + f'categories: ["{args.category}"]\n'
        "---\n\n"
    )
    doc = (
        fm
        + '<div class="ai-knowledge-shell">\n\n'
        + sidebar
        + "\n\n"
        + '<article class="ai-knowledge-article">\n\n'
        + hero
        + body
        + "\n\n</article>\n\n</div>\n"
    )
    out = kdir / f"{stem}.md"
    out.write_text(doc, encoding="utf-8")
    print(f"[작성] {out}")
    print(f"[카테고리] {args.category}  [stem] {stem}")
    print("[다음] 본문 확인 후 OK 면: git add + commit + push (review-first 게이트)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
