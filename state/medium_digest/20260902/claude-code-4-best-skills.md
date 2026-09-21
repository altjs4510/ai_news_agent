---
title: "I Tested Claude Code Skills Until I Struck Gold (4 Best Claude Skills)"
author: Divad
url: https://medium.com/@divadsanders/i-tested-claude-code-skills-until-i-struck-gold-4-best-claude-skills-bc199475e2b8
published: 2026-08-12
fetched: 2026-09-02
category: 코딩 에이전트
tags: [Claude Code, Skills, 토큰 절감, Ponytail, Claude Video, Last30Days, Humanizer, 플러그인 마켓플레이스]
---

> ⚠️ 원문 전문은 저작권상 저장하지 않음 — 아래는 패러프레이즈 요약. 원문은 위 url 참조.

## 한글 요약

수개월간 GitHub 의 Claude Code 스킬 레포를 써 본 저자가 "Claude Code 가 기본 상태에서 못하는 네 가지" — 영상을 못 보고, AI 티 나는 글을 쓰고, 앱 설계를 시키면 과잉 산출물을 내고, 사용량 한도를 빨리 소진하는 것 — 를 각각 메우는 스킬 넷을 고른 글이다. 수백 개 스킬 중 대부분은 시간 낭비라는 전제에서 출발한다.

**1. Ponytail — 토큰 낭비 억제.** 영화 속 "한 줄 코드로 뚫는 해커" 클리셰에서 이름을 땄다. Claude 가 바이브 코딩 중 요청보다 많이 짓는 경향(오버빌드)이 두 번 비용을 물린다고 본다: 불필요한 줄도 토큰으로 과금되고, 쌓인 코드가 이후 Claude 자신을 혼란시켜 하나 고치면 다른 게 깨진다. Ponytail 은 코드를 쓰기 전 네 가지 질문을 강제한다 — 이게 존재해야 하나, 프로젝트 내 비슷한 걸 이미 만들었나, 브라우저가 이미 공짜로 해주나, 50줄 대신 1줄로 되나. 부작용은 채팅 답변까지 과하게 압축돼 기술적 내용을 두세 번 읽어야 한다는 것이고, 저자의 우회책은 "5학년에게 설명하듯" 요청하면 코드는 그대로 간결하게 두고 설명만 풀어준다는 것이다.

**2. Claude Video — 영상 시청·분석.** YouTube 링크를 주면 자막은 뽑아도 화면에 뭐가 나오는지는 모르는 한계를 겨냥한다. 이 스킬(bradautomates/claude-video)은 자막과 화면 시각 정보를 합쳐 전체 맥락을 만들고, YouTube 외 Loom·TikTok·X·Instagram 도 지원한다. 설치는 플러그인 마켓플레이스 추가 후 install, 또는 레포 URL 을 Claude 에게 주고 설치시키는 방식이며, 이후 `/watch` 명령에 URL 을 붙인다. 저자는 GitHub 에서 뭔가 설치하기 전 **레포 안에 숨은 프롬프트 인젝션**을 경계하라고 덧붙인다 — 출처가 미심쩍으면 Claude 에게 레포를 먼저 분석시키고 필요한 부분만 가져오게 한다.

**3. Last30Days — 최신 시장 조사.** 목록 중 가장 큰 레포(GitHub 스타 약 5만). 일반 검색은 몇 달~몇 년 지난 인기 블로그 글을 긁어오지만, 이 스킬은 Reddit·X·YouTube·TikTok·Instagram·Threads·GitHub 등 "사람들이 실제로 얘기하는 곳"으로 보낸다. 핵심 가치는 **댓글까지 읽는다**는 점이다 — 보통 검색은 게시물 본문에서 멈추지만 인사이트는 댓글에 있다. 여러 플랫폼에서 같은 불만이 독립적으로 반복되면 패턴으로 인식해 순위를 매기고, 한 사람의 단발 불평은 무시한다. 광고성 기사가 아니라 잠재 구매자의 목소리를 찾는다는 논리. `/last30days <주제>` 로 실행하며, 저자는 앱 아이디어 검증과 뉴스레터 소재 판단에 매주 쓴다.

**4. Humanizer — AI 문체 제거.** 이제 다들 아는 AI 글의 흔적(em dash, "A 가 아니라 B" 구문, "진짜 중요한 건 이거다" 식 도입, quietly/taste/signal/skyrocket 같은 유행어)을 Wikipedia 의 AI 글 식별 가이드에 기반한 33개 패턴으로 잡아 제거한다. 매번 "더 사람처럼 써"라고 반복할 필요를 없앤다. 저자는 자기 글 샘플을 먼저 주어 목소리를 맞춘 뒤 초안을 Humanizer 로 후처리하는 식으로 쓴다. 단, 이건 **집필 도구가 아니라 정리 도구**다 — 아이디어를 주거나 약한 글을 살리지는 못하고 플래그될 표현만 걷어낸다.

결론은 넷 다 Claude Code 를 벗어나거나 추가 구독을 요구하지 않으니, 이번 주 가장 시간을 잡아먹는 결핍부터 하나 깔라는 것이다. (말미에 저자의 유료 상품 홍보가 붙어 있음.)

**적용 각도(참고용 메모)**: Humanizer 는 이미 우리 writer/creative 스킬 계열에 있는 "humanized prose" 와 겹침 — 33개 패턴 목록을 대조해 빠진 게 있는지 볼 만함. Last30Days 의 "댓글까지 읽고 교차 플랫폼 반복을 신호로 승격" 로직은 `sources/x_trends.py` 키워드 추세 산정과 researcher 스킬의 신뢰도 판정에 참고 가능. 서드파티 스킬 설치 전 레포 프롬프트 인젝션 점검 습관은 우리도 규칙화할 가치.
