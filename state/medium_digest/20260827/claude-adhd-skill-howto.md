---
title: "How to Use Claude ADHD Skill Better Than 99% of People"
author: Gao Dalie (高達烈) (Data Science Collective)
url: https://medium.com/@GaoDalie_AI/how-to-use-claude-adhd-skill-better-than-99-of-people-9876934d8548
published: 2026-07-24
fetched: 2026-08-27
category: 에이전트 오케스트레이션
tags: [ADHD-skill, multi-agent, divergent-thinking, Claude Code]
---

> ⚠️ 원문 전문은 저작권상 저장하지 않음 — 아래는 패러프레이즈 요약. 원문은 위 url 참조.

## 한글 요약

지난번(8/25)에 요약한 "ADHD skill"(`UditAkhourii/adhd`, 이 글에선 `ayghri/i-have-adhd`로 소개)을 실제로 설치·운용하는 법과, 왜 그게 통하는지를 논문 수준까지 파고든 딥다이브.

**문제의식**: Claude에게 아이디어를 물으면 "티어형 가격제, 종량제, 토큰 플랜, 광고" 같은 구글 검색해도 나올 법한 뻔한 답만 나온다는 것. 원인은 LLM의 autoregressive 생성 방식 — 앞 문장이 이미 뒤 문장의 방향을 강하게 앵커링해서, 훈련 분포에 맞는 "무난한" 답으로 수렴하기 쉽다는 것.

**ADHD skill의 3가지 설계 원칙**:
1. **5개의 완전 독립 에이전트** — 한 모델이 5번 생각하는 게 아니라, 서로 맥락을 공유하지 않는 5개의 완전히 별도 LLM 호출을 돌림. "이전 아이디어를 무시하라"는 프롬프트가 아니라 물리적으로 이전 아이디어 자체가 존재하지 않는 구조 (Anthropic의 harness 설계 문서에서 "긴 작업은 맥락을 압축하지 말고 아예 리셋하라"는 권고와 같은 맥락이라고 언급).
2. **인지 프레임 강제 부여** — 각 에이전트에게 완전히 다른 역할("규제기관 감사관", "소프트웨어를 한 번도 본 적 없는 10살 아이" 등)을 부여. 논문에는 15개 프레임이 있고 실행마다 5개를 무작위 선택. 목표는 각 답이 "정확"한 게 아니라 "서로 다르게" 만드는 것.
3. **발산과 수렴을 분리** — 발산 단계 프롬프트는 "너는 생성자다, 평가·정렬·헤징 금지"로 명시하고, 수렴 단계는 완전히 다른 LLM 호출·다른 시스템 프롬프트로 "너는 이제 비평가다, 적대적으로 읽고 점수 매기고 함정을 찾아라"로 전환. 저자는 이 분리가 가장 정교한 설계라고 평가 — 창작과 비평이 동시에 작동하면 창작이 제대로 안 나온다는 논리(초안 쓰면서 동시에 퇴고하면 아예 못 쓰는 것과 같은 이치).

**논문 근거**: 저자들이 "ADHD: Parallel Divergent Ideation for Coding Agents"라는 논문을 씀. 6개의 개방형 엔지니어링 질문으로 단일 응답과 비교해 5승 1패, novelty +5.17, breadth +4.17 향상.

**CoT/ToT와의 차이**: CoT는 한 경로를 더 깊게, ToT는 여러 분기를 시도하지만 분기끼리 맥락을 공유해 "관점 자체"는 안 바뀜. ADHD는 관점 자체를 물리적으로 격리해 바꾼다는 게 차별점. 저자는 이걸 "다음 차별화 지점은 inference-time engineering(호출을 어떻게 조직하고, 맥락을 어떻게 격리하고, 생성과 평가를 언제 나눌지)"이라는 더 큰 주장으로 연결.

**설치**: `claude plugin marketplace add ayghri/i-have-adhd` → `claude plugin install i-have-adhd@i-have-adhd`. Codex는 `codex plugin` 계열 명령 사용. 세션에서 `/i-have-adhd`로 발동, `stop adhd mode`로 해제.

**저자가 제안하는 단계적 온보딩(1주~)**: 1일차엔 그냥 지금 막힌 걸 Claude에 말해보기 → 1주 후 `MEMORY.md`에 의사결정 기준·과거 실패·반복 지시사항 저장(단, 계좌번호·인증정보·건강정보 등 민감정보는 절대 저장 금지) → 익숙해지면 반복 작업을 Skill로 만들기 → 더 익숙해지면 Claude 결과를 Codex/ChatGPT/Gemini 등 다른 모델로 적대적 검토(Claude는 동조 편향이 강해 "그거 좋네요"라고 하는 경향이 있어서 외부 검토가 필요하다는 지적) → 습관화 전엔 주 반나절은 AI 없이 손으로 작업해 의존도를 측정해보라는 조언.

**적용 각도(참고용 메모)**: 이 세션에서도 다양한 서브에이전트/워크플로우 병렬 실행 패턴을 쓰는데, "발산-수렴 역할 분리"는 브레인스토밍류 작업(예: 블로그 개편 아이디어, OKF 설계안)에 시도해볼 만한 구체적 기법.
