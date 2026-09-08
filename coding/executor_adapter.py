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
    """Safety wrapper around Friday's existing Executor."""

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

    def _run_repository_verification(self) -> dict[str, Any] | None:
        """Run the complete repository gate for a real Git workspace."""
        if not (self.workspace / ".git").exists():
            return None
        try:
            from plugins.builtins.friday_verification import VerifyCodingChangePlugin

            result = VerifyCodingChangePlugin().execute(
                workspace=str(self.workspace),
                timeout=300,
            )
        except Exception as exc:
            return {
                "success": False,
                "all_gates_passed": False,
                "error": f"Final verification could not run: {exc}",
            }
        if not isinstance(result, dict):
            return {
                "success": False,
                "all_gates_passed": False,
                "error": "Final verification returned an invalid result.",
            }
        return result

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
        events: list[dict[str, Any]] = []
        try:
            self.run.start()
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

            self.run.verify_surface()
            changed = self.run.changed_paths()
            if not changed:
                raise CodingExecutorAdapterError(
                    "Completion gate failed: no authorized source change was detected."
                )

            yield {
                "type": "coding_transaction",
                "status": "surface_verified",
                "transaction_id": self.transaction_id,
                "changed_paths": changed,
            }

            implementation_ok = bool(
                implementation_check() if implementation_check else bool(changed)
            )
            tests_ok = bool(test_check() if test_check else True)
            review_ok = bool(review_check() if review_check else True)
            final_ok = bool(
                final_verification_check() if final_verification_check else True
            )

            if test_fn is not None:
                tests_ok = bool(tests_ok and test_fn())
            if review_fn is not None:
                review_ok = bool(review_ok and review_fn())
            if final_verification_fn is not None:
                final_ok = bool(final_ok and final_verification_fn())

            repository_verification = self._run_repository_verification()
            if repository_verification is not None:
                verification_passed = bool(
                    repository_verification.get("success")
                    and repository_verification.get("all_gates_passed")
                )
                final_ok = bool(final_ok and verification_passed)
                tests_ok = bool(tests_ok and verification_passed)
                yield {
                    "type": "verification",
                    "content": repository_verification.get(
                        "message",
                        repository_verification.get(
                            "error",
                            "Repository verification completed.",
                        ),
                    ),
                    "success": verification_passed,
                    "all_gates_passed": verification_passed,
                    "gates": repository_verification.get("gates", []),
                }

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

            self.run.finish(
                implementation_complete=True,
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
            error_text = str(exc)
            try:
                task.status = "failed"
                task.error = error_text
            except Exception:
                pass

            unexpected: list[str] = []
            if self.run.started:
                try:
                    unexpected = list(self.run.unexpected_changes())
                except Exception:
                    pass

            rolled_back = False
            if self.run.started:
                try:
                    self.run.fail_and_rollback()
                    rolled_back = True
                except Exception as rollback_exc:
                    raise CodingExecutorAdapterError(
                        "Coding task failed and rollback also failed: "
                        f"{rollback_exc}"
                    ) from exc

            yield {
                "type": "coding_transaction",
                "status": "rolled_back" if rolled_back else "failed",
                "transaction_id": self.transaction_id,
                "error": error_text,
                "unexpected_changes": unexpected,
            }

            return CodingExecutionResult(
                events=events,
                completed=False,
                rolled_back=rolled_back,
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