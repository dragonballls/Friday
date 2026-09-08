from pathlib import Path

import pytest

from coding.coding_run import (
    CodingRunError,
    SafeCodingRun,
)


def test_successful_run_keeps_authorized_change(tmp_path):
    target = tmp_path / "code.py"
    target.write_text(
        "original\n",
        encoding="utf-8",
    )

    run = SafeCodingRun(
        tmp_path,
        ["code.py"],
    )

    result = run.run(
        lambda ctx: (
            target.write_text(
                "Friday change\n",
                encoding="utf-8",
            )
        )
    )

    assert result["success"] is True
    assert target.read_text(
        encoding="utf-8"
    ) == "Friday change\n"


def test_failed_run_restores_dirty_file(tmp_path):
    target = tmp_path / "code.py"

    original = (
        "# user's existing dirty work\n"
        "value = 123\n"
    )

    target.write_text(
        original,
        encoding="utf-8",
    )

    run = SafeCodingRun(
        tmp_path,
        ["code.py"],
    )

    def task(ctx):
        target.write_text(
            "Friday attempted change\n",
            encoding="utf-8",
        )
        raise RuntimeError("simulated coding failure")

    with pytest.raises(RuntimeError):
        run.run(task)

    assert target.read_text(
        encoding="utf-8"
    ) == original

    assert run.failed is True


def test_failed_run_removes_created_authorized_file(tmp_path):
    target = tmp_path / "new.py"

    run = SafeCodingRun(
        tmp_path,
        ["new.py"],
    )

    def task(ctx):
        target.write_text(
            "created by Friday\n",
            encoding="utf-8",
        )
        raise RuntimeError("test failure")

    with pytest.raises(RuntimeError):
        run.run(task)

    assert not target.exists()


def test_failed_run_restores_deleted_authorized_file(tmp_path):
    target = tmp_path / "existing.py"

    original = b"important user content\n"

    target.write_bytes(original)

    run = SafeCodingRun(
        tmp_path,
        ["existing.py"],
    )

    def task(ctx):
        target.unlink()
        raise RuntimeError("test failure")

    with pytest.raises(RuntimeError):
        run.run(task)

    assert target.exists()
    assert target.read_bytes() == original


def test_unexpected_authorization_is_blocked(tmp_path):
    allowed = tmp_path / "allowed.py"
    outside = tmp_path / "outside.py"

    allowed.write_text(
        "allowed",
        encoding="utf-8",
    )

    run = SafeCodingRun(
        tmp_path,
        ["allowed.py"],
    )

    run.start()

    with pytest.raises(CodingRunError):
        run.authorize(outside)


def test_unexpected_workspace_change_is_detected(tmp_path):
    allowed = tmp_path / "allowed.py"
    unexpected = tmp_path / "unexpected.py"

    allowed.write_text(
        "original",
        encoding="utf-8",
    )

    run = SafeCodingRun(
        tmp_path,
        ["allowed.py"],
    )

    run.start()

    allowed.write_text(
        "authorized change",
        encoding="utf-8",
    )

    unexpected.write_text(
        "unauthorized change",
        encoding="utf-8",
    )

    with pytest.raises(CodingRunError):
        run.finish()

    # Safety rule: detection does NOT silently delete an
    # unauthorized file.
    assert unexpected.exists()

    # The authorized transaction remains active because
    # finish() rejected the completion gate.
    assert run.transaction.active is True


def test_failed_run_rolls_back_authorized_change_but_not_unexpected_change(
    tmp_path,
):
    allowed = tmp_path / "allowed.py"
    unexpected = tmp_path / "unexpected.py"

    allowed.write_text(
        "user content",
        encoding="utf-8",
    )

    run = SafeCodingRun(
        tmp_path,
        ["allowed.py"],
    )

    def task(ctx):
        allowed.write_text(
            "Friday change",
            encoding="utf-8",
        )

        unexpected.write_text(
            "unexpected change",
            encoding="utf-8",
        )

        raise RuntimeError("failure")

    with pytest.raises(RuntimeError):
        run.run(task)

    assert allowed.read_text(
        encoding="utf-8"
    ) == "user content"

    # We intentionally do not delete an unauthorized file.
    assert unexpected.exists()


