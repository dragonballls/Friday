from coding.coding_run import SafeCodingRun


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
    assert run.changed_paths() == {"code.py"}
    assert (cache / "code.cpython-311.pyc").exists()
