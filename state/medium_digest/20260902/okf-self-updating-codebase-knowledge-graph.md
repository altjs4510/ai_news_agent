---
title: "Stop Wasting LLM Tokens: Building a Self-Updating Codebase Knowledge Graph with OKF"
author: Udaykiran Estari (Data Science Collective)
url: https://medium.com/@UdaykiranEstari/stop-wasting-llm-tokens-building-a-self-updating-codebase-knowledge-graph-with-okf-20284060c1b1
published: 2026-07-03
fetched: 2026-09-02
category: 에이전트 오케스트레이션
tags: [OKF, Open Knowledge Format, 지식그래프, 코드베이스 컨텍스트, 토큰 절감, git hook, LLM Wiki, RAG]
---

> ⚠️ 원문 전문은 저작권상 저장하지 않음 — 아래는 패러프레이즈 요약. 원문은 위 url 참조.

## 한글 요약

(현재 Medium 상 제목은 "Standardizing Agent Memory: Building a Self-Updating Codebase Knowledge Graph with Google's OKF" 로 바뀌어 있음. 다이제스트 발송 시점 제목을 그대로 둠.)

코딩 에이전트는 작업마다 코드베이스 구조를 처음부터 다시 파악하느라 토큰을 낭비하고, 업계의 대응은 레포 전체 덤프 아니면 예측 불가능한 RAG 둘 중 하나였다는 문제의식에서 출발한다. 저자는 구글이 2026년 6월 12~13일에 공개한 Open Knowledge Format(OKF) v0.1이 이 문제에 대한 "포맷" 답은 됐지만, 정작 어려운 부분 — 하루 수십 커밋이 쌓이는 수천 파일 레포에서 지식그래프를 어떻게 최신으로 유지하느냐 — 는 독자 몫으로 남겨졌다고 지적하고, 그 빈칸을 메우는 파이프라인을 제안한다.

**OKF 데이터 모델 요약.** 번들은 마크다운 파일 디렉토리이고, 파일 하나가 개념(concept) 하나다(테이블·서비스·런북·API 엔드포인트 등). 파일 경로가 곧 ID라 별도 ID 체계가 없다. 권장 frontmatter 는 type/title/description/resource/tags/timestamp 여섯 개지만 **필수는 type 하나뿐**이다. 예약 파일 두 개가 구조를 만든다: `index.md`(디렉토리 목록 → 에이전트가 루트에서 시작해 필요한 깊이까지만 링크를 따라가는 점진적 공개, 곧 토큰 예산 제어 수단)와 `log.md`(git log 와 별개로 "이 시스템이 아는 것이 무엇이 바뀌었나"를 날짜별로 기록). 준수 규칙은 세 개뿐이고, 소비자는 선택 필드 누락·미지 type·미지 키·깨진 링크를 이유로 번들을 거부하면 안 된다. 저자는 이 극단적 미니멀리즘을 한계가 아니라 채택 가능성의 이유로 본다 — 스키마 레지스트리·검증 서버·벤더 SDK 를 요구하던 기존 메타데이터 카탈로그 표준과 대비된다. 구글이 카르파시의 2026년 4월 "LLM Wiki" 패턴을 명시적 계보로 언급하는 점도 짚는다: LLM 이 컴파일된 교차링크 위키를 외부 기억으로 유지한다는 발상이며, 질의 때마다 관계를 재유도하는 RAG 기본 가정에 대한 반론이다.

**데이터 → 코드로 옮기기.** 구글 레퍼런스는 BigQuery 테이블이지만, 같은 형태가 서비스·모듈·API 에 그대로 대응된다. resource 를 콘솔 URL 대신 레포 경로로, `# Schema` 대신 `# Responsibilities`/`# Dependencies` 섹션으로 바꾸면 된다. 번들 상대경로 마크다운 링크가 평면 디렉토리를 의존성 그래프로 바꾸는 핵심이다 — 파일시스템의 부모/자식 계층보다 풍부하게, 어떤 서비스가 무엇을 호출하고 무엇을 발행하는지를 물리 위치와 무관하게 표현한다. 루트 `index.md` 는 에이전트가 파일을 건드리기 전 읽는 사전 컨텍스트 로드이지, 작업 중 질의하는 검색 인덱스가 아니다.

**핵심 주장: 어려운 건 채택이 아니라 enrichment 에이전트.** OKF 채택 자체는 사소하다(필수 필드 하나, 폴더 컨벤션, 일반 링크). 진짜 엔지니어링은 코드가 바뀔 때 그래프를 정확하게 유지하는 파이프라인이다. 구글의 BigQuery 레퍼런스 구현이 템플릿이 된다: 1패스는 데이터셋의 모든 테이블을 돌며 스키마에서 개념 문서를 초안하고, 2패스는 기존 문서를 교차참조해 인용을 붙인다. 코드에 옮기면 1패스는 모듈/서비스의 인터페이스·호출 그래프에서 개념 파일을 초안하고, 2패스는 런북·ADR·PR 로 인용을 건다.

