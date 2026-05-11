"""Bedrock에서 사용 가능한 Anthropic 모델/inference profile ID 목록을 출력.

목적: utils/llm_client.py의 _BEDROCK_DEFAULTS가 어떤 ID여야 하는지 식별.
USE_BEDROCK 모드 활성화 후 모델 ID가 맞지 않아 발생한 BadRequestError
('The provided model identifier is invalid.')를 해결하기 위한 일회용 진단.

실행:
  AWS_REGION=ap-northeast-2 AWS_BEARER_TOKEN_BEDROCK=... uv run python scripts/list_bedrock_models.py
"""

from __future__ import annotations

import os
import sys

import boto3


def main() -> int:
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    print(f"# region: {region}\n")

    client = boto3.client("bedrock", region_name=region)

    print("## Foundation Models (Anthropic)")
    try:
        resp = client.list_foundation_models(byProvider="anthropic")
        for m in resp.get("modelSummaries", []):
            mid = m.get("modelId", "")
            lifecycle = m.get("modelLifecycle", {}).get("status", "")
            print(f"  {mid}\t[{lifecycle}]")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n## Inference Profiles")
    try:
        # SYSTEM_DEFINED 포함해서 cross-region inference profile 노출.
        resp = client.list_inference_profiles(typeEquals="SYSTEM_DEFINED")
        for p in resp.get("inferenceProfileSummaries", []):
            pid = p.get("inferenceProfileId", "")
            name = p.get("inferenceProfileName", "")
            models = ", ".join(
                m.get("modelArn", "").split("/")[-1]
                for m in p.get("models", [])
            )
            if "anthropic" in pid.lower() or "claude" in name.lower():
                print(f"  {pid}\t({name})\t→ {models}")
    except Exception as e:
        print(f"  ERROR: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
