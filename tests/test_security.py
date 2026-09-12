from core.security import ApprovalRegistry, PermissionManager, PermissionRule, RateLimiter, Sandbox


class TestSandbox:
    def test_no_restriction(self):
        s = Sandbox()
        assert s.check_path("/any/path")["allowed"]

    def test_allowed_dir(self, tmp_path):
        s = Sandbox([str(tmp_path)])
        test_file = tmp_path / "test.txt"
        assert s.check_path(str(test_file))["allowed"]

    def test_denied_dir(self, tmp_path):
        s = Sandbox([str(tmp_path)])
        assert not s.check_path("/etc/passwd")["allowed"]


class TestRateLimiter:
    def test_allowed_within_limit(self):
        rl = RateLimiter(max_calls=5, window_sec=60)
        for _ in range(5):
            assert rl.check()["allowed"]

    def test_blocked_over_limit(self):
        rl = RateLimiter(max_calls=3, window_sec=60)
        for _ in range(3):
            rl.check()
        result = rl.check()
        assert not result["allowed"]
        assert "retry_after" in result


class TestPermissionManager:
    def test_default_allow(self):
        pm = PermissionManager()
        assert pm.check_tool("anything")["allowed"]

    def test_deny_tool(self):
        pm = PermissionManager()
        pm.deny_tool("dangerous")
        assert not pm.check_tool("dangerous")["allowed"]

    def test_allow_denied_tool(self):
        pm = PermissionManager()
        pm.deny_tool("temp")
        pm.allow_tool("temp")
        assert pm.check_tool("temp")["allowed"]

    def test_command_blacklist(self):
        pm = PermissionManager()
        result = pm._check_command("rm -rf /")
        assert not result["allowed"]

    def test_destructive_commands_are_hard_blocked(self):
        pm = PermissionManager()
        for command in ("rm file.txt", "mv a b", "del file.txt", "shutdown /s", "format C:"):
            result = pm._check_command(command)
            assert not result["allowed"]
            assert not result.get("requires_confirmation")

    def test_safe_command(self):
        pm = PermissionManager()
        result = pm._check_command("ls -la")
        assert result["allowed"]
        assert not result.get("requires_confirmation")

    def test_destructive_file_path_is_hard_blocked(self):
        pm = PermissionManager()
        result = pm.check_tool("delete_file", {"path": "rm -rf backup"})
        assert not result["allowed"]
        assert not result.get("requires_confirmation")

    def test_safe_operation_is_auto_allowed(self):
        pm = PermissionManager()
        result = pm.check_tool("write_file", {"path": "/tmp/notes.txt", "content": "hi"})
        assert result["allowed"]
        assert not result.get("requires_confirmation")

    def test_desktop_control_is_auto_allowed(self):
        pm = PermissionManager()
        for name in ("open_app", "focus_window", "type_text", "press_key", "click_mouse", "close_app"):
            result = pm.check_tool(name, {})
            assert result["allowed"]
            assert not result.get("requires_confirmation")

    def test_non_interactive_does_not_weaken_hard_blocks(self):
        pm = PermissionManager()
        pm.set_interactive(False)
        result = pm.check_tool("run_command", {"command": "rm file.txt"})
        assert not result["allowed"]

    def test_paid_or_billing_tools_are_hard_blocked(self):
        pm = PermissionManager()
        for name in ("set_billing", "enable_billing", "add_payment_method", "purchase", "buy_credits", "upgrade_plan", "change_plan", "create_paid_account"):
            result = pm.check_tool(name)
            assert not result["allowed"]

    def test_denied_tool_never_asked_confirmation(self):
        pm = PermissionManager()
        pm.deny_tool("delete_file")
        result = pm.check_tool("delete_file", {"path": "x"})
        assert not result["allowed"]

    def test_rule_list(self):
        pm = PermissionManager()
        pm.add_rule(PermissionRule(tool="test", reason="testing"))
        rules = pm.get_rules()
        assert len(rules) >= 1


class TestApprovalRegistry:
    def test_request_and_resolve(self):
        reg = ApprovalRegistry()
        request_id = reg.request("delete_file", {"path": "x"})
        assert reg.resolve(request_id, True)
        assert reg.wait(request_id, timeout=0.1) is True

    def test_wait_timeout_returns_false(self):
        reg = ApprovalRegistry()
        request_id = reg.request("delete_file", {"path": "x"})
        assert reg.wait(request_id, timeout=0.05) is False

    def test_resolve_unknown_returns_false(self):
        reg = ApprovalRegistry()
        assert reg.resolve("nope", True) is False

    def test_pending_lists_requests(self):
        reg = ApprovalRegistry()
        reg.request("rm_cmd")
        pending = reg.pending()
        assert len(pending) == 1
        assert pending[0]["tool"] == "rm_cmd"
