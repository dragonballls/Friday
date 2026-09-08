from main import _launch_ui


def test_launch_ui_builds_commands(monkeypatch):
    """--ui should spawn the API server and frontend dev server, then open the browser."""
    spawned: list[list[str]] = []
    opened: list[str] = []

    class FakeProc:
        def __init__(self, cmd):
            self._cmd = cmd
            self._polls = 0

        def poll(self):
            self._polls += 1
            return None if self._polls < 3 else 0

        def terminate(self):
            self._terminated = True

    def fake_popen(cmd, **kwargs):
        spawned.append(cmd)
        return FakeProc(cmd)

    def fake_sleep(_secs):
        pass

    def fake_open(url):
        opened.append(url)

    # The updater is independently covered; keep this launch smoke test focused
    # on the two UI child processes so its git polling cannot interfere with the
    # Popen monkeypatch used to observe those children.
    monkeypatch.setattr("main._auto_update_monitor", lambda *_args: None)
    monkeypatch.setattr("main.subprocess.Popen", fake_popen)
    monkeypatch.setattr("main.time.sleep", fake_sleep)
    monkeypatch.setattr("main.webbrowser.open", fake_open)

    _launch_ui()

    assert len(spawned) == 2
    assert "api_server.py" in " ".join(spawned[0])
    assert any("dev" in str(c) for c in spawned[1])
    assert "--port" in spawned[1]
    assert "5173" in spawned[1]
    assert opened == ["http://localhost:5173"]


def test_launch_ui_uses_custom_port(monkeypatch):
    """A custom UI port should be passed to Vite and the browser URL."""
    spawned: list[list[str]] = []
    opened: list[str] = []

    class FakeProc:
        def __init__(self, cmd):
            self._cmd = cmd
            self._polls = 0

        def poll(self):
            self._polls += 1
            return None if self._polls < 3 else 0

        def terminate(self):
            self._terminated = True

    def fake_popen(cmd, **kwargs):
        spawned.append(cmd)
        return FakeProc(cmd)

    monkeypatch.setattr("main._auto_update_monitor", lambda *_args: None)
    monkeypatch.setattr("main.subprocess.Popen", fake_popen)
    monkeypatch.setattr("main.time.sleep", lambda _secs: None)
    monkeypatch.setattr("main.webbrowser.open", opened.append)

    _launch_ui(6123)

    assert spawned[1][-2:] == ["--port", "6123"]
    assert opened == ["http://localhost:6123"]
