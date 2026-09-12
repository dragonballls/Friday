from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


API = "https://api.github.com"


def _token() -> str | None:
    for key in ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT"):
        value = os.environ.get(key)
        if value:
            return value.strip()
    gh = shutil.which("gh")
    if gh:
        try:
            result = subprocess.run(
                [gh, "auth", "token"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            token = result.stdout.strip()
            if result.returncode == 0 and token:
                return token
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def _repo_parts(repository: str) -> tuple[str, str]:
    value = repository.strip().rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if value.startswith("https://github.com/"):
        value = value[len("https://github.com/"):]
    elif value.startswith("http://github.com/"):
        value = value[len("http://github.com/"):]
    value = value.strip("/")
    parts = value.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("repository must be owner/name or a GitHub repository URL")
    return parts[0], parts[1]


def _api(method: str, path: str, payload: dict | None = None) -> dict | list:
    token = _token()
    if not token:
        raise RuntimeError(
            "GitHub authorization is unavailable. Authenticate GitHub CLI (gh auth login) "
            "or provide GITHUB_TOKEN/GH_TOKEN before using fork/private-repository operations."
        )
    body = None
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
        "User-Agent": "Friday-GitHub-Agent",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(API + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
            message = data.get("message", raw)
        except json.JSONDecodeError:
            message = raw
        raise RuntimeError(f"GitHub API {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub network error: {exc.reason}") from exc


def github_current_user() -> dict:
    """Return the authenticated GitHub account used by Friday's repository tools."""
    data = _api("GET", "/user")
    return {"login": data.get("login"), "name": data.get("name"), "html_url": data.get("html_url")}


def github_fork_repository(repository: str, new_name: str | None = None, organization: str | None = None) -> dict:
    """Fork a GitHub repository into the authenticated user's account, optionally using a custom fork name."""
    owner, repo = _repo_parts(repository)
    payload: dict[str, str] = {}
    if new_name:
        payload["name"] = new_name
    if organization:
        payload["organization"] = organization
    data = _api("POST", f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/forks", payload or None)
    return {
        "full_name": data.get("full_name"),
        "clone_url": data.get("clone_url"),
        "html_url": data.get("html_url"),
        "default_branch": data.get("default_branch"),
        "private": data.get("private"),
    }


def github_clone_repository(repository: str, destination: str, branch: str | None = None) -> dict:
    """Clone a public or authenticated GitHub repository into an isolated local workspace."""
    owner, repo = _repo_parts(repository)
    destination_path = Path(destination).expanduser().resolve()
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists() and any(destination_path.iterdir()):
        raise RuntimeError(f"destination is not empty: {destination_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    token = _token()
    clone_url = f"https://github.com/{owner}/{repo}.git"
    if token:
        clone_url = f"https://x-access-token:{urllib.parse.quote(token, safe='')}@github.com/{owner}/{repo}.git"

    command = ["git", "clone"]
    if branch:
        command += ["--branch", branch]
    command += [clone_url, str(destination_path)]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        raise RuntimeError(f"git is unavailable: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "git clone failed").strip()[-4000:])
    return {"repository": f"{owner}/{repo}", "workspace": str(destination_path), "status": "cloned"}


def github_get_repository(repository: str) -> dict:
    """Inspect a GitHub repository's metadata without modifying it."""
    owner, repo = _repo_parts(repository)
    data = _api("GET", f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}")
    return {
        "full_name": data.get("full_name"),
        "description": data.get("description"),
        "default_branch": data.get("default_branch"),
        "private": data.get("private"),
        "fork": data.get("fork"),
        "html_url": data.get("html_url"),
        "clone_url": data.get("clone_url"),
        "archived": data.get("archived"),
    }
