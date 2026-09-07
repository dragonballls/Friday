from __future__ import annotations

def _extract_paths_from_text(text: str) -> list[str]:
    import os, re
    if not text:
        return []
    # Match Windows drive paths, relative directory paths, and extension-based filenames
    pattern = r'(?i)(?:[A-Za-z]:[\\/])?[A-Za-z0-9_.-]+(?:[\\/][A-Za-z0-9_.-]+)*\.(?:py|js|ts|tsx|jsx|json|yaml|yml|ps1|bat|cmd|html|css|md)'
    matches = re.findall(pattern, text)
    normalized = []
    for m in matches:
        norm = os.path.normpath(m)
        if norm not in normalized:
            normalized.append(norm)
    return normalized

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from coding.ast_utils import find_references, parse_file
from coding.coding_workflow import CodingPlan
from coding.indexer import ProjectIndex


class CodingHandoffError(RuntimeError):
    """Base error for Explorer -> Planner -> Coder handoff failures."""


@dataclass(frozen=True)
class ExplorerEvidence:
    """Read-only repository evidence gathered before coding."""

    workspace: str
    goal: str
    files: tuple[str, ...] = ()
    source_files: tuple[str, ...] = ()
    relevant_files: tuple[str, ...] = ()
    symbols: tuple[str, ...] = ()
    references: dict[str, tuple[str, ...]] = field(default_factory=dict)
    file_details: dict[str, dict] = field(default_factory=dict)
    git_head: str | None = None
    git_status: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "workspace": self.workspace,
            "goal": self.goal,
            "files": list(self.files),
            "source_files": list(self.source_files),
            "relevant_files": list(self.relevant_files),
            "symbols": list(self.symbols),
            "references": {
                key: list(value)
                for key, value in self.references.items()
            },
            "file_details": dict(self.file_details),
            "git_head": self.git_head,
            "git_status": list(self.git_status),
        }


@dataclass(frozen=True)
class CodingHandoff:
    """Immutable handoff from repository exploration to coding."""

    goal: str
    workspace: str
    evidence: ExplorerEvidence
    plan: CodingPlan

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "workspace": self.workspace,
            "evidence": self.evidence.to_dict(),
            "plan": {
                "goal": self.plan.goal,
                "expected_paths": list(self.plan.expected_paths),
                "implementation_steps": list(self.plan.implementation_steps),
                "test_paths": list(self.plan.test_paths),
                "review_required": self.plan.review_required,
            },
        }


