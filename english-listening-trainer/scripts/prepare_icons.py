from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
ICONS_DIR = BASE_DIR / "src-tauri" / "icons"
SOURCE_ICON = ICONS_DIR / "icon.png"
BUILD_DIR = BASE_DIR / ".build" / "icon.iconset"

PNG_OUTPUTS = {
    "32x32.png": 32,
    "128x128.png": 128,
    "128x128@2x.png": 256,
}

ICONSET_OUTPUTS = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}


def resize(source: Path, destination: Path, size: int) -> None:
    subprocess.run(
        [
            "sips",
            "-z",
            str(size),
            str(size),
            str(source),
            "--out",
            str(destination),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def main() -> int:
    if sys.platform != "darwin":
        raise SystemExit("macOS icon preparation currently supports macOS only.")

    if not SOURCE_ICON.exists():
        raise SystemExit(f"Missing source icon: {SOURCE_ICON}")

    if shutil.which("sips") is None or shutil.which("iconutil") is None:
        raise SystemExit("macOS `sips` and `iconutil` are required to prepare bundle icons.")

    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    for filename, size in PNG_OUTPUTS.items():
        resize(SOURCE_ICON, ICONS_DIR / filename, size)

    for filename, size in ICONSET_OUTPUTS.items():
        resize(SOURCE_ICON, BUILD_DIR / filename, size)

    subprocess.run(
        [
            "iconutil",
            "-c",
            "icns",
            str(BUILD_DIR),
            "-o",
            str(ICONS_DIR / "icon.icns"),
        ],
        check=True,
    )

    print(f"Bundle icons ready in {ICONS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
