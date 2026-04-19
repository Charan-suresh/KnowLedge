#!/usr/bin/env python3
"""
Run before sharing the demo URL with judges.
Usage: python scripts/verify_deployment.py https://knowledge.onrender.com
"""

import asyncio
import sys

import httpx


async def verify(base_url: str) -> bool:
    checks = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{base_url}/health")
            data = response.json()
            checks.append(("App health", response.status_code == 200, data.get("status")))
            checks.append(("Ollama reachable from app", data.get("ollama") == "reachable", data.get("ollama")))
        except Exception as exc:
            checks.append(("App health", False, str(exc)))

        try:
            response = await client.get(f"{base_url}/ledger")
            checks.append(("Ledger page", response.status_code == 200, f"{response.status_code}"))
        except Exception as exc:
            checks.append(("Ledger page", False, str(exc)))

        try:
            response = await client.get(f"{base_url}/progress")
            checks.append(("Progress page", response.status_code == 200, f"{response.status_code}"))
        except Exception as exc:
            checks.append(("Progress page", False, str(exc)))

        try:
            response = await client.get(f"{base_url}/reports")
            checks.append(("Reports page", response.status_code == 200, f"{response.status_code}"))
        except Exception as exc:
            checks.append(("Reports page", False, str(exc)))

        try:
            response = await client.post(
                f"{base_url}/api/v1/ingest",
                json={
                    "source": "verify_script",
                    "content": "Recursion is a method where a function calls itself with a base case to prevent infinite loops.",
                    "assignment_id": "verify-001",
                    "course_id": "CS301",
                },
            )
            checks.append(("Scout ingest", response.status_code == 200, response.json().get("status")))
        except Exception as exc:
            checks.append(("Scout ingest", False, str(exc)))

        try:
            response = await client.get(f"{base_url}/api/events")
            checks.append(("Events endpoint", response.status_code == 200, f"{len(response.json())} events"))
        except Exception as exc:
            checks.append(("Events endpoint", False, str(exc)))

        try:
            response = await client.get(f"{base_url}/api/sync/status")
            checks.append(("Sync status", response.status_code == 200, str(response.json())))
        except Exception as exc:
            checks.append(("Sync status", False, str(exc)))

    print(f"\n{'=' * 55}")
    print("  KnowLedge deployment verification")
    print(f"  Target: {base_url}")
    print(f"{'=' * 55}")

    all_passed = True
    for name, passed, detail in checks:
        icon = "✓" if passed else "✗"
        print(f"  {icon}  {name:<30} {detail}")
        if not passed:
            all_passed = False

    print(f"{'=' * 55}")
    if all_passed:
        print("  All checks passed. Safe to share with judges.")
    else:
        print("  Some checks failed. Fix before sharing.")
    print(f"{'=' * 55}\n")
    return all_passed


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    passed = asyncio.run(verify(url))
    sys.exit(0 if passed else 1)
