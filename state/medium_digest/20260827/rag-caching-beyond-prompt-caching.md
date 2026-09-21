---
title: "Beyond Prompt Caching: 5 More Things You Should Cache in RAG Pipelines"
author: Maria Mouschoutzi, PhD (AI Advances)
url: https://medium.com/@m.mouschoutzi/beyond-prompt-caching-5-more-things-you-should-cache-in-rag-pipelines-138e972e22df
published: 2026-05-15
fetched: 2026-08-27
category: 응용 사례
tags: [RAG, caching, Redis, vector-db]
---

> ⚠️ 원문 전문은 저작권상 저장하지 않음 — 아래는 패러프레이즈 요약. 원문은 위 url 참조.

## 한글 요약

LLM API가 기본 제공하는 Prompt Caching 말고도, RAG 파이프라인 곳곳에 캐싱을 넣을 수 있다는 실무 가이드. 핵심 구분은 **정확 일치 캐싱**(원문 그대로 매칭, Redis 같은 KV store)과 **의미 캐싱**(임베딩 후 코사인 유사도 ~0.95 이상이면 히트, ChromaDB 같은 벡터DB 필요) 두 가지.

**캐싱 5계층**:
1. **쿼리 임베딩 캐시** — 같은(또는 정규화 후 동일한) 질문의 임베딩을 매번 재계산하지 않고 재사용. `query → embedding`.
2. **검색(retrieval) 캐시** — 쿼리(또는 쿼리 임베딩)에 대해 이미 검색된 청크를 캐싱. 쿼리 임베딩 캐시와 별개로 두는 이유는 지식베이스 문서가 바뀌면 같은 쿼리라도 검색 결과가 달라질 수 있어 TTL 정책을 다르게 가져가야 하기 때문. `query → retrieved_chunks`.
3. **리랭킹 캐시** — 리랭커 모델을 다시 안 돌리고 이미 계산된 재정렬 순서를 재사용. `(query + retrieved_chunks) → reranked_chunks`.
4. **프롬프트 조립 캐시** — 시스템 프롬프트+쿼리+청크가 모두 일치하면 최종 조립된 프롬프트(또는 컨텍스트 부분)를 그대로 재사용. 절감 효과는 상대적으로 작지만, 가드레일 삽입 등 조립 로직이 복잡한 시스템에서 유효.
5. **쿼리-응답 캐시** — 동일/매우 유사한 질문엔 파이프라인 전체를 건너뛰고 캐시된 최종 응답을 바로 반환. 가장 큰 절감 효과("잭팟").

실전에서는 이 5계층을 조합해서 쓰는 게 일반적이며, 트래픽이 늘수록 비용·지연시간 절감 효과가 커진다는 결론.

**적용 각도(참고용 메모)**: 우리 파이프라인의 `x_trends.py`(LLM 키워드 추출)나 요약 호출들이 하루 배치라 캐싱 이득이 크진 않지만, 만약 대화형/조회형 기능을 추가한다면 이 5계층 프레임을 그대로 참고할 만함.
