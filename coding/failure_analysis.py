from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FailureAnalysis:
    """Structured diagnosis of a failed coding attempt."""

    failure_class: str
    error: str
    evidence: tuple[str, ...] = ()
    likely_cause: str = ""
    recommended_action: str = ""
    avoid: tuple[str, ...] = ()
    confidence: str = "low"

    def as_dict(self) -> dict[str, Any]:
        return {
            "failure_class": self.failure_class,
            "error": self.error,
            "evidence": list(self.evidence),
            "likely_cause": self.likely_cause,
            "recommended_action": self.recommended_action,
            "avoid": list(self.avoid),
            "confidence": self.confidence,
        }

    def to_prompt(self) -> str:
        lines = [
            "CODING FAILURE ANALYSIS",
            "",
            f"Failure class: {self.failure_class}",
            f"Error: {self.error}",
        ]

        if self.evidence:
            lines.append("Evidence:")
            lines.extend(f"- {item}" for item in self.evidence)

        if self.likely_cause:
            lines.extend(
                [
                    "",
                    f"Likely cause: {self.likely_cause}",
                ]
            )

        if self.recommended_action:
            lines.extend(
                [
                    "",
                    f"Recommended next action: {self.recommended_action}",
                ]
            )

        if self.avoid:
            lines.extend(
                [
                    "",
                    "Avoid repeating:",
                    *[f"- {item}" for item in self.avoid],
                ]
            )

        lines.extend(
            [
                "",
                f"Confidence: {self.confidence}",
                "",
                "Do not blindly repeat the previous approach. "
                "Use the evidence above to investigate the failure "
                "before making another authorized change.",
            ]
        )

        return "\n".join(lines)


