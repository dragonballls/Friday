from coding.capability_broker import (
    CapabilityBroker,
    CapabilityRequest,
    Decision,
)


def test_known_read_capability_is_allowed_with_scope():
    broker = CapabilityBroker()
    decision = broker.authorize(
        CapabilityRequest(
            agent_id="coder",
            capability="filesystem.read",
            purpose="inspect source",
            scope="workspace",
        )
    )

    assert decision.decision is Decision.ALLOW
    assert decision.lease_seconds > 0


def test_unknown_capability_is_denied():
    broker = CapabilityBroker()
    decision = broker.authorize(
        CapabilityRequest(
            agent_id="coder",
            capability="system.magic_unrestricted_access",
            purpose="test",
            scope="workspace",
        )
    )

    assert decision.decision is Decision.DENY


def test_elevated_power_shell_requires_approval():
    broker = CapabilityBroker()
    decision = broker.authorize(
        CapabilityRequest(
            agent_id="windows-repair",
            capability="powershell.elevated",
            purpose="repair task",
            scope="C:/Users/smart/Friday",
            elevated=True,
        )
    )

    assert decision.decision is Decision.APPROVAL_REQUIRED


def test_github_admin_requires_approval():
    broker = CapabilityBroker()
    decision = broker.authorize(
        CapabilityRequest(
            agent_id="github-admin",
            capability="github.repository_admin",
            purpose="apply approved repository configuration",
            scope="dragonballls/Friday",
        )
    )

    assert decision.decision is Decision.APPROVAL_REQUIRED


def test_ui_design_can_be_autonomous_but_live_apply_requires_approval():
    broker = CapabilityBroker()

    design = broker.authorize(
        CapabilityRequest(
            agent_id="ui-designer",
            capability="ui.design",
            purpose="prototype a better workspace",
        )
    )
    apply = broker.authorize(
        CapabilityRequest(
            agent_id="ui-designer",
            capability="ui.apply",
            purpose="apply approved workspace design",
            scope="live-ui",
        )
    )

    assert design.decision is Decision.ALLOW
    assert apply.decision is Decision.APPROVAL_REQUIRED
