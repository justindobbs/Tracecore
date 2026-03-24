"""Environment setup for the saas_access_review task."""

from __future__ import annotations

from random import Random

from tasks.saas_access_review.service import MockSaaSAccessService
from tasks.saas_access_review.shared import APPROVAL_KEY, README_PATH, REQUEST_KEY, SERVICE_KEY


def setup(seed: int, env) -> None:
    rng = Random(seed)

    request_id = f"REQ-{rng.randint(1000, 9999)}"
    user_email = f"engineer{rng.randint(10, 99)}@example.com"
    current_role = "viewer"
    target_role = "billing_admin"
    justification_hint = "quarterly close"
    approval_code = f"APR-{rng.randint(100000, 999999)}"

    service = MockSaaSAccessService(
        request_id=request_id,
        user_email=user_email,
        target_role=target_role,
        current_role=current_role,
        justification_hint=justification_hint,
        approval_code=approval_code,
        review_ready_at=2,
    )

    env.set_hidden_state(SERVICE_KEY, service)
    env.set_hidden_state(REQUEST_KEY, {
        "request_id": request_id,
        "user_email": user_email,
        "current_role": current_role,
        "target_role": target_role,
        "justification_hint": justification_hint,
    })
    env.set_hidden_state(APPROVAL_KEY, approval_code)

    instructions = (
        "# SaaS Access Review\n"
        "A user requested a privileged SaaS role change. Your job is to complete the deterministic admin workflow and emit the approval token.\n\n"
        "1. Read the request details and required justification hint.\n"
        "2. Submit a review ticket with the exact request_id, user_email, target_role, and a justification that includes the hint phrase.\n"
        "3. Poll review status until the approval_code is ready. If you get `review_pending`, wait the requested number of steps.\n"
        "4. If review_status returns `temporary_failure`, retry immediately without waiting.\n"
        "5. Confirm approval using request_id + approval_code.\n"
        "6. Store the final token using key ACCESS_REVIEW_TOKEN.\n"
    )

    env.write_file(README_PATH, instructions)
    env.mark_seen([README_PATH])
