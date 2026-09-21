---
title: "Databricks introduced a new database that could change everything (?)"
author: Vu Trinh
url: https://medium.com/@vutrinh274/databricks-introduced-a-new-database-that-could-change-everything-99e24709846f
published: 2026-09-06
fetched: 2026-09-09
category: 인프라 & 컴퓨트
tags: [Databricks, Lakebase, Neon, PostgreSQL, WAL, 오브젝트 스토리지, DB 브랜칭, 에이전트 인프라, LTAP]
---

> ⚠️ 원문 전문은 저작권상 저장하지 않음 — 아래는 패러프레이즈 요약. 원문은 위 url 참조.

## 한글 요약

Databricks 가 2025년 5월 서버리스 Postgres 업체 Neon 을 인수한 뒤 내놓은 OLTP 데이터베이스 **Lakebase** 를 아키텍처 관점에서 뜯어본 글이다. 저자는 처음엔 "또 하나의 컴퓨트·스토리지 분리 DB" 정도로 봤지만, Databricks 블로그를 읽고 나서 핵심은 분리 자체가 아니라 **WAL(Write-Ahead Log)을 데이터베이스 그 자체로 승격시킨 설계**라고 결론짓는다.

배경 설명으로 Postgres 의 두 개념을 먼저 짚는다. 하나는 **페이지** — DB 가 디스크 I/O 단위로 쓰는 블록으로, 행 하나를 읽더라도 페이지 전체를 메모리에 올리고 통째로 되쓴다. 다른 하나는 **WAL** — 수정된 페이지가 디스크에 내려가기 전에 반드시 먼저 기록되는 append-only 로그로, Postgres 는 WAL 에만 durable 하게 남으면 커밋을 인정한다. 전통 Postgres 에서 WAL 은 복구용 보험이며, 페이지가 디스크에 반영되면 버려도 되는 존재다.

Lakebase 의 동기는 세 가지다. (1) Postgres·MySQL 은 네트워크가 느리고 서버를 선구매하던 시대에 설계돼 컴퓨트와 스토리지가 묶여 있어 종량제·탄력성과 안 맞는다. Aurora·AlloyDB 가 분리를 해결했지만 독점 포맷이라 락인이 생긴다. (2) 코드는 git 브랜치가 메타데이터 조작 한 번으로 생기는데 DB 는 인스턴스를 새로 띄우고 데이터를 복제해야 해서 무겁다. (3) **에이전트가 앱을 만드는 시대**엔 스키마 시도·마이그레이션 실험이 프롬프트마다, 때론 병렬로 일어나 짧게 살다 죽는 DB 가 대량으로 필요한데, DB 생성 비용이 병목이 된다. 그래서 목표는 컴퓨트·스토리지 분리 + 개방형 포맷 + 브랜칭 가능.

설계 결정 첫 번째는 **오브젝트 스토리지를 저장 계층으로** 쓰는 것. 지연시간 문제는 stateless 컴퓨트 노드의 로컬 SSD 캐시로 메우고, 캐시 미스 때만 별도 컴포넌트가 오브젝트 스토리지에서 가져온다. 컴퓨트는 데이터 재배치 없이 독립적으로 미세 단위 스케일링이 되며, 유휴 시 0 까지 내려갔다가 웜 풀 덕에 1초 내 복귀한다.

두 번째 결정이 핵심인 **WAL 의 1급 시민화**다. WAL 레코드는 어떤 페이지(blkref)가 관여했는지와 단조 증가하는 순서 번호(LSN)를 함께 담으므로, WAL 전체 이력을 보관하면 DB 의 완전한 타임라인이 된다. Lakebase 는 데이터 파일을 제자리 수정하지 않고 WAL 을 **불변 파일**로 물질화한다. 파일은 두 종류 — 특정 페이지 키 범위·LSN 구간의 변경분만 담은 **delta layer**, 그리고 한 LSN 시점에 해당 키 범위의 모든 페이지를 통째로 스냅샷한 **image layer**. 둘 다 한 번 쓰면 수정하지 않고, 백그라운드 컴팩션이 delta 를 기존 image 위에 재생해 새 image 를 만든다. CDC 의 base 테이블 + changes 테이블 병합과 같은 그림이며, 과거 이력이 보존된다는 점이 전통 방식과 다르다.

아키텍처는 컴퓨트(쿼리 파싱·계획·실행·인덱스 처리를 하는 Postgres, 다만 데이터 영속화는 안 함)와 스토리지 세 컴포넌트로 나뉜다. **Safekeeper** 는 컴퓨트로부터 WAL 을 받아 복제하고 쿼럼이 디스크에 쓰면 ACK 를 돌려준 뒤 나중에 오브젝트 스토리지로 업로드한다. **Pageserver** 는 WAL 을 스트리밍해 LSM 트리 유사 구조로 페이지를 물질화하고, `GetPage@LSN` API 로 특정 LSN 시점의 페이지를 돌려준다(가장 가까운 image 를 찾아 delta 를 재생). **오브젝트 스토리지**가 단일 진실 원천이다.

쓰기 경로: 메모리에서 변경 → WAL 을 로컬 디스크 대신 Safekeeper 로 전송 → 쿼럼 기록 시 커밋 → 로드밸런싱된 SK 가 오브젝트 스토리지 업로드 → Pageserver 가 비동기로 인메모리 버퍼에 append 하다 임계치에 delta layer 로 flush, 쌓이면 컴팩션으로 image layer 생성. 읽기 경로: 컴퓨트의 shared buffer → 로컬 NVMe 캐시 → 미스 시 Pageserver 에 GetPage@LSN → 인덱스로 수백만 레이어 파일 중 해당 레이어 탐색 → 페이지 재구성 후 반환·캐시.

이 구조 덕분에 **브랜칭은 데이터 복사가 아니라 참조 생성**이 된다. 새 타임라인 ID 와 부모의 어느 LSN 에서 갈라졌는지만 기록하면 끝이라, `git checkout -b` 와 동일하게 변경 전까지는 부모와 모든 객체를 공유한다. 저자는 마이그레이션·롤백을 많이 다루는 개발자에게 이 기능만으로도 바닐라 Postgres 의 대안이 되며, 특히 에이전트가 DB 20개를 동시에 브랜치해 실험하고 안 쓰는 브랜치는 자동 축소되는 시나리오에서 빛난다고 본다.

부수 효과로 데이터가 이미 오브젝트 스토리지에 있으니 OLTP→OLAP 내보내기 단계가 사라진다. `wal2delta` 논리 디코딩 확장이 WAL 스트림을 SCD Type 2 형태의 Delta Lake 테이블로 직접 쓰고, 반대 방향(Lakehouse→Lakebase)은 Spark 스트리밍으로 분석 결과를 Postgres 로 되먹여 추천·reverse ETL 에 쓴다. Databricks 는 이를 OLAP 과 OLTP 를 단일 데이터 사본 위에 통합하는 "LTAP" 의 기반으로 위치시킨다.

**적용 각도(참고용 메모)**: 코딩 에이전트가 스키마 실험을 병렬로 돌리는 워크플로우에서 "DB 브랜치 = 포인터" 모델이 샌드박스 비용을 없앤다는 논지 — 로컬 Postgres 대신 Neon/Lakebase 류를 에이전트 개발 환경에 붙일 때의 근거 자료.
