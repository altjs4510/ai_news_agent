---
title: "Anthropic Said No to the Most-Requested Feature in Claude Code"
author: Anubhav (Data Science Collective)
url: https://medium.com/@anubhavgoyal101/anthropic-said-no-to-the-most-requested-feature-in-claude-code-8109051f804b
published: 2026-08-01
fetched: 2026-08-27
category: 코딩 에이전트
tags: [Claude Code, AGENTS.md, CLAUDE.md, Anthropic]
---

> ⚠️ 원문 전문은 저작권상 저장하지 않음 — 아래는 패러프레이즈 요약. 원문은 위 url 참조.

## 한글 요약

Claude Code 이슈 트래커에서 5,200개 넘는 추천을 받은 최다 요청 기능 — "Claude Code가 AGENTS.md(다른 코딩 에이전트들이 공용으로 읽는 표준 지침 파일)를 읽게 해달라"는 요청에, Anthropic이 5월경부터 "지금은 계획 없음(not planned for now)"으로 일관 거절하고 있다는 이야기.

**AGENTS.md란**: OpenAI가 2025년 8월 Codex와 함께 내놓고 Linux Foundation에 기증한 오픈 마크다운 표준. 현재 Codex, GitHub Copilot, Gemini CLI, Aider, Zed 등 20개 이상 툴이 네이티브로 읽고, 6만 개 이상 저장소가 채택. 한때 버텼던 Cursor·Windsurf·Cline도 2026년 6월부터 심볼릭 링크 없이 네이티브 지원 추가. Anthropic 자신도 이 표준이 있는 Linux Foundation 그룹의 창립 멤버(자사 MCP도 그 그룹의 창립 프로젝트 중 하나).

**Anthropic이 거절하는 이유(저자 분석)**: CLAUDE.md가 AGENTS.md보다 기능이 많기 때문. `@`로 다른 파일을 임포트할 수 있고, 경로별로 메모리 범위를 나눌 수 있고(예: backend 폴더 안에서만 로드되는 CLAUDE.md), 프로젝트 메모리·유저 메모리·`claudeMdExcludes` 설정까지 있음 — AGENTS.md는 이런 게 전혀 없는 단일 평면 파일이라, "더 잘하는 자사 포맷"에 굳이 "더 못하는 공용 포맷"을 위한 폴백을 만들 유인이 적다는 것.

**실질적 해법(이미 문서화돼 있음, PR 안 기다려도 됨)**: CLAUDE.md 맨 위에 임포트 한 줄만 넣으면 됨:
```
# CLAUDE.md
@AGENTS.md

# Claude 전용 지침은 여기부터
```
세션 시작 시 인라인으로 확장되므로(즉 컨텍스트 절감 효과는 없음 — AGENTS.md 전체가 그대로 윈도우를 먹음) 두 파일을 따로 유지보수할 필요만 없어짐. 임포트는 최대 4단계까지 중첩 가능. 저장소 루트에 `@AGENTS.md`를 두면 승인 팝업 없이 조용히 로드됨(외부 경로를 가리키는 임포트에만 승인을 물음). `/context` 실행하면 실제로 로드된 Memory files 목록에서 확인 가능. Windows에서 symlink 방식(`ln -s AGENTS.md CLAUDE.md`)은 관리자 권한이 필요해 임포트 방식이 더 이식성 좋음. "Claude Code가 AGENTS.md를 자동 폴백으로 읽는다"는 건 사실무근(GitHub 이슈에 도는 루머) — 임포트나 심볼릭 링크 없인 그냥 무시됨.

**저자의 결론**: Anthropic만 쓰는 개발자에겐 자사 포맷이 실제로 더 낫다는 논리가 타당하지만, 여러 에이전트를 동시에 쓰는 게 일반화된 지금 "이식성이 존재 이유인 표준 파일"을 거절하는 건 이상한 언덕에서 버티는 선택이라는 평가. 엔지니어링 리더 입장 제안: AGENTS.md를 팀의 단일 진실 소스로 삼고, 각 저장소 CLAUDE.md엔 `@AGENTS.md` 임포트만 넣으라는 것.

**적용 각도(참고용 메모)**: 우리 `ai_news_agent`/`ai_news_blog` 등은 현재 AGENTS.md가 없고 CLAUDE.md만 씀 — Claude Code 외 다른 에이전트(Codex 등)를 이 레포들에서 병행할 계획이 생기면 이 임포트 패턴(`@AGENTS.md`)이 바로 적용 가능한 실전 팁.
