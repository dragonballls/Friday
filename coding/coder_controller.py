from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from coding.coding_handoff import CodingHandoff
from coding.coding_run import CodingRunError
from coding.repair_loop import BoundedRepairLoop


class CoderControllerError(CodingRunError):
    """Raised when the real coding controller cannot safely complete."""


@dataclass(frozen=True)
class CoderResult:
    success: bool
    changed_paths: tuple[str, ...]
    transaction_id: str
    tests_ok: bool
    review_ok: bool
    final_verification_ok: bool
    error: str | None = None


class RealCoderController:
    """
    Stage 3O controller.

    Ownership model:

        RealCoderController
            -> coding lifecycle
            -> completion gates

        SafeExecutorAdapter
            -> durable transaction
            -> authorization
            -> existing Executor
            -> surface verification
            -> rollback

        Existing Executor
            -> actual LLM/tool execution

    The controller deliberately does NOT create SafeCodingRun.
    """

    def __init__(
        self,
        *,
        workspace: str | Path,
        handoff: CodingHandoff,
        execute_coder: Callable[..., Any],
        run_tests: Callable[[CodingHandoff], bool],
        run_review: Callable[[CodingHandoff], bool],
        final_verify: Callable[[CodingHandoff], bool],
        repair_coder: Callable[[CodingHandoff, int, Any], Any] | None = None,
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.handoff = handoff
        self.execute_coder = execute_coder
        self.run_tests = run_tests
        self.run_review = run_review
        self.final_verify = final_verify
        self.repair_coder = repair_coder

        if self.workspace != Path(handoff.workspace).resolve():
            raise CoderControllerError(
                "Coder workspace does not match Explorer handoff."
            )

        if not handoff.plan.expected_paths:
            raise CoderControllerError(
                "Coder requires at least one explicit expected path."
            )

    @staticmethod
    def _get_value(
        result: Any,
        name: str,
        default: Any = None,
    ) -> Any:
        if result is None:
            return default

        value = getattr(result, name, None)

        if value is not None:
            return value

        if isinstance(result, dict):
            return result.get(name, default)

        return default

    @staticmethod
    def _consume_execution_result(result: Any) -> Any:
        """
        Accept the existing Agent bridge contract.

        execute_coder may return:

          1. CodingExecutionResult directly
          2. a generator yielding execution events and returning
             CodingExecutionResult through StopIteration.value
          3. a normal iterable of events with no return value

        The real Agent bridge uses case (2).
        """

        if result is None:
            return None

        # The actual Agent bridge is a generator because it yields
        # Executor/transaction events to the caller. Consume it before
        # evaluating completion gates so StopIteration.value becomes the
        # execution result instead of the generator object itself.
        if hasattr(result, "__next__"):
            iterator = result

            try:
                while True:
                    next(iterator)
            except StopIteration as stop:
                return stop.value

        return result

    def run(self) -> CoderResult:
        """
        Run the complete bounded coding lifecycle.

        Every attempt owns its complete transaction boundary:
            execute -> tests -> review -> final verification

        SafeExecutorAdapter is therefore able to roll back an attempt
        before BoundedRepairLoop starts the next attempt.
        """

        def run_attempt(attempt_number: int) -> Any:
            try:
                result = self._consume_execution_result(
                    self.execute_coder(
                        self.handoff,
                        self.run_tests,
                        self.run_review,
                        self.final_verify,
                    )
                )

                if result is None:
                    return {
                        "success": False,
                        "error": "Coding executor returned no execution result.",
                    }

                completed = self._get_value(
                    result,
                    "completed",
                    False,
                )

                if completed is not True:
                    return {
                        "success": False,
                        "error": (
                            self._get_value(
                                result,
                                "error",
                            )
                            or
                            f"Coding attempt {attempt_number} did not complete."
                        ),
                    }

                return {
                    "success": True,
                    "result": result,
                }

            except Exception as exc:
                return {
                    "success": False,
                    "error": str(exc),
                }

        def repair(attempt_number: int, failed_result: Any) -> Any:
            """
            Repair preparation is deliberately delegated to the Agent
            bridge. The controller itself never edits files.
            """

            repair_callback = getattr(
                self,
                "repair_coder",
                None,
            )

            if repair_callback is None:
                raise CoderControllerError(
                    "No repair callback is available; "
                    "coding repair fails closed."
                )

            return repair_callback(
                self.handoff,
                attempt_number,
                failed_result,
            )

        # The controller currently receives the repair capability
        # through an optional attribute installed by the Agent bridge.
        #
        # If no repair callback exists, the first failed attempt is
        # intentionally not retried.
        repair_callback = getattr(
            self,
            "repair_coder",
            None,
        )

        loop = BoundedRepairLoop(
            max_attempts=3,
            run_attempt=run_attempt,
            repair=(
                repair
                if repair_callback is not None
                else None
            ),
        )

        loop_result = loop.run()

        if not loop_result.success:
            error = (
                loop_result.error
                or
                "Bounded coding repair loop failed."
            )

            raise CoderControllerError(
                f"Coding completion gate failed: {error}"
            )

        execution_result = loop_result.final_result

        if isinstance(execution_result, dict):
            execution_result = execution_result.get(
                "result",
                execution_result,
            )

        if execution_result is None:
            raise CoderControllerError(
                "Coding repair loop completed without a final result."
            )

        transaction_id = self._get_value(
            execution_result,
            "transaction_id",
        )

        if not transaction_id:
            raise CoderControllerError(
                "Coding executor did not provide a transaction ID."
            )

        changed_paths = self._get_value(
            execution_result,
            "changed_paths",
            [],
        )

        changed_paths = tuple(
            sorted(
                str(path)
                for path in (changed_paths or [])
            )
        )

        tests_ok = self._get_value(execution_result, "tests_ok", None)
        review_ok = self._get_value(execution_result, "review_ok", None)
        final_verification_ok = self._get_value(
            execution_result,
            "final_verification_ok",
            None,
        )
        implementation_ok = self._get_value(
            execution_result,
            "implementation_ok",
            None,
        )

        if not all(
            value is True
            for value in (
                implementation_ok,
                tests_ok,
                review_ok,
                final_verification_ok,
            )
        ):
            raise CoderControllerError(
                "Coding completion gate failed: "
                "execution result did not explicitly verify "
                "implementation, tests, review, and final verification."
            )

        return CoderResult(
            success=True,
            changed_paths=changed_paths,
            transaction_id=str(transaction_id),
            tests_ok=tests_ok,
            review_ok=review_ok,
            final_verification_ok=final_verification_ok,
        )


def create_coder_controller(
    *,
    workspace: str | Path,
    handoff: CodingHandoff,
    execute_coder: Callable[..., Any],
    run_tests: Callable[[CodingHandoff], bool],
    run_review: Callable[[CodingHandoff], bool],
    final_verify: Callable[[CodingHandoff], bool],
    repair_coder: Callable[[CodingHandoff, int, Any], Any] | None = None,
) -> RealCoderController:
    return RealCoderController(
        workspace=workspace,
        handoff=handoff,
        execute_coder=execute_coder,
        run_tests=run_tests,
        run_review=run_review,
        final_verify=final_verify,
        repair_coder=repair_coder,
    )
