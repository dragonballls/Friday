from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CodingAttempt:
    """Structured record of one coding attempt."""

    attempt: int
    success: bool
    failure_class: str | None = None
    error: str | None = None
    strategy: str | None = None
    recommended_action: str | None = None
    confidence: str | None = None
    evidence: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "attempt": self.attempt,
            "success": self.success,
            "failure_class": self.failure_class,
            "error": self.error,
            "strategy": self.strategy,
            "recommended_action": self.recommended_action,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
        }


@dataclass
class CodingAttemptHistory:
    """In-memory history of attempts within one coding session."""

    attempts: list[CodingAttempt] = field(default_factory=list)

    def record(
        self,
        attempt: int,
        *,
        success: bool,
        failure_class: str | None = None,
        error: str | None = None,
        strategy: str | None = None,
        recommended_action: str | None = None,
        confidence: str | None = None,
        evidence: tuple[str, ...] = (),
    ) -> CodingAttempt:
        entry = CodingAttempt(
            attempt=attempt,
            success=success,
            failure_class=failure_class,
            error=error,
            strategy=strategy,
            recommended_action=recommended_action,
            confidence=confidence,
            evidence=evidence,
        )
        self.attempts.append(entry)
        return entry

    @property
    def last(self) -> CodingAttempt | None:
        if not self.attempts:
            return None
        return self.attempts[-1]

    @property
    def failures(self) -> tuple[CodingAttempt, ...]:
        return tuple(
            attempt
            for attempt in self.attempts
            if not attempt.success
        )

    def has_failed_strategy(self, strategy: str | None) -> bool:
        if not strategy:
            return False

        return any(
            attempt.strategy == strategy
            for attempt in self.failures
        )

    def failed_strategies(self) -> tuple[str, ...]:
        return tuple(
            attempt.strategy
            for attempt in self.failures
            if attempt.strategy
        )

    def choose_repair_strategy(
        self,
        failure_class: str,
        recommended_action: str,
    ) -> str:
        """Choose a concrete repair approach that has not already failed."""

        strategies = {
            "TEST_FAILURE": (
                "Trace the failing test and affected call path before "
                "changing code."
            ),
            "IMPORT_ERROR": (
                "Inspect the existing module and dependency structure, "
                "then repair the failing import path without adding "
                "unnecessary dependencies."
            ),
            "SYNTAX_ERROR": (
                "Inspect the exact syntax location and make the smallest "
                "localized source correction."
            ),
            "LINT_FAILURE": (
                "Inspect the reported lint rule and affected line, then "
                "make the smallest compliant source correction."
            ),
            "FORMAT_FAILURE": (
                "Inspect the formatter difference and apply only the "
                "required formatting correction."
            ),
            "SECURITY_BLOCK": (
                "Re-evaluate the authorized coding surface and restrict "
                "the repair to explicitly permitted files and operations."
            ),
            "UNEXPECTED_CHANGE": (
                "Trace the operation that caused the unauthorized mutation "
                "and narrow the implementation to the approved paths."
            ),
            "REVIEW_FAILURE": (
                "Inspect the independent review finding, reproduce the "
                "reported defect, and correct only the affected behavior."
            ),
            "TIMEOUT": (
                "Reduce the operation to the smallest reproducible scope, "
                "identify what is blocking progress, and fix that bottleneck."
            ),
            "TOOL_ERROR": (
                "Inspect the failed tool invocation and correct its inputs "
                "or usage before changing application code."
            ),
        }

        primary = strategies.get(
            failure_class,
            (
                "Inspect the failure evidence, reproduce the problem with "
                "a focused check, and make the smallest authorized change."
            ),
        )

        if not self.has_failed_strategy(primary):
            return primary

        alternatives = (
            (
                "Create a minimal reproduction of the failure, verify the "
                "observed behavior, then change only the responsible code path."
            ),
            (
                "Compare the failing behavior against the existing contract "
                "and nearby working implementations, then apply a minimal "
                "compatible correction."
            ),
            (
                "Instrument the affected path with existing diagnostics, "
                "identify the first incorrect state, and repair that state "
                "without broad refactoring."
            ),
        )

        for alternative in alternatives:
            if not self.has_failed_strategy(alternative):
                return alternative

        return (
            "Stop repeating previous repair approaches. Inspect the complete "
            "failure history and choose a new evidence-driven implementation "
            "that remains within the authorized coding surface."
        )
    def reject_failed_strategy(
        self,
        strategy: str | None,
    ) -> str | None:
        """Return a safe alternative when a planned strategy already failed."""

        if not strategy:
            return strategy

        if not self.has_failed_strategy(strategy):
            return strategy

        return (
            "Choose a materially different repair strategy. "
            "Do not repeat the failed strategy recorded in this session. "
            "Verify the relevant evidence first and make the smallest "
            "authorized change that addresses the failure."
        )

    def to_prompt(self) -> str:
        if not self.attempts:
            return "CODING ATTEMPT HISTORY\n\nNo previous attempts."

        lines = [
            "CODING ATTEMPT HISTORY",
            "",
        ]

        for attempt in self.attempts:
            status = "SUCCESS" if attempt.success else "FAILED"
            lines.append(
                f"Attempt {attempt.attempt}: {status}"
            )

            if attempt.failure_class:
                lines.append(
                    f"  Failure class: {attempt.failure_class}"
                )

            if attempt.error:
                lines.append(
                    f"  Error: {attempt.error[:500]}"
                )

            if attempt.strategy:
                lines.append(
                    f"  Planned strategy: {attempt.strategy}"
                )

            if attempt.recommended_action:
                lines.append(
                    f"  Recommended action: {attempt.recommended_action}"
                )

        if self.failed_strategies():
            lines.extend(
                [
                    "",
                    "Do not blindly repeat these failed strategies:",
                ]
            )
            lines.extend(
                f"- {strategy}"
                for strategy in self.failed_strategies()
            )

        return "\n".join(lines)
