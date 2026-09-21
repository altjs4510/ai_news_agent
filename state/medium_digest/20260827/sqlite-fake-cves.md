---
title: "1 Trillion Databases Run His Code. 26 Years of Leadership. AI Buried Him in Accusations."
author: Can Artuc
url: https://medium.com/@canartuc/1-trillion-databases-run-his-code-26-years-of-leadership-ai-buried-him-in-accusations-321423d04c83
published: 2026-08-06
fetched: 2026-08-27
category: 보안 & 거버넌스
tags: [SQLite, CVE, AI-생성-취약점, 오픈소스, MITRE, CISA]
---

> ⚠️ 원문 전문은 저작권상 저장하지 않음 — 아래는 패러프레이즈 요약. 원문은 위 url 참조. (출처가 명시된 취재 기사 — JFrog 분석, MITRE 커밋 기록, SQLite 포럼 글 등 1차 자료 인용)

## 한글 요약

전 세계 스마트폰마다 들어있는 SQLite(2000년부터 D. Richard Hipp이 26년째 유지보수, 프로젝트 자체 추산으로 활성 DB 파일 1조 개 이상, libz 다음으로 널리 배포된 라이브러리)를 둘러싸고 실제로 벌어진 "AI가 지어낸 가짜 CVE" 사건의 취재 기록.

**타임라인**:
- 2026-07-27: SQLite에 대한 보안 취약점(CVE) 27건이 갑자기 등록됨. CISA가 심각도 점수까지 매겨 전 세계 스캐너에 자동 전파.
- 2026-07-29: Hipp이 SQLite 포럼에 "Fake CVEs against SQLite" 글 게시. Linux 배포판 회사 SUSE가 다수 보고서를 Claude(AI 챗봇)에 넣어보니 "조작된 것"이라는 판정이 나왔다고 전함.
- 2026-07-30: JFrog Security Research(Afek Berger)가 27건 중 6건을 실제 소스코드로 빌드하고 AddressSanitizer로 PoC를 직접 실행 — 6건 모두 버그가 존재하지 않음을 확인. 그중 하나(CVE-2026-51302)는 취약점이 있다고 지목한 문제의 함수(`exprComputeOperands()`)가 2025-06-30에야 작성됐는데, 취약하다고 지목된 버전은 그보다 2년도 더 전인 2023-02 배포본 — 즉 시간순서상 성립 불가능한 주장이었음. 이미 하루 전(7/28) GitHub 사용자 `extratao`가 동일한 방식으로 반박하고 "AI slop"이라 라벨링한 상태.
- SQLite 자체 통계: 3.42.0 기준 소스 15.6만 줄에 테스트 코드 9,200만 줄(줄당 590줄 테스트 비율).

**같은 계정의 전과**: 이 CVE들을 신고한 계정 `programmervuln`은 2026-04-22에도 이미지 라이브러리 LibRaw에 유사한 신고 5건을 냈던 이력. LibRaw 관리자 Alex Tutubalin이 직접 PoC를 돌려본 결과 1건만 진짜(정수 오버플로, 실제로 고쳐줌), 나머지는 기각 — 그중 "Critical Heap Buffer Overflow(RCE 위험)"이라던 신고 하나는 접수 12분 만에 닫히고 나중에 이슈 제목이 "AI Spam"으로 바뀜. 그런데도 2026-07-27, 그 "AI Spam" 신고에 CVE 번호와 8.8(High) 점수가 정식으로 부여됨.

**구조적 문제**: CVE 식별자 발급기관(MITRE, CNA)은 "명예 시스템(honor system)"으로 운영돼 신고 내용을 검증할 인력·인프라가 없다는 게 Oracle Solaris 엔지니어 Alan Coopersmith의 지적. 심각도 점수를 매기는 CISA도 실제 코드를 빌드하거나 PoC를 실행하지 않음 — LibRaw 건에서 "PoC가 존재한다"고 기록한 근거는 그 신고서 자체에 있던 "PoC Concept"(실제 PoC가 아니라 어떻게 만들지 서술한 절) 섹션이었음.

**신고 계정의 정체**: `programmervuln`은 2026-01-29 생성, 프로필 정보 전무, 팔로워 0. 신고 CVE들이 주장한 버그 유형과 정확히 일치하는 "vlmuaf(vision-language-model 기반 use-after-free 마이닝)"이라는 리포지토리를 다음날 공개 — AI로 취약점을 대량 생성했을 가능성을 강하게 시사.

**결말**: 2026-07-31 14:43:58 UTC, MITRE가 CVE-2026-51229~51304 사이 76개 식별자를 한 커밋으로 일괄 반려(SQLite 27건, LibRaw 건 포함) — 27건 중 14건은 공개되기도 전에 반려됨. 하지만 GitHub 자체 보안 권고(Advisory) DB에 복사된 사본(GHSA-vrg3-8p22-cwh8)은 취재 시점까지도 "unreviewed" 상태로 여전히 CVSS 9.8 Critical로 표시된 채 방치 — JFrog가 GitHub·Red Hat·NVD에 정식 보고했고 Red Hat·NVD는 반영했지만 GitHub만 안 움직임.

**적용 각도(참고용 메모)**: AI가 생성한 그럴듯한 가짜 취약점 신고가 공식 CVE 채번·정부기관 심각도 점수까지 통과한 실제 사례 — "AI 생성 콘텐츠의 권위 있는 시스템 침투" 리스크의 구체적 선례로, 우리 자체 보안/거버넌스 관련 판단 시 참고할 만함(예: 자동화된 취약점 스캐너·리포트를 검증 없이 신뢰하지 않기).
