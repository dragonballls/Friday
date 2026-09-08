from pathlib import Path

import pytest

from coding.safe_transaction import (
    CodingTransactionError,
    SafeCodingTransaction,
    create_safe_transaction,
)


def test_dirty_file_is_restored_to_exact_pre_run_content(tmp_path):
    target = tmp_path / "dirty.py"

    original = (
        b"# USER'S EXISTING DIRTY CHANGE\n"
        b"value = 123\n"
    )

    target.write_bytes(original)

    transaction = SafeCodingTransaction(tmp_path)
    transaction.begin(["dirty.py"])

    target.write_bytes(
        b"# FRIDAY CHANGED THIS\n"
        b"value = 999\n"
    )

    transaction.rollback()

    assert target.read_bytes() == original
    assert transaction.verify_snapshot_state()["dirty.py"] is True


def test_new_file_is_removed_on_rollback(tmp_path):
    transaction = SafeCodingTransaction(tmp_path)

    transaction.begin(["new_file.py"])

    target = tmp_path / "new_file.py"
    target.write_text("created by Friday", encoding="utf-8")

    transaction.rollback()

    assert not target.exists()


def test_deleted_existing_file_is_restored(tmp_path):
    target = tmp_path / "existing.py"
    original = b"important user content\n"
    target.write_bytes(original)

    transaction = SafeCodingTransaction(tmp_path)
    transaction.begin(["existing.py"])

    target.unlink()

    transaction.rollback()

    assert target.exists()
    assert target.read_bytes() == original


def test_multiple_files_restore_independently(tmp_path):
    first = tmp_path / "one.py"
    second = tmp_path / "two.py"

    first_original = b"ONE\n"
    second_original = b"TWO\n"

    first.write_bytes(first_original)
    second.write_bytes(second_original)

    transaction = SafeCodingTransaction(tmp_path)
    transaction.begin(["one.py", "two.py"])

    first.write_bytes(b"CHANGED ONE\n")
    second.write_bytes(b"CHANGED TWO\n")

    transaction.rollback()

    assert first.read_bytes() == first_original
    assert second.read_bytes() == second_original


def test_case_distinct_paths_are_tracked_independently(tmp_path):
    upper = tmp_path / "Config.py"
    lower = tmp_path / "config.py"
    upper.write_text("UPPER", encoding="utf-8")
    lower.write_text("LOWER", encoding="utf-8")

    transaction = SafeCodingTransaction(tmp_path)
    transaction.begin(["Config.py", "config.py"])

    upper.write_text("CHANGED UPPER", encoding="utf-8")
    lower.write_text("CHANGED LOWER", encoding="utf-8")

    transaction.rollback()

    assert upper.read_text(encoding="utf-8") == "UPPER"
    assert lower.read_text(encoding="utf-8") == "LOWER"


def test_preexisting_dirty_file_is_not_replaced_by_git_head(tmp_path):
    target = tmp_path / "planner.py"

    # Simulates a file that was already modified before Friday starts.
    user_version = b"user's pre-run planner changes\n"
    friday_version = b"Friday's attempted planner changes\n"

    target.write_bytes(user_version)

    transaction = SafeCodingTransaction(tmp_path)
    transaction.begin(["planner.py"])

    target.write_bytes(friday_version)

    transaction.rollback()

    assert target.read_bytes() == user_version


def test_unexpected_path_cannot_be_authorized(tmp_path):
    transaction = SafeCodingTransaction(tmp_path)
    transaction.begin(["safe.py"])

    outside = tmp_path.parent / "outside.py"

    with pytest.raises(CodingTransactionError):
        transaction.authorize(outside)


def test_protected_path_is_blocked(tmp_path):
    (tmp_path / "Start-Friday.ps1").write_text(
        "existing startup configuration",
        encoding="utf-8",
    )

    transaction = SafeCodingTransaction(tmp_path)

    with pytest.raises(CodingTransactionError):
        transaction.begin(["Start-Friday.ps1"])


def test_git_directory_is_blocked(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    transaction = SafeCodingTransaction(tmp_path)

    with pytest.raises(CodingTransactionError):
        transaction.begin([".git/config"])


def test_venv_directory_is_blocked(tmp_path):
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()

    transaction = SafeCodingTransaction(tmp_path)

    with pytest.raises(CodingTransactionError):
        transaction.begin([".venv/test.py"])


def test_transaction_detects_changes_before_rollback(tmp_path):
    target = tmp_path / "code.py"
    target.write_text("before\n", encoding="utf-8")

    transaction = create_safe_transaction(
        tmp_path,
        ["code.py"],
    )

    target.write_text("after\n", encoding="utf-8")

    assert transaction.changed_from_snapshot() == ["code.py"]

    transaction.rollback()

    assert transaction.changed_from_snapshot() == []


def test_rollback_refuses_to_delete_created_directory(tmp_path):
    transaction = SafeCodingTransaction(tmp_path)
    transaction.begin(["new_dir"])

    created = tmp_path / "new_dir"
    created.mkdir()

    with pytest.raises(CodingTransactionError):
        transaction.rollback()


def test_no_git_commands_are_required_for_rollback(tmp_path):
    target = tmp_path / "code.py"
    target.write_text("original\n", encoding="utf-8")

    transaction = SafeCodingTransaction(tmp_path)
    transaction.begin(["code.py"])

    target.write_text("changed\n", encoding="utf-8")

    # The rollback is purely filesystem-based.
    result = transaction.rollback()

    assert result["code.py"] == "restored"
    assert target.read_text(encoding="utf-8") == "original\n"