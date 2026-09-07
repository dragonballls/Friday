from pathlib import Path

import pytest

from coding.agent_pipeline import (
    CodingSafetyError,
    SafeCodingPipeline,
    _run_git,
)


def test_pipeline_can_checkpoint_dirty_workspace():
    root = Path(__file__).resolve().parents[1]

    pipeline = SafeCodingPipeline(root)
    checkpoint = pipeline.create_checkpoint()

    assert checkpoint.root == str(root)
    assert checkpoint.git_head
    assert isinstance(checkpoint.git_status, str)
    assert isinstance(checkpoint.tracked_diff, str)


def test_dangerous_git_reset_is_blocked():
    root = Path(__file__).resolve().parents[1]

    with pytest.raises(CodingSafetyError):
        _run_git(root, ["reset", "--hard"])


def test_dangerous_git_clean_is_blocked():
    root = Path(__file__).resolve().parents[1]

    with pytest.raises(CodingSafetyError):
        _run_git(root, ["clean", "-fd"])


def test_workspace_escape_is_blocked():
    root = Path(__file__).resolve().parents[1]

    pipeline = SafeCodingPipeline(root)

    outside = root.parent / "outside-friday-test"

    with pytest.raises(CodingSafetyError):
        pipeline.create_checkpoint([str(outside)])


def test_protected_paths_are_blocked():
    root = Path(__file__).resolve().parents[1]

    pipeline = SafeCodingPipeline(root)

    with pytest.raises(CodingSafetyError):
        pipeline.create_checkpoint(["core/security.py"])


def test_pipeline_itself_is_protected():
    root = Path(__file__).resolve().parents[1]

    pipeline = SafeCodingPipeline(root)

    with pytest.raises(CodingSafetyError):
        pipeline.create_checkpoint(["coding/agent_pipeline.py"])


def test_venv_is_protected():
    root = Path(__file__).resolve().parents[1]

    pipeline = SafeCodingPipeline(root)

    with pytest.raises(CodingSafetyError):
        pipeline.create_checkpoint([".venv"])


def test_completion_gate_fails_when_requirements_are_missing():
    root = Path(__file__).resolve().parents[1]

    pipeline = SafeCodingPipeline(root)
    checkpoint = pipeline.create_checkpoint()

    result = pipeline.completion_gate(
        checkpoint=checkpoint,
        expected_paths=[],
        tests_passed=False,
        implementation_complete=False,
        diff_reviewed=False,
        final_verification=False,
    )

    assert result["passed"] is False
    assert result["checks"]["tests_passed"] is False
    assert result["checks"]["implementation_complete"] is False


def test_completion_gate_can_pass_without_mutating_workspace():
    root = Path(__file__).resolve().parents[1]

    pipeline = SafeCodingPipeline(root)
    checkpoint = pipeline.create_checkpoint()

    result = pipeline.completion_gate(
        checkpoint=checkpoint,
        expected_paths=[],
        tests_passed=True,
        implementation_complete=True,
        diff_reviewed=True,
        final_verification=True,
    )

    assert result["passed"] is True


def test_checkpoint_does_not_modify_git_state():
    root = Path(__file__).resolve().parents[1]

    pipeline = SafeCodingPipeline(root)

    before = pipeline.git_status()
    checkpoint = pipeline.create_checkpoint()
    after = pipeline.git_status()

    assert checkpoint.git_status == before
    assert after == before