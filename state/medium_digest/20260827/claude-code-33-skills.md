---
title: "I Tried 33 Claude Code Skills. These Are The Best"
author: The PyCoach (Artificial Corner)
url: https://medium.com/@frank-andrade/i-tried-33-claude-code-skills-these-are-the-best-daf8caf92a2a
published: 2026-06-11
fetched: 2026-08-27
category: 코딩 에이전트
tags: [Claude Code, Skills, plugin]
---

> ⚠️ 원문 전문은 저작권상 저장하지 않음 — 아래는 패러프레이즈 요약. 원문은 위 url 참조. (뉴스레터 홍보성 문구 다수 포함된 원문 — 광고 부분은 요약에서 제외)

## 한글 요약

Claude Code Skill 33개를 써보고 추천 6개 + 보너스로 정리한 글. 지난번(8/25) 요약한 "5개 필수 Skill" 글과 겹치지 않는 라인업이라 같이 보면 보완됨.

**설치법**: `/plugin install <skill>@<marketplace>` 한 줄이면 대부분 1분 내 설치. 자주 쓰는 건 "global"로 설치해두면 모든 프로젝트에서 바로 동작.

**추천 6개**:
1. **Skill Creator**(Anthropic 공식) — 원하는 걸 평범한 문장으로 설명하면 Claude가 직접 Skill을 만들고 테스트·패키징까지 해줌. "Skill 만드는 법 학습" 자체를 건너뛰게 해줘서 제일 먼저 설치할 만하다고 추천. `/plugin install skill-creator@claude-plugins-official`
2. **Grill Me**(Matt Pocock) — 계획을 던지면 실행 전에 집요하게 되물어서(때론 30~50개 질문) 서로 진짜 이해했는지 확인. "Claude가 뭘 원하는지 추측하다 생기는 실수"를 죽이는 게 핵심. `npx skills@latest add mattpocock/skills -s grill-me -g`
3. **Superpowers** — 계획 없이 바로 전력 질주해서 작성한 코드가 실전에서 무너지는 문제를 막기 위해, 격리된 환경에서 작업→테스트 먼저 작성→"요청한 대로 맞나"와 "코드 품질" 두 번 자체 리뷰하도록 강제. `/plugin install superpowers@claude-plugins-official`
4. **Frontend Design**(Anthropic 공식) — AI가 만든 티가 나는 제너릭한 UI를 벗어나게 해줌(8/25 요약과 동일 Skill, 저자만 다름). `/plugin install frontend-design@claude-plugins-official`
5. **Context Mode** — 세션이 길어지면 명령어 원시 출력이 메모리를 잠식해 30분쯤 지나면 Claude가 파일·맥락을 까먹는 문제를, (1) 각 명령 출력에서 유용한 부분만 필터링하고 (2) 세션 로그(수정 파일·진행 중 작업·마지막 프롬프트)를 남겨뒀다가 리셋 시 다시 불러오는 방식으로 해결. 30분에서 죽던 세션이 몇 시간씩 유지됨. `/plugin marketplace add mksglu/context-mode` → `/plugin install context-mode@context-mode`
6. **Claude Mem** — 매 세션 프로젝트를 처음부터 다시 설명해야 하는 문제를 해결. 세션 훅으로 파일 수정·결정·버그 수정을 자동 캡처해 로컬에 요약 저장하고, 새 세션에서 관련 부분을 자동으로 다시 불러옴. 프로젝트 노트도 자동 갱신. `/plugin marketplace add thedotmack/claude-mem` → `/plugin install claude-mem`

**보너스(설치 불필요, 내장 기능)**: `/review`(빠른 무료 자체 리뷰: 버그·엣지케이스·설계 문제 탐지), `/ultra-review`(클라우드로 보내 로직·보안·성능 등 다른 각도의 리뷰어 팀을 병렬로 돌림 — 결제/DB 건드리는 큰 변경에만 쓰라고 권장).

**저자 조언**: 한 번에 다 설치하지 말고 하나씩 익힌 뒤 다음으로 넘어갈 것.

**적용 각도(참고용 메모)**: `/ultra-review`는 우리 세션에서 이미 `/code-review ultra`로 쓰고 있는 것과 동일한 메커니즘으로 보임(설명 일치) — 이 글은 그 존재를 사용자 입장에서 재확인해주는 자료. Context Mode·Claude Mem은 장시간 세션 관리 문제(우리도 종종 컨텍스트 압축을 겪음)에 바로 적용 검토해볼 만함.
