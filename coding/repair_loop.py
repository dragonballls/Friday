from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class RepairLoopError(RuntimeError):
    """Raised when the bounded coding repair loop cannot proceed safely."""


@dataclass(frozen=True)
class RepairAttempt:
    attempt: int
    success: bool
    error: str | None = None
    repaired: bool = False


@dataclass(frozen=True)
class RepairLoopResult:
    success: bool
    attempts: tuple[RepairAttempt, ...]
    final_result: Any = None
    error: str | None = None


class BoundedRepairLoop:
    """
    Safe orchestration primitive for automatic coding repair.

    The loop deliberately does not mutate files directly, perform Git reset/clean
    operations, own coding transactions, bypass SafeExecutorAdapter, or modify
    the existing Executor. The supplied run_attempt callback owns one complete
    safe coding attempt and must roll it back before another attempt begins.
    """

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        run_attempt: Callable[[int], Any],
        repair: Callable[[int, Any], Any] | None = None,
        should_repair: Callable[[int, Any], bool] | None = None,
    ) -> None:
        if max_attempts < 1:
            raise RepairLoopError("max_attempts must be at least 1.")
        self.max_attempts = int(max_attempts)
        self.run_attempt = run_attempt
        self.repair = repair
        self.should_repair = should_repair

    @staticmethod
    def _success(result: Any) -> bool:
        if isinstance(result, dict):
            return result.get("success", False) is True
        value = getattr(result, "success", None)
        return value is True

    @staticmethod
    def _error(result: Any) -> str | None:
        if isinstance(result, dict):
            value = result.get("error")
            return None if value is None else str(value)
        value = getattr(result, "error", None)
        return None if value is None else str(value)

    def run(self) -> RepairLoopResult:
        attempts: list[RepairAttempt] = []
        last_result: Any = None
        last_error: str | None = None

        for attempt_number in range(1, self.max_attempts + 1):
            try:
                result = self.run_attempt(attempt_number)
                last_result = result

                if self._success(result):
                    attempts.append(
                        RepairAttempt(
                            attempt=attempt_number,
                            success=True,
                        )
                    )
                    return RepairLoopResult(
                        success=True,
                        attempts=tuple(attempts),
                        final_result=result,
                    )

                last_error = self._error(result) or (
                    f"Repair attempt {attempt_number} failed."
                )
                attempts.append(
                    RepairAttempt(
                        attempt=attempt_number,
                        success=False,
                        error=last_error,
                    )
                )
            except Exception as exc:
                last_error = str(exc)
                attempts.append(
                    RepairAttempt(
                        attempt=attempt_number,
                        success=False,
                        error=last_error,
                    )
                )
                last_result = None

            if attempt_number >= self.max_attempts:
                break

            allow_repair = True
            if self.should_repair is not None:
                try:
                    allow_repair = self.should_repair(
                        attempt_number,
                        last_result,
                    ) is True
                except Exception as exc:
                    last_error = f"Repair policy failed: {exc}"
                    break

            if not allow_repair or self.repair is None:
                break

            try:
                self.repair(attempt_number, last_result)
                previous = attempts[-1]
                attempts[-1] = RepairAttempt(
                    attempt=previous.attempt,
                    success=previous.success,
                    error=previous.error,
                    repaired=True,
                )
            except Exception as exc:
                last_error = f"Repair preparation failed: {exc}"
                break

        return RepairLoopResult(
            success=False,
            attempts=tuple(attempts),
            final_result=last_result,
            error=last_error,
        )


def create_repair_loop(
    *,
    max_attempts: int,
    run_attempt: Callable[[int], Any],
    repair: Callable[[int, Any], Any] | None = None,
    should_repair: Callable[[int, Any], bool] | None = None,
) -> BoundedRepairLoop:
    return BoundedRepairLoop(
        max_attempts=max_attempts,
        run_attempt=run_attempt,
        repair=repair,
        should_repair=should_repair,
    )
