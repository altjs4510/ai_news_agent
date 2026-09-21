---
title: "Ox Alpha Just Appeared Out of Nowhere: The Free AI Model With a 1M Token Context Window"
author: inprogrammer
url: https://medium.com/@inprogrammer/ox-alpha-just-appeared-out-of-nowhere-the-free-ai-model-with-a-1m-token-context-window-dc94942c827d
published: 2026-08-22
fetched: 2026-08-25
category: 모델 & 연구
tags: [OpenRouter, stealth-model, 무료모델, context-window]
---

> ⚠️ 원문 전문은 저작권상 저장하지 않음 — 아래는 패러프레이즈 요약. 원문은 위 url 참조.
> ⚠️ 스텔스 모델 소식이라 시의성 정보(스펙·순위·요금)가 빠르게 바뀔 수 있음 — 원문 자체도 "2026-08-22 기준 스냅샷"이라 명시.

## 한글 요약

2026-08-20 OpenRouter에 provider명 "Stealth", 모델 ID `stealth/ox-alpha`로 정체불명의 모델이 등장. 무료(프리뷰 기간), 1,048,576 토큰 컨텍스트, 텍스트·이미지·비디오 입력 + 툴콜링 지원, 코딩/에이전트 작업 타깃.

커뮤니티 벤치마크(비공식)에서 DeepSWE 기준 GPT 5.6 sol, Claude Fable 5보다 앞선다는 결과가 보고됐지만 검증된 바는 없음. 처리량은 ~29 tok/s 수준으로 보고. OpenRouter, OpenCode Zen, Mercury Cloud 세 채널에서 동시에 무료 제공 중 — 스텔스 릴리즈치고는 이례적으로 빠른 확산.

**흥미 포인트**: 비디오 입력을 지원하는 첫 익명 스텔스 모델. 필자도 아직 테스트 못했지만, 화면 녹화(버그 재현)와 코드베이스를 함께 넣어 트레이싱하는 용도를 가설로 제시.

**"스텔스 모델"이라는 패턴**: OpenRouter가 이전에도 써먹은 방식(2025년 Optimus Alpha 사례) — 이름 없이 공개 게이트웨이에 태워 개발자들이 무료로 스트레스 테스트하게 하고, 나중에 정체를 공개하거나 조용히 내림. Ox Alpha는 최근 ~6개월 사이 OpenRouter 무료 모델군에 올라온 다섯 번째 "중국계 랩 추정" 익명 모델이라고.

**추정 출처**: 토크나이저 지문 분석 결과 Z.ai(구 Zhipu AI)의 GLM 5.3과 거의 일치(고정 75토큰 wrapper 차이만 있음) — 우연이라기엔 특징적. 다른 후보는 Xiaomi MiMo 팀(과거 "Hunter Alpha"라는 이름으로 같은 패턴을 쓴 전례 — MiMo V2 Pro). OpenRouter는 "라우팅만 할 뿐 개발사가 아니다"라는 입장.

**주의사항(필자 정리)**: 무료 기간 종료 시점 미확정 — 자동화에 넣으려면 폴백 필요. 프롬프트/응답이 학습에는 안 쓰인다고 밝혔지만 "저장은 안 한다"는 뜻은 아님 — 익명 제공자에게 로그가 남는 리스크는 실명 랩과 다른 성격. 사내 코드·크레덴셜·고객정보는 정체가 밝혀지기 전까지 넣지 말 것.

**적용 각도(참고용 메모)**: 우리 `USE_CLAUDE_CLI` 폴백 백엔드처럼 무료/저비용 대체 모델을 실험할 때 후보로 볼 순 있으나, 익명 제공자 리스크 때문에 사내망 프록시(민감 데이터) 용도로는 부적합 — 참고만.
