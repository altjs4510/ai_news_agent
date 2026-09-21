---
title: "9 Claude Code Plugins Every Developer Should Install in 2026"
author: Mohit Vaswani
url: https://medium.com/@hii_mohit/9-claude-code-plugins-every-developer-should-install-in-2026-9a35b8fe5a83
published: 2026-08-17
fetched: 2026-09-09
category: 코딩 에이전트
tags: [Claude Code, 플러그인, 마켓플레이스, security-guidance, code-review, Context7, Superpowers, Chrome DevTools MCP, LSP, claude-mem, skill-creator]
---

> ⚠️ 원문 전문은 저작권상 저장하지 않음 — 아래는 패러프레이즈 요약. 원문은 위 url 참조.

## 한글 요약

Anthropic 이 5월에 플러그인 마켓플레이스를 열면서 Claude Code 가 "똑똑한 터미널"에서 외부 감각을 덧붙이는 플랫폼으로 바뀌었다는 관찰에서 출발한다. 공식 마켓플레이스가 200개를 넘겼지만 대부분은 슬래시 커맨드 하나짜리 잡음이고, 저자가 걸러낸 9개만 소개한다. 설치는 `/plugin` 으로 Discover 탭을 열면 되고, 외부 마켓플레이스는 `/plugin marketplace add <owner>/<repo>` 뒤 `/plugin install <name>` 순서다. (중간에 저자 본인의 상용 번들 AgentsKit 홍보가 끼어 있다.)

1. **security-guidance** (Anthropic 공식) — Claude 가 파일을 편집하기 직전에 변경 내용을 읽어 커맨드 인젝션, 하드코딩된 시크릿, 검증 없는 입력, 위험한 셸 호출을 잡는다. 편집 루프 위에 앉아 있어 커밋 세 개 뒤가 아니라 쓰는 순간 잡는다. 저자는 git 추적 설정 파일에 API 키를 붙여넣다 잡힌 뒤로 계속 켜 두고 있다.
2. **code-review** (Anthropic 공식) — 위 플러그인이 위험을 보면 이건 품질을 본다. 로직·엣지 케이스·네이밍을 시니어 개발자처럼 보되 잔소리는 안 한다. AI 생성 코드를 자기 손으로 꼼꼼히 리뷰하는 사람은 없으니 리뷰를 강제로 일어나게 하는 장치.
3. **Context7** — 버전 정확한 라이브러리 문서를 컨텍스트로 실시간 주입한다. Next.js 15, React 19, Tailwind 4 등 빠르게 바뀌는 프론트 스택에서 학습 데이터에 기반한 존재하지 않는 API 환각을 크게 줄여 준다.
4. **Superpowers** — 도구라기보다 "성격 이식". TDD, 체계적 디버깅, 구조화된 브레인스토밍, 서브에이전트 상호 리뷰 같은 방법론 묶음을 Claude 가 꺼내 쓰게 한다. 작은 스크립트보다 큰 작업에서 차이가 난다.
5. **Chrome DevTools MCP** — 로그인된 Chrome 세션에서 네트워크 요청·콘솔 에러·DOM 을 직접 본다. "버튼이 안 눌려요"에 401 반환 엔드포인트를 스스로 찾아낸 경험이 결정적이었다고.
6. **Anthropic Language Servers (LSP 팩)** — 12개 이상 언어에 실제 타입 정보·정의 이동·진단을 제공한다. 눈에 안 띄지만 리팩터가 존재하지 않는 함수로 새는 일이 줄고, 타입 언어에선 다른 플러그인까지 조용히 좋아진다.
7. **claude-mem** — 세션 내용을 압축 저장했다가 다음 세션에 관련 부분을 되먹인다. GitHub 스타 2.1만 이상. 장기 프로젝트에서 매일 아침 재브리핑이 사라진 게 체감 포인트.
8. **Frontend Design** (Anthropic 공식) — 회색 Bootstrap 템플릿 같은 UI 를 벗어나 레이아웃·시각 위계·취향 있는 선택을 밀어붙인다. 디자이너가 아닌 사람이 "보여줄 만한" 수준까지 가는 데 유용.
9. **skill-creator** — 반복 워크플로우·하우스 스타일·배포 체크리스트를 한 번 가르쳐 영구 호출하게 만드는, 플러그인 소비자에서 제작자로 넘어가는 진입로.

마무리 조언은 9개를 첫날 다 깔지 말라는 것. security-guidance 와 code-review 로 시작하고, 빠른 프레임워크를 쓰면 Context7, 프로젝트가 하루를 넘기면 claude-mem 을 더한다. 깔아 놓고 잊은 플러그인은 그냥 오버헤드다. 살아남는 플러그인의 공통점은 새 명령어가 아니라 **새 감각**(실제 문서, 실제 기억, 브라우저를 보는 눈, 타입 인식)을 준다는 점이다. FAQ 로 플러그인은 `~/.claude/plugins/` 에 살며 전역 적용이고, 플러그인 자체는 무료지만 연결되는 서드파티 서비스는 별도 과금일 수 있다고 정리한다.

**적용 각도(참고용 메모)**: 이 세션 환경에 이미 code-review·frontend-design·chrome-devtools(연결 실패 중)·LSP 가 깔려 있다 — 없는 것 중 security-guidance(편집 전 시크릿 가드)와 claude-mem(세션 간 기억) 은 auto-memory 와 역할이 겹치는지 검토해 볼 만함.
