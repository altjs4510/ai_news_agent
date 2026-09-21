---
title: "The Free, Open-Source Alternative to ElevenLabs Is Finally Here"
author: Bytefer
url: https://medium.com/@bytefer/the-free-open-source-alternative-to-elevenlabs-is-finally-here-d50171168ad4
published: 2026-08-10
fetched: 2026-09-12
category: 모델 & 연구
tags: [TTS, OmniVoice, 음성 복제, 오픈소스, diffusion LM, mlx-audio, 온디바이스]
---

> ⚠️ 원문 전문은 저작권상 저장하지 않음 — 아래는 패러프레이즈 요약. 원문은 위 url 참조.

## 한글 요약

k2-fsa 팀이 Hugging Face에 오픈소스로 공개한 TTS 모델 OmniVoice를 소개하는 짧은 실무 글이다. 저자는 이미 Qwen3-TTS, Chatterbox Turbo, VoxCPM2 등을 다룬 적 있고, 이번 OmniVoice는 음성 복제와 음성 디자인을 지원하면서 영어·중국어·일본어·한국어·독일어·프랑스어를 포함한 600개 이상 언어를 다룬다는 점을 강조한다.

주요 기능은 네 가지다. 고품질 음성 복제를 지원하며 [laughter] 같은 비언어 기호와 음소로 세밀한 제어가 가능하다. 음성 디자인은 성별·나이·피치·방언/억양·속삭임 같은 화자 속성을 설정해 목소리를 만들어 낸다. 추론이 빠른데 RTF(실시간 대비 비율)가 0.025까지 내려가 실시간의 40배 속도를 낸다. 아키텍처는 품질과 속도를 절충하는 diffusion language model 계열을 쓴다.

기술적으로 OmniVoice는 단일 단계(single-stage) NAR TTS 모델로, 이산 확산(discrete diffusion) 목적함수로 학습되고 양방향 Transformer 백본을 채택한다. 텍스트를 다중 코드북 음향 토큰으로 직접 매핑해, 기존 2단계 캐스케이드 파이프라인의 오류 전파와 정보 병목 문제를 없앤다. 온라인 데모는 Hugging Face Spaces에서 텍스트와 3~10초짜리 참조 오디오·그 전사문을 넣고 Generate를 누르면 합성된다.

로컬 배포는 두 갈래로 안내한다. 공식 문서는 PyTorch+CUDA 실행을 다루고, 저자는 macOS에서 mlx-audio로 돌리는 법을 설명한다 — 가상환경 구성, mlx-audio 설치, 컴퓨터 사양에 맞춘 양자화 모델(fp32/bf16/8bit) 다운로드 순이다. 이어 zero-shot 생성 코드와 음성 복제 코드 예시를 보여 준다. 복제는 앞서 만든 output.wav를 참조 오디오(ref_audio)로, 그 전사를 ref_text로 넘겨 새 문장을 그 목소리로 합성하는 식이다. 저자는 음성 합성 수요가 있다면 실제로 역량을 평가해 보고, 요구에 안 맞으면 Qwen3-TTS나 VoxCPM2를, 추론 속도가 최우선이면 Chatterbox Turbo를 시험해 보라고 권한다.

**적용 각도(참고용 메모)**: 한국어를 포함한 600+ 언어를 커버하고 온디바이스(Apple Silicon)에서 40배속으로 도는 오픈 TTS라면, 뉴스 다이제스트·리포트를 오디오로 바꾸거나 사내 데모의 음성 출력에 API 비용 없이 붙일 수 있는 후보로 기록해 둘 만하다.
