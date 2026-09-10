from pathlib import Path

import pytest

from core.self_protection import SelfModificationBlocked, SelfProtectionGate, ValidationResult


def test_protected_branch_is_blocked(tmp_path: Path):
    gate = SelfProtectionGate(tmp_path)
    with pytest.raises(SelfModificationBlocked):
        gate.authorize_change("main", ["agent/core.py"])


def test_path_escape_is_blocked(tmp_path: Path):
    gate = SelfProtectionGate(tmp_path)
    with pytest.raises(SelfModificationBlocked):
        gate.authorize_change("repair/test", ["../outside.py"])


def test_failed_validation_rolls_back(tmp_path: Path):
    gate = SelfProtectionGate(tmp_path)
    rolled_back = []

    result = gate.validate_and_promote(
        "repair/test",
        ["agent/core.py"],
        validator=lambda: ValidationResult(False, ("compile",), "compile failed"),
        rollback=lambda: rolled_back.append(True),
    )

    assert not result.passed
    assert rolled_back == [True]


def test_successful_validation_does_not_roll_back(tmp_path: Path):
    gate = SelfProtectionGate(tmp_path)
    rolled_back = []

    result = gate.validate_and_promote(
        "repair/test",
        ["agent/core.py"],
        validator=lambda: ValidationResult(True, ("compile", "tests")),
        rollback=lambda: rolled_back.append(True),
    )

    assert result.passed
    assert rolled_back == []
