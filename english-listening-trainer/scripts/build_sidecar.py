from __future__ import annotations

import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
VENV_PYTHON = BASE_DIR / ".venv" / "bin" / "python"
BUILD_ROOT = BASE_DIR / ".build" / "pyinstaller"
DIST_DIR = BUILD_ROOT / "dist"
WORK_DIR = BUILD_ROOT / "work"
SPEC_DIR = BUILD_ROOT / "spec"
SIDECAR_NAME = "english-listening-backend"
EXPECTED_TARGET = "aarch64-apple-darwin"

COLLECT_ALL_CANDIDATES = [
    "faster_whisper",
    "ctranslate2",
    "av",
    "tokenizers",
    "huggingface_hub",
    "onnxruntime",
    "certifi",
    "multipart",
    "uvicorn",
]

COPY_METADATA_CANDIDATES = [
    "faster-whisper",
    "ctranslate2",
    "tokenizers",
    "huggingface-hub",
    "onnxruntime",
    "certifi",
    "uvicorn",
]


def run_output(command: list[str]) -> str:
    return subprocess.check_output(command, text=True).strip()


def rust_target() -> str:
    output = run_output(["rustc", "-vV"])
    for line in output.splitlines():
        if line.startswith("host: "):
            return line.removeprefix("host: ").strip()
    raise RuntimeError("Could not determine Rust host target from `rustc -vV`.")


def module_exists(python: Path, module_name: str) -> bool:
    code = (
        "import importlib.util, sys; "
        f"sys.exit(0 if importlib.util.find_spec({module_name!r}) else 1)"
    )
    return subprocess.run(
        [str(python), "-c", code],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def distribution_exists(python: Path, distribution_name: str) -> bool:
    code = (
        "import importlib.metadata, sys\n"
        "try:\n"
        "    importlib.metadata.version(sys.argv[1])\n"
        "except importlib.metadata.PackageNotFoundError:\n"
        "    sys.exit(1)\n"
        "sys.exit(0)\n"
    )
    return subprocess.run(
        [str(python), "-c", code, distribution_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def main() -> int:
    if sys.platform != "darwin":
        raise SystemExit("v0.2 sidecar packaging currently supports macOS only.")

    machine = platform.machine().lower()
    if machine not in {"arm64", "aarch64"}:
        raise SystemExit(
            f"v0.2 sidecar packaging targets Apple Silicon arm64 only; detected {machine!r}."
        )

    if not VENV_PYTHON.exists():
        raise SystemExit(
            "Missing .venv/bin/python. Create the project virtual environment first and "
            "install requirements-build.txt."
        )

    target = rust_target()
    if target != EXPECTED_TARGET:
        raise SystemExit(
            f"Expected Rust target {EXPECTED_TARGET!r}, but rustc reports {target!r}. "
            "Build the arm64 package from an Apple Silicon terminal/toolchain."
        )

    pyinstaller_check = subprocess.run(
        [str(VENV_PYTHON), "-c", "import PyInstaller"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if pyinstaller_check.returncode != 0:
        raise SystemExit(
            "PyInstaller is not installed in .venv. Run: "
            "pip install -r requirements-build.txt"
        )

    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)

    command = [
        str(VENV_PYTHON),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--noupx",
        "--name",
        SIDECAR_NAME,
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(WORK_DIR),
        "--specpath",
        str(SPEC_DIR),
        "--paths",
        str(BASE_DIR),
        "--add-data",
        f"{BASE_DIR / 'static'}:static",
        "--hidden-import",
        "persistence",
    ]

    for module_name in COLLECT_ALL_CANDIDATES:
        if module_exists(VENV_PYTHON, module_name):
            command.extend(["--collect-all", module_name])

    for distribution_name in COPY_METADATA_CANDIDATES:
        if distribution_exists(VENV_PYTHON, distribution_name):
            command.extend(["--copy-metadata", distribution_name])

    command.append(str(BASE_DIR / "backend_main.py"))

    print("Building Apple Silicon backend sidecar with PyInstaller...")
    subprocess.run(command, cwd=BASE_DIR, check=True)

    built_binary = DIST_DIR / SIDECAR_NAME
    if not built_binary.exists():
        raise SystemExit(f"PyInstaller finished but did not produce {built_binary}.")

    binaries_dir = BASE_DIR / "src-tauri" / "binaries"
    binaries_dir.mkdir(parents=True, exist_ok=True)
    target_binary = binaries_dir / f"{SIDECAR_NAME}-{target}"
    shutil.copy2(built_binary, target_binary)

    mode = target_binary.stat().st_mode
    target_binary.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    size_mb = target_binary.stat().st_size / (1024 * 1024)
    print(f"Sidecar ready: {target_binary}")
    print(f"Size: {size_mb:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
