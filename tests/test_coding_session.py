from coding.coding_session import CodingSessionState


def test_session_tracks_full_coding_state():
    session = CodingSessionState(
        goal="Add a coding capability",
        constraints=["Only modify authorized files"],
        relevant_files=["agent/core.py"],
    )

    session.add_evidence("Existing executor already provides tool execution.")
    session.hypothesis = "The missing behavior belongs in the coding controller."
    session.plan.extend([
        "Inspect the controller",
        "Reproduce the failure",
        "Make the smallest change",
    ])
    session.set_stage("investigate")
    session.begin_attempt()
    session.add_change("Updated controller integration.")
    session.add_test("Focused coding tests: 35 passed.")
    session.add_failure("First implementation failed review.")
    session.add_lesson("Do not repeat the failed strategy.")
    session.checkpoint_now("after-review")
    session.complete("high")

    state = session.to_dict()

    assert state["goal"] == "Add a coding capability"
    assert state["constraints"] == ["Only modify authorized files"]
    assert state["relevant_files"] == ["agent/core.py"]
    assert state["evidence"]
    assert state["hypothesis"]
    assert len(state["plan"]) == 3
    assert state["changes"]
    assert state["tests"]
    assert state["failures"]
    assert state["lessons"]
    assert state["attempt"] == 1
    assert state["checkpoint"] == "after-review"
    assert state["status"] == "completed"
    assert state["current_stage"] == "complete"
    assert state["confidence"] == "high"


def test_session_prompt_contains_state_sections():
    session = CodingSessionState(goal="Test task")
    session.add_evidence("Observed failure")
    session.hypothesis = "Bad state transition"
    session.plan.append("Trace transition")
    session.add_change("Fixed transition")
    session.add_test("pytest passed")
    session.add_failure("Initial failure")
    session.add_lesson("Keep retry bounded")

    prompt = session.to_prompt()

    assert "CODING SESSION STATE" in prompt
    assert "Goal: Test task" in prompt
    assert "Evidence:" in prompt
    assert "Hypothesis:" in prompt
    assert "Plan:" in prompt
    assert "Changes made:" in prompt
    assert "Tests performed:" in prompt
    assert "Failures:" in prompt
    assert "Lessons learned:" in prompt


def test_session_rejects_unknown_stage():
    session = CodingSessionState(goal="Test task")

    try:
        session.set_stage("invent")
    except ValueError:
        pass
    else:
        raise AssertionError("Unknown coding stage was accepted")
