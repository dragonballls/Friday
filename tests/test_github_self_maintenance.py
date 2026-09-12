from __future__ import annotations

import os

import pytest

from core.github_self_maintenance import GitHubSelfMaintenance, GitHubSelfMaintenanceError


def test_write_allowlist_rejects_escape():
    with pytest.raises(GitHubSelfMaintenanceError):
        GitHubSelfMaintenance.validate_write("../secrets.txt", "safe")


def test_write_allowlist_rejects_unapproved_root():
    with pytest.raises(GitHubSelfMaintenanceError):
        GitHubSelfMaintenance.validate_write("README.md", "safe")


def test_write_rejects_secret_markers():
    with pytest.raises(GitHubSelfMaintenanceError):
        GitHubSelfMaintenance.validate_write("core/example.py", "token=ghp_example")


def test_workflow_changes_require_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("FRIDAY_ALLOW_WORKFLOW_EDITS", raising=False)
    with pytest.raises(GitHubSelfMaintenanceError):
        GitHubSelfMaintenance.validate_write(".github/workflows/ci.yml", "name: CI")


def test_workflow_changes_can_be_explicitly_enabled(monkeypatch):
    monkeypatch.setenv("FRIDAY_ALLOW_WORKFLOW_EDITS", "1")
    # Workflow paths remain outside the general source allowlist by design.
    with pytest.raises(GitHubSelfMaintenanceError):
        GitHubSelfMaintenance.validate_write(".github/workflows/ci.yml", "name: CI")


def test_main_branch_is_never_a_write_target():
    controller = GitHubSelfMaintenance(repository="dragonballls/Friday", token="test")
    with pytest.raises(GitHubSelfMaintenanceError):
        controller.write_file("core/example.py", "safe", "main", "test")


def test_default_repo_is_friday(monkeypatch):
    monkeypatch.delenv("FRIDAY_GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("FRIDAY_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    controller = GitHubSelfMaintenance()
    assert controller.repository == "dragonballls/Friday"
    assert controller.configured is False
