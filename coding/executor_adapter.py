from __future__ import annotations

from collections.abc import Callable, Generator, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from coding.coding_run import SafeCodingRun, create_safe_coding_run


class CodingExecutorAdapterError(RuntimeError):
    """Raised when the safe coding executor adapter fails."""


@dataclass
class CodingExecutionResult:
    events: list[dict[str, Any]]
    completed: bool
    rolled_back: bool
    changed_paths: list[str]
    unexpected_changes: list[str]
    transaction_id: str
    implementation_ok: bool = False
    tests_ok: bool = False
    review_ok: bool = False
    final_verification_ok: bool = False


class SafeExecutorAdapter:
    """
    Safety wrapper around Friday's existing Executor.

    The existing Executor remains responsible for:
      - LLM interaction
      - tool selection
      - tool execution
      - permissions
      - confirmations
      - ReAct iterations
      - existing retry behavior

    This adapter adds:
      - explicit coding surface
      - durable pre-run snapshots
      - authorization of expected files
      - unexpected-change detection
      - automatic rollback on failure
      - completion verification
    """

    def __init__(
        self,
        executor,
        workspace: str | Path,
        expected_paths: Iterable[str | Path],
    ) -> None:
        self.executor = executor
        self.workspace = Path(workspace).resolve()

        expected = [str(path) for path in expected_paths]

        if not expected:
            raise CodingExecutorAdapterError(
                "Coding execution requires at least one expected path."
            )

        self.run: SafeCodingRun = create_safe_coding_run(
            self.workspace,
            expected,
        )

    @property
    def transaction_id(self) -> str:
        return self.run.transaction_id

    def execute(
        self,
        task,
        messages: list[dict],
        tool_definitions: list[dict],
        *,
        implementation_check: Callable[[], bool] | None = None,
        test_check: Callable[[], bool] | None = None,
        review_check: Callable[[], bool] | None = None,
        final_verification_check: Callable[[], bool] | None = None,
        max_iterations: int = 10,
        test_fn=None,
        review_fn=None,
        final_verification_fn=None,
    ) -> Generator[dict[str, Any], None, CodingExecutionResult]:
        """
        Execute one coding task through the existing Executor while
        placing the workspace inside a SafeCodingRun transaction.

        Any exception, failed task, unexpected workspace mutation, failed
        test, failed review, or failed final verification causes rollback.
        """

        events: list[dict[str, Any]] = []

        try:
            self.run.start()

            # SafeCodingRun requires authorization only after the
            # transaction has started. expected_paths is the explicit
            # coding surface supplied by the caller, so authorize each
            # path before the existing Executor is allowed to modify it.
            for expected_path in self.run.expected_paths:
                self.run.authorize(expected_path)

            yield {
                "type": "coding_transaction",
                "status": "started",
                "transaction_id": self.transaction_id,
                "expected_paths": self.run.expected_paths,
            }

            for event in self.executor.execute_task(
                task,
                messages,
                tool_definitions,
                max_iterations=max_iterations,
            ):
                events.append(event)
                yield event

            if getattr(task, "status", None) == "failed":
                raise CodingExecutorAdapterError(
                    getattr(task, "error", None)
                    or "Existing Executor reported task failure."
                )

            # Verify that the executor touched only the explicitly
            # authorized coding surface.
            self.run.verify_surface()

            changed = self.run.changed_paths()

            yield {
                "type": "coding_transaction",
                "status": "surface_verified",
                "transaction_id": self.transaction_id,
                "changed_paths": changed,
            }

            implementation_ok = (
                implementation_check() if implementation_check else True
            )

            tests_ok = (
                test_check() if test_check else True
            )

            review_ok = (
                review_check() if review_check else True
            )

            final_ok = (
                final_verification_check()
                if final_verification_check
                else True
            )

            if not implementation_ok:
                raise CodingExecutorAdapterError(
                    "Completion gate failed: implementation check failed."
                )

            if not tests_ok:
                raise CodingExecutorAdapterError(
                    "Completion gate failed: tests failed."
                )

            if not review_ok:
                raise CodingExecutorAdapterError(
                    "Completion gate failed: review failed."
                )

            if not final_ok:
                raise CodingExecutorAdapterError(
                    "Completion gate failed: final verification failed."
                )

            # SafeCodingRun is responsible for the final transaction
            # completion decision. If it rejects completion, the exception
            # enters the rollback path below.

            # Completion gates execute while the durable transaction is open.
            # A failed gate therefore enters the exception/rollback path.
            if test_fn is not None and not bool(test_fn()):
                raise RuntimeError(
                    "Coding completion gate failed: tests did not pass."
                )

            if review_fn is not None and not bool(review_fn()):
                raise RuntimeError(
                    "Coding completion gate failed: review did not pass."
                )

            if (
                final_verification_fn is not None
                and not bool(final_verification_fn())
            ):
                raise RuntimeError(
                    "Coding completion gate failed: final verification did not pass."
                )
            self.run.finish(
                implementation_complete=implementation_ok,
                test_passed=tests_ok,
                review_passed=review_ok,
                final_verification_passed=final_ok,
            )

            changed = self.run.changed_paths()

            yield {
                "type": "coding_transaction",
                "status": "completed",
                "transaction_id": self.transaction_id,
                "changed_paths": changed,
            }

            return CodingExecutionResult(
                events=events,
                completed=True,
                rolled_back=False,
                changed_paths=changed,
                unexpected_changes=[],
                transaction_id=self.transaction_id,
                implementation_ok=bool(implementation_ok),
                tests_ok=bool(tests_ok),
                review_ok=bool(review_ok),
                final_verification_ok=bool(final_ok),
            )

        except Exception as exc:
            unexpected: list[str] = []

            try:
                unexpected = list(self.run.unexpected_changes())
            except Exception:
                pass

            try:
                self.run.fail_and_rollback()
            except Exception as rollback_exc:
                raise CodingExecutorAdapterError(
                    "Coding task failed and rollback also failed: "
                    f"{rollback_exc}"
                ) from exc

            yield {
                "type": "coding_transaction",
                "status": "rolled_back",
                "transaction_id": self.transaction_id,
                "error": str(exc),
                "unexpected_changes": unexpected,
            }

            return CodingExecutionResult(
                events=events,
                completed=False,
                rolled_back=True,
                changed_paths=[],
                unexpected_changes=unexpected,
                transaction_id=self.transaction_id,
            )


def create_safe_executor_adapter(
    executor,
    workspace: str | Path,
    expected_paths: Iterable[str | Path],
) -> SafeExecutorAdapter:
    return SafeExecutorAdapter(
        executor=executor,
        workspace=workspace,
        expected_paths=expected_paths,
    )