class FailureAnalyzer:
    """Deterministic first-pass classifier for coding failures."""

    def analyze(
        self,
        error: str | None = None,
        *,
        result: dict[str, Any] | None = None,
        attempt: int | None = None,
        previous_strategy: str | None = None,
    ) -> FailureAnalysis:
        result = result or {}

        text_parts = [
            str(error or ""),
            str(result.get("error") or ""),
            str(result.get("stderr") or ""),
            str(result.get("stdout") or ""),
        ]

        text = "\n".join(part for part in text_parts if part).strip()
        lowered = text.lower()

        evidence: list[str] = []

        exit_code = result.get("exit_code")
        if exit_code is not None:
            evidence.append(f"exit_code={exit_code}")

        if result.get("stderr"):
            evidence.append(
                f"stderr: {str(result['stderr']).strip()[:500]}"
            )

        if result.get("stdout"):
            evidence.append(
                f"stdout: {str(result['stdout']).strip()[:500]}"
            )

        if result.get("unexpected_changes"):
            evidence.append(
                "unexpected changes: "
                + ", ".join(map(str, result["unexpected_changes"]))
            )

        if attempt is not None:
            evidence.insert(0, f"attempt={attempt}")

        failure_class = "UNKNOWN"
        likely_cause = "The available failure evidence is insufficient to determine the root cause."
        recommended_action = (
            "Inspect the failure output, affected files, and relevant tests "
            "before making another change."
        )
        confidence = "low"

        if (
            "timed out" in lowered
            or "timeout" in lowered
            or "time out" in lowered
        ):
            failure_class = "TIMEOUT"
            likely_cause = (
                "The operation exceeded its allowed execution time "
                "or became stuck."
            )
            recommended_action = (
                "Determine whether the operation is slow, blocked, "
                "or waiting indefinitely; reduce the scope or fix the "
                "blocking behavior before retrying."
            )
            confidence = "high"

        elif (
            "syntaxerror" in lowered
            or "syntax error" in lowered
        ):
            failure_class = "SYNTAX_ERROR"
            likely_cause = (
                "The modified source contains invalid Python syntax."
            )
            recommended_action = (
                "Inspect the exact syntax location and make the smallest "
                "source correction necessary."
            )
            confidence = "high"

        elif (
            "modulenotfounderror" in lowered
            or "no module named" in lowered
            or "importerror" in lowered
        ):
            failure_class = "IMPORT_ERROR"
            likely_cause = (
                "A required module cannot be imported, or an import path "
                "was changed incorrectly."
            )
            recommended_action = (
                "Inspect the failing import and existing project dependency "
                "and module structure before changing dependencies."
            )
            confidence = "high"

        elif (
            "assertionerror" in lowered
            or "failed" in lowered
            or "test_" in lowered
            or "pytest" in lowered
        ) and (
            result.get("exit_code", 0) not in (None, 0)
            or result.get("passed") is False
        ):
            failure_class = "TEST_FAILURE"
            likely_cause = (
                "The implementation does not satisfy an existing behavioral "
                "contract or regression test."
            )
            recommended_action = (
                "Inspect the failing test and its expected behavior, trace "
                "the affected code path, then make the smallest compatible fix."
            )
            confidence = "medium"

        elif (
            "ruff" in lowered
            or "lint" in lowered
            or "flake8" in lowered
        ):
            failure_class = "LINT_FAILURE"
            likely_cause = (
                "The changed source violates a configured static-analysis rule."
            )
            recommended_action = (
                "Inspect the reported rule and affected line, then make the "
                "smallest source correction without changing unrelated behavior."
            )
            confidence = "high"

        elif (
            "format" in lowered
            or "would reformat" in lowered
        ):
            failure_class = "FORMAT_FAILURE"
            likely_cause = (
                "The changed source does not satisfy the project's formatting check."
            )
            recommended_action = (
                "Apply only the required formatting correction and rerun "
                "the format check."
            )
            confidence = "high"

        elif (
            "security" in lowered
            or "blocked" in lowered
            or "protected path" in lowered
            or "permission denied" in lowered
        ):
            failure_class = "SECURITY_BLOCK"
            likely_cause = (
                "The requested operation crossed an authorization or safety boundary."
            )
            recommended_action = (
                "Do not bypass the safety boundary. Re-evaluate the plan and "
                "restrict changes to explicitly authorized paths and operations."
            )
            confidence = "high"

        elif (
            "unexpected change" in lowered
            or "unexpected changes" in lowered
            or result.get("unexpected_changes")
        ):
            failure_class = "UNEXPECTED_CHANGE"
            likely_cause = (
                "The coding attempt modified files outside the explicitly "
                "authorized coding surface."
            )
            recommended_action = (
                "Inspect which operation caused the extra mutation and "
                "restrict the implementation to the authorized paths."
            )
            confidence = "high"

        elif "review" in lowered:
            failure_class = "REVIEW_FAILURE"
            likely_cause = (
                "The implementation passed earlier gates but did not satisfy "
                "the independent review criteria."
            )
            recommended_action = (
                "Read the review findings, identify the specific defect, "
                "and correct only the relevant authorized code."
            )
            confidence = "medium"

        elif "tool" in lowered:
            failure_class = "TOOL_ERROR"
            likely_cause = (
                "A coding tool failed before the intended implementation "
                "could complete."
            )
            recommended_action = (
                "Inspect the tool error and invocation arguments, then "
                "retry with corrected tool usage rather than changing source code blindly."
            )
            confidence = "medium"

        avoid: list[str] = []

        if previous_strategy:
            avoid.append(
                f"Repeating the previous strategy: {previous_strategy}"
            )

        if failure_class == "SECURITY_BLOCK":
            avoid.append("Bypassing or weakening the safety boundary.")

        if failure_class == "UNEXPECTED_CHANGE":
            avoid.append(
                "Broad filesystem operations outside the authorized paths."
            )

        if failure_class == "TEST_FAILURE":
            avoid.append(
                "Changing tests merely to make the implementation pass."
            )

        return FailureAnalysis(
            failure_class=failure_class,
            error=text or "Unknown coding failure.",
            evidence=tuple(evidence),
            likely_cause=likely_cause,
            recommended_action=recommended_action,
            avoid=tuple(avoid),
            confidence=confidence,
        )


def analyze_failure(
    error: str | None = None,
    *,
    result: dict[str, Any] | None = None,
    attempt: int | None = None,
    previous_strategy: str | None = None,
) -> FailureAnalysis:
    return FailureAnalyzer().analyze(
        error,
        result=result,
        attempt=attempt,
        previous_strategy=previous_strategy,
    )
