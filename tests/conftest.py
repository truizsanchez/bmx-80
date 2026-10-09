"""Shared headless Pyxel session, and one arrangement for measuring coverage.

Pyxel can only be initialized once per process, so the window (well, the lack of
one -- headless=True) is session-scoped. Tests that only exercise the model
should not need this fixture at all: everything outside game/render and main.py
is deliberately free of Pyxel imports.

The same fact is why anything wanting a second window drives it in a
**subprocess** -- and why `pytest_configure` below exists. See `.coveragerc`.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def pytest_configure(config):
    """Make a subprocess count toward coverage, without anyone remembering to.

    Coverage measures the process it starts and no other. The mechanism for the
    rest is an environment variable -- coverage's own `.pth` reads
    `COVERAGE_PROCESS_START` at interpreter start and arms itself -- and a
    subprocess inherits it, so setting it here covers every `pytest -n auto`
    worker, and whatever else the suite has to start in a process of its own.

    **It is set here rather than written down in a command** because forgetting
    it is silent and expensive: the run still passes and the modules driven in a
    subprocess report a fraction of what they ran. A number that says something
    is untested invites somebody to delete something live. A comment saying
    "remember the variable" is not a mechanism; this is.

    Does nothing at all unless a coverage run is already under way, which is what
    `Coverage.current()` answers.
    """
    try:
        import coverage
    except ImportError:
        return
    if coverage.Coverage.current() is not None:
        os.environ.setdefault("COVERAGE_PROCESS_START", os.path.join(ROOT, ".coveragerc"))


@pytest.fixture(scope="session")
def pyxel_headless():
    import pyxel

    from game.render import headless

    # The suite drives whole frames in `test_app`, `test_debug` and the one race
    # in `test_rocks` that proves the game can draw a rock, and `boot` is
    # unthrottled for them: pacing a window nobody sees was 26 of the suite's
    # 83 seconds spent asleep. See `game/render/headless.py`.
    headless.boot(chdir_to=__file__)
    return pyxel
