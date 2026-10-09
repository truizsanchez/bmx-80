"""Where the game reads from, and where it writes -- which stop being the same
directory the moment it is an executable.

Two roots and one asymmetry:

- **Reading needs nothing from this file.** `render/assets.py`,
  `render/style.py` and `maps/from_data.py` each derive their root from their
  own `__file__`, and inside a PyInstaller bundle that resolves to the temporary
  directory the bundle unpacked itself into. Ship `art/` and the map JSON at the
  same relative paths and every one of them finds its files unchanged; there is
  no `if frozen` anywhere on the reading side and this module is not imported
  there.
- **Writing cannot survive that.** That directory is deleted when the process
  ends, so a `records.json` written beside the art would be a scoreboard that
  forgets every run. `user_dir` is the one answer to the question, and every
  place that writes a file asks it -- a count here would only go stale.

The rule it answers with is the one `records.py` already wrote down: a file the
game writes lives where the game does. In a checkout that is the repo, exactly as
before -- **the unfrozen answers are the literal paths that were there before
this file existed**, which is what `tests/test_paths.py` pins. In a build it is
`bmx-80-data/` beside the executable: the folder the player already has open,
visible, deletable, and not a dot-directory in a home they will never look in.

Pyxel-free, like everything under `game/` that is not `render/`.
"""

import os
import shutil
import sys

# The repo, as seen from `game/`. Under a bundle this is where the *data* went,
# which is why `seed` reads out of it and nothing writes into it.
BUNDLE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The name of the folder that appears beside a shared executable. Named for the
# game rather than something generic because a player unzips it into Downloads
# next to everything else they ever unzipped.
USER_DIRNAME = "bmx-80-data"


def frozen() -> bool:
    """Whether this is running out of a built executable.

    PyInstaller sets `sys.frozen`; a checkout has no such attribute. A function
    rather than a constant so a test can patch the two lines it reads.
    """
    return bool(getattr(sys, "frozen", False))


def user_dir() -> str:
    """The directory the game writes into: the repo, or beside the executable.

    **It is made when it is asked for**, and only in a build. Nothing that
    writes here creates its own root -- `records.save` swallows the `OSError`
    and would quietly keep no scoreboard at all, and `Trace` opens its file on
    the first line -- so the directory has to exist by the time either of them
    looks. A checkout already exists and is never touched.
    """
    if frozen():
        path = os.path.join(os.path.dirname(os.path.abspath(sys.executable)),
                            USER_DIRNAME)
        os.makedirs(path, exist_ok=True)
        return path
    return BUNDLE


def user_path(*parts: str) -> str:
    """A path under `user_dir`. A join, and it makes no directory of its own:
    the two writers of a nested path (the editor's `write`, `parts.write`) make
    theirs already, and a `maps/drafts/` conjured at import time in a checkout
    would be a menu tab appearing out of nothing."""
    return os.path.join(user_dir(), *parts)


def seed() -> None:
    """Copy the shipped parts out of the bundle, once, on a first run.

    `maps/parts/` is committed and it is the editor's palette, so moving the
    writable copy beside the executable would otherwise hand a player an editor
    with no parts in it. Only ever copied when the destination is absent: after
    that the folder is theirs, and a part they deleted stays deleted.

    A no-op outside a bundle, where the two paths are the same directory.
    """
    if not frozen():
        return
    src = os.path.join(BUNDLE, "maps", "parts")
    dst = os.path.join(user_dir(), "maps", "parts")
    if os.path.isdir(src) and not os.path.exists(dst):
        shutil.copytree(src, dst)


def make_chdir_target(module_file: str) -> None:
    """Make the directory `pyxel.init` is about to `chdir` into, if it is missing.

    Pyxel's `init` ends with `os.chdir(os.path.dirname(inspect.stack()[1].filename))`
    -- it moves the process to wherever the calling *file* is. Every caller in a
    checkout is a real directory, so this is a no-op there and the behaviour is
    unchanged.

    A bundle is the exception: it unpacks its data files to a temporary
    directory and keeps the modules in an archive, so a caller that is not
    top-level -- `tools/editor/ui.py` -- names a directory that does not exist,
    and Pyxel raises rather than carrying on. One `makedirs` inside a folder that
    is already ours and already temporary.
    """
    if not frozen():
        return
    os.makedirs(os.path.dirname(os.path.abspath(module_file)), exist_ok=True)


def short(path: str) -> str:
    """`path` relative to the working directory, or the whole of it if it cannot be.

    A message for a person: "editing maps/drafts/foo.json" reads, and the
    absolute path does not. `os.path.relpath` is the obvious way to get one and
    it **raises on Windows** when the two paths are on different drives -- an
    editor once died opening a map with `ValueError: path is on mount 'C:', start
    on mount 'D:'` on a machine whose checkout and working directory were on
    different disks, which is an ordinary thing for a Windows machine to be and
    a thing no amount of running it on Linux would ever show.

    The long path is a worse message and a fine one. This is a print.
    """
    try:
        return os.path.relpath(path)
    except ValueError:
        return path
