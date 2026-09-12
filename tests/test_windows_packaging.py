import ast
import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = PROJECT_ROOT / "packaging" / "windows" / "app.py"
BUILD_PATH = PROJECT_ROOT / "packaging" / "windows" / "build.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_webview_is_not_imported_at_module_level():
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] != "webview" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("webview")


def test_smoke_test_force_exits_instead_of_reraising():
    source = APP_PATH.read_text(encoding="utf-8")
    assert "os._exit" in source
    assert "arm_smoke_watchdog" in source


def test_pyinstaller_command_includes_project_root_and_api():
    build = load_module("friday_windows_build", BUILD_PATH)
    cmd = build.app_pyinstaller_cmd(console=True)
    assert "--paths" in cmd
    assert str(build.ROOT) in cmd
    assert "--console" in cmd
    assert "--windowed" not in cmd
    assert "desktop.api_server" in cmd
    hidden_imports = [cmd[index + 1] for index, value in enumerate(cmd) if value == "--hidden-import"]
    collected = [cmd[index + 1] for index, value in enumerate(cmd) if value == "--collect-submodules"]
    assert "desktop.api_server" in hidden_imports
    assert "desktop" in collected
    assert "core" in collected


def test_pyinstaller_defaults_to_windowed_for_users():
    build = load_module("friday_windows_build_windowed", BUILD_PATH)
    cmd = build.app_pyinstaller_cmd(console=False)
    assert "--windowed" in cmd
    assert "--console" not in cmd


def test_api_server_skips_plugin_discovery_during_packaged_smoke(monkeypatch):
    source = (PROJECT_ROOT / "desktop" / "api_server.py").read_text(encoding="utf-8")
    assert 'os.environ.get("FRIDAY_SMOKE_TEST") == "1"' in source
