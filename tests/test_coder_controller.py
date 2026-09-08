from dataclasses import dataclass
from pathlib import Path

import pytest

from coding.coding_handoff import (
    CodingHandoff,
    CodingPlan,
    ExplorerEvidence,
)
from coding.coder_controller import (
    CoderControllerError,
    RealCoderController,
)


@dataclass
class FakeExecutionResult:
    completed: bool
    transaction_id: str
    changed_paths: list[str]
    rolled_back: bool = False
    error: str | None = None


def make_handoff(tmp_path: Path) -> CodingHandoff:
    evidence = ExplorerEvidence(
        workspace=str(tmp_path),
        goal="Implement feature",
        files=("feature.py",),
        source_files=("feature.py",),
        relevant_files=("feature.py",),
        symbols=(),
        references=(),
        file_details={},
        git_head="test-head",
        git_status="",
    )

    plan = CodingPlan(
        goal="Implement feature",
        expected_paths=("feature.py",),
        implementation_steps=("Implement the requested feature.",),
        test_paths=(),
        review_required=True,
    )

    return CodingHandoff(
        goal="Implement feature",
        workspace=str(tmp_path),
        evidence=evidence,
        plan=plan,
    )


def test_successful_coder_reaches_completion(tmp_path):
    handoff = make_handoff(tmp_path)

    target = tmp_path / "feature.py"
    target.write_text("implemented\n", encoding="utf-8")

    execution = FakeExecutionResult(
        completed=True,
        transaction_id="txn-success",
        changed_paths=["feature.py"],
    )

    controller = RealCoderController(
        workspace=tmp_path,
        handoff=handoff,
        execute_coder=lambda _, *gate_callbacks: execution,
        run_tests=lambda _: True,
        run_review=lambda _: True,
        final_verify=lambda _: True,
    )

    result = controller.run()

    assert result.success is True
    assert result.tests_ok is True
    assert result.review_ok is True
    assert result.final_verification_ok is True
    assert result.transaction_id == "txn-success"
    assert result.changed_paths == ("feature.py",)


def test_failed_tests_roll_back(tmp_path):
    handoff = make_handoff(tmp_path)

    execution = FakeExecutionResult(
        completed=False,
        transaction_id="txn-tests-failed",
        changed_paths=[],
        rolled_back=True,
        error="Completion gate failed: tests failed.",
    )

    controller = RealCoderController(
        workspace=tmp_path,
        handoff=handoff,
        execute_coder=lambda _, *gate_callbacks: execution,
        run_tests=lambda _: False,
        run_review=lambda _: True,
        final_verify=lambda _: True,
    )

    with pytest.raises(CoderControllerError):
        controller.run()

    assert execution.rolled_back is True


def test_failed_review_rolls_back(tmp_path):
    handoff = make_handoff(tmp_path)

    execution = FakeExecutionResult(
        completed=False,
        transaction_id="txn-review-failed",
        changed_paths=["feature.py"],
        rolled_back=True,
        error="Coding completion gate failed: review did not pass.",
    )

    def execute(_, test_fn, review_fn, final_verify_fn):
        assert test_fn(handoff) is True
        assert review_fn(handoff) is False
        assert final_verify_fn(handoff) is True
        return execution

    controller = RealCoderController(
        workspace=tmp_path,
        handoff=handoff,
        execute_coder=execute,
        run_tests=lambda _: True,
        run_review=lambda _: False,
        final_verify=lambda _: True,
    )

    with pytest.raises(CoderControllerError):
        controller.run()

    # The executor/transaction owner reports the failed review
    # and performs rollback before the controller sees the failure.
    assert execution.transaction_id == "txn-review-failed"
    assert execution.rolled_back is True


