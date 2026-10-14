"""X(Twitter) 로그인 세션 1회 발급 — 수동 실행 전용.

파이프라인(main.py)에서 자동 호출되지 않는다. 사람이 터미널에서 직접 실행해
본인 X 계정 세션을 state/x_auth_state.json 에 저장하는 용도.
이후 x_timeline.py 가 이 파일을 읽어 헤드리스로 수집한다. 세션이 만료되면 다시 실행한다.

사용법 (둘 중 하나):
    # 1) 새 브라우저 창에서 로그인 — 홈 타임라인이 뜨면 터미널에서 Enter
    uv run python sources/x_login.py

    # 2) 이미 X 에 로그인된 내 Chrome 프로필의 x.com 쿠키를 그대로 가져오기
    #    (Playwright 창에서 구글 로그인 리디렉션이 막힐 때). macOS 키체인
    #    "Chrome Safe Storage" 접근 허용 창이 뜨면 허용.
    uv run --with browser-cookie3 python sources/x_login.py --from-chrome [--profile "Profile 1"]
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

STATE_PATH = "state/x_auth_state.json"
CHROME_DIR = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"


async def login_in_browser():
    from playwright.async_api import async_playwright

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


def import_from_chrome(profile: str):
    """Chrome 프로필의 x.com 쿠키 → Playwright storage_state 형식으로 저장."""
    import browser_cookie3

    cookie_file = CHROME_DIR / profile / "Cookies"
    if not cookie_file.exists():
        raise SystemExit(f"Chrome 프로필 '{profile}' 의 쿠키 파일이 없음: {cookie_file}")

    jar = browser_cookie3.chrome(cookie_file=str(cookie_file), domain_name="x.com")
    cookies = [
        {
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path or "/",
            "expires": float(c.expires) if c.expires else -1,
            "httpOnly": bool(c.has_nonstandard_attr("HttpOnly")),
            "secure": bool(c.secure),
            "sameSite": "None" if c.secure else "Lax",
        }
        for c in jar
    ]
    if not any(c["name"] == "auth_token" for c in cookies):
        raise SystemExit(
            f"'{profile}' 프로필에 X 로그인 쿠키(auth_token)가 없음 — "
            "그 프로필의 Chrome 에서 x.com 로그인 상태인지 확인하거나 --profile 을 바꿔 다시 실행"
        )

    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"cookies": cookies, "origins": []}, f)
    os.chmod(STATE_PATH, 0o600)
    print(f"Chrome '{profile}' 에서 x.com 쿠키 {len(cookies)}개 가져옴 → {STATE_PATH}")


def main():
    parser = argparse.ArgumentParser(description="X 로그인 세션 발급")
    parser.add_argument("--from-chrome", action="store_true", help="로그인된 Chrome 프로필의 쿠키 사용")
    parser.add_argument("--profile", default="Default", help="Chrome 프로필 디렉터리 이름 (기본 Default)")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    if args.from_chrome:
        import_from_chrome(args.profile)
    else:
        asyncio.run(login_in_browser())


if __name__ == "__main__":
    main()
