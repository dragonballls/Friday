from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CodingSessionState:
    """Structured state for one autonomous coding session."""

    goal: str
    constraints: list[str] = field(default_factory=list)
    relevant_files: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    hypothesis: str = ""
    plan: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    confidence: str = "low"
    status: str = "investigating"
    current_stage: str = "understand"
    attempt: int = 0
    checkpoint: str = ""

    def add_evidence(self, *items: str) -> None:
        for item in items:
            if item and item not in self.evidence:
                self.evidence.append(str(item))

    def add_change(self, *items: str) -> None:
        for item in items:
            if item and item not in self.changes:
                self.changes.append(str(item))

    def add_test(self, *items: str) -> None:
        for item in items:
            if item:
                self.tests.append(str(item))

    def add_failure(self, *items: str) -> None:
        for item in items:
            if item:
                self.failures.append(str(item))

    def add_lesson(self, *items: str) -> None:
        for item in items:
            if item and item not in self.lessons:
                self.lessons.append(str(item))

    def set_stage(self, stage: str) -> None:
        allowed = {
            "understand",
            "investigate",
            "reproduce",
            "hypothesize",
            "verify",
            "modify",
            "test",
            "review",
            "recover",
            "complete",
        }
        if stage not in allowed:
            raise ValueError(f"Unknown coding stage: {stage}")
        self.current_stage = stage

    def checkpoint_now(self, name: str) -> None:
        self.checkpoint = str(name)

    def begin_attempt(self) -> int:
        self.attempt += 1
        return self.attempt

    def complete(self, confidence: str = "high") -> None:
        self.status = "completed"
        self.current_stage = "complete"
        self.confidence = confidence

    def fail(self) -> None:
        self.status = "failed"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_prompt(self) -> str:
        lines = [
            "CODING SESSION STATE",
            "",
            f"Goal: {self.goal}",
            f"Status: {self.status}",
            f"Current stage: {self.current_stage}",
            f"Attempt: {self.attempt}",
            f"Confidence: {self.confidence}",
        ]

        if self.constraints:
            lines.extend(["", "Constraints:"])
            lines.extend(f"- {item}" for item in self.constraints)

        if self.relevant_files:
            lines.extend(["", "Relevant files:"])
            lines.extend(f"- {item}" for item in self.relevant_files)

        if self.evidence:
            lines.extend(["", "Evidence:"])
            lines.extend(f"- {item}" for item in self.evidence)

        if self.hypothesis:
            lines.extend(["", f"Hypothesis: {self.hypothesis}"])

        if self.plan:
            lines.extend(["", "Plan:"])
            lines.extend(f"- {item}" for item in self.plan)

        if self.changes:
            lines.extend(["", "Changes made:"])
            lines.extend(f"- {item}" for item in self.changes)

        if self.tests:
            lines.extend(["", "Tests performed:"])
            lines.extend(f"- {item}" for item in self.tests)

        if self.failures:
            lines.extend(["", "Failures:"])
            lines.extend(f"- {item}" for item in self.failures)

        if self.lessons:
            lines.extend(["", "Lessons learned:"])
            lines.extend(f"- {item}" for item in self.lessons)

        if self.checkpoint:
            lines.extend(["", f"Checkpoint: {self.checkpoint}"])

        return "\n".join(lines)
