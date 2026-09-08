from __future__ import annotations

from pathlib import Path

import pytest

from coding.coding_handoff import (
    CodingHandoffError,
    CodingPlanner,
    RepositoryExplorer,
    build_coding_handoff,
)
from coding.coding_workflow import CodingWorkflow


def test_explorer_is_read_only(tmp_path):
    target = tmp_path / "example.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")

    before = target.read_bytes()

    evidence = RepositoryExplorer(tmp_path).explore(
        "inspect example.py"
    )

    assert evidence.workspace == str(tmp_path.resolve())
    assert target.read_bytes() == before


def test_explorer_returns_git_evidence():
    workspace = Path.cwd()

    evidence = RepositoryExplorer(workspace).explore(
        "inspect coding workflow"
    )

    assert evidence.workspace == str(workspace.resolve())
    assert evidence.git_head
    assert isinstance(evidence.git_status, tuple)


def test_planner_requires_explicit_paths(tmp_path):
    evidence = RepositoryExplorer(tmp_path).explore(
        "inspect project"
    )

    planner = CodingPlanner(tmp_path)

    with pytest.raises(CodingHandoffError):
        planner.create_plan(
            "test",
            evidence,
            expected_paths=[],
        )


def test_multiple_paths_survive_handoff(tmp_path):
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"

    first.write_text("A = 1\n", encoding="utf-8")
    second.write_text("B = 2\n", encoding="utf-8")

    handoff = build_coding_handoff(
        tmp_path,
        "modify two files",
        expected_paths=[
            "first.py",
            "second.py",
        ],
    )

    assert handoff.plan.expected_paths == (
        "first.py",
        "second.py",
    )


def test_workspace_escape_is_rejected(tmp_path):
    evidence = RepositoryExplorer(tmp_path).explore(
        "inspect project"
    )

    planner = CodingPlanner(tmp_path)

    with pytest.raises(CodingHandoffError):
        planner.create_plan(
            "escape",
            evidence,
            expected_paths=["../outside.py"],
        )


def test_protected_directory_is_rejected(tmp_path):
    evidence = RepositoryExplorer(tmp_path).explore(
        "inspect project"
    )

    planner = CodingPlanner(tmp_path)

    with pytest.raises(CodingHandoffError):
        planner.create_plan(
            "protected",
            evidence,
            expected_paths=[".venv/evil.py"],
        )


def test_handoff_contains_explorer_and_plan(tmp_path):
    target = tmp_path / "example.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")

    handoff = build_coding_handoff(
        tmp_path,
        "modify example",
        expected_paths=["example.py"],
        implementation_steps=["change VALUE"],
        test_paths=["tests"],
    )

    assert handoff.evidence.goal == "modify example"
    assert handoff.plan.goal == "modify example"
    assert handoff.plan.expected_paths == ("example.py",)
    assert handoff.evidence.workspace == handoff.workspace


def test_review_requirement_is_preserved(tmp_path):
    target = tmp_path / "example.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")

    handoff = build_coding_handoff(
        tmp_path,
        "modify example",
        expected_paths=["example.py"],
        review_required=True,
    )

    assert handoff.plan.review_required is True


def test_no_mutation_methods_are_exposed():
    mutation_names = {
        "write_file",
        "create_file",
        "save_file",
        "delete_file",
        "rename_file",
        "remove_file",
    }

    explorer_methods = set(dir(RepositoryExplorer))
    planner_methods = set(dir(CodingPlanner))

    assert not mutation_names.intersection(explorer_methods)
    assert not mutation_names.intersection(planner_methods)


def test_existing_coding_workflow_accepts_handoff_plan(tmp_path):
    target = tmp_path / "example.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")

    handoff = build_coding_handoff(
        tmp_path,
        "modify example",
        expected_paths=["example.py"],
    )

    events = []
    state = {"started": False, "finished": False}

    workflow = CodingWorkflow(
        tmp_path,
        handoff.plan,
        begin_transaction=lambda paths: state.update(
            started=True
        ),
        code=lambda plan: None,
        test=lambda plan: True,
        review=lambda plan: True,
        final_verify=lambda plan: True,
        finish_transaction=lambda **kwargs: state.update(
            finished=True
        ),
        rollback_transaction=lambda: None,
        changed_paths=lambda: [],
    )

    result = workflow.run()
    events.append(result)

    assert result.completed is True
    assert result.rolled_back is False
    assert state["started"] is True
    assert state["finished"] is True