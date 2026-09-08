from __future__ import annotations

import os

import pytest

from coding.safe_transaction import (
    CodingTransactionError,
    SafeCodingTransaction,
)


def test_multiple_files_restore_independently(tmp_path):
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first_original = b"first original\n"
    second_original = b"second original\n"
    first.write_bytes(first_original)
    second.write_bytes(second_original)

    transaction = SafeCodingTransaction(tmp_path)
    transaction.begin(["first.py", "second.py"])

    first.write_bytes(b"first changed\n")
    second.write_bytes(b"second changed\n")

    transaction.rollback()

    assert first.read_bytes() == first_original
    assert second.read_bytes() == second_original


@pytest.mark.skipif(os.name == "nt", reason="Windows filesystems are normally case-insensitive")
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
    transaction.begin(["allowed.py"])

    with pytest.raises(CodingTransactionError):
        transaction.authorize("unexpected.py")
