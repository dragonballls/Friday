from core import registry
from core.security import PermissionManager, PermissionRule


def test_browser_helper_prefix_is_excluded():
    assert registry._is_tool_allowed("browse_search") is False
    assert registry._is_tool_allowed("browse_get_page_text") is False
    assert registry._is_tool_allowed("search") is True


def test_permission_rules_are_enforced():
    permissions = PermissionManager()
    permissions.add_rule(PermissionRule(tool="run_command", command_prefix="echo ", allow=False, reason="test denial"))

    result = permissions.check_tool("run_command", {"command": "echo hello"})

    assert result["allowed"] is False
    assert result["reason"] == "test denial"


def test_permission_rule_command_prefix_is_case_insensitive():
    permissions = PermissionManager()
    permissions.add_rule(PermissionRule(tool="run_command", command_prefix="git status", allow=False))

    result = permissions.check_tool("run_command", {"command": "GIT STATUS --short"})

    assert result["allowed"] is False
