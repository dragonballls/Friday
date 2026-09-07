from types import SimpleNamespace

from coding.coding_session import CodingSessionState


def test_agent_coding_session_state_tracks_investigation_lifecycle():
    session = CodingSessionState(
        goal="Fix the coding pipeline",
        constraints=[
            "Only modify authorized coding paths.",
            "Investigate before modifying files.",
        ],
        relevant_files=["agent/core.py"],
    )

    session.set_stage("understand")
    session.add_evidence("Task supplied an explicit authorized path.")
    session.set_stage("investigate")
    session.add_evidence("Explorer inspected the authorized source.")
    session.set_stage("reproduce")
    session.add_evidence("Existing behavior was reproduced by the focused test.")
    session.set_stage("hypothesize")
    session.hypothesis = "The behavior is caused by the coding bridge."
    session.set_stage("verify")
    session.add_evidence("The bridge path was confirmed in agent/core.py.")
    session.set_stage("modify")
    session.add_change("Updated the coding bridge.")
    session.set_stage("test")
    session.add_test("Focused coding tests passed.")
    session.set_stage("review")
    session.add_test("Independent review passed.")
    session.set_stage("complete")
    session.complete("high")

    state = session.to_dict()

    assert state["goal"] == "Fix the coding pipeline"
    assert state["relevant_files"] == ["agent/core.py"]
    assert len(state["evidence"]) >= 4
    assert state["hypothesis"]
    assert state["changes"]
    assert state["tests"]
    assert state["current_stage"] == "complete"
    assert state["status"] == "completed"


def test_agent_coding_session_prompt_requires_evidence_before_modification():
    session = CodingSessionState(goal="Implement a fix")
    session.set_stage("investigate")
    session.add_evidence("Observed the existing implementation.")

    prompt = session.to_prompt()

    assert "Goal: Implement a fix" in prompt
    assert "Current stage: investigate" in prompt
    assert "Evidence:" in prompt
    assert "Observed the existing implementation." in prompt
