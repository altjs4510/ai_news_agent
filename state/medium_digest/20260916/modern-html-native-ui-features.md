---
title: "HTML Features in 2026 That Most Devs Don’t Know Exist"
author: Rahul Kaklotar
url: https://medium.com/@kaklotarrahul79/html-features-in-2026-that-most-devs-dont-know-exist-6d3aa7c9db5b
published: 2026-08-13
fetched: 2026-09-16
category: 응용 사례
tags: [HTML, Popover API, dialog, Declarative Shadow DOM, fetchpriority, datalist, 프론트엔드, 접근성]
---

> ⚠️ 원문 전문은 저작권상 저장하지 않음 — 아래는 패러프레이즈 요약. 원문은 위 url 참조.

## 한글 요약

브라우저가 이제 네이티브로 해 주는 일을 위해 50kB짜리 자바스크립트 라이브러리를 설치하지 말라는 것이 이 글의 부제이자 요지다. 10년 넘게 프론트엔드에는 "HTML 은 멍청한 뼈대고 두뇌는 자바스크립트"라는 암묵적 규칙이 있었다 — 모달이 필요하면 React 라이브러리를, 툴팁이나 드롭다운이 필요하면 Popper.js 나 Tippy 를 끌어오고, 동적 콘텐츠 스트리밍 같은 건 JS 수백 줄로 처리했다. 그런데 프레임워크들이 DOM 을 추상화하느라 바쁜 사이, WHATWG Living Standard 와 브라우저 엔진은 조용히 HTML 자체를 꽤 강력한 UI 툴킷으로 바꿔 놨다는 것이다. 필자는 지금 당장 쓸 수 있는데도 많은 개발자가 여전히 JS 로 직접 만들고 있는 여섯 가지를 꼽는다.

**1) 네이티브 Popover API.** 툴팁·플로팅 메뉴·팝오버를 만들려면 z-index 스택 컨텍스트와 씨름하고, 절대 위치를 계산하고, 포커스 트랩과 바깥 클릭 리스너를 붙여야 했다. `popover` 속성과 트리거 쪽 `popovertarget` 만으로 임의의 요소를 플로팅 UI 로 바꿀 수 있고, 해당 요소는 CSS z-index 와 무관하게 Top Layer 로 자동 승격된다. 클릭 토글, ESC 나 바깥 클릭을 통한 자동 닫힘(light-dismiss)이 JS 없이 동작하고 z-index 싸움도 사라진다.

**2) JS 없는 아코디언 — `<details name="...">`.** `<details>`/`<summary>` 로 접히는 영역을 만드는 건 이미 알려진 이야기지만, 여러 `<details>` 에 같은 `name` 값을 주면 브라우저가 알아서 한 번에 하나만 열려 있도록 관리해 준다. 사용자가 하나를 펼치면 같은 `name="faq"` 를 공유하는 이전 항목이 자동으로 닫힌다 — 이벤트 리스너도, 상태 훅도, 동적 클래스도 필요 없는 고전적 아코디언 동작이다.

**3) 네이티브 모달 — `<dialog>` 와 `::backdrop`.** 아직도 커스텀 `<div>` 오버레이로 모달을 만들고 있다면 접근성 감사에서 떨어질 가능성이 높다는 지적이다. Tab 이동을 모달 안에 가두는 포커스 트랩, 닫힐 때 트리거 버튼으로 포커스를 되돌리는 처리 등은 꼼꼼한 JS 를 요구한다. `<dialog>` 는 이를 기본 제공한다 — `.showModal()` 로 열면 Top Layer 로 올라가면서 뒤쪽 페이지와의 상호작용이 차단되고, 키보드 포커스가 안에 갇히며, ESC 로 닫기가 기본 지원된다. 안에 `method="dialog"` 인 폼을 두면 버튼 클릭으로 자동으로 닫히고 어떤 버튼이 눌렸는지도 값으로 받을 수 있다. 백드롭은 `dialog::backdrop` 선택자로 배경색이나 `backdrop-filter` 블러까지 직접 스타일링한다.

**4) Declarative Shadow DOM — `<template shadowrootmode>`.** 원래 웹 컴포넌트와 Shadow DOM 은 클라이언트 JS(`element.attachShadow({mode:'open'})`)가 있어야 인스턴스화됐고, 그래서 SSR·SSG 와 궁합이 몹시 나빴다 — 스타일 없는 콘텐츠가 번쩍 보이는 FOUC 나 레이아웃 시프트로 이어지기 일쑤였다. 선언적 Shadow DOM 은 순수 HTML 안에서 캡슐화된 DOM 트리를 만들 수 있게 해 이를 해결한다. 브라우저가 `<template shadowrootmode="open">` 을 파싱하는 즉시 그 자식들을 렌더링 전에 Shadow Root 로 변환하므로, 서버에서 렌더링한 웹 컴포넌트가 매끄럽게 동작하고 내부 `<style>` 도 그 컴포넌트 안에 갇힌 채 유지된다.

**5) 성능 힌트 — `fetchpriority`.** 이미지의 `loading="lazy"` 나 스크립트의 `async`/`defer` 는 익숙하지만, 첫 화면에 중요한 이미지 셋이 있고 그중 LCP(Largest Contentful Paint)를 좌우하는 히어로 이미지를 소셜 배지나 잔 아이콘보다 먼저 받고 싶다면? `fetchpriority="high"` / `"low"` 로 브라우저 네트워크 스케줄러에 리소스 중요도를 명시적으로 알려 줄 수 있다. 이미지뿐 아니라 핵심 JS 번들에도 붙일 수 있고, 로직을 한 줄도 바꾸지 않고 Core Web Vitals 를 개선하는 수단이라는 설명이다.

**6) 네이티브 자동완성 — `<datalist>`.** 사용자가 직접 입력도 하면서 추천 목록도 보게 하려고 무거운 커스텀 자동완성 컴포넌트를 꺼내 든 적이 얼마나 많은가. `<input list="...">` 와 `<datalist>` 조합이면 JS 의존성 없이 입력 조회가 된다. 브라우저가 목록 형식을 알아서 잡고, 타이핑에 따라 옵션을 필터링하고, 키보드 내비게이션을 처리하며, 호스트 운영체제의 네이티브 외형에 맞춰 준다.

전체를 관통하는 논지는 성능·번들 크기·접근성이 한 방향으로 정렬된다는 것이다 — 플랫폼 네이티브 기능으로 내려갈수록 보일러플레이트 수천 줄이 사라지고, 번들이 줄고, 접근성은 기본값으로 좋아진다.

**적용 각도(참고용 메모)**: 단일 파일 HTML 로 뽑는 사내 대시보드·리포트(quick-dashboard 류)에 바로 닿는다 — 라이브러리 없이 `<dialog>` 로 상세 드릴다운 모달, `<details name>` 로 섹션 아코디언, `<datalist>` 로 브랜드·시즌 입력 자동완성, 히어로 차트 이미지에 `fetchpriority="high"` 를 쓰면 의존성 0 인 정적 산출물의 UX 를 올릴 수 있다.
