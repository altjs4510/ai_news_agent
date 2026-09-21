---
title: "A Faster Alternative to MarkItDown, Pandoc, Docling, and Unstructured Is Here"
author: Bytefer
url: https://medium.com/@bytefer/a-faster-alternative-to-markitdown-pandoc-docling-and-unstructured-is-here-e5608fd09de7
published: 2026-08-07
fetched: 2026-09-06
category: MCP & 도구 통합
tags: [anydoc, Firecrawl, 문서변환, Markdown, RAG-ingestion, OCR, PaddleOCR, Agent-Skill]
---

> ⚠️ 원문 전문은 저작권상 저장하지 않음 — 아래는 패러프레이즈 요약. 원문은 위 url 참조.

## 한글 요약

사무 환경에 LLM이 깊이 들어오면서 Word·PowerPoint·Excel·PDF 같은 포맷을 다뤄야 하는데, 이들은 본질적으로 LLM 친화적이지 않다. 그래서 표준 접근은 **Markdown으로 변환**하는 것이고, 결국 변환기 품질이 파이프라인 품질을 좌우한다. 이 글은 Firecrawl 팀이 내놓은 오픈소스 크로스플랫폼 변환기 **anydoc**을 소개한다.

핵심 특징은 다섯 가지다. (1) 에이전트 플랫폼에 바로 꽂을 수 있는 **Agent Skill이 내장**돼 있다. (2) Rust로 작성돼 빠르고, Node.js·Python 바인딩을 제공한다. (3) 스캔본이 아닌 PDF는 **로컬에서 처리**하므로 외부 OCR 서비스가 필요 없다. (4) 확장자가 아니라 **바이너리 데이터로 포맷을 판별**해 확장자가 틀려도 정확히 변환한다. (5) 통합 문서 모델 + Markdown 시리얼라이저를 둬 포맷이 달라도 렌더링 결과가 일관된다.

지원 범위는 14개 포맷: Word(.doc/.docx/.docm), PowerPoint(.ppt/.pps/.pot/.pptx/.pptm/.ppsx/.ppsm), Excel(.xls/.xlsx/.xlsm/.xlsb), OpenDocument(.odt/.ods/.odp), RTF, EPUB, CSV, PDF. 성능은 주류 변환기 6종과 비교했고, 14개 포맷에 걸친 실제 문서 100건으로 0~100점 척도 벤치마크를 돌렸다(구체 점수표는 원문 이미지).

사용법은 세 갈래다. CLI는 `npx @firecrawl/anydoc report.docx`로 stdout에 Markdown을 뱉고, `-o slides.md`로 파일 출력, `-`와 `--format csv`로 stdin도 받는다. Node.js에서는 `@firecrawl/anydoc`을 설치해 `toMarkdown(경로)` / `toMarkdownBytes(바이트, 내용 기반 포맷 자동 판별)` / `toDocument(바이트)`를 쓴다. 마지막 것은 Markdown 직전 문서 모델에서 멈춰 임베디드 에셋까지 들고 있는데, PDF에는 지원되지 않는다. 브라우저에서 쓰려면 `@firecrawl/anydoc-wasm` 모듈이 따로 있다.

실무 팁으로 저자가 짚는 건 **try…catch 필수**다. 예를 들어 이미지로만 이루어진 PDF를 변환하면 `unsupported` 에러 코드로 예외가 던져진다.

에이전트 연동은 한 줄이다 — Claude Code, Codex, Cursor, OpenCode에서 쓰려면 `npx skills add firecrawl/anydoc`으로 내장 anydoc Agent Skill을 먼저 설치하면 된다.

이미지 전용 PDF라는 빈틈은 OCR로 메운다. 저자는 PaddlePaddle의 오픈소스 모델 **PP-OCRv6**를 붙이는 방법을 보여주는데, 간체·번체 중국어, 영어, 일본어와 라틴 문자 46개 언어를 포함해 50개 언어를 지원한다. 더 복잡한 PDF에는 PaddleOCR-VL-1.6이나 MinerU2.5-Pro 같은 더 강력한 모델을 권한다.

구현은 `ppu-paddle-ocr` 모듈로, 런타임에 따라 `onnxruntime-web`(브라우저) 또는 `onnxruntime-node`(Node/Bun)를 같이 깐다. Node 쪽 흐름은 서비스 인스턴스를 만들고 `initialize()` → 이미지 파일을 읽어 ArrayBuffer 슬라이스로 넘겨 `recognize()` → **finally에서 `destroy()`로 정리**하는 형태다. 브라우저에서는 `ppu-paddle-ocr/web`의 `PaddleOcrService`를 쓰고, 업로드된 파일을 Image로 로드한 뒤 canvas에 그려 그 canvas를 `recognize()`에 넘긴다.

정리하면 anydoc 하나로 환경·플랫폼을 가리지 않고 문서 변환을 붙일 수 있고, PDF만 다루면 된다면 같은 팀의 `pdf-inspector`를 써도 된다 — 다만 이쪽도 이미지 기반 PDF는 지원하지 않아 OCR은 직접 붙여야 한다. 저자는 PP-OCRv6 Medium 모델을 실제 이미지 번역 프로젝트에 통합해봤고 정확도가 꽤 인상적이었다고 덧붙인다.

**적용 각도(참고용 메모)**: 사내 문서를 KG/RAG에 넣을 때의 전처리 후보로 볼 만하다 — 특히 확장자 신뢰 없이 바이너리로 포맷을 판별하는 점과 스캔본 아닌 PDF를 외부 OCR 서비스 없이 로컬 처리하는 점은 사내 데이터 반출 제약이 있는 환경에 유리하다. `npx skills add firecrawl/anydoc`으로 Claude Code 스킬로 바로 붙는 것도 우리 워크플로에 낮은 비용으로 실험 가능.
