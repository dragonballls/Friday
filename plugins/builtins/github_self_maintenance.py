"""Built-in tools for Friday's guarded GitHub self-maintenance plane."""

from __future__ import annotations

from typing import Any

from core.github_self_maintenance import GitHubSelfMaintenance, GitHubSelfMaintenanceError
from plugins.base import ToolPlugin


class GitHubSelfMaintenancePlugin(ToolPlugin):
    name = "github_self_maintain"
    description = (
        "Inspect Friday's GitHub repository and, when explicitly requested, repair failed main CI "
        "by creating a guarded branch, writing approved source files, and opening a PR. Never writes main."
    )
    category = "coding"

    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "status",
                        "latest_failure",
                        "repair_plan",
                        "repair_apply",
                    ],
                    "description": "Operation to perform against Friday's GitHub repository.",
                },
                "apply": {
                    "type": "boolean",
                    "description": "For repair_plan, whether to actually create a branch, write files, and open a PR.",
                },
                "max_files": {
                    "type": "integer",
                    "description": "Maximum source files a repair may change; capped at 3.",
                },
            },
            "required": ["action"],
        }

    def execute(self, action: str, apply: bool = False, max_files: int = 3) -> dict[str, Any]:
        try:
            controller = GitHubSelfMaintenance()
            if action == "status":
                return controller.status()
            if action == "latest_failure":
                failure = controller.latest_failed_run()
                return {"success": True, "failure": failure}
            if action in {"repair_plan", "repair_apply"}:
                should_apply = bool(apply or action == "repair_apply")
                if should_apply and action == "repair_apply" and not controller.configured:
                    return {"success": False, "error": "GitHub token is not configured."}
                return controller.repair_latest_failure(apply=should_apply, max_files=max(1, min(int(max_files), 3)))
            return {"success": False, "error": f"Unknown GitHub self-maintenance action: {action}"}
        except (GitHubSelfMaintenanceError, ValueError) as exc:
            return {"success": False, "error": str(exc)}
