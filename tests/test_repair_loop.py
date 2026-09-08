from coding.repair_loop import (
    BoundedRepairLoop,
    RepairLoopError,
)


def test_success_on_first_attempt():
    calls = []
    loop = BoundedRepairLoop(
        max_attempts=3,
        run_attempt=lambda attempt: calls.append(attempt) or {"success": True},
    )
    result = loop.run()
    assert result.success is True
    assert calls == [1]
    assert len(result.attempts) == 1
    assert result.attempts[0].success is True


def test_failed_attempt_is_repaired_then_retried():
    calls = []
    repairs = []

    def run_attempt(attempt):
        calls.append(attempt)
        if attempt == 1:
            return {"success": False, "error": "tests failed"}
        return {"success": True}

    def repair(attempt, result):
        repairs.append((attempt, result["error"]))

    loop = BoundedRepairLoop(
        max_attempts=3,
        run_attempt=run_attempt,
        repair=repair,
    )
    result = loop.run()
    assert result.success is True
    assert calls == [1, 2]
    assert repairs == [(1, "tests failed")]
    assert len(result.attempts) == 2
    assert result.attempts[0].repaired is True
    assert result.attempts[1].success is True


def test_repair_is_bounded():
    calls = []
    repairs = []
    loop = BoundedRepairLoop(
        max_attempts=3,
        run_attempt=lambda attempt: calls.append(attempt) or {
            "success": False,
            "error": "still broken",
        },
        repair=lambda attempt, result: repairs.append(attempt),
    )
    result = loop.run()
    assert result.success is False
    assert calls == [1, 2, 3]
    assert repairs == [1, 2]
    assert len(result.attempts) == 3


def test_repair_can_be_stopped():
    calls = []
    repairs = []
    loop = BoundedRepairLoop(
        max_attempts=5,
        run_attempt=lambda attempt: calls.append(attempt) or {
            "success": False,
            "error": "blocked",
        },
        repair=lambda attempt, result: repairs.append(attempt),
        should_repair=lambda attempt, result: False,
    )
    result = loop.run()
    assert result.success is False
    assert calls == [1]
    assert repairs == []


def test_missing_success_field_fails_closed():
    calls = []
    loop = BoundedRepairLoop(
        max_attempts=2,
        run_attempt=lambda attempt: calls.append(attempt) or {"error": "unknown result"},
    )
    result = loop.run()
    assert result.success is False
    assert calls == [1]


def test_string_success_value_fails_closed():
    loop = BoundedRepairLoop(
        max_attempts=2,
        run_attempt=lambda _: {"success": "true"},
    )
    result = loop.run()
    assert result.success is False


def test_string_should_repair_value_fails_closed():
    calls = []
    repairs = []
    loop = BoundedRepairLoop(
        max_attempts=3,
        run_attempt=lambda attempt: calls.append(attempt) or {
            "success": False,
            "error": "blocked",
        },
        repair=lambda attempt, result: repairs.append(attempt),
        should_repair=lambda attempt, result: "true",
    )
    result = loop.run()
    assert result.success is False
    assert calls == [1]
    assert repairs == []


def test_exception_is_contained_and_retried():
    calls = []

    def run_attempt(attempt):
        calls.append(attempt)
        if attempt == 1:
            raise RuntimeError("executor crashed")
        return {"success": True}

    loop = BoundedRepairLoop(
        max_attempts=3,
        run_attempt=run_attempt,
        repair=lambda attempt, result: None,
    )
    result = loop.run()
    assert result.success is True
    assert calls == [1, 2]
    assert result.attempts[0].success is False
    assert result.attempts[1].success is True


def test_constructor_rejects_zero_attempts():
    try:
        BoundedRepairLoop(max_attempts=0, run_attempt=lambda _: {"success": True})
    except RepairLoopError:
        return
    raise AssertionError("Expected RepairLoopError.")
