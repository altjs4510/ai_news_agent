"""X(Twitter) 로그인 세션 1회 발급 — 수동 실행 전용.

파이프라인(main.py)에서 자동 호출되지 않는다. 사람이 터미널에서 직접 실행해
브라우저 창에서 본인 X 계정으로 로그인한 뒤 세션을 저장하는 용도.

사용법:
    uv run python sources/x_login.py

로그인 완료(홈 타임라인이 뜬 상태) 후 터미널로 돌아와 Enter를 누르면
세션이 state/x_auth_state.json 에 저장된다. 이후 x_timeline.py 가 이 파일을 읽어
헤드리스로 홈 타임라인을 수집한다. 세션이 만료되면 이 스크립트를 다시 실행한다.
"""

import asyncio
import os

STATE_PATH = "state/x_auth_state.json"


async def main():
    from playwright.async_api import async_playwright

    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://x.com/login")

        print("브라우저에서 X 계정으로 로그인하세요.")
        input("홈 타임라인이 뜨면 이 터미널로 돌아와 Enter를 누르세요...")

        await context.storage_state(path=STATE_PATH)
        await browser.close()
        print(f"세션 저장 완료: {STATE_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
