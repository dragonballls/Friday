import core.live_update_lock as lock


def test_active_coding_pid_blocks_updates(monkeypatch, tmp_path):
    lock_path = tmp_path / ".jarvis_coding.lock"
    monkeypatch.setattr(lock, "LOCK_PATH", lock_path)
    lock_path.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(lock, "_pid_is_alive", lambda pid: pid == 12345)

    assert lock.coding_update_locked() is True
    assert lock_path.exists()


def test_stale_coding_pid_is_cleaned(monkeypatch, tmp_path):
    lock_path = tmp_path / ".jarvis_coding.lock"
    monkeypatch.setattr(lock, "LOCK_PATH", lock_path)
    lock_path.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(lock, "_pid_is_alive", lambda pid: False)

    assert lock.coding_update_locked() is False
    assert not lock_path.exists()
