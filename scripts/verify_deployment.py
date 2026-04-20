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
    health_data = {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{base_url}/health")
            health_data = response.json() if response.status_code == 200 else {}
            checks.append(("App health", response.status_code == 200, health_data.get("status")))

            backend = health_data.get("inference_backend", "unknown")
            backend_ok = health_data.get("backend_reachable", False)
            checks.append(
                (
                    f"Inference backend ({backend})",
                    backend_ok,
                    "reachable" if backend_ok else "UNREACHABLE",
                )
            )

            if backend == "hf_space":
                try:
                    response2 = await client.post(
                        f"{base_url}/api/v1/ingest",
                        json={
                            "source": "verify_script",
                            "content": "A recursive function calls itself with a base case.",
                            "assignment_id": "smoke-test",
                            "course_id": "CS301",
                        },
                    )
                    tagged = response2.json().get("status") == "queued"
                    checks.append(
                        (
                            "HF Space inference smoke test",
                            tagged,
                            "Scout queued" if tagged else "failed",
                        )
                    )
                except Exception as exc:
                    checks.append(("HF Space inference smoke test", False, str(exc)))
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
