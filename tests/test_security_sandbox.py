from core.security import Sandbox


def test_sandbox_does_not_allow_prefix_siblings(tmp_path):
    allowed = tmp_path / "workspace"
    sibling = tmp_path / "workspace-other"
    allowed.mkdir()
    sibling.mkdir()

    sandbox = Sandbox([str(allowed)])

    assert sandbox.check_path(str(allowed / "file.py"))["allowed"] is True
    assert sandbox.check_path(str(sibling / "file.py"))["allowed"] is False


def test_sandbox_resolves_symlinks_when_supported(tmp_path):
    allowed = tmp_path / "workspace"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()

    link = allowed / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        return

    sandbox = Sandbox([str(allowed)])
    assert sandbox.check_path(str(link / "secret.txt"))["allowed"] is False
