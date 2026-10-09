"""Where the game writes, in a checkout and in a built executable.

Two claims, and the first one is the load-bearing one: **running from a checkout
must be byte for byte what it was before `game/paths.py` existed.** The five
files the game writes had their paths spelled out inline in five modules, and
folding them into one function is only safe if the answers do not move -- a
`records.json` that quietly relocated would lose a scoreboard somebody has been
adding to.

The second is why the module exists at all. In a PyInstaller onefile bundle
`__file__` resolves under a directory that is **deleted when the process ends**,
so writing beside the code means writing into a temporary folder: records that
forget every run, drafts that vanish on quit. Frozen, all five have to land in a
directory that outlives the process, beside the executable the player double
clicked.

If this file fails, ask which of those two it is before touching anything.
"""

import os

from game import paths


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _writers():
    """The paths the game writes, imported here and not at module scope."""
    from game import records

    return {"records.json": records.PATH}


def test_a_checkout_writes_exactly_where_it_always_did():
    """Why this test: `paths` exists so that a frozen build writes beside the
    executable, and the danger of a module like that is that it quietly moves
    where a *checkout* writes as well. So every path the game writes is named
    here at the literal place it had before `paths` existed.

    **One writer at the moment.** The editor's log and the map directories went
    with the format they belonged to; each one comes back into this dict as its
    writer comes back, and the claim is the same claim.
    """
    assert _writers() == {"records.json": os.path.join(REPO, "records.json")}


def test_a_checkout_is_never_told_it_is_frozen():
    assert not paths.frozen()
    assert paths.user_dir() == REPO


def test_frozen_writes_beside_the_executable(monkeypatch, tmp_path):
    """...and not under the bundle, which is a temporary directory.

    The constants in the five modules are evaluated at import, so this checks
    the function they are built out of rather than re-importing them.
    """
    executable = tmp_path / "downloads" / "bmx-80"
    executable.parent.mkdir()
    executable.write_text("")
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(executable))

    assert paths.frozen()
    assert paths.user_dir() == str(tmp_path / "downloads" / paths.USER_DIRNAME)
    assert os.path.isdir(paths.user_dir())
    assert paths.user_path("records.json") == os.path.join(
        paths.user_dir(), "records.json")
    assert paths.user_path("maps", "drafts").startswith(paths.user_dir())


def test_a_checkout_conjures_no_directory(tmp_path, monkeypatch):
    """`user_path` joins and nothing more.

    A `maps/drafts/` created at import time would be a menu tab appearing on a
    clone that has no drafts, and an `os.makedirs` in the wrong place is how
    that happens.
    """
    assert paths.user_path("nowhere", "at", "all") == os.path.join(
        REPO, "nowhere", "at", "all")
    assert not os.path.exists(os.path.join(REPO, "nowhere"))


def test_seed_copies_the_shipped_parts_once(monkeypatch, tmp_path):
    """A player's editor opens with the parts the repo ships, and keeps their edits.

    `maps/parts/` is the only map directory that is both committed and written
    to, so in a build it moves out of the read-only bundle and has to be
    refilled -- once. Copied again on every launch, a part somebody deleted
    would keep coming back.
    """
    bundle = tmp_path / "bundle"
    (bundle / "maps" / "parts").mkdir(parents=True)
    (bundle / "maps" / "parts" / "loop.json").write_text("{}")
    executable = tmp_path / "here" / "bmx-80"
    executable.parent.mkdir()
    executable.write_text("")
    monkeypatch.setattr(paths, "BUNDLE", str(bundle))
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(executable))

    paths.seed()
    landed = tmp_path / "here" / paths.USER_DIRNAME / "maps" / "parts" / "loop.json"
    assert landed.exists()

    landed.unlink()
    paths.seed()
    assert not landed.exists()


def test_seed_does_nothing_in_a_checkout(monkeypatch):
    """Where the two directories are the same one, and copying is a way to lose it."""
    called = []
    monkeypatch.setattr(paths.shutil, "copytree",
                        lambda *a, **k: called.append(a))
    paths.seed()
    assert called == []


def test_make_chdir_target_makes_the_directory_pyxel_will_move_into(monkeypatch, tmp_path):
    """`pyxel.init` chdirs to the caller's own directory, and a bundle has none.

    The Rust binding ends `init` with
    `os.chdir(os.path.dirname(inspect.stack()[1].filename))`. In a frozen build
    the modules stay in the archive, so for a caller that is not top-level --
    `game/render/headless.py`, and the editor's own window before it -- that path
    exists nowhere and Pyxel raises. Which is exactly what the first executable
    that was built did: a `FileNotFoundError` naming a temp folder, from a game
    that had just started fine.
    """
    executable = tmp_path / "here" / "bmx-80"
    executable.parent.mkdir()
    executable.write_text("")
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(executable))

    caller = tmp_path / "bundle" / "game" / "render" / "headless.py"
    assert not caller.parent.exists()
    paths.make_chdir_target(str(caller))
    assert caller.parent.is_dir()


def test_make_chdir_target_is_a_no_op_in_a_checkout(tmp_path):
    """Where every caller is a real directory already."""
    caller = tmp_path / "nowhere" / "headless.py"
    paths.make_chdir_target(str(caller))
    assert not caller.parent.exists()


def test_short_survives_a_path_relpath_refuses(monkeypatch):
    """Two drives is a Windows fact, and it killed the editor on one.

    `os.path.relpath` raises `ValueError: path is on mount 'C:', start on mount
    'D:'` -- which is what a CI runner looks like, and what plenty of Windows
    machines look like. The message is a `print`; refusing to open the editor
    over one is not a trade anybody would make.
    """
    def refuse(*args, **kwargs):
        raise ValueError("path is on mount 'C:', start on mount 'D:'")

    monkeypatch.setattr(paths.os.path, "relpath", refuse)
    assert paths.short(os.path.join("D:", "repo", "map.json")) == \
        os.path.join("D:", "repo", "map.json")


def test_short_is_the_short_one_when_it_can_be():
    assert paths.short(os.path.join(os.getcwd(), "records.json")) == "records.json"
