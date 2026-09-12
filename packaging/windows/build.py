from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "windows"
DIST = ROOT / "desktop" / "dist"
ENTRY = ROOT / "packaging" / "windows" / "app.py"


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


def current_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else "dev"


def jarvis_pyinstaller_args(name: str, windowed: bool, onefile: bool, distpath: Path, workpath: Path) -> list[str]:
    separator = ";"
    args = [
        "pyinstaller", "--noconfirm", "--clean",
        "--windowed" if windowed else "--console",
        "--name", name,
        "--onefile" if onefile else "--onedir",
        "--distpath", str(distpath), "--workpath", str(workpath),
        "--paths", str(ROOT),
        "--add-data", f"{DIST}{separator}desktop/dist",
        "--collect-all", "webview",
        "--collect-submodules", "core",
        "--collect-submodules", "agent",
        "--collect-submodules", "integrations",
        "--collect-submodules", "plugins",
        "--collect-submodules", "providers",
        "--hidden-import", "desktop.api_server",
        "--hidden-import", "desktop",
    ]
    prompts = ROOT / "prompts"
    if prompts.exists():
        args += ["--add-data", f"{prompts}{separator}prompts"]
    args.append(str(ENTRY))
    return args


def main() -> None:
    if not DIST.joinpath("index.html").is_file():
        raise SystemExit("desktop/dist/index.html is missing; run npm run build first")

    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True, exist_ok=True)

    # User-facing build: a single self-contained GUI executable.
    run(*jarvis_pyinstaller_args(
        "Jarvis", True, True, BUILD,
        ROOT / "build" / "pyinstaller-work"
    ))

    # CI diagnostic build: console bootloader, used only for smoke testing.
    smoke_dist = BUILD / "_smoke"
    run(*jarvis_pyinstaller_args(
        "JarvisSmoke", False, False, smoke_dist,
        ROOT / "build" / "pyinstaller-work-smoke"
    ))

    exe = BUILD / "Jarvis.exe"
    smoke_exe = smoke_dist / "JarvisSmoke" / "JarvisSmoke.exe"
    if not exe.is_file():
        raise SystemExit(f"PyInstaller did not create {exe}")
    if not smoke_exe.is_file():
        raise SystemExit(f"PyInstaller did not create {smoke_exe}")

    (BUILD / "VERSION").write_text(current_commit() + "\n", encoding="utf-8")
    print(f"Windows Jarvis app ready: {exe}")
    print(f"Windows Jarvis smoke diagnostic ready: {smoke_exe}")


if __name__ == "__main__":
    main()
