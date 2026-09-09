"""Fail-closed verification for Friday's coding workflow."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from plugins.base import ToolPlugin

_SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".html"}


def _run(command: list[str], cwd: Path, timeout: int) -> dict:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {"passed": False, "exit_code": -1, "output": f"Timed out after {timeout}s"}
    except OSError as exc:
        return {"passed": False, "exit_code": -1, "output": str(exc)}
    return {
        "passed": result.returncode == 0,
        "exit_code": result.returncode,
        "output": (result.stdout + result.stderr)[-12000:],
    }


class VerifyCodingChangePlugin(ToolPlugin):
    name = "verify_coding_change"
    description = (
        "Run Friday's complete coding verification gate. Requires an actual source change, "
        "then runs backend tests, frontend tests/build, and syntax checks. Fails closed and "
        "never installs dependencies or modifies source files."
    )
    category = "coding"

    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Project workspace"},
                "timeout": {
                    "type": "integer",
                    "description": "Maximum seconds per gate, capped at 300",
                },
            },
            "required": ["workspace"],
        }

    def execute(self, workspace: str, timeout: int = 180) -> dict:
        root = Path(os.path.abspath(os.path.expanduser(workspace))).resolve()
        if not root.is_dir():
            return {
                "success": False,
                "all_gates_passed": False,
                "error": f"Workspace does not exist: {workspace}",
            }
        timeout = max(1, min(int(timeout), 300))

        gates: list[dict] = []
        status = _run(["git", "status", "--short"], root, 30)
        changed = [line for line in status["output"].splitlines() if line.strip()]

        changed_paths: list[Path] = []
        for line in changed:
            path_text = line[3:].strip() if len(line) >= 3 else ""
            if not path_text:
                continue
            # Git may quote unusual paths; only use safe relative paths here.
            candidate = (root / path_text).resolve()
            if candidate != root and root in candidate.parents:
                changed_paths.append(candidate)

        source_changed = any(path.suffix.lower() in _SOURCE_SUFFIXES for path in changed_paths)
        gates.append(
            {
                "name": "implementation",
                "passed": status["passed"] and source_changed,
                "details": changed[-100:],
            }
        )

        python_files = [path for path in changed_paths if path.suffix.lower() == ".py" and path.is_file()]
        if python_files:
            python_gate = _run(
                ["python", "-m", "py_compile", *[str(path) for path in python_files]],
                root,
                timeout,
            )
            gates.append({"name": "python_syntax", **python_gate})

        tests_dir = root / "tests"
        if not tests_dir.is_dir():
            gates.append(
                {
                    "name": "backend_tests",
                    "passed": False,
                    "exit_code": -1,
                    "output": "Friday backend tests directory is missing.",
                }
            )
        else:
            test_python = root / ".venv" / "Scripts" / "python.exe"
            python_cmd = str(test_python) if test_python.is_file() else "python"
            backend_gate = _run([python_cmd, "-m", "pytest", "tests", "-q"], root, timeout)
            gates.append({"name": "backend_tests", **backend_gate})

        frontend = root / "desktop"
        package_desktop = frontend / "package.json"
        if not package_desktop.is_file():
            gates.append(
                {
                    "name": "frontend_project",
                    "passed": False,
                    "exit_code": -1,
                    "output": "Friday desktop/package.json is missing.",
                }
            )
        else:
            npm = "npm.cmd" if os.name == "nt" else "npm"
            frontend_test = _run([npm, "test"], frontend, timeout)
            gates.append({"name": "frontend_tests", **frontend_test})
            frontend_build = _run([npm, "run", "build"], frontend, timeout)
            gates.append({"name": "frontend_build", **frontend_build})

        all_passed = bool(gates) and all(gate.get("passed") for gate in gates)
        return {
            "success": all_passed,
            "all_gates_passed": all_passed,
            "gates": gates,
            "changed_files": changed,
            "message": (
                "All coding verification gates passed."
                if all_passed
                else "Coding verification failed; task must not be reported as successful."
            ),
        }
