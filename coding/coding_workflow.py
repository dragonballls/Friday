from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable


class CodingWorkflowError(RuntimeError):
    """Base error for the safe coding workflow."""


class CodingWorkflowState(str, Enum):
    CREATED = "created"
    EXPLORING = "exploring"
    PLANNING = "planning"
    AUTHORIZED = "authorized"
    CODING = "coding"
    TESTING = "testing"
    REVIEWING = "reviewing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class CodingPlan:
    """Explicit plan produced before source mutation."""

    goal: str
    expected_paths: tuple[str, ...]
    implementation_steps: tuple[str, ...] = ()
    test_paths: tuple[str, ...] = ()
    review_required: bool = True

    def __post_init__(self) -> None:
        if not self.goal.strip():
            raise CodingWorkflowError("Coding plan requires a non-empty goal.")

        if not self.expected_paths:
            raise CodingWorkflowError(
                "Coding plan requires at least one explicit expected path."
            )

        normalized = tuple(
            dict.fromkeys(
                str(path).strip()
                for path in self.expected_paths
                if str(path).strip()
            )
        )

        if not normalized:
            raise CodingWorkflowError(
                "Coding plan contains no usable expected paths."
            )

        object.__setattr__(self, "expected_paths", normalized)


@dataclass
class CodingWorkflowResult:
    state: CodingWorkflowState
    completed: bool
    rolled_back: bool
    implementation_ok: bool = False
    tests_ok: bool = False
    review_ok: bool = False
    final_verification_ok: bool = False
    changed_paths: list[str] = field(default_factory=list)
    error: str | None = None


class CodingWorkflow:
    """
    Orchestrates a safe coding lifecycle without owning filesystem mutation.

    The existing SafeCodingRun remains responsible for the actual transaction
    boundary. This class is deliberately dependency-injected so Stage 3J can
    be tested without changing Agent, Executor, or production startup code.
    """

    def __init__(
        self,
        workspace: str | Path,
        plan: CodingPlan,
        *,
        begin_transaction: Callable[[Iterable[str]], object],
        code: Callable[[CodingPlan], object],
        test: Callable[[CodingPlan], bool],
        review: Callable[[CodingPlan], bool],
        final_verify: Callable[[CodingPlan], bool],
        finish_transaction: Callable[..., object],
        rollback_transaction: Callable[[], object],
        changed_paths: Callable[[], Iterable[str]],
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.plan = plan

        self._begin_transaction = begin_transaction
        self._code = code
        self._test = test
        self._review = review
        self._final_verify = final_verify
        self._finish_transaction = finish_transaction
        self._rollback_transaction = rollback_transaction
        self._changed_paths = changed_paths

        self.state = CodingWorkflowState.CREATED

    def run(self) -> CodingWorkflowResult:
        """
        Execute the complete coding lifecycle.

        Any gate failure enters the rollback boundary. Exceptions also enter
        rollback. No gate may silently declare success.
        """

        try:
            self.state = CodingWorkflowState.EXPLORING
            self._validate_workspace()

            self.state = CodingWorkflowState.PLANNING
            self._validate_plan()

            self._begin_transaction(self.plan.expected_paths)
            self.state = CodingWorkflowState.AUTHORIZED

            self.state = CodingWorkflowState.CODING
            self._code(self.plan)

            implementation_ok = True

            self.state = CodingWorkflowState.TESTING
            tests_ok = bool(self._test(self.plan))
            if not tests_ok:
                return self._rollback_result(
                    implementation_ok=implementation_ok,
                    tests_ok=False,
                    review_ok=False,
                    final_verification_ok=False,
                    error="Coding workflow test gate failed.",
                )

            self.state = CodingWorkflowState.REVIEWING
            review_ok = (
                bool(self._review(self.plan))
                if self.plan.review_required
                else True
            )

            if not review_ok:
                return self._rollback_result(
                    implementation_ok=implementation_ok,
                    tests_ok=tests_ok,
                    review_ok=False,
                    final_verification_ok=False,
                    error="Coding workflow review gate failed.",
                )

            self.state = CodingWorkflowState.VERIFYING
            final_verification_ok = bool(self._final_verify(self.plan))

            if not final_verification_ok:
                return self._rollback_result(
                    implementation_ok=implementation_ok,
                    tests_ok=tests_ok,
                    review_ok=review_ok,
                    final_verification_ok=False,
                    error="Coding workflow final verification failed.",
                )

            changed = list(self._changed_paths())

            self._finish_transaction(
                implementation_complete=implementation_ok,
                test_passed=tests_ok,
                review_passed=review_ok,
                final_verification_passed=final_verification_ok,
            )

            self.state = CodingWorkflowState.COMPLETED

            return CodingWorkflowResult(
                state=self.state,
                completed=True,
                rolled_back=False,
                implementation_ok=implementation_ok,
                tests_ok=tests_ok,
                review_ok=review_ok,
                final_verification_ok=final_verification_ok,
                changed_paths=changed,
            )

        except Exception as exc:
            self._rollback_transaction()
            self.state = CodingWorkflowState.ROLLED_BACK

            return CodingWorkflowResult(
                state=self.state,
                completed=False,
                rolled_back=True,
                error=str(exc),
            )

    def _rollback_result(
        self,
        *,
        implementation_ok: bool,
        tests_ok: bool,
        review_ok: bool,
        final_verification_ok: bool,
        error: str,
    ) -> CodingWorkflowResult:
        self._rollback_transaction()
        self.state = CodingWorkflowState.ROLLED_BACK

        return CodingWorkflowResult(
            state=self.state,
            completed=False,
            rolled_back=True,
            implementation_ok=implementation_ok,
            tests_ok=tests_ok,
            review_ok=review_ok,
            final_verification_ok=final_verification_ok,
            error=error,
        )

    def _validate_workspace(self) -> None:
        if not self.workspace.exists():
            raise CodingWorkflowError(
                f"Workspace does not exist: {self.workspace}"
            )

        if not self.workspace.is_dir():
            raise CodingWorkflowError(
                f"Workspace is not a directory: {self.workspace}"
            )

    def _validate_plan(self) -> None:
        if not self.plan.expected_paths:
            raise CodingWorkflowError(
                "No explicit coding paths were authorized."
            )

        for raw_path in self.plan.expected_paths:
            candidate = Path(raw_path)

            if candidate.is_absolute():
                resolved = candidate.resolve()
            else:
                resolved = (self.workspace / candidate).resolve()

            try:
                resolved.relative_to(self.workspace)
            except ValueError as exc:
                raise CodingWorkflowError(
                    f"Coding path escapes workspace: {raw_path}"
                ) from exc

            relative_parts = resolved.relative_to(self.workspace).parts
            blocked = {
                ".git",
                ".venv",
                "venv",
                "env",
            }

            if any(part.lower() in blocked for part in relative_parts):
                raise CodingWorkflowError(
                    f"Coding path enters protected directory: {raw_path}"
                )