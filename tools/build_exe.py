"""Freeze the game into one executable, check it, and zip it.

    python tools/build_exe.py                  # this system, version off git
    python tools/build_exe.py --version 0.2.0  # ...or say it

Out comes `dist/bmx-80-<version>-<system>-x64.zip`: one binary, the README and
the licence. That is the whole of what somebody who does not have Python gets
handed, and it is the reason this file exists -- "clone it, make a venv, pip
install pyxel" is not a way to share a game.

**PyInstaller directly, and not `pyxel package` / `pyxel app2exe`.** Pyxel has
its own packager and it does not fit here. `pyxel package` zips *everything*
under the app directory -- `.venv/`, `tests/`, `tools/`, everything but `.gif`,
`.zip` and `__pycache__` -- and writes a startup marker into the source tree
while it does it. `pyxel app2exe` then runs this same tool underneath, but it
hands it a bootstrap that unpacks that zip at runtime, so our modules travel as
*data* and its `--hidden-import` list is scanned off the startup script alone.
An import reached from three modules in would be missed and would fail on the
screen that needs it. PyInstaller pointed at `main.py` follows the real import
graph instead. Written down here because it is a decision that looks like an
oversight.

**Nothing is done about the read paths, on purpose.** `render/assets.py`,
`render/style.py` and `maps/from_data.py` each build their root out of their own
`__file__`, which inside a bundle resolves under the directory it unpacked into;
ship `art/` and the map JSON at the same relative paths -- which is what `DATA`
below says -- and every one of them finds its files with no `if frozen` anywhere.
The *write* paths are the ones that had to move, and they moved once, in
`game/paths.py`.
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

NAME = "bmx-80"
DIST = os.path.join(ROOT, "dist")

# What the bundle carries that is not code, each at the same relative path it has
# in the repo -- see the module docstring for why that matters.
#
# `maps/drafts/` is not here and never will be: it is gitignored, it does not
# exist on a clone, and in a build it is the player's, beside the executable.
# `art/hand/` rides along inside `art/` if anybody has drawn anything.
#
# The vocabulary a course is written in, and the courses: the classic ones and
# the enhanced ones, each in its own. `maps/read.py` reads every one of these and
# `PyInstaller` follows only imports, so each is named here -- and
# `maps/enhanced/drafts/` is not, for the reason `maps/drafts/` is not.
_VOCABULARY = ("tiles.json", "metatiles.json", "pieces.json")
DATA = ("art",
        *(os.path.join("maps", name) for name in _VOCABULARY),
        os.path.join("maps", "tables.json"), os.path.join("maps", "labels.json"),
        os.path.join("maps", "courses"),
        *(os.path.join("maps", "enhanced", name) for name in _VOCABULARY),
        os.path.join("maps", "enhanced", "courses"))

# Rule 2 of the repo, said in the packaging: `tests/` has no business in a
# player's download. `pytest` follows it
# out. Neither is imported from `main.py`, so this is a guard rather than a fix --
# and `tests/test_build_manifest.py` is what keeps it one.
EXCLUDE = ("tests", "pytest")

# What the zip carries beside the binary.
EXTRAS = ("README.md", "LICENSE")

FALLBACK_VERSION = "0.1.0-alpha"


def version() -> str:
    """The tag we are on, or the commit, or a stated fallback.

    Nothing in the game names a version -- there has never been a release -- so
    git is the only thing that knows, and on a tarball with no git it is the
    fallback. This is a filename, not a claim the game makes about itself.
    """
    try:
        out = subprocess.run(["git", "describe", "--tags", "--always", "--dirty"],
                             cwd=ROOT, capture_output=True, text=True)
    except OSError:
        return FALLBACK_VERSION
    described = out.stdout.strip()
    if out.returncode != 0 or not described:
        return FALLBACK_VERSION
    return described.lstrip("v")


def system() -> str:
    """`windows` or `linux`. macOS is not built and is not refused -- untested."""
    return {"Windows": "windows", "Linux": "linux"}.get(
        platform.system(), platform.system().lower())


def binary() -> str:
    return os.path.join(DIST, NAME + (".exe" if system() == "windows" else ""))


def build() -> None:
    """Run PyInstaller. Raises `CalledProcessError` if it fails."""
    command = [sys.executable, "-m", "PyInstaller", "--onefile", "--clean",
               "--noconfirm", "--name", NAME, "--distpath", DIST,
               "--workpath", os.path.join(ROOT, "build"),
               "--specpath", os.path.join(ROOT, "build")]
    for source in DATA:
        # PyInstaller's destination is a directory: a directory lands at its own
        # path, and a file in the directory it is in.
        where = source if os.path.isdir(os.path.join(ROOT, source)) else os.path.dirname(source)
        command += ["--add-data", "%s%s%s" % (os.path.join(ROOT, source), os.pathsep, where)]
    for module in EXCLUDE:
        command += ["--exclude-module", module]
    if system() == "windows":
        # No console window behind the game. Pyxel opens its own, and a player
        # double-clicking the exe should not get a terminal as well.
        command.append("--windowed")
    command.append(os.path.join(ROOT, "main.py"))
    print(" ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def selftest() -> bool:
    """Ask the binary itself whether its bundle is complete. See `main.selftest`."""
    print("--- %s --selftest" % binary())
    return subprocess.run([binary(), "--selftest"]).returncode == 0


def package(tag: str) -> str:
    """Zip the binary with the README and the licence. Returns the path."""
    path = os.path.join(DIST, "%s-%s-%s-x64.zip" % (NAME, tag, system()))
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(binary(), os.path.basename(binary()))
        for extra in EXTRAS:
            zf.write(os.path.join(ROOT, extra), extra)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", dest="tag", default=None,
                        help="version for the zip's name (default: git describe)")
    parser.add_argument("--no-selftest", action="store_true",
                        help="skip running the built binary (don't)")
    args = parser.parse_args(argv)

    tag = args.tag or version()
    shutil.rmtree(DIST, ignore_errors=True)
    build()
    if not args.no_selftest and not selftest():
        print("selftest failed: the bundle is missing something. Not packaging.")
        return 1
    path = package(tag)
    print("%s  (%.1f MB)" % (path, os.path.getsize(path) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