제안 파이프라인은 커밋 푸시 → **diff 범위로 한정한** 모듈 스캔 → 2패스 enrichment 로 개념 문서 초안/갱신 → 교차참조 재링크 → lint → 발행(번들 커밋/CI/카탈로그 등록) 순이다. 레포 전체가 아니라 git diff 로 스캔 범위를 좁히는 것이 야간 배치가 아닌 매 커밋 실행을 감당 가능하게 만드는 요소다. 처음부터 만들 필요는 없다: 서드파티 `okf` CLI(Go, Apache-2.0)가 `okf init`(스캐폴딩), `okf hook install`(커밋 시 자동 갱신), `okf search`, `okf lint`(13개 준수 규칙)로 이 형태를 이미 증명했다.

**멀티에이전트 워크플로 연결.** 오케스트레이터가 `index.md` 를 먼저 읽고 서브태스크에 따라 어떤 서브에이전트에 어떤 개념 파일이 필요한지 라우팅한다 — 서비스 하나 건드리는 작업에 번들 전체를 싣지 않는다. Go 라이브러리의 `LoadBundle`/`Search`/`LintBundle` 이 오케스트레이션 레이어와 CI 의 결합 지점이다. 번들을 외부에서도 소비하려면 Kiso 엔진이 OKF 를 정적 사이트(사람용 HTML + 에이전트용 llms.txt/sitemap)로 컴파일해 CI 에서 머지마다 돌린다.

**OKF 와 RAG 의 경계.** OKF 는 안정적이고 큐레이션된 지식(서비스, 소유 경계, 의존성 그래프, 작성해 둔 런북)용이고, RAG 는 롱테일(비정형 티켓, Slack 스레드, 일회성 설계 문서)용이다. OKF 를 RAG 대체재로 보는 건 틀린 프레임이고, RAG 가 재유도할 필요 없는 컴파일된 캐시로 보는 게 맞다. 초기 분석가들은 순진한 문서 로딩 대비 최대 95% 가량 토큰 절감을 주장하지만, 저자는 이 수치가 일화적이며 대규모 운영 검증이 필요하다고 명시한다.

**솔직한 한계.** (1) 내장 검색/서빙 없음 — 인덱서·검색·서빙은 전부 사용자 몫이고 `okf search`/Kiso 는 초기 비공식 시도다. (2) type 레지스트리·스키마 강제 없음 — "API Endpoint"/"Endpoint"/"Route" 식 드리프트를 외부 거버넌스와 lint 없이는 막을 수 없다. (3) 링크가 비타입·비강제 — 관계 의미가 주변 산문에 암시될 뿐이라 RDF/OWL 급 의존성 순회·영향 분석 자동화엔 한계. (4) 마크다운은 지식 품질을 고치지 못함 — 원본이 낡거나 모순이면 그대로 보존될 뿐이며 충돌 탐지는 enrichment 에이전트 몫. (5) 생태계가 극초기 — 2026년 6월 v0.1, 구글 외 도구는 파편적, 장기 운영 사례 없음.

**의사결정 프레임.** 이미 자기 레포/지식베이스에 여러 에이전트를 돌리고 있다면 만들어라 — 작업당 컨텍스트 재유도 토큰과 낡은 컨텍스트 버그가 직접 줄어든다. 아직 에이전틱 워크플로가 없다면 당장은 건너뛰어라 — 아무도 안 읽는 위키 유지가 된다. 만든다면 최소 파이프라인은 반나절 분량이다: `okf init` + git hook, 가장 자주 바뀌는 서비스에만 enrichment 1회, 모든 에이전트가 먼저 읽는 `index.md`. 비용은 포맷이 아니라 enrichment 에이전트의 컴퓨트와 드리프트 모니터링에서 나온다. 결론은 "포맷 결정이 아니라 파이프라인 결정으로 프로토타이핑하고, 다음 멀티에이전트 작업의 토큰 델타를 측정해 데이터로 판단하라"이다. 후속편으로 OKF v0.2 의 provenance/verification/freshness 를 다루는 "Production Trust System" 편과 Graphify·CodeGraph·agentic grep 비교 편을 예고한다.

**적용 각도(참고용 메모)**: 우리 `okf` 스킬(`~/.hermes/knowledge/agents/okf/STATUS.md`)·cookie-knowledge 번들에 직접 닿음 — 특히 "diff 범위 스캔 + git hook + lint" 의 자동 갱신 루프와 "OKF=안정 지식 캐시 / RAG=롱테일" 경계 설정, `index.md` 우선 읽기의 진행적 공개는 hermes 오케스트레이터의 서브에이전트 컨텍스트 라우팅에 그대로 적용 가능. okf-followup 모니터에 superops `okf` CLI 와 Kiso 를 추적 대상으로 추가할 만함.