def test_verification_cache_artifacts_are_ignored(tmp_path):
    target = tmp_path / "code.py"
    target.write_text("original\n", encoding="utf-8")

    run = SafeCodingRun(tmp_path, ["code.py"])
    run.start()

    target.write_text("changed\n", encoding="utf-8")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "code.cpython-311.pyc").write_bytes(b"generated")

    run.finish(
        implementation_complete=True,
        test_passed=True,
        review_passed=True,
        final_verification_passed=True,
    )

    assert run.completed is True
    assert run.changed_paths() == ["code.py"]
    assert (cache / "code.cpython-311.pyc").exists()


def test_protected_path_is_rejected(tmp_path):
    startup = tmp_path / "Start-Friday.ps1"

    startup.write_text(
        "startup",
        encoding="utf-8",
    )

    with pytest.raises(Exception):
        SafeCodingRun(
            tmp_path,
            ["Start-Friday.ps1"],
        )


def test_git_directory_is_rejected(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    with pytest.raises(Exception):
        SafeCodingRun(
            tmp_path,
            [".git/config"],
        )


def test_venv_directory_is_rejected(tmp_path):
    venv = tmp_path / ".venv"
    venv.mkdir()

    with pytest.raises(Exception):
        SafeCodingRun(
            tmp_path,
            [".venv/test.py"],
        )


def test_completion_gate_rejects_failed_tests(tmp_path):
    target = tmp_path / "code.py"

    target.write_text(
        "original",
        encoding="utf-8",
    )

    run = SafeCodingRun(
        tmp_path,
        ["code.py"],
    )

    run.start()

    target.write_text(
        "change",
        encoding="utf-8",
    )

    with pytest.raises(CodingRunError):
        run.finish(
            implementation_complete=True,
            test_passed=False,
            review_passed=True,
            final_verification_passed=True,
        )

    run.fail_and_rollback()

    assert target.read_text(
        encoding="utf-8"
    ) == "original"


def test_completion_gate_rejects_failed_review(tmp_path):
    target = tmp_path / "code.py"

    target.write_text(
        "original",
        encoding="utf-8",
    )

    run = SafeCodingRun(
        tmp_path,
        ["code.py"],
    )

    run.start()

    target.write_text(
        "change",
        encoding="utf-8",
    )

    with pytest.raises(CodingRunError):
        run.finish(
            implementation_complete=True,
            test_passed=True,
            review_passed=False,
            final_verification_passed=True,
        )

    run.fail_and_rollback()

    assert target.read_text(
        encoding="utf-8"
    ) == "original"


def test_completion_gate_rejects_failed_final_verification(tmp_path):
    target = tmp_path / "code.py"

    target.write_text(
        "original",
        encoding="utf-8",
    )

    run = SafeCodingRun(
        tmp_path,
        ["code.py"],
    )

    run.start()

    target.write_text(
        "change",
        encoding="utf-8",
    )

    with pytest.raises(CodingRunError):
        run.finish(
            implementation_complete=True,
            test_passed=True,
            review_passed=True,
            final_verification_passed=False,
        )

    run.fail_and_rollback()

    assert target.read_text(
        encoding="utf-8"
    ) == "original"


def test_authorized_change_set_is_reported(tmp_path):
    one = tmp_path / "one.py"
    two = tmp_path / "two.py"

    one.write_text(
        "ONE",
        encoding="utf-8",
    )

    two.write_text(
        "TWO",
        encoding="utf-8",
    )

    run = SafeCodingRun(
        tmp_path,
        ["one.py", "two.py"],
    )

    result = run.run(
        lambda ctx: (
            one.write_text(
                "CHANGED ONE",
                encoding="utf-8",
            ),
            two.write_text(
                "CHANGED TWO",
                encoding="utf-8",
            ),
        )
    )

    assert result["success"] is True
    assert set(result["changed_paths"]) == {
        "one.py",
        "two.py",
    }


def test_transaction_id_is_available_for_recovery(tmp_path):
    target = tmp_path / "code.py"

    target.write_text(
        "original",
        encoding="utf-8",
    )

    run = SafeCodingRun(
        tmp_path,
        ["code.py"],
    )

    run.start()

    transaction_id = run.transaction_id

    assert transaction_id
    assert run.transaction.storage_root.exists()
    assert run.transaction.manifest_path.exists()

    run.fail_and_rollback()
