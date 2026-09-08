from coding.failure_analysis import FailureAnalyzer


def test_classifies_test_failure():
    result = {
        "stdout": "tests/test_example.py::test_behavior FAILED",
        "stderr": "AssertionError: expected 2 got 1",
        "exit_code": 1,
        "passed": False,
    }

    analysis = FailureAnalyzer().analyze(
        result=result,
        attempt=2,
        previous_strategy="modified the return value directly",
    )

    assert analysis.failure_class == "TEST_FAILURE"
    assert analysis.confidence == "medium"
    assert "attempt=2" in analysis.evidence
    assert analysis.likely_cause
    assert analysis.recommended_action
    assert analysis.avoid


def test_classifies_timeout():
    analysis = FailureAnalyzer().analyze(
        "Tests timed out after 60s",
        attempt=3,
    )

    assert analysis.failure_class == "TIMEOUT"
    assert analysis.confidence == "high"


def test_classifies_import_error():
    analysis = FailureAnalyzer().analyze(
        "ModuleNotFoundError: No module named 'example'",
    )

    assert analysis.failure_class == "IMPORT_ERROR"


def test_classifies_security_block():
    analysis = FailureAnalyzer().analyze(
        "Protected path cannot be modified: core/security.py",
    )

    assert analysis.failure_class == "SECURITY_BLOCK"
    assert "safety boundary" in analysis.avoid[0].lower()


def test_classifies_unexpected_change():
    analysis = FailureAnalyzer().analyze(
        result={
            "error": "Workspace verification failed",
            "unexpected_changes": ["notes.txt"],
        }
    )

    assert analysis.failure_class == "UNEXPECTED_CHANGE"
    assert "notes.txt" in analysis.evidence[-1]


def test_prompt_contains_structured_diagnosis():
    analysis = FailureAnalyzer().analyze(
        "AssertionError: expected X got Y",
        result={
            "exit_code": 1,
            "passed": False,
        },
        attempt=2,
        previous_strategy="changed foo() directly",
    )

    prompt = analysis.to_prompt()

    assert "CODING FAILURE ANALYSIS" in prompt
    assert "TEST_FAILURE" in prompt
    assert "Recommended next action:" in prompt
    assert "Avoid repeating:" in prompt
    assert "changed foo() directly" in prompt


def test_unknown_failure_still_produces_actionable_analysis():
    analysis = FailureAnalyzer().analyze("Something went wrong")

    assert analysis.failure_class == "UNKNOWN"
    assert analysis.recommended_action
    assert analysis.error == "Something went wrong"