class RepositoryExplorer:
    """
    Read-only repository explorer.

    This class deliberately exposes no filesystem mutation operation.
    It may index files, parse source, inspect symbols, search references,
    and read Git metadata/status.
    """

    MAX_FILES = 100
    MAX_RELEVANT_FILES = 25
    MAX_REFERENCES_PER_SYMBOL = 20
    MAX_FILE_BYTES = 256_000

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).resolve()

        if not self.workspace.exists():
            raise CodingHandoffError(
                f"Workspace does not exist: {self.workspace}"
            )

        if not self.workspace.is_dir():
            raise CodingHandoffError(
                f"Workspace is not a directory: {self.workspace}"
            )

    def explore(self, goal: str) -> ExplorerEvidence:
        if not str(goal).strip():
            raise CodingHandoffError(
                "Explorer requires a non-empty coding goal."
            )

        index = ProjectIndex(str(self.workspace))
        index.index(force=True)

        all_files = tuple(
            entry["path"]
            for entry in index.files[: self.MAX_FILES]
        )

        source_files = tuple(
            index.get_source_files()[: self.MAX_FILES]
        )

        relevant_files = tuple(
            self._find_relevant_files(goal, index)
            [: self.MAX_RELEVANT_FILES]
        )

        file_details: dict[str, dict] = {}

        for relative_path in relevant_files:
            detail = self._inspect_file(relative_path)

            if detail is not None:
                file_details[relative_path] = detail

        symbols = self._extract_symbols(file_details)

        references: dict[str, tuple[str, ...]] = {}

        for symbol in symbols[:20]:
            matches = self._find_symbol_references(
                symbol,
                source_files,
            )

            if matches:
                references[symbol] = tuple(
                    matches[: self.MAX_REFERENCES_PER_SYMBOL]
                )

        git_head = self._git(["rev-parse", "HEAD"], required=False)
        status_text = self._git(["status", "--short"], required=False)

        git_status = tuple(
            line
            for line in status_text.splitlines()
            if line.strip()
        )

        return ExplorerEvidence(
            workspace=str(self.workspace),
            goal=str(goal),
            files=all_files,
            source_files=source_files,
            relevant_files=relevant_files,
            symbols=tuple(symbols[:20]),
            references=references,
            file_details=file_details,
            git_head=git_head.strip() or None,
            git_status=git_status[:100],
        )

    def _find_relevant_files(
        self,
        goal: str,
        index: ProjectIndex,
    ) -> list[str]:
        tokens = {
            token.lower()
            for token in (
                str(goal)
                .replace("/", " ")
                .replace("\\", " ")
                .split()
            )
            if len(token) >= 3
        }

        scored: list[tuple[int, str]] = []

        for entry in index.files:
            path = str(entry["path"])
            lowered = path.lower()
            score = 0

            for token in tokens:
                if token in lowered:
                    score += 3

            if entry.get("type") == "source":
                score += 1

            if score:
                scored.append((score, path))

        scored.sort(key=lambda item: (-item[0], item[1]))

        return [path for _, path in scored]

    def _inspect_file(
        self,
        relative_path: str,
    ) -> dict | None:
        candidate = self._resolve_workspace_path(relative_path)

        if not candidate.is_file():
            return None

        try:
            size = candidate.stat().st_size
        except OSError:
            return None

        if size > self.MAX_FILE_BYTES:
            return {
                "path": relative_path,
                "size": size,
                "too_large": True,
            }

        extension = candidate.suffix.lower()

        result: dict = {
            "path": relative_path,
            "size": size,
            "extension": extension,
        }

        if extension == ".py":
            try:
                parsed = parse_file(str(candidate))

                if isinstance(parsed, dict):
                    result["ast"] = parsed
            except Exception as exc:
                result["parse_error"] = str(exc)

        return result

    def _extract_symbols(
        self,
        file_details: dict[str, dict],
    ) -> list[str]:
        symbols: list[str] = []

        for detail in file_details.values():
            ast_data = detail.get("ast")

            if not isinstance(ast_data, dict):
                continue

            for key in ("functions", "classes"):
                values = ast_data.get(key, [])

                if not isinstance(values, list):
                    continue

                for value in values:
                    if isinstance(value, str):
                        symbols.append(value)
                    elif isinstance(value, dict):
                        name = value.get("name")

                        if isinstance(name, str) and name.strip():
                            symbols.append(name.strip())

        return list(dict.fromkeys(symbols))

    def _find_symbol_references(
        self,
        symbol: str,
        source_files: Iterable[str],
    ) -> list[str]:
        matches: list[str] = []

        for relative_path in source_files:
            candidate = self._resolve_workspace_path(relative_path)

            if not candidate.is_file():
                continue

            if candidate.suffix.lower() != ".py":
                continue

            try:
                result = find_references(
                    str(candidate),
                    symbol,
                )
            except Exception:
                continue

            if not isinstance(result, dict):
                continue

            raw_matches = (
                result.get("matches")
                or result.get("references")
                or result.get("results")
                or []
            )

            if isinstance(raw_matches, list) and raw_matches:
                matches.append(relative_path)

        return matches

    def _resolve_workspace_path(
        self,
        relative_path: str,
    ) -> Path:
        candidate = Path(relative_path)

        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.workspace / candidate).resolve()

        try:
            resolved.relative_to(self.workspace)
        except ValueError as exc:
            raise CodingHandoffError(
                f"Explorer path escaped workspace: {relative_path}"
            ) from exc

        return resolved

    def _git(
        self,
        args: list[str],
        *,
        required: bool = True,
    ) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                check=False,
            )
        except Exception as exc:
            if required:
                raise CodingHandoffError(
                    f"Git inspection failed: {exc}"
                ) from exc
            return ""

        if result.returncode != 0:
            if required:
                detail = (
                    result.stderr.strip()
                    or result.stdout.strip()
                    or f"exit code {result.returncode}"
                )
                raise CodingHandoffError(
                    f"Git inspection failed: {detail}"
                )

            return ""

        return result.stdout


