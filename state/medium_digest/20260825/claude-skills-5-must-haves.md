---
title: "I Tried Dozens of Claude Skills. These are the 5 Must-Haves!"
author: Infinity
url: https://medium.com/@the_infinity/i-tried-dozens-of-claude-skills-these-are-the-5-must-haves-e5b60013ffe9
published: 2026-08-07
fetched: 2026-08-25
category: 코딩 에이전트
tags: [Claude Skills, Claude Code, productivity]
---

> ⚠️ 원문 전문은 저작권상 저장하지 않음 — 아래는 패러프레이즈 요약. 원문은 위 url 참조.

## 한글 요약

"Skill은 결국 마크다운 파일 아니냐, 프롬프트 잘 쓰면 되는 거 아니냐"고 생각했던 필자가 수십 개 Claude Skill을 실사용해본 뒤 입장을 바꾼 글. Skill의 진짜 가치는 다른 사람들이 이미 여러 코드베이스에서 검증하고 edge case를 다듬어놓은 "재사용 가능한 명령 패키지"라는 점, 그리고 필요할 때만 알아서 발동되고 아닐 땐 빠지는 조합성(composability)에 있다고 정리.

**꼽은 5개 + 보너스 1개**:

1. **`/grill-me`** (`mattpocock/skills`) — 계획을 바로 실행하지 않고, 먼저 사용자를 집요하게 인터뷰해서 놓친 엣지 케이스와 논리적 모순을 찾아냄. 설계 단계 실수를 잡는 용도.
2. **`/frontend-design`** (Anthropic 공식) — AI가 생성하는 UI가 다 비슷해 보이는(크림색 배경+테라코타 포인트+세리프 폰트) 문제를 해결. "대상이 속한 세계(예: 목공 도구라면 목공의 소재·어휘)"에서 디자인을 끌어오도록 강제.
3. **`/teach`** (`mattpocock/skills`) — 프로젝트 디렉토리를 영속적인 학습 공간으로 재정의. 레슨 파일·참고자료·학습기록·미션 문서를 커리큘럼처럼 생성. 코드베이스 학습부터 프랑스어 학습까지 응용 가능.
4. **ADHD skill** (`UditAkhourii/adhd`) — Claude가 첫 번째 그럴듯한 아이디어에 안주하는 습관을 막기 위해, 서로 못 보는 여러 독립 사고 스레드를 병렬로 돌린 뒤 별도 필터링 패스로 골라냄. 한 벤치마크에서 다양성(breadth) 9 vs 6, 참신성(novelty) 8 vs 3로 일반 Claude 대비 우세.
5. **`/improve-codebase-architecture`** (`mattpocock/skills`) — "삭제 테스트"(모듈을 지워봤을 때 영향을 보고 리팩토링 필요 여부 판단) + 커밋 로그 분석(가장 활발히 바뀌는 코드 우선)으로 리팩토링 지점을 짚어줌.
6. **보너스: Caveman skill** (`JuliusBrussee/caveman`) — 응답을 "원시인 말투"로 바꿔 산문 출력 토큰 65%, 장기 에이전틱 코딩 실행 토큰 8.5% 절감. 기술적 정확도는 유지된다고 주장.

전부 `npx skills@latest add <repo> --skill <name>` 형태로 설치. 필자는 "이 5개가 실제 워크플로우를 바꿨다"는 점을 강조하며, 각자 선호하는 Skill을 댓글로 공유해달라고 마무리.

**적용 각도(참고용 메모)**: `/grill-me`, `/frontend-design`, `/improve-codebase-architecture`는 이름만으로도 ai_news_agent/hermes 작업 관행(계획 확인 단계, 리팩토링 판단)과 바로 비교 가능 — 실제 채택 여부는 별도 판단.
