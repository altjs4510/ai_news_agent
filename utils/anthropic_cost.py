"""Anthropic Admin API에서 조직 사용 비용을 조회한다.

ANTHROPIC_ADMIN_KEY 환경변수가 필요. (일반 API key와 다른, sk-ant-admin01-... 키)
미설정/실패 시에는 안내 문자열을 반환한다 — 호출 측이 fail-soft 할 수 있게.

CLI로 실행하면 Slack에 그대로 붙일 수 있는 한 줄을 stdout에 출력한다.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import requests

ADMIN_KEY = os.getenv("ANTHROPIC_ADMIN_KEY")
COST_URL = "https://api.anthropic.com/v1/organizations/cost_report"


def _fmt_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_cost_usd(starting_at: datetime, ending_at: datetime) -> float | None:
    if not ADMIN_KEY:
        return None
    try:
        resp = requests.get(
            COST_URL,
            params={
                "starting_at": _fmt_iso(starting_at),
                "ending_at": _fmt_iso(ending_at),
            },
            headers={
                "x-api-key": ADMIN_KEY,
                "anthropic-version": "2023-06-01",
            },
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:
        print(f"cost_report 호출 실패: {e}", file=sys.stderr)
        return None

    total = 0.0
    for bucket in body.get("data", []):
        for r in bucket.get("results", []):
            try:
                total += float(r.get("amount", 0))
            except (TypeError, ValueError):
                pass
    return total


def slack_summary() -> str:
    # Bedrock 모드: 비용은 AWS Cost Explorer 영역. Anthropic Admin API는 $0만 반환.
    if os.getenv("USE_BEDROCK", "").strip() in ("1", "true", "yes"):
        return "사용 비용: (Bedrock 모드 — AWS Cost Explorer 확인)"
    if not ADMIN_KEY:
        return "사용 비용: (ANTHROPIC_ADMIN_KEY 미설정)"

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    today = _fetch_cost_usd(today_start, now)
    mtd = _fetch_cost_usd(month_start, now)

    parts: list[str] = []
    if today is not None:
        parts.append(f"오늘 ${today:.2f}")
    if mtd is not None:
        parts.append(f"이번달 ${mtd:.2f}")

    if not parts:
        return "사용 비용: (조회 실패)"
    return "사용 비용: " + " / ".join(parts)


if __name__ == "__main__":
    print(slack_summary())