def test_failed_final_verification_rolls_back(tmp_path):
    handoff = make_handoff(tmp_path)

    execution = FakeExecutionResult(
        completed=False,
        transaction_id="txn-final-failed",
        changed_paths=["feature.py"],
        rolled_back=True,
        error="Coding completion gate failed: final verification did not pass.",
    )

    def execute(_, test_fn, review_fn, final_verify_fn):
        assert test_fn(handoff) is True
        assert review_fn(handoff) is True
        assert final_verify_fn(handoff) is False
        return execution

    controller = RealCoderController(
        workspace=tmp_path,
        handoff=handoff,
        execute_coder=execute,
        run_tests=lambda _: True,
        run_review=lambda _: True,
        final_verify=lambda _: False,
    )

    with pytest.raises(CoderControllerError):
        controller.run()

    assert execution.transaction_id == "txn-final-failed"
    assert execution.rolled_back is True


def test_unauthorized_change_fails_closed(tmp_path):
    handoff = make_handoff(tmp_path)

    execution = FakeExecutionResult(
        completed=False,
        transaction_id="txn-unauthorized",
        changed_paths=[],
        rolled_back=True,
        error=(
            "Coding run modified paths outside the authorized "
            "coding surface: secret.py"
        ),
    )

    controller = RealCoderController(
        workspace=tmp_path,
        handoff=handoff,
        execute_coder=lambda _, *gate_callbacks: execution,
        run_tests=lambda _: True,
        run_review=lambda _: True,
        final_verify=lambda _: True,
    )

    with pytest.raises(CoderControllerError):
        controller.run()

    assert execution.rolled_back is True


def test_workspace_mismatch_is_rejected(tmp_path):
    handoff = make_handoff(tmp_path)

    other = tmp_path / "other"
    other.mkdir()

    with pytest.raises(CoderControllerError):
        RealCoderController(
            workspace=other,
            handoff=handoff,
            execute_coder=lambda _, test_fn, review_fn, final_verify_fn: FakeExecutionResult(
                completed=True,
                transaction_id="txn",
                changed_paths=[],
            ),
            run_tests=lambda _: True,
            run_review=lambda _: True,
            final_verify=lambda _: True,
        )
def test_repair_callback_can_prepare_bounded_retry(tmp_path):
    handoff = make_handoff(tmp_path)

    attempts = []
    repairs = []

    def execute(
        _,
        test_fn,
        review_fn,
        final_verify_fn,
    ):
        attempt = len(attempts) + 1
        attempts.append(attempt)

        if attempt == 1:
            return FakeExecutionResult(
                completed=False,
                transaction_id=f"txn-{attempt}",
                changed_paths=[],
                rolled_back=True,
                error="tests failed",
            )

        assert test_fn(handoff) is True
        assert review_fn(handoff) is True
        assert final_verify_fn(handoff) is True

        return FakeExecutionResult(
            completed=True,
            transaction_id=f"txn-{attempt}",
            changed_paths=["feature.py"],
        )

    controller = RealCoderController(
        workspace=tmp_path,
        handoff=handoff,
        execute_coder=execute,
        run_tests=lambda _: True,
        run_review=lambda _: True,
        final_verify=lambda _: True,
        repair_coder=lambda _, attempt, result: repairs.append(attempt),
    )

    result = controller.run()

    assert result.success is True
    assert result.transaction_id == "txn-2"
    assert attempts == [1, 2]
    assert repairs == [1]


def test_repair_without_callback_fails_closed(tmp_path):
    handoff = make_handoff(tmp_path)

    calls = []

    def execute(_, test_fn, review_fn, final_verify_fn):
        calls.append(1)

        return FakeExecutionResult(
            completed=False,
            transaction_id="txn-failed",
            changed_paths=[],
            rolled_back=True,
            error="tests failed",
        )

    controller = RealCoderController(
        workspace=tmp_path,
        handoff=handoff,
        execute_coder=execute,
        run_tests=lambda _: False,
        run_review=lambda _: True,
        final_verify=lambda _: True,
    )

    with pytest.raises(CoderControllerError):
        controller.run()

    assert calls == [1]