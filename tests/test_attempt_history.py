from coding.attempt_history import CodingAttemptHistory


def test_records_attempts():
    history = CodingAttemptHistory()

    entry = history.record(
        1,
        success=False,
        failure_class="TEST_FAILURE",
        error="AssertionError",
        strategy="changed return value",
        recommended_action="inspect failing test",
        confidence="medium",
    )

    assert entry.attempt == 1
    assert history.last == entry
    assert len(history.attempts) == 1
    assert len(history.failures) == 1


def test_detects_failed_strategy():
    history = CodingAttemptHistory()

    history.record(
        1,
        success=False,
        failure_class="TEST_FAILURE",
        strategy="change return value",
    )

    assert history.has_failed_strategy("change return value")
    assert not history.has_failed_strategy("trace caller first")


def test_prompt_contains_attempt_history():
    history = CodingAttemptHistory()

    history.record(
        1,
        success=False,
        failure_class="TEST_FAILURE",
        error="expected 2 got 1",
        strategy="change return value",
        recommended_action="inspect the failing test",
    )

    history.record(
        2,
        success=False,
        failure_class="REVIEW_FAILURE",
        error="review rejected change",
        strategy="change return value again",
    )

    prompt = history.to_prompt()

    assert "CODING ATTEMPT HISTORY" in prompt
    assert "Attempt 1: FAILED" in prompt
    assert "Attempt 2: FAILED" in prompt
    assert "TEST_FAILURE" in prompt
    assert "REVIEW_FAILURE" in prompt
    assert "change return value" in prompt
    assert "Do not blindly repeat" in prompt


def test_successful_attempt_is_not_a_failed_strategy():
    history = CodingAttemptHistory()

    history.record(
        1,
        success=True,
        strategy="correct implementation",
    )

    assert not history.has_failed_strategy("correct implementation")
    assert history.failures == ()

def test_reject_failed_strategy_returns_alternative_instruction():
    history = CodingAttemptHistory()

    failed = history.record(
        1,
        success=False,
        strategy="reuse the same implementation",
        failure_class="TEST_FAILURE",
        error="failed",
    )

    assert failed.strategy == "reuse the same implementation"
    assert history.has_failed_strategy(
        "reuse the same implementation"
    )

    rejected = history.reject_failed_strategy(
        "reuse the same implementation"
    )

    assert rejected != "reuse the same implementation"
    assert "Do not repeat" in rejected
    assert "materially different" in rejected


def test_reject_failed_strategy_allows_new_strategy():
    history = CodingAttemptHistory()

    history.record(
        1,
        success=False,
        strategy="patch the existing helper",
    )

    new_strategy = history.reject_failed_strategy(
        "replace the broken call path"
    )

    assert new_strategy == "replace the broken call path"
def test_strategy_and_recommendation_are_stored_separately():
    history = CodingAttemptHistory()

    entry = history.record(
        1,
        success=False,
        strategy="inspect the failing call path",
        recommended_action="inspect the failing test first",
    )

    assert entry.strategy == "inspect the failing call path"
    assert entry.recommended_action == "inspect the failing test first"
    assert entry.strategy != entry.recommended_action


def test_failed_strategy_is_the_planned_strategy_not_recommendation():
    history = CodingAttemptHistory()

    history.record(
        1,
        success=False,
        strategy="reuse the existing implementation",
        recommended_action="inspect the failing test",
    )

    assert history.has_failed_strategy(
        "reuse the existing implementation"
    )

    assert not history.has_failed_strategy(
        "inspect the failing test"
    )
def test_choose_repair_strategy_returns_concrete_first_strategy():
    history = CodingAttemptHistory()

    strategy = history.choose_repair_strategy(
        "TEST_FAILURE",
        "inspect the failing test first",
    )

    assert strategy
    assert "Trace the failing test" in strategy
    assert not history.has_failed_strategy(strategy)


def test_choose_repair_strategy_changes_after_failure():
    history = CodingAttemptHistory()

    first = history.choose_repair_strategy(
        "TEST_FAILURE",
        "inspect the failing test first",
    )

    history.record(
        1,
        success=False,
        failure_class="TEST_FAILURE",
        error="assertion failed",
        strategy=first,
    )

    second = history.choose_repair_strategy(
        "TEST_FAILURE",
        "inspect the failing test first",
    )

    assert second
    assert second != first
    assert not history.has_failed_strategy(second)


def test_choose_repair_strategy_uses_multiple_alternatives():
    history = CodingAttemptHistory()

    first = history.choose_repair_strategy(
        "TEST_FAILURE",
        "inspect",
    )
    history.record(1, success=False, strategy=first)

    second = history.choose_repair_strategy(
        "TEST_FAILURE",
        "inspect",
    )
    history.record(2, success=False, strategy=second)

    third = history.choose_repair_strategy(
        "TEST_FAILURE",
        "inspect",
    )

    assert first != second
    assert second != third
    assert first != third