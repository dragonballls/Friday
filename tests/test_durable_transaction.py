from pathlib import Path

import pytest

from coding.durable_transaction import (
    DurableCodingTransaction,
    DurableTransactionError,
)


def test_existing_dirty_file_survives_rollback(tmp_path):
    target = tmp_path / "planner.py"

    original = (
        b"# user's existing changes\n"
        b"value = 123\n"
    )

    target.write_bytes(original)

    transaction = DurableCodingTransaction(tmp_path)
    transaction.begin(["planner.py"])

    target.write_bytes(
        b"# Friday attempted change\n"
        b"value = 999\n"
    )

    transaction.rollback()

    assert target.read_bytes() == original
    assert transaction.rolled_back is True


def test_snapshot_is_persisted_outside_workspace(tmp_path):
    target = tmp_path / "code.py"
    original = b"original bytes\n"

    target.write_bytes(original)

    transaction = DurableCodingTransaction(tmp_path)
    transaction.begin(["code.py"])

    assert transaction.storage_root.exists()
    assert transaction.manifest_path.exists()
    assert transaction.files_root.exists()

    # Journal must not live inside the workspace.
    assert (
        tmp_path.resolve()
        not in transaction.storage_root.resolve().parents
    )


def test_transaction_can_be_recovered_after_object_loss(tmp_path):
    target = tmp_path / "code.py"
    original = b"before crash\n"

    target.write_bytes(original)

    first = DurableCodingTransaction(tmp_path)
    first.begin(["code.py"])

    transaction_id = first.transaction_id

    target.write_bytes(b"Friday changed it\n")

    # Simulate the original Python transaction object disappearing.
    recovered = DurableCodingTransaction.recover(
        tmp_path,
        transaction_id,
    )

    recovered.rollback()

    assert target.read_bytes() == original


def test_new_file_is_removed_after_recovered_rollback(tmp_path):
    transaction = DurableCodingTransaction(tmp_path)
    transaction.begin(["new.py"])

    target = tmp_path / "new.py"
    target.write_text(
        "created by Friday",
        encoding="utf-8",
    )

    recovered = DurableCodingTransaction.recover(
        tmp_path,
        transaction.transaction_id,
    )

    recovered.rollback()

    assert not target.exists()


def test_deleted_existing_file_is_restored_after_recovery(tmp_path):
    target = tmp_path / "existing.py"
    original = b"important content\n"

    target.write_bytes(original)

    transaction = DurableCodingTransaction(tmp_path)
    transaction.begin(["existing.py"])

    transaction_id = transaction.transaction_id

    target.unlink()

    recovered = DurableCodingTransaction.recover(
        tmp_path,
        transaction_id,
    )

    recovered.rollback()

    assert target.exists()
    assert target.read_bytes() == original


def test_snapshot_hash_detects_corruption(tmp_path):
    target = tmp_path / "code.py"
    target.write_bytes(b"original\n")

    transaction = DurableCodingTransaction(tmp_path)
    transaction.begin(["code.py"])

    snapshot_files = list(
        transaction.files_root.glob("*.bin")
    )

    assert snapshot_files

    snapshot_files[0].write_bytes(
        b"CORRUPTED SNAPSHOT"
    )

    target.write_bytes(b"changed\n")

    with pytest.raises(DurableTransactionError):
        transaction.rollback()


def test_workspace_escape_is_blocked(tmp_path):
    transaction = DurableCodingTransaction(tmp_path)

    transaction.begin(["safe.py"])

    outside = tmp_path.parent / "outside.py"

    with pytest.raises(DurableTransactionError):
        transaction.authorize(outside)


def test_protected_startup_file_is_blocked(tmp_path):
    target = tmp_path / "Start-Friday.ps1"
    target.write_text(
        "startup",
        encoding="utf-8",
    )

    transaction = DurableCodingTransaction(tmp_path)

    with pytest.raises(DurableTransactionError):
        transaction.begin(["Start-Friday.ps1"])


def test_git_directory_is_blocked(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    transaction = DurableCodingTransaction(tmp_path)

    with pytest.raises(DurableTransactionError):
        transaction.begin([".git/config"])


def test_venv_directory_is_blocked(tmp_path):
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()

    transaction = DurableCodingTransaction(tmp_path)

    with pytest.raises(DurableTransactionError):
        transaction.begin([".venv/test.py"])


def test_authorize_captures_file_before_change(tmp_path):
    target = tmp_path / "new.py"
    target.write_text(
        "user version",
        encoding="utf-8",
    )

    transaction = DurableCodingTransaction(tmp_path)
    transaction.begin(["safe.py"])

    transaction.authorize("new.py")

    target.write_text(
        "Friday version",
        encoding="utf-8",
    )

    transaction.rollback()

    assert target.read_text(
        encoding="utf-8"
    ) == "user version"


def test_multiple_files_are_recoverable(tmp_path):
    one = tmp_path / "one.py"
    two = tmp_path / "two.py"

    one.write_bytes(b"ONE")
    two.write_bytes(b"TWO")

    transaction = DurableCodingTransaction(tmp_path)
    transaction.begin(["one.py", "two.py"])

    transaction_id = transaction.transaction_id

    one.write_bytes(b"CHANGED ONE")
    two.write_bytes(b"CHANGED TWO")

    recovered = DurableCodingTransaction.recover(
        tmp_path,
        transaction_id,
    )

    result = recovered.rollback()

    assert one.read_bytes() == b"ONE"
    assert two.read_bytes() == b"TWO"
    assert result["one.py"] == "restored"
    assert result["two.py"] == "restored"


def test_rollback_does_not_use_git(tmp_path):
    target = tmp_path / "code.py"
    target.write_bytes(b"original")

    transaction = DurableCodingTransaction(tmp_path)
    transaction.begin(["code.py"])

    target.write_bytes(b"changed")

    result = transaction.rollback()

    assert result["code.py"] == "restored"
    assert target.read_bytes() == b"original"