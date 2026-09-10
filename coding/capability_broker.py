"""Capability policy foundation for Friday's autonomous workers.

The broker is deliberately policy-first: agents request named capabilities,
and the broker returns a scoped decision before an executor is allowed to run.
This module does not execute PowerShell, GitHub, filesystem, or UI actions.
Execution adapters should call ``authorize`` immediately before performing
side effects and record the returned decision in Friday's activity stream.

The design supports the long-term Friday goals of background self-repair,
GitHub development, Windows tooling, visible execution, and scoped elevated
operations without handing every agent an unrestricted capability set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import monotonic
from typing import Iterable, Mapping


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


@dataclass(frozen=True)
class CapabilityRequest:
    """A single requested side-effect capability."""

    agent_id: str
    capability: str
    purpose: str
    scope: str = ""
    target: str = ""
    elevated: bool = False
    reversible: bool = True
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityDecision:
    """Policy result returned to the caller and suitable for audit logging."""

    decision: Decision
    capability: str
    agent_id: str
    reason: str
    lease_seconds: int = 0


@dataclass(frozen=True)
class CapabilityRule:
    """A simple rule for a capability family."""

    capability: str
    allow: bool = False
    approval_required: bool = False
    require_scope: bool = True
    allow_elevated: bool = False


class CapabilityBroker:
    """Authorize Friday worker capabilities without executing them.

    The broker intentionally uses an allow-list. Unknown capabilities are
    denied instead of being inferred from an agent's prompt.
    """

    DEFAULT_RULES = (
        CapabilityRule("filesystem.read", allow=True),
        CapabilityRule("filesystem.write", allow=True),
        CapabilityRule("git.read", allow=True),
        CapabilityRule("git.write", allow=True),
        CapabilityRule("tests.run", allow=True),
        CapabilityRule("powershell", allow=True),
        CapabilityRule("cmd", allow=True),
        CapabilityRule("github.read", allow=True),
        CapabilityRule("github.branch", allow=True),
        CapabilityRule("github.commit", allow=True),
        CapabilityRule("github.pull_request", allow=True),
        CapabilityRule(
            "github.fork",
            allow=True,
            require_scope=True,
        ),
        CapabilityRule(
            "github.repository_admin",
            approval_required=True,
            require_scope=True,
        ),
        CapabilityRule(
            "github.actions_admin",
            approval_required=True,
            require_scope=True,
        ),
        CapabilityRule(
            "powershell.elevated",
            approval_required=True,
            require_scope=True,
            allow_elevated=True,
        ),
        CapabilityRule(
            "cmd.elevated",
            approval_required=True,
            require_scope=True,
            allow_elevated=True,
        ),
        CapabilityRule(
            "ui.design",
            allow=True,
        ),
        CapabilityRule(
            "ui.apply",
            approval_required=True,
            require_scope=True,
        ),
    )

    def __init__(
        self,
        rules: Iterable[CapabilityRule] | None = None,
        *,
        default_lease_seconds: int = 300,
    ) -> None:
        self._rules = {
            rule.capability: rule
            for rule in (rules or self.DEFAULT_RULES)
        }
        self.default_lease_seconds = max(1, int(default_lease_seconds))

    def authorize(self, request: CapabilityRequest) -> CapabilityDecision:
        """Return an authorization decision without performing the action."""

        if not request.agent_id.strip():
            return self._deny(request, "agent_id is required")

        if not request.purpose.strip():
            return self._deny(request, "purpose is required")

        rule = self._rules.get(request.capability)
        if rule is None:
            return self._deny(request, "capability is not allow-listed")

        if rule.require_scope and not request.scope.strip():
            return self._deny(request, "an explicit scope is required")

        if request.elevated and not rule.allow_elevated:
            return self._deny(request, "elevated execution is not allowed for this capability")

        if not request.reversible and rule.approval_required is False:
            return CapabilityDecision(
                Decision.APPROVAL_REQUIRED,
                request.capability,
                request.agent_id,
                "irreversible operation requires explicit approval",
                0,
            )

        if rule.approval_required:
            return CapabilityDecision(
                Decision.APPROVAL_REQUIRED,
                request.capability,
                request.agent_id,
                "capability requires explicit approval",
                0,
            )

        if not rule.allow:
            return self._deny(request, "capability is disabled by policy")

        return CapabilityDecision(
            Decision.ALLOW,
            request.capability,
            request.agent_id,
            "allowed by capability policy",
            self.default_lease_seconds,
        )

    @staticmethod
    def _deny(request: CapabilityRequest, reason: str) -> CapabilityDecision:
        return CapabilityDecision(
            Decision.DENY,
            request.capability,
            request.agent_id,
            reason,
            0,
        )


@dataclass
class CapabilityLease:
    """Short-lived authorization for a previously approved capability."""

    decision: CapabilityDecision
    scope: str
    issued_at: float = field(default_factory=monotonic)

    @property
    def expired(self) -> bool:
        if self.decision.lease_seconds <= 0:
            return True
        return monotonic() - self.issued_at >= self.decision.lease_seconds

    def permits(self, capability: str, scope: str) -> bool:
        """Check the lease immediately before an executor performs a side effect."""

        return (
            self.decision.decision is Decision.ALLOW
            and not self.expired
            and self.decision.capability == capability
            and self.scope == scope
        )


__all__ = [
    "CapabilityBroker",
    "CapabilityDecision",
    "CapabilityLease",
    "CapabilityRequest",
    "CapabilityRule",
    "Decision",
]
