---
title: "Qwen 3.8–27B on a 16 GB Mac mini: Alibaba's new vision model, fully in memory"
author: Manjunath Janardhan (Data Science Collective)
url: https://medium.com/@manjunath.shiva/qwen-3-8-27b-on-a-16-gb-mac-mini-alibabas-new-vision-model-fully-in-memory-f3aaaacbfeb4
published: 2026-08-17
fetched: 2026-08-25
category: 인프라 & 컴퓨트
tags: [Qwen, quantization, MLX, Mac, on-device, agentic-coding]
---

> ⚠️ 원문 전문은 저작권상 저장하지 않음 — 아래는 패러프레이즈 요약. 원문은 위 url 참조.

## 한글 요약

Alibaba가 2026-08-14 공개한 Qwen3.8-27B(278억 파라미터, 텍스트·이미지·비디오 입력, Apache 2.0)를 필자 본인이 만든 오픈소스 양자화 엔진(TurboQuant-MLX)으로 11.55GB(비전 인코더 포함)까지 압축해, 기본 사양 16GB Mac mini에서 완전 인메모리로 돌려본 실측기.

**모델 자체 주장(Qwen 발표치, 미검증)**: SWE-bench Pro·LiveCodeBench v6·OSWorld·AndroidWorld에서 Claude Opus 4.6 Max를 능가, Terminal-Bench 2.1 73.0점, DeepSWE 1.1 42.2점(전작 13.3에서 3배 이상 상승). 원본 가중치는 55.6GB로 64GB 맥 필요.

**아키텍처 포인트**: 64개 레이어 중 16개만 KV 캐시를 유지하고 나머지 48개는 Gated DeltaNet(선형 어텐션, 상태 크기가 프롬프트 길이에 비례해 커지지 않음)을 씀 — 토큰당 메모리가 일반 모델 대비 훨씬 작음.

**실측 결과(16GB Mac mini, 3비트 압축본)**:
- 220~5,017 토큰 전 구간에서 3.6~3.9 tok/s(읽는 속도 수준)로 안정적 — 프롬프트 처리 속도도 19~21 tok/s로 평탄. 비교 대상 dense 30B 비전 모델은 2,000토큰 넘어가면 20→6 tok/s로 급락했는데, 이 모델은 그 붕괴가 없음(48개 레이어가 캐시를 안 쌓기 때문).
- 4비트에서는 Apple 자체 MLX affine 양자화가 필자 포맷보다 정확도 0.3% 우세 + 속도 2.6배 빠름 — 필자도 "4비트면 Apple 것 써라"고 권장. 자기 포맷(TurboQuant)의 존재 이유는 3비트/16GB 구간뿐.
- OCR(비전) 테스트 2건 모두 성공. 다만 메모리 한계는 프롬프트 길이보다 "이미지 크기"가 좌우 — 640×420 이미지가 64GB 맥에서도 피크치를 캡 이상으로 밀어올림.
- 반직관적 발견: 같은 프롬프트에서 16GB 미니가 64GB M4 Max보다 피크 메모리가 오히려 낮음 — MLX 할당기가 여유 메모리가 많을 때 스크래치 공간을 더 잡아두기 때문. "큰 머신 기준 추정이 보수적(안전한) 추정"이라는 결론.

**에이전틱 코딩은 실패**: 버그 수정(테스트 실행→버그 찾기→최소 수정→재실행) 과제를 16GB 미니에서 4번 시도해 4번 다 실패(계획만 말하고 멈춤/툴콜 후 시간초과/OOM). 동일 과제를 64GB 맥에서는 4번 다 성공 — 압축 자체의 문제는 아니고 원인 불명(RAM 차이 또는 MLX 빌드 차이로 추정). 결정적으로, 이 하이브리드 아키텍처는 prefix caching이 안 됨(Gated DeltaNet 상태는 KV 캐시처럼 잘라 재사용 불가) — 에이전트 루프마다 시스템 프롬프트(~7,200토큰)를 매번 통째로 재처리해야 해서 턴당 비용이 매우 큼. 에이전틱 용도로는 24GB급이 사실상 최저선.

**결론**: 16GB 티어에서 27B급 "프론티어 주장" 모델을 무료·오프라인으로 돌려 질문·이미지 인식은 가능해졌지만, 에이전트 코딩까지 되는 건 아님.

**적용 각도(참고용 메모)**: 로컬 온디바이스 LLM으로 뭔가 돌릴 계획이 생기면(현재는 없음) 이 수치(3비트/16GB 인퍼런스 O, 에이전틱 X)가 바로 참고선.
