---
title: "2026-07-20 요약"
date: 2026-07-20
---

{{< callout emoji="🎯" >}}
**[Nutlope/hallmark — Claude Code·Cursor·Codex용 Anti-AI-slop 디자인 스킬](https://github.com/Nutlope/hallmark)**

한 주에 8,834 스타를 쓸어담으며 skills 생태계의 폭발을 상징적으로 보여준 신규 항목으로, '디자인 시스템을 스킬로 캡슐화해 에이전트가 매 턴 재해석하지 않게 만든다'는 결이 DCSAI `dcs-ai-plugin`의 skills 레이어와 Team Agent FSD 프런트엔드의 일관성 결을 동시에 건드립니다. 최근 픽이 다룬 design.md·agent-skills 카탈로그가 '설계 원칙'을 다뤘다면, hallmark는 실제로 배포·소비되고 있는 1차 스킬 레퍼런스라는 점에서 결이 다릅니다.

**접목 →** DCSAI `dcs-ai-plugin`의 skills 디렉토리에 hallmark 구조를 참조해 F&F 브랜드 UI 규칙(컬러·타이포·컴포넌트 계층)을 'anti-slop 디자인 스킬'로 포팅하면, Claude Code로 사내 프런트엔드를 생성할 때 매번 시스템 프롬프트에 디자인 규칙을 재주입하지 않아도 되는 컨텍스트 세금 절감 경로가 열립니다. Team Agent 쪽에서는 `discovery.yaml` 브랜드 상수와 결합해 브랜드별 skill 변형(brand-scoped skill)을 실험할 수 있습니다.
{{< /callout >}}

{{< callout emoji="📖" >}}
- **[Zero risk isn't the job: a CISO's guide to agentic AI](https://claude.com/blog/ciso-guide-to-agentic-ai)** — Anthropic이 '제로 리스크는 목표가 아니다'라는 프레이밍으로 에이전틱 AI의 위험을 관리 가능한 영역으로 재정의한 1차 문서로, DCSAI의 MCP host server tool 실행 경계와 HITL 분기에서 '무엇을 차단하고 무엇을 감사만 할 것인가'를 정하는 조직 관점의 논거로 곧장 활용할 수 있습니다.
- **[kangarooking/cangjie-skill — 책·팟캐스트를 실행 가능한 Agent Skill로 증류](https://github.com/kangarooking/cangjie-skill)** — 장문 콘텐츠를 '스킬'이라는 압축 실행 포맷으로 증류한다는 컨셉으로, ai_news_agent의 요약 파이프라인이 단순 마크다운 발행을 넘어 '재사용 가능한 스킬 아티팩트'까지 산출하도록 확장할 때 참고할 만한 새로운 결입니다.
{{< /callout >}}

{{< callout emoji="🏷" >}}
`Claude Skills` · `Anti-AI-slop` · `디자인 시스템` · `Claude Fable 5` · `컨텍스트 세금`
{{< /callout >}}
