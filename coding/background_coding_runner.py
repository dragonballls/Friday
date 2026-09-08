"""Real background coding runner for Friday.

This module connects CodingJobManager to Friday's existing Agent coding
pipeline.

The runner itself does not mutate source files. Real mutations remain behind
Agent -> coding handoff -> RealCoderController -> SafeExecutorAdapter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from agent.core import Agent
from coding.coding_jobs import CodingJob, CodingJobManager


AgentFactory = Callable[[], Agent]


def _build_prompt(job: CodingJob) -> str:
    """Build a coding instruction with explicit safety boundaries."""

    expected_paths = "\n".join(
        f"- {path}"
        for path in job.expected_paths
    )

    requirements = "\n".join(
        f"- {requirement}"
        for requirement in job.requirements
    )

    if not requirements:
        requirements = "- No additional requirements were supplied."

    return f"""
You are performing a background coding job for Friday.

PRIMARY GOAL:
{job.goal}

AUTHORIZED WORKSPACE:
{job_metadata_workspace(job)}

AUTHORIZED SOURCE PATHS:
{expected_paths or "- No paths supplied; do not guess a coding surface."}

CURRENT REQUIREMENTS:
{requirements}

BACKGROUND EXECUTION RULES:
1. Investigate the existing implementation before changing anything.
2. Only modify the explicitly authorized source paths.
3. Do not modify Friday's safety mechanisms, protected files, credentials,
   environment files, or unrelated files.
4. Make the smallest coherent change that solves the goal.
5. Run relevant tests or verification.
6. Review the resulting change.
7. Do not claim success unless verification actually passes.
8. If the first approach fails, diagnose the failure rather than blindly
   repeating the same change.
9. Preserve the existing SafeExecutorAdapter transaction and rollback
   protections.

This is a real background coding job. Work toward a verified implementation,
not merely an explanation of what should be changed.
""".strip()


def job_metadata_workspace(job: CodingJob) -> str:
    """Return workspace metadata if supplied by an extended job object."""

    workspace = getattr(job, "workspace", None)

    if workspace:
        return str(workspace)

    return str(Path.cwd())


def _event_is_success(event: Any) -> bool:
    if not isinstance(event, dict):
        return False

    event_type = str(event.get("type", "")).lower()

    if event_type in {
        "coding_transaction_completed",
        "coding_completed",
    }:
        return True

    if event_type == "coding_transaction":
        status = str(
            event.get("status")
            or event.get("state")
            or ""
        ).lower()

        return status in {
            "completed",
            "success",
            "succeeded",
        }

    return False


def _event_is_failure(event: Any) -> bool:
    if not isinstance(event, dict):
        return False

    event_type = str(event.get("type", "")).lower()

    if event_type in {
        "coding_transaction_failed",
        "coding_transaction_rolled_back",
        "coding_failed",
        "error",
    }:
        return True

    return False


def _event_message(event: Any) -> str:
    if not isinstance(event, dict):
        return str(event)

    for key in ("message", "error", "detail", "result"):
        value = event.get(key)

        if value:
            return str(value)

    return ""


def run_background_coding_job(
    job: CodingJob,
    manager: CodingJobManager,
    *,
    agent_factory: AgentFactory | None = None,
) -> dict[str, Any]:
    """Execute one real Friday coding job.

    The Agent is intentionally created inside the worker. The interactive
    chat Agent is not shared across threads.
    """

    if not job.expected_paths:
        manager.emit(
            job.job_id,
            "blocked",
            "Background coding job has no explicit authorized paths.",
        )

        return {
            "success": False,
            "verified": False,
            "blocked": True,
            "reason": "No explicit expected_paths were supplied.",
        }

    if manager.remaining_seconds(job.job_id) == 0:
        return {
            "success": False,
            "verified": False,
            "expired": True,
        }

    manager.checkpoint(
        job.job_id,
        stage="investigating",
        attempt=max(1, job.attempt + 1),
        message="Starting real Friday background coding worker.",
    )

    factory = agent_factory or (
        lambda: Agent(
            language="english",
            confirm_enabled=False,
        )
    )

    try:
        agent = factory()

        manager.checkpoint(
            job.job_id,
            stage="coding",
            message="Friday coding agent started.",
        )

        prompt = _build_prompt(job)

        events: list[dict[str, Any]] = []
        success_event = False
        failure_event = False

        for event in agent.run(prompt):
            if manager.remaining_seconds(job.job_id) == 0:
                manager.emit(
                    job.job_id,
                    "deadline_reached",
                    "Background coding job reached its time budget.",
                )

                return {
                    "success": False,
                    "verified": False,
                    "expired": True,
                    "events": events[-50:],
                }

            if manager.is_cancelled(job.job_id):
                manager.emit(
                    job.job_id,
                    "cancel_observed",
                    "Background coding worker observed cancellation.",
                )

                return {
                    "success": False,
                    "verified": False,
                    "cancelled": True,
                    "events": events[-50:],
                }

            if isinstance(event, dict):
                events.append(event)

                event_type = str(event.get("type", "")).lower()

                if event_type in {
                    "coding_handoff",
                    "coding_transaction_started",
                    "coding_started",
                }:
                    manager.checkpoint(
                        job.job_id,
                        stage="coding",
                        message=_event_message(event)
                        or "Coding pipeline is active.",
                    )

                elif event_type in {
                    "test",
                    "testing",
                    "tests_started",
                    "tests_completed",
                }:
                    manager.checkpoint(
                        job.job_id,
                        stage="testing",
                        message=_event_message(event)
                        or "Testing stage reached.",
                    )

                elif event_type in {
                    "review",
                    "review_started",
                    "review_completed",
                }:
                    manager.checkpoint(
                        job.job_id,
                        stage="reviewing",
                        message=_event_message(event)
                        or "Review stage reached.",
                    )

                elif event_type in {
                    "final_verify",
                    "final_verification",
                    "verification",
                }:
                    manager.checkpoint(
                        job.job_id,
                        stage="verifying",
                        message=_event_message(event)
                        or "Final verification stage reached.",
                    )

                success_event = success_event or _event_is_success(event)
                failure_event = failure_event or _event_is_failure(event)

        manager.checkpoint(
            job.job_id,
            stage="verifying",
            message="Friday coding worker finished; evaluating verified result.",
        )

        if success_event and not failure_event:
            manager.emit(
                job.job_id,
                "verified",
                "Real Friday coding pipeline reported successful completion.",
            )

            return {
                "success": True,
                "verified": True,
                "events": events[-100:],
            }

        manager.emit(
            job.job_id,
            "repair_needed",
            "Coding run did not produce a verified success event.",
        )

        return {
            "success": False,
            "verified": False,
            "events": events[-100:],
            "reason": (
                "Real coding pipeline completed without a verified "
                "success event."
            ),
        }

    except Exception as exc:
        manager.emit(
            job.job_id,
            "worker_exception",
            f"Background coding worker exception: {exc}",
        )

        return {
            "success": False,
            "verified": False,
            "error": str(exc),
            "exception_type": type(exc).__name__,
        }


def make_background_runner(
    *,
    agent_factory: AgentFactory | None = None,
):
    """Return a CodingJobManager-compatible runner."""

    def runner(job: CodingJob, manager: CodingJobManager):
        return run_background_coding_job(
            job,
            manager,
            agent_factory=agent_factory,
        )

    return runner


__all__ = [
    "make_background_runner",
    "run_background_coding_job",
]