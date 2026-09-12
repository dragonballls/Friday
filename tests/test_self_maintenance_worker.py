import threading

from scripts.self_maintenance import ContinuousSelfMaintenance


def test_worker_is_disabled_without_github_token(monkeypatch):
    monkeypatch.setenv("FRIDAY_GITHUB_AUTOFIX", "1")
    monkeypatch.delenv("FRIDAY_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    worker = ContinuousSelfMaintenance(interval=60)
    assert worker.configured is False
    assert worker.run_once()["status"] == "disabled"


def test_worker_can_stop_without_starting_thread(monkeypatch):
    monkeypatch.setenv("FRIDAY_GITHUB_AUTOFIX", "0")
    monkeypatch.delenv("FRIDAY_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    worker = ContinuousSelfMaintenance(interval=60)
    worker.stop()
    assert worker.stop_event.is_set()
    assert isinstance(worker.stop_event, threading.Event)
