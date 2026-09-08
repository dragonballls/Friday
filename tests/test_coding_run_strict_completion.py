from coding.coding_run import CodingRunError, SafeCodingRun


def test_finish_rejects_non_boolean_gate_values(tmp_path):
    target = tmp_path / "feature.py"
    target.write_text("original\n", encoding="utf-8")

    run = SafeCodingRun(tmp_path, ["feature.py"])
    run.start()
    target.write_text("changed\n", encoding="utf-8")

    try:
        run.finish(
            implementation_complete=True,
            test_passed="false",
            review_passed=True,
            final_verification_passed=True,
        )
    except CodingRunError:
        pass
    else:
        raise AssertionError("Non-boolean gate value must fail closed.")

    run.fail_and_rollback()
    assert target.read_text(encoding="utf-8") == "original\n"


def test_finish_rejects_noop_coding_run(tmp_path):
    target = tmp_path / "feature.py"
    target.write_text("unchanged\n", encoding="utf-8")

    run = SafeCodingRun(tmp_path, ["feature.py"])
    run.start()

    try:
        run.finish()
    except CodingRunError:
        pass
    else:
        raise AssertionError("A coding run with no change must not complete.")

    assert run.transaction.active is True
    run.fail_and_rollback()
