import json

import pytest

from coding.durable_transaction import (
    DurableCodingTransaction,
    DurableTransactionError,
)


def test_existing_dirty_file_survives_rollback(tmp_path):
    target = tmp_path / "planner.py"
    original = b"# user's existing changes\nvalue = 123\n"
    target.write_bytes(original)
    transaction = DurableCodingTransaction(tmp_path)
    transaction.begin(["planner.py"])
    target.write_bytes(b"# Friday attempted change\nvalue = 999\n")
    transaction.rollback()
    assert target.read_bytes() == original
    assert transaction.rolled_back is True


def test_snapshot_is_persisted_outside_workspace(tmp_path):
    target = tmp_path / "code.py"
    target.write_bytes(b"original bytes\n")
    transaction = DurableCodingTransaction(tmp_path)
    transaction.begin(["code.py"])
    assert transaction.storage_root.exists()
    assert transaction.manifest_path.exists()
    assert transaction.files_root.exists()
    assert tmp_path.resolve() not in transaction.storage_root.resolve().parents


def test_transaction_can_be_recovered_after_object_loss(tmp_path):
    target = tmp_path / "code.py"
    target.write_bytes(b"before crash\n")
    first = DurableCodingTransaction(tmp_path)
    first.begin(["code.py"])
    target.write_bytes(b"Friday changed it\n")
    recovered = DurableCodingTransaction.recover(tmp_path, first.transaction_id)
    recovered.rollback()
    assert target.read_bytes() == b"before crash\n"


def test_new_file_is_removed_after_recovered_rollback(tmp_path):
    transaction = DurableCodingTransaction(tmp_path)
    transaction.begin(["new.py"])
    target = tmp_path / "new.py"
    target.write_text("created by Friday", encoding="utf-8")
    recovered = DurableCodingTransaction.recover(tmp_path, transaction.transaction_id)
    recovered.rollback()
    assert not target.exists()


def test_deleted_existing_file_is_restored_after_recovery(tmp_path):
    target = tmp_path / "existing.py"
    original = b"important content\n"
    target.write_bytes(original)
    transaction = DurableCodingTransaction(tmp_path)
    transaction.begin(["existing.py"])
    target.unlink()
    recovered = DurableCodingTransaction.recover(tmp_path, transaction.transaction_id)
    recovered.rollback()
    assert target.exists()
    assert target.read_bytes() == original


def test_snapshot_hash_detects_corruption(tmp_path):
    target = tmp_path / "code.py"
    target.write_bytes(b"original\n")
    transaction = DurableCodingTransaction(tmp_path)
    transaction.begin(["code.py"])
    snapshot_files = list(transaction.files_root.glob("*.bin"))
    assert snapshot_files
    snapshot_files[0].write_bytes(b"CORRUPTED SNAPSHOT")
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
    target.write_text("startup", encoding="utf-8")
    transaction = DurableCodingTransaction(tmp_path)
    with pytest.raises(DurableTransactionError):
        transaction.begin(["Start-Friday.ps1"])


def test_git_directory_is_blocked(tmp_path):
    (tmp_path / ".git").mkdir()
    transaction = DurableCodingTransaction(tmp_path)
    with pytest.raises(DurableTransactionError):
        transaction.begin([".git/config"])


def test_venv_directory_is_blocked(tmp_path):
    (tmp_path / ".venv").mkdir()
    transaction = DurableCodingTransaction(tmp_path)
    with pytest.raises(DurableTransactionError):
        transaction.begin([".venv/test.py"])


def test_authorize_captures_file_before_change(tmp_path):
    target = tmp_path / "new.py"
    target.write_text("user version", encoding="utf-8")
    transaction = DurableCodingTransaction(tmp_path)
    transaction.begin(["safe.py"])
    transaction.authorize("new.py")
    target.write_text("Friday version", encoding="utf-8")
    transaction.rollback()
    assert target.read_text(encoding="utf-8") == "user version"


def test_multiple_files_are_recoverable(tmp_path):
    one = tmp_path / "one.py"
    two = tmp_path / "two.py"
    one.write_bytes(b"ONE")
    two.write_bytes(b"TWO")
    transaction = DurableCodingTransaction(tmp_path)
    transaction.begin(["one.py", "two.py"])
    one.write_bytes(b"CHANGED ONE")
    two.write_bytes(b"CHANGED TWO")
    recovered = DurableCodingTransaction.recover(tmp_path, transaction.transaction_id)
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


def test_manifest_rejects_non_list_snapshots(tmp_path):
    transaction = DurableCodingTransaction(tmp_path)
    transaction.storage_root.mkdir(parents=True)
    transaction.manifest_path.write_text(
        json.dumps(
            {
                "format_version": 1,
                "transaction_id": transaction.transaction_id,
                "workspace": str(tmp_path.resolve()),
                "snapshots": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(DurableTransactionError, match="snapshot manifest"):
        DurableCodingTransaction.recover(tmp_path, transaction.transaction_id)


@pytest.mark.parametrize(
    "snapshot",
    [
        "not-a-dict",
        {"relative_path": "code.py"},
        {
            "relative_path": "code.py",
            "existed": "yes",
            "is_file": True,
            "sha256": "a" * 64,
            "content_file": "00000000.bin",
        },
        {
            "relative_path": "code.py",
            "existed": True,
            "is_file": False,
            "sha256": "a" * 64,
            "content_file": "00000000.bin",
        },
        {
            "relative_path": "code.py",
            "existed": True,
            "is_file": True,
            "sha256": "not-a-hash",
            "content_file": "00000000.bin",
        },
        {
            "relative_path": "code.py",
            "existed": False,
            "is_file": False,
            "sha256": "a" * 64,
            "content_file": "00000000.bin",
        },
    ],
)
def test_manifest_rejects_malformed_snapshot_entries(tmp_path, snapshot):
    transaction = DurableCodingTransaction(tmp_path)
    transaction.storage_root.mkdir(parents=True)
    transaction.manifest_path.write_text(
        json.dumps(
            {
                "format_version": 1,
                "transaction_id": transaction.transaction_id,
                "workspace": str(tmp_path.resolve()),
                "snapshots": [snapshot],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(DurableTransactionError, match="snapshot"):
        DurableCodingTransaction.recover(tmp_path, transaction.transaction_id)
