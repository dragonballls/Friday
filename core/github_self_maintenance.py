"""Guarded GitHub-native self-maintenance for Friday.

This module gives Friday a small, explicit control plane over its own public
repository. It can inspect GitHub Actions failures, create an isolated branch,
read repository files, write approved files on that branch, and open a PR.

The controller never writes to ``main`` and never merges a PR. Autonomous
repair is opt-in through ``FRIDAY_GITHUB_AUTOFIX=1``; interactive tool calls
may still perform a requested repair when the caller explicitly asks Friday
to do so.
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BLOCKED_PATH_PARTS = {
    ".git",
    ".github/workflows",
    ".env",
    ".venv",
    "node_modules",
    "__pycache__",
}
_SECRET_MARKERS = (
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "ghp_",
    "github_pat_",
    "sk-proj-",
    "OPENAI_API_KEY=",
)
_ALLOWED_PREFIXES = (
    "agent/",
    "coding/",
    "config/",
    "core/",
    "desktop/src/",
    "packaging/",
    "plugins/",
    "scripts/",
    "tests/",
)


@dataclass(frozen=True)
class GitHubFile:
    path: str
    content: str
    sha: str


class GitHubSelfMaintenanceError(RuntimeError):
    """Raised when a self-maintenance operation is refused or fails."""


class GitHubSelfMaintenance:
    def __init__(self, repository: str | None = None, token: str | None = None):
        self.repository = repository or os.environ.get("FRIDAY_GITHUB_REPOSITORY", "dragonballls/Friday")
        self.token = token or os.environ.get("FRIDAY_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not _REPO_RE.fullmatch(self.repository):
            raise GitHubSelfMaintenanceError("Invalid FRIDAY_GITHUB_REPOSITORY; expected owner/name.")
        self.api_root = "https://api.github.com"

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        if not self.token:
            raise GitHubSelfMaintenanceError(
                "GitHub self-maintenance requires FRIDAY_GITHUB_TOKEN or GITHUB_TOKEN."
            )
        url = self.api_root + path
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[-2000:]
            raise GitHubSelfMaintenanceError(
                f"GitHub API {exc.code} for {method} {path}: {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise GitHubSelfMaintenanceError(f"GitHub API request failed: {exc}") from exc
        return json.loads(raw) if raw else None

    def status(self) -> dict[str, Any]:
        repo = self._request("GET", f"/repos/{self.repository}")
        runs = self._request(
            "GET",
            f"/repos/{self.repository}/actions/runs?branch=main&per_page=10",
        )
        recent = []
        for run in runs.get("workflow_runs", []):
            recent.append(
                {
                    "id": run.get("id"),
                    "name": run.get("name"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "head_sha": run.get("head_sha"),
                    "html_url": run.get("html_url"),
                }
            )
        return {
            "repository": self.repository,
            "default_branch": repo.get("default_branch"),
            "permissions": repo.get("permissions", {}),
            "recent_runs": recent,
            "autofix_enabled": os.environ.get("FRIDAY_GITHUB_AUTOFIX") == "1",
        }

    def latest_failed_run(self) -> dict[str, Any] | None:
        runs = self._request(
            "GET",
            f"/repos/{self.repository}/actions/runs?branch=main&status=failure&per_page=10",
        )
        failed = [run for run in runs.get("workflow_runs", []) if run.get("conclusion") == "failure"]
        if not failed:
            return None
        return failed[0]

    def workflow_failure_context(self, run_id: int) -> dict[str, Any]:
        jobs = self._request("GET", f"/repos/{self.repository}/actions/runs/{run_id}/jobs?per_page=100")
        failures = []
        for job in jobs.get("jobs", []):
            if job.get("conclusion") != "failure":
                continue
            job_id = job.get("id")
            log = ""
            try:
                log = str(self._request("GET", f"/repos/{self.repository}/actions/jobs/{job_id}/logs"))
            except GitHubSelfMaintenanceError as exc:
                log = f"Unable to fetch job log: {exc}"
            failures.append(
                {
                    "job_id": job_id,
                    "name": job.get("name"),
                    "html_url": job.get("html_url"),
                    "log": log[-20000:],
                }
            )
        return {"run_id": run_id, "failures": failures}

    @staticmethod
    def normalize_path(path: str) -> str:
        candidate = path.replace("\\", "/").strip().lstrip("/")
        pure = PurePosixPath(candidate)
        if not candidate or candidate.startswith("../") or ".." in pure.parts:
            raise GitHubSelfMaintenanceError(f"Path escapes repository root: {path}")
        return str(pure)

    @classmethod
    def validate_write(cls, path: str, content: str) -> str:
        normalized = cls.normalize_path(path)
        lower = normalized.lower()
        if any(lower == blocked or lower.startswith(blocked + "/") for blocked in _BLOCKED_PATH_PARTS):
            raise GitHubSelfMaintenanceError(f"Path is blocked from self-maintenance: {normalized}")
        if normalized.startswith(".github/workflows/") and os.environ.get("FRIDAY_ALLOW_WORKFLOW_EDITS") != "1":
            raise GitHubSelfMaintenanceError("Workflow edits require FRIDAY_ALLOW_WORKFLOW_EDITS=1.")
        if not normalized.startswith(_ALLOWED_PREFIXES):
            raise GitHubSelfMaintenanceError(f"Path is outside the self-maintenance allowlist: {normalized}")
        if len(content.encode("utf-8")) > 1_000_000:
            raise GitHubSelfMaintenanceError("Refusing files larger than 1 MB.")
        if any(marker in content for marker in _SECRET_MARKERS):
            raise GitHubSelfMaintenanceError("Refusing content that contains a blocked secret marker.")
        return normalized

    def main_head(self) -> str:
        ref = self._request("GET", f"/repos/{self.repository}/git/ref/heads/main")
        return str(ref["object"]["sha"])

    def create_branch(self, branch: str, base_sha: str | None = None) -> str:
        branch = self.normalize_path(branch)
        branch = branch.strip("/")
        if branch in {"main", "master"} or branch.startswith("main/"):
            raise GitHubSelfMaintenanceError("Self-maintenance branches may not target main/master.")
        sha = base_sha or self.main_head()
        self._request(
            "POST",
            f"/repos/{self.repository}/git/refs",
            {"ref": f"refs/heads/{branch}", "sha": sha},
        )
        return branch

    def read_file(self, path: str, ref: str = "main") -> GitHubFile:
        normalized = self.normalize_path(path)
        encoded = urllib.parse.quote(normalized, safe="/")
        payload = self._request(
            "GET",
            f"/repos/{self.repository}/contents/{encoded}?ref={urllib.parse.quote(ref, safe='/:')}",
        )
        if not isinstance(payload, dict) or payload.get("type") != "file":
            raise GitHubSelfMaintenanceError(f"GitHub path is not a file: {normalized}")
        raw = base64.b64decode(payload["content"].replace("\n", "")).decode("utf-8")
        return GitHubFile(path=normalized, content=raw, sha=str(payload["sha"]))

    def write_file(self, path: str, content: str, branch: str, message: str) -> dict[str, str]:
        normalized = self.validate_write(path, content)
        branch = branch.strip("/")
        if branch in {"main", "master"} or branch.startswith("main/"):
            raise GitHubSelfMaintenanceError("Refusing to write self-maintenance changes directly to main/master.")
        try:
            current = self.read_file(normalized, ref=branch)
            sha = current.sha
            method = "PUT"
        except GitHubSelfMaintenanceError as exc:
            if "not a file" in str(exc).lower() or "404" in str(exc):
                sha = None
                method = "PUT"
            else:
                raise
        payload: dict[str, Any] = {
            "message": message[:200],
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        encoded = urllib.parse.quote(normalized, safe="/")
        result = self._request("PUT", f"/repos/{self.repository}/contents/{encoded}", payload)
        return {"path": normalized, "commit_sha": str(result["commit"]["sha"]), "blob_sha": str(result["content"]["sha"])}

    def open_pr(self, branch: str, title: str, body: str, draft: bool = False) -> dict[str, Any]:
        branch = branch.strip("/")
        if branch in {"main", "master"}:
            raise GitHubSelfMaintenanceError("A pull request head must be an isolated branch.")
        return self._request(
            "POST",
            f"/repos/{self.repository}/pulls",
            {
                "title": title[:256],
                "body": body[:10000],
                "head": branch,
                "base": "main",
                "draft": bool(draft),
                "maintainer_can_modify": True,
            },
        )

    def repair_latest_failure(self, apply: bool = False, max_files: int = 3) -> dict[str, Any]:
        failure = self.latest_failed_run()
        if failure is None:
            return {"success": True, "changed": False, "message": "No failed main-branch workflow was found."}

        context = self.workflow_failure_context(int(failure["id"]))
        prompt = self._build_repair_prompt(failure, context, max_files=max_files)
        from agent.llm import chat as llm_chat

        response = llm_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are Friday's repository repair planner. Return ONLY valid JSON with "
                        "an object containing 'summary' and 'edits'. 'edits' is an array of at most "
                        f"{max_files} objects, each with path, content, and reason. Provide complete file "
                        "contents, not diffs. Never modify workflows, secrets, binaries, or unrelated files."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            provider_name="zen_coder",
        )
        plan = self._parse_repair_plan(response)
        if not apply:
            return {"success": True, "changed": False, "mode": "plan", "failure": failure, "plan": plan}

        branch = f"friday/self-repair-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        self.create_branch(branch, base_sha=str(failure.get("head_sha") or self.main_head()))
        changed = []
        for edit in plan["edits"]:
            result = self.write_file(
                edit["path"],
                edit["content"],
                branch,
                f"Friday self-repair: {edit['path']}",
            )
            changed.append(result)
        pr = self.open_pr(
            branch,
            f"fix: Friday self-repair for {failure.get('name', 'failed workflow')}",
            (
                "Automated Friday self-repair.\n\n"
                f"Workflow: {failure.get('name')}\n"
                f"Run: {failure.get('html_url')}\n\n"
                f"Reasoning: {plan['summary']}\n\n"
                "Changes are isolated to a branch and require the normal CI/PR gates before merge."
            ),
            draft=False,
        )
        return {
            "success": True,
            "changed": True,
            "branch": branch,
            "changes": changed,
            "pr": {"number": pr.get("number"), "url": pr.get("html_url")},
            "failure": failure,
            "plan": plan,
        }

    @staticmethod
    def _build_repair_prompt(failure: dict[str, Any], context: dict[str, Any], max_files: int) -> str:
        logs = "\n\n".join(
            f"JOB {item.get('name')}\n{item.get('log', '')}" for item in context.get("failures", [])
        )[-40000:]
        paths = []
        for match in re.findall(r"(?:File|file)[ \t]+[\"']([^\"']+\.py|[^\"']+\.(?:ts|tsx|js|jsx))[\"']", logs):
            normalized = match.replace("\\", "/").lstrip("./")
            if normalized not in paths and normalized.startswith(_ALLOWED_PREFIXES):
                paths.append(normalized)
            if len(paths) >= max_files:
                break
        return (
            f"Repository: {failure.get('name')}\n"
            f"Failed run URL: {failure.get('html_url')}\n"
            f"Head SHA: {failure.get('head_sha')}\n"
            f"Likely files from the stack trace: {paths}\n\n"
            "Failure logs:\n"
            f"{logs}\n\n"
            "Produce the smallest safe correction. Preserve existing architecture and tests. "
            "Do not invent files that are not needed."
        )

    @staticmethod
    def _parse_repair_plan(response: Any) -> dict[str, Any]:
        text = response if isinstance(response, str) else str(response)
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].lstrip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GitHubSelfMaintenanceError(f"Repair planner returned invalid JSON: {exc}") from exc
        if not isinstance(parsed, dict) or not isinstance(parsed.get("edits"), list):
            raise GitHubSelfMaintenanceError("Repair planner response must contain an edits array.")
        edits = []
        for edit in parsed["edits"]:
            if not isinstance(edit, dict) or not isinstance(edit.get("path"), str) or not isinstance(edit.get("content"), str):
                raise GitHubSelfMaintenanceError("Every repair edit must include string path and content.")
            normalized = GitHubSelfMaintenance.validate_write(edit["path"], edit["content"])
            edits.append(
                {
                    "path": normalized,
                    "content": edit["content"],
                    "reason": str(edit.get("reason", ""))[:500],
                }
            )
        return {"summary": str(parsed.get("summary", ""))[:2000], "edits": edits}