class CodingPlanner:
    """
    Convert read-only Explorer evidence into an explicit CodingPlan.

    This planner does not mutate files and does not authorize mutations.
    """

    PROTECTED_DIRS = {
        ".git",
        ".venv",
        "venv",
        "env",
    }

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).resolve()

    def create_plan(
        self,
        goal: str,
        evidence: ExplorerEvidence,
        *,
        expected_paths: Iterable[str] | None = None,
        implementation_steps: Iterable[str] = (),
        test_paths: Iterable[str] = (),
        review_required: bool = True,
    ) -> CodingPlan:
        if not str(goal).strip():
            raise CodingHandoffError(
                "Coding planner requires a non-empty goal."
            )

        if evidence.workspace != str(self.workspace):
            raise CodingHandoffError(
                "Explorer evidence belongs to a different workspace."
            )

        paths = tuple(
            dict.fromkeys(
                str(path).strip()
                for path in (
                    expected_paths
                    if expected_paths is not None
                    else evidence.relevant_files
                )
                if str(path).strip()
            )
        )

        if not paths:
            raise CodingHandoffError(
                "Coding planner requires explicit expected paths."
            )

        validated_paths: list[str] = []

        for raw_path in paths:
            resolved = self._resolve_path(raw_path)

            relative = resolved.relative_to(
                self.workspace
            ).as_posix()

            validated_paths.append(relative)

        return CodingPlan(
            goal=str(goal),
            expected_paths=tuple(
                dict.fromkeys(validated_paths)
            ),
            implementation_steps=tuple(
                str(step).strip()
                for step in implementation_steps
                if str(step).strip()
            ),
            test_paths=tuple(
                str(path).strip()
                for path in test_paths
                if str(path).strip()
            ),
            review_required=bool(review_required),
        )

    def _resolve_path(
        self,
        raw_path: str,
    ) -> Path:
        candidate = Path(raw_path)

        resolved = (
            candidate.resolve()
            if candidate.is_absolute()
            else (self.workspace / candidate).resolve()
        )

        try:
            resolved.relative_to(self.workspace)
        except ValueError as exc:
            raise CodingHandoffError(
                f"Coding path escapes workspace: {raw_path}"
            ) from exc

        parts = {
            part.lower()
            for part in resolved.relative_to(
                self.workspace
            ).parts
        }

        if parts & self.PROTECTED_DIRS:
            raise CodingHandoffError(
                f"Coding path enters protected directory: {raw_path}"
            )

        return resolved


def build_coding_handoff(
    workspace: str | Path,
    goal: str,
    *,
    expected_paths: Iterable[str] | None = None,
    implementation_steps: Iterable[str] = (),
    test_paths: Iterable[str] = (),
    review_required: bool = True,
) -> CodingHandoff:
    """
    Execute the read-only Explorer -> explicit Planner handoff.

    No source mutation occurs here.
    """

    explorer = RepositoryExplorer(workspace)
    evidence = explorer.explore(goal)

    planner = CodingPlanner(workspace)

    plan = planner.create_plan(
        goal,
        evidence,
        expected_paths=expected_paths,
        implementation_steps=implementation_steps,
        test_paths=test_paths,
        review_required=review_required,
    )

    return CodingHandoff(
        goal=str(goal),
        workspace=str(Path(workspace).resolve()),
        evidence=evidence,
        plan=plan,
    )