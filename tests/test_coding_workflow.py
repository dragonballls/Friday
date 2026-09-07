from pathlib import Path

import pytest

from coding.coding_workflow import (
    CodingPlan,
    CodingWorkflow,
    CodingWorkflowError,
    CodingWorkflowState,
)


def _workflow(tmp_path, plan, *, test=True, review=True, final=True):
    events = []
    changed = ["feature.py"]

    def begin(paths):
        events.append(("begin", tuple(paths)))

    def code(current_plan):
        events.append(("code", current_plan.expected_paths))

    def run_test(current_plan):
        events.append(("test", current_plan.expected_paths))
        return test

    def run_review(current_plan):
        events.append(("review", current_plan.expected_paths))
        return review

    def run_final(current_plan):
        events.append(("final", current_plan.expected_paths))
        return final

    def finish_transaction(**kwargs):
        events.append(("finish", kwargs))

    def rollback():
        events.append(("rollback", None))

    def changed_paths():
        return changed

    workflow = CodingWorkflow(
        tmp_path,
        plan,
        begin_transaction=begin,
        code=code,
        test=run_test,
        review=run_review,
        final_verify=run_final,
        finish_transaction=finish_transaction,
        rollback_transaction=rollback,
        changed_paths=changed_paths,
    )

    return workflow, events


def test_plan_requires_explicit_paths():
    with pytest.raises(CodingWorkflowError):
        CodingPlan(goal="fix bug", expected_paths=())


def test_plan_deduplicates_paths():
    plan = CodingPlan(
        goal="fix bug",
        expected_paths=("a.py", "a.py", "b.py"),
    )

    assert plan.expected_paths == ("a.py", "b.py")


def test_successful_workflow_reaches_completion(tmp_path):
    plan = CodingPlan(
        goal="implement feature",
        expected_paths=("feature.py",),
    )

    workflow, events = _workflow(tmp_path, plan)

    result = workflow.run()

    assert result.completed is True
    assert result.rolled_back is False
    assert result.state is CodingWorkflowState.COMPLETED
    assert result.changed_paths == ["feature.py"]
    assert ("rollback", None) not in events


def test_failed_tests_roll_back(tmp_path):
    plan = CodingPlan(
        goal="implement feature",
        expected_paths=("feature.py",),
    )

    workflow, events = _workflow(
        tmp_path,
        plan,
        test=False,
    )

    result = workflow.run()

    assert result.completed is False
    assert result.rolled_back is True
    assert result.state is CodingWorkflowState.ROLLED_BACK
    assert result.tests_ok is False
    assert ("rollback", None) in events
    assert not any(event[0] == "review" for event in events)


def test_failed_review_rolls_back(tmp_path):
    plan = CodingPlan(
        goal="implement feature",
        expected_paths=("feature.py",),
    )

    workflow, events = _workflow(
        tmp_path,
        plan,
        review=False,
    )

    result = workflow.run()

    assert result.completed is False
    assert result.rolled_back is True
    assert result.state is CodingWorkflowState.ROLLED_BACK
    assert result.review_ok is False
    assert ("rollback", None) in events
    assert not any(event[0] == "final" for event in events)


def test_failed_final_verification_rolls_back(tmp_path):
    plan = CodingPlan(
        goal="implement feature",
        expected_paths=("feature.py",),
    )

    workflow, events = _workflow(
        tmp_path,
        plan,
        final=False,
    )

    result = workflow.run()

    assert result.completed is False
    assert result.rolled_back is True
    assert result.state is CodingWorkflowState.ROLLED_BACK
    assert result.final_verification_ok is False
    assert ("rollback", None) in events


def test_exception_rolls_back(tmp_path):
    plan = CodingPlan(
        goal="implement feature",
        expected_paths=("feature.py",),
    )

    events = []

    def explode(_):
        events.append(("code", None))
        raise RuntimeError("coder crashed")

    workflow = CodingWorkflow(
        tmp_path,
        plan,
        begin_transaction=lambda paths: events.append(("begin", tuple(paths))),
        code=explode,
        test=lambda _: True,
        review=lambda _: True,
        final_verify=lambda _: True,
        finish_transaction=lambda **_: events.append(("finish", None)),
        rollback_transaction=lambda: events.append(("rollback", None)),
        changed_paths=lambda: [],
    )

    result = workflow.run()

    assert result.completed is False
    assert result.rolled_back is True
    assert result.state is CodingWorkflowState.ROLLED_BACK
    assert "coder crashed" in result.error
    assert ("rollback", None) in events
    assert not any(event[0] == "finish" for event in events)


def test_workspace_escape_is_rejected(tmp_path):
    outside = tmp_path.parent / "outside.py"

    plan = CodingPlan(
        goal="bad path",
        expected_paths=(str(outside),),
    )

    workflow, events = _workflow(tmp_path, plan)

    result = workflow.run()

    assert result.completed is False
    assert result.rolled_back is True
    assert result.state is CodingWorkflowState.ROLLED_BACK
    assert "escapes workspace" in result.error
    assert ("begin", (str(outside),)) not in events


def test_protected_directory_is_rejected(tmp_path):
    plan = CodingPlan(
        goal="bad path",
        expected_paths=(".git/config",),
    )

    workflow, events = _workflow(tmp_path, plan)

    result = workflow.run()

    assert result.completed is False
    assert result.rolled_back is True
    assert result.state is CodingWorkflowState.ROLLED_BACK
    assert "protected directory" in result.error
    assert ("begin", (".git/config",)) not in events


def test_review_can_be_disabled_explicitly(tmp_path):
    plan = CodingPlan(
        goal="implement feature",
        expected_paths=("feature.py",),
        review_required=False,
    )

    workflow, events = _workflow(
        tmp_path,
        plan,
        review=False,
    )

    result = workflow.run()

    assert result.completed is True
    assert result.review_ok is True
    assert not any(event[0] == "review" for event in events)