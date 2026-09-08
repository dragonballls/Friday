from pathlib import Path

from plugins.builtins import friday_verification


def test_verifier_requires_a_real_source_change(tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "desktop").mkdir()
    (tmp_path / "desktop" / "package.json").write_text("{}", encoding="utf-8")

    def fake_run(command, cwd, timeout):
        if command[:3] == ["git", "status", "--short"]:
            return {"passed": True, "exit_code": 0, "output": " M README.md\n"}
        return {"passed": True, "exit_code": 0, "output": "ok"}

    monkeypatch.setattr(friday_verification, "_run", fake_run)
    result = friday_verification.VerifyCodingChangePlugin().execute(str(tmp_path))

    assert result["success"] is False
    assert result["all_gates_passed"] is False
    assert result["gates"][0]["name"] == "implementation"
    assert result["gates"][0]["passed"] is False


def test_verifier_passes_all_required_gates_for_source_change(tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "desktop").mkdir()
    (tmp_path / "desktop" / "package.json").write_text("{}", encoding="utf-8")
    changed = tmp_path / "feature.py"
    changed.write_text("VALUE = 1\n", encoding="utf-8")

    def fake_run(command, cwd, timeout):
        if command[:3] == ["git", "status", "--short"]:
            return {"passed": True, "exit_code": 0, "output": " M feature.py\n"}
        return {"passed": True, "exit_code": 0, "output": "ok"}

    monkeypatch.setattr(friday_verification, "_run", fake_run)
    result = friday_verification.VerifyCodingChangePlugin().execute(str(tmp_path))

    assert result["success"] is True
    assert result["all_gates_passed"] is True
    assert {gate["name"] for gate in result["gates"]} == {
        "implementation",
        "python_syntax",
        "backend_tests",
        "frontend_tests",
        "frontend_build",
    }


def test_verifier_fails_closed_when_backend_tests_are_missing(tmp_path, monkeypatch):
    (tmp_path / "desktop").mkdir()
    (tmp_path / "desktop" / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "feature.ts").write_text("export const value = 1;\n", encoding="utf-8")

    def fake_run(command, cwd, timeout):
        if command[:3] == ["git", "status", "--short"]:
            return {"passed": True, "exit_code": 0, "output": " M feature.ts\n"}
        return {"passed": True, "exit_code": 0, "output": "ok"}

    monkeypatch.setattr(friday_verification, "_run", fake_run)
    result = friday_verification.VerifyCodingChangePlugin().execute(str(tmp_path))

    assert result["success"] is False
    backend = next(gate for gate in result["gates"] if gate["name"] == "backend_tests")
    assert backend["passed"] is False
    assert "missing" in backend["output"].lower()


def test_git_status_parser_uses_rename_destination(tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "desktop").mkdir()
    (tmp_path / "desktop" / "package.json").write_text("{}", encoding="utf-8")
    destination = tmp_path / "renamed.py"
    destination.write_text("VALUE = 1\n", encoding="utf-8")

    def fake_run(command, cwd, timeout):
        if command[:3] == ["git", "status", "--short"]:
            return {"passed": True, "exit_code": 0, "output": "R  old.py -> renamed.py\n"}
        return {"passed": True, "exit_code": 0, "output": "ok"}

    monkeypatch.setattr(friday_verification, "_run", fake_run)
    result = friday_verification.VerifyCodingChangePlugin().execute(str(tmp_path))

    assert result["gates"][0]["passed"] is True


def test_git_status_failure_never_passes_implementation(tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "desktop").mkdir()
    (tmp_path / "desktop" / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")

    def fake_run(command, cwd, timeout):
        if command[:3] == ["git", "status", "--short"]:
            return {"passed": False, "exit_code": 128, "output": " M feature.py\n"}
        return {"passed": True, "exit_code": 0, "output": "ok"}

    monkeypatch.setattr(friday_verification, "_run", fake_run)
    result = friday_verification.VerifyCodingChangePlugin().execute(str(tmp_path))

    assert result["success"] is False
    assert result["gates"][0]["passed"] is False
