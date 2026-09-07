"""First-class, verification-oriented coding tools."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import json

from plugins.base import ToolPlugin


_PROJECT_PROCESSES: dict[str, subprocess.Popen] = {}


def _github_request(
    method: str,
    path: str,
    payload: dict | None = None,
    *,
    required_auth: bool = False,
) -> dict:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if required_auth and not token:
        return {"success": False, "error": "GITHUB_TOKEN is not configured"}
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Friday-Coding-Agent",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    request = Request(
        f"https://api.github.com{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return {"success": True, "status": response.status, "data": json.loads(raw) if raw else {}}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(detail).get("message", detail)
        except json.JSONDecodeError:
            message = detail
        return {"success": False, "status": exc.code, "error": str(message)}
    except (URLError, TimeoutError, OSError) as exc:
        return {"success": False, "error": f"GitHub request failed: {exc}"}


class GitHubSearchRepositoriesPlugin(ToolPlugin):
    name = "github_search_repositories"
    description = "Search GitHub repositories by name, topic, or description."
    category = "coding"

    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "GitHub repository search query"},
                "limit": {"type": "integer", "description": "Maximum results, capped at 20"},
            },
            "required": ["query"],
        }

    def execute(self, query: str, limit: int = 10) -> dict:
        if not query.strip():
            return {"success": False, "error": "Search query cannot be empty"}
        result = _github_request("GET", f"/search/repositories?q={quote(query)}")
        if not result["success"]:
            return result
        items = result["data"].get("items", [])[: max(1, min(int(limit), 20))]
        return {
            "success": True,
            "total_count": result["data"].get("total_count", 0),
            "repositories": [
                {
                    "full_name": item.get("full_name"),
                    "description": item.get("description"),
                    "url": item.get("html_url"),
                    "default_branch": item.get("default_branch"),
                    "stars": item.get("stargazers_count", 0),
                }
                for item in items
            ],
        }


class GitHubSearchCodePlugin(ToolPlugin):
    name = "github_search_code"
    description = "Search code across GitHub repositories using the configured GitHub account."
    category = "coding"

    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "GitHub code search query"},
                "limit": {"type": "integer", "description": "Maximum results, capped at 20"},
            },
            "required": ["query"],
        }

    def execute(self, query: str, limit: int = 10) -> dict:
        if not query.strip():
            return {"success": False, "error": "Search query cannot be empty"}
        result = _github_request(
            "GET",
            f"/search/code?q={quote(query)}",
            required_auth=True,
        )
        if not result["success"]:
            return result
        items = result["data"].get("items", [])[: max(1, min(int(limit), 20))]
        return {
            "success": True,
            "total_count": result["data"].get("total_count", 0),
            "matches": [
                {
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "repository": item.get("repository", {}).get("full_name"),
                    "url": item.get("html_url"),
                }
                for item in items
            ],
        }


class GitHubCreateRepositoryPlugin(ToolPlugin):
    name = "github_create_repository"
    description = "Create a GitHub repository for the user after explicit approval."
    category = "coding"

    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "New repository name"},
                "description": {"type": "string", "description": "Repository description"},
                "private": {"type": "boolean", "description": "Whether the repository is private"},
            },
            "required": ["name"],
        }

    def execute(self, name: str, description: str = "", private: bool = True) -> dict:
        clean_name = name.strip()
        if not clean_name or any(char in clean_name for char in "/\\:"):
            return {"success": False, "error": "Invalid repository name"}
        return _github_request(
            "POST",
            "/user/repos",
            {"name": clean_name, "description": description, "private": bool(private), "auto_init": True},
            required_auth=True,
        )


class GitHubCloneRepositoryPlugin(ToolPlugin):
    name = "github_clone_repository"
    description = "Clone a GitHub repository into a new directory inside an approved workspace."
    category = "coding"

    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "repository": {"type": "string", "description": "Repository URL or owner/name"},
                "workspace": {"type": "string", "description": "Existing destination workspace"},
                "directory": {"type": "string", "description": "New child directory name"},
            },
            "required": ["repository", "workspace", "directory"],
        }

    def execute(self, repository: str, workspace: str, directory: str) -> dict:
        root = Path(os.path.abspath(os.path.expanduser(workspace))).resolve()
        target = (root / directory).resolve()
        if not root.is_dir():
            return {"success": False, "error": "Workspace does not exist"}
        if root not in target.parents or target == root or target.exists():
            return {"success": False, "error": "Clone directory must be a new child of workspace"}
        source = repository.strip()
        if "/" in source and not source.startswith(("http://", "https://", "git@")):
            source = f"https://github.com/{source}.git"
        try:
            result = subprocess.run(
                ["git", "clone", "--", source, str(target)],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"success": False, "error": f"Unable to clone repository: {exc}"}
        return {
            "success": result.returncode == 0,
            "path": str(target) if result.returncode == 0 else None,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
            "exit_code": result.returncode,
        }


class GitCommitChangesPlugin(ToolPlugin):
    name = "git_commit_changes"
    description = "Create a Git commit for reviewed changes in an existing workspace."
    category = "coding"

    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Git workspace"},
                "message": {"type": "string", "description": "Commit message"},
            },
            "required": ["workspace", "message"],
        }

    def execute(self, workspace: str, message: str) -> dict:
        root = Path(os.path.abspath(os.path.expanduser(workspace))).resolve()
        if not root.is_dir() or not message.strip():
            return {"success": False, "error": "Workspace and non-empty commit message are required"}
        try:
            result = subprocess.run(
                ["git", "commit", "-am", message.strip()],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"success": False, "error": f"Unable to create commit: {exc}"}
        return {"success": result.returncode == 0, "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:], "exit_code": result.returncode}


class GitPushBranchPlugin(ToolPlugin):
    name = "git_push_branch"
    description = "Push a reviewed local Git branch to its configured remote."
    category = "coding"

    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Git workspace"},
                "branch": {"type": "string", "description": "Branch to push"},
                "remote": {"type": "string", "description": "Remote name, normally origin"},
            },
            "required": ["workspace", "branch"],
        }

    def execute(self, workspace: str, branch: str, remote: str = "origin") -> dict:
        root = Path(os.path.abspath(os.path.expanduser(workspace))).resolve()
        if not root.is_dir() or not branch.strip() or not remote.strip():
            return {"success": False, "error": "Workspace, branch, and remote are required"}
        if any(token in branch + remote for token in ("..", "/", "\\", " ", ";")):
            return {"success": False, "error": "Invalid branch or remote name"}
        try:
            result = subprocess.run(
                ["git", "push", remote, branch],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"success": False, "error": f"Unable to push branch: {exc}"}
        return {"success": result.returncode == 0, "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:], "exit_code": result.returncode}


class AppCodingCheckpointPlugin(ToolPlugin):
    name = "app_coding_checkpoint"
    description = (
        "Create a timestamped, restorable Git diff checkpoint and append a coding "
        "session log before changing the Friday app. Read-only with respect to source files."
    )
    category = "coding"

    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "workspace": {
                    "type": "string",
                    "description": "Friday app project directory",
                },
            },
            "required": ["workspace"],
        }

    def execute(self, workspace: str) -> dict:
        root = Path(os.path.abspath(os.path.expanduser(workspace)))
        if not root.is_dir():
            return {"success": False, "error": f"Workspace does not exist: {workspace}"}

        try:
            inside = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"success": False, "error": f"Unable to inspect Git workspace: {exc}"}
        if inside.returncode != 0:
            return {"success": False, "error": "Workspace is not inside a Git repository"}

        git_root = Path(inside.stdout.strip()).resolve()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        checkpoint_dir = git_root / ".friday" / "coding-checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        diff_path = checkpoint_dir / f"{stamp}.diff"
        log_path = git_root / ".friday" / "coding-session.log"

        try:
            diff = subprocess.run(
                ["git", "diff", "--binary", "HEAD", "--"],
                cwd=git_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                shell=False,
            )
            status = subprocess.run(
                ["git", "status", "--short", "--branch"],
                cwd=git_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                shell=False,
            )
            diff_path.write_text(diff.stdout, encoding="utf-8")
            with log_path.open("a", encoding="utf-8") as log:
                log.write(
                    f"[{stamp}] checkpoint root={git_root} "
                    f"status={status.stdout.strip()!r} diff={diff_path}\n"
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"success": False, "error": f"Unable to write coding checkpoint: {exc}"}

        return {
            "success": diff.returncode == 0 and status.returncode == 0,
            "repository": str(git_root),
            "checkpoint": str(diff_path),
            "log": str(log_path),
            "status": status.stdout.strip(),
            "restore": f"git apply {diff_path}",
        }


class RunProjectTestsPlugin(ToolPlugin):
    name = "run_project_tests"
    description = (
        "Run the project's existing test suite or a focused test path after "
        "a code change. Never installs packages or modifies source files."
    )
    category = "coding"

    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "workspace": {
                    "type": "string",
                    "description": "Project directory in which to run tests",
                },
                "test_path": {
                    "type": "string",
                    "description": "Optional existing test file or test selector",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum seconds, capped at 300",
                },
            },
            "required": ["workspace"],
        }

    def execute(
        self,
        workspace: str,
        test_path: str = "",
        timeout: int = 120,
    ) -> dict:
        root = os.path.abspath(os.path.expanduser(workspace))
        if not os.path.isdir(root):
            return {"error": f"Workspace does not exist: {workspace}"}
        if test_path and any(token in test_path for token in ("&", "|", ";", ">", "<")):
            return {"error": "Invalid test path"}

        timeout = max(1, min(int(timeout), 300))
        if os.path.exists(os.path.join(root, "pyproject.toml")):
            command = [os.path.join(root, ".venv", "Scripts", "python.exe"), "-m", "pytest", "-q"]
            if not os.path.exists(command[0]):
                command = ["python", "-m", "pytest", "-q"]
        elif os.path.exists(os.path.join(root, "package.json")):
            command = ["npm.cmd" if os.name == "nt" else "npm", "test", "--"]
        else:
            return {"error": "No supported project manifest found"}

        if test_path:
            command.append(test_path)
        try:
            result = subprocess.run(
                command,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return {"error": f"Tests timed out after {timeout}s", "exit_code": -1}
        except OSError as exc:
            return {"error": f"Unable to start tests: {exc}", "exit_code": -1}

        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout[-12000:],
            "stderr": result.stderr[-12000:],
        }


class RunProjectPlugin(ToolPlugin):
    name = "run_project"
    description = (
        "Start, stop, or inspect a project using an existing package.json script. "
        "Does not install packages or execute arbitrary shell commands."
    )
    category = "coding"

    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "workspace": {
                    "type": "string",
                    "description": "Project directory containing package.json",
                },
                "action": {
                    "type": "string",
                    "enum": ["start", "stop", "status"],
                    "description": "Lifecycle action",
                },
                "script": {
                    "type": "string",
                    "enum": ["start", "dev", "serve"],
                    "description": "Existing package.json script to run",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Seconds to wait for a short-lived process, capped at 30",
                },
            },
            "required": ["workspace", "action"],
        }

    def execute(
        self,
        workspace: str,
        action: str,
        script: str = "start",
        timeout: int = 5,
    ) -> dict:
        root = Path(os.path.abspath(os.path.expanduser(workspace))).resolve()
        if not root.is_dir():
            return {"success": False, "error": f"Workspace does not exist: {workspace}"}
        if action not in {"start", "stop", "status"}:
            return {"success": False, "error": "Action must be start, stop, or status"}

        key = str(root)
        process = _PROJECT_PROCESSES.get(key)
        if process is not None and process.poll() is not None:
            _PROJECT_PROCESSES.pop(key, None)
            process = None

        if action == "status":
            return {
                "success": True,
                "running": process is not None,
                "pid": process.pid if process is not None else None,
                "workspace": key,
            }

        if action == "stop":
            if process is None:
                return {"success": True, "running": False, "message": "Project is not running"}
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            _PROJECT_PROCESSES.pop(key, None)
            return {"success": True, "running": False, "workspace": key}

        if process is not None:
            return {
                "success": True,
                "running": True,
                "pid": process.pid,
                "workspace": key,
                "message": "Project is already running",
            }

        manifest_path = root / "package.json"
        if not manifest_path.is_file():
            return {
                "success": False,
                "error": "Only projects with an existing package.json are supported",
            }
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"success": False, "error": f"Unable to read package.json: {exc}"}

        scripts = manifest.get("scripts", {})
        if not isinstance(scripts, dict) or script not in scripts:
            available = sorted(str(name) for name in scripts) if isinstance(scripts, dict) else []
            return {
                "success": False,
                "error": f"Script '{script}' is not defined",
                "available_scripts": available,
            }

        log_dir = root / ".friday" / "project-runs"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
            log_file = log_path.open("ab")
        except OSError as exc:
            return {"success": False, "error": f"Unable to create project log: {exc}"}

        command = ["npm.cmd" if os.name == "nt" else "npm", "run", script]
        try:
            process = subprocess.Popen(
                command,
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            log_file.close()
            return {"success": False, "error": f"Unable to start project: {exc}"}

        log_file.close()
        _PROJECT_PROCESSES[key] = process
        return {
            "success": True,
            "running": True,
            "pid": process.pid,
            "workspace": key,
            "script": script,
            "log": str(log_path),
            "message": "Project started in the background",
        }


class ReviewCodeChangePlugin(ToolPlugin):
    name = "review_code_change"
    description = (
        "Review changed source files and run safe, existing project checks. "
        "Reports failures without modifying files or installing dependencies."
    )
    category = "coding"

    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Project directory"},
                "paths": {
                    "type": "array",
                    "description": "Optional relative source paths to review",
                    "items": {"type": "string"},
                },
            },
            "required": ["workspace"],
        }

    def execute(self, workspace: str, paths: list[str] | None = None) -> dict:
        root = Path(os.path.abspath(os.path.expanduser(workspace)))
        if not root.is_dir():
            return {"error": f"Workspace does not exist: {workspace}"}

        selected = []
        for raw_path in paths or []:
            candidate = (root / raw_path).resolve()
            if root != candidate and root not in candidate.parents:
                return {"error": f"Path outside workspace: {raw_path}"}
            if candidate.is_file():
                selected.append(candidate)

        if not selected:
            selected = [
                path for path in root.rglob("*")
                if path.is_file()
                and ".git" not in path.parts
                and path.suffix.lower() in {".py", ".js", ".jsx", ".ts", ".tsx"}
            ][:200]

        checks: list[dict] = []
        python_files = [str(path) for path in selected if path.suffix.lower() == ".py"]
        if python_files:
            result = subprocess.run(
                ["python", "-m", "py_compile", *python_files],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=120,
                shell=False,
            )
            checks.append({
                "name": "python_syntax",
                "passed": result.returncode == 0,
                "output": (result.stdout + result.stderr)[-6000:],
            })

        if (root / "package.json").is_file():
            npm = "npm.cmd" if os.name == "nt" else "npm"
            result = subprocess.run(
                [npm, "run", "build"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=300,
                shell=False,
            )
            checks.append({
                "name": "frontend_build",
                "passed": result.returncode == 0,
                "output": (result.stdout + result.stderr)[-6000:],
            })

        return {
            "success": bool(checks) and all(check["passed"] for check in checks),
            "files_reviewed": [str(path.relative_to(root)) for path in selected],
            "checks": checks,
        }
