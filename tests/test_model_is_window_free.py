"""The model must stay importable without Pyxel.

The engine, the maps and the menu are the parts a test can drive step by step;
the moment one of them reaches for Pyxel, it needs a window and that stops being
true. An old MVP called `pyxel.btn()` from inside the bike's physics, which is
exactly how it ended up untestable.

Checked in a subprocess because the rest of the suite has already imported
Pyxel through the headless fixture.
"""

import subprocess
import sys
import os

MODEL_MODULES = [
    "game.constants",
    # Which displayed frames step an engine: arithmetic about rates, asked by
    # tests with no window.
    "game.cadence",
    # How a race is played: a ruleset and a rate.
    "game.mode",
    # What a race with no cartridge sounds like, as data.
    "game.sfx",
    # The engine: the original's rules, stepped with no window.
    "game.engine",
    "game.engine.original",
    "game.engine.rules",
    "game.engine.speed",
    "game.engine.vector",
    "game.engine.terrain",
    "game.engine.probes",
    "game.engine.bike",
    "game.engine.flight",
    "game.engine.run",
    "game.engine.items",
    "game.engine.camera",
    "game.engine.background",
    "game.engine.rival",
    # The original's courses, read out of the player's cartridge.
    "game.rom",
    "game.rom.cartridge",
    "game.rom.course",
    "game.rom.graphics",
    "game.rom.sound",
    "game.rom.apu",
    "game.rom.mixer",
    "game.course",
    "game.menu",
    "game.records",
    # The log. It takes the frame number as a callable for exactly this reason.
    "game.trace",
    # The map format. `maps/` reads `game/` and is read by whatever writes a
    # map, which is the one direction that must not reverse: a vocabulary that
    # needed a window could not be validated without one.
    "maps",
    "maps.read",
    # Undo: every state a document has been in, and it never looks inside one.
    # **It has now outlived two editors**, which is the evidence it was never
    # about the window -- and the reason it survived a deletion that took the
    # rest of `tools/editor/` with it.
    "tools.editor.history",
    # The course in hand and its file: every edit an editor makes, and whether
    # a save would change anything -- all of it testable with no window open.
    "tools.editor.document",
    "tools.editor.map_file",
    # ...and where everything in its window is, which is arithmetic.
    "tools.editor.view",
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_model_modules_do_not_pull_in_pyxel():
    script = (
        "import sys;"
        + "".join("import %s;" % module for module in MODEL_MODULES)
        + "sys.exit(1 if 'pyxel' in sys.modules else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, (
        "importing the model pulled in pyxel (or failed): %s%s" % (result.stdout, result.stderr)
    )


def test_the_game_does_not_reach_into_the_tests():
    """`game/` must not name `tests/`, and that is the whole of the decoupling.

    It only stays true in one direction: `tests/` names `game/` freely, and what
    must never happen is the game growing an opinion about what it is measured
    with, because then the two move together and the measurement stops being one.
    A comment saying so is not a mechanism.
    """
    game = os.path.join(ROOT, "game")
    offenders = []
    for directory, _, names in os.walk(game):
        for name in names:
            if not name.endswith(".py"):
                continue
            path = os.path.join(directory, name)
            with open(path) as handle:
                lines = handle.read().splitlines()
            # An `import`, not the word: a comment may say where something lives,
            # and what must not exist is the dependency.
            if any(
                "tests" in line and line.lstrip().startswith(("import ", "from "))
                for line in lines
            ):
                offenders.append(os.path.relpath(path, ROOT))
    assert not offenders, "game/ reached into the tests: %s" % offenders
