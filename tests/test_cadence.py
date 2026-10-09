"""Which displayed frames step an engine, and how many steps a second that makes.

The window runs faster than this engine steps, and an engine that reproduces the
original game has to step at the original's rate, which does not divide the
window's. `Cadence` is the one place that decides; these tests pin what it hands
out, because a cadence that drifted by a step a second would be a speed change
nobody wrote down.

There are three rates in the window and they are not the same: the race's, the
countdown's -- slower, and its own test below -- and the sound driver's, which
is on the timer at 64 a second and does not follow either.
"""

import pytest

from game.cadence import Cadence
from game.constants import DISPLAY_FPS


def _pattern(cadence, frames):
    return [cadence.tick() for _ in range(frames)]


def test_a_rate_that_divides_the_window_steps_on_a_fixed_beat():
    """Half the window's rate is one step in two, starting on a step.

    The simple case, and the one a replay would notice first if the spreading
    ever changed: the same run has to step on the same frames every time.
    """
    cadence = Cadence(DISPLAY_FPS // 2, DISPLAY_FPS)
    assert _pattern(cadence, 8) == [1, 0, 1, 0, 1, 0, 1, 0]


def test_a_rate_that_does_not_divide_the_window_is_exact_over_a_second():
    """The original game's rate, 41 steps a second, is exact and evenly spread.

    Exact over the period, so a race timed in steps and a race timed in seconds
    agree; spread, so no frame owes two steps and no run of frames owes none for
    longer than the rate itself implies.
    """
    cadence = Cadence(41, 60)
    owed = _pattern(cadence, 600)
    assert sum(owed) == 410
    assert set(owed) == {0, 1}
    gaps = [len(run) for run in "".join(map(str, owed)).split("1") if run]
    assert max(gaps) == 1          # never two displayed frames in a row without a step


def test_the_first_frame_after_a_reset_steps():
    """Enter starts a race, and the race should move on the next frame drawn.

    A cadence that started halfway through its cycle would hold the first step
    back by a frame, and one that remembered the last race would start the next
    one at a different phase -- the same run would not replay the same way.
    """
    cadence = Cadence(41, DISPLAY_FPS)
    _pattern(cadence, 3)
    cadence.reset()
    assert cadence.tick() == 1


def test_the_countdown_runs_at_its_own_slower_rate():
    """The original's main loop is slower before the green than after it.

    Measured on the cartridge: 3.340 displayed frames an iteration counting down
    against 1.44 racing, the same to three decimals on every course and every
    level, and 54 frames held at 48 before the first one. Nothing physical
    happens in the countdown -- the clocks are stopped and the bike idles -- so
    the whole of what the rate decides is the start's four tones, which land 27
    frames apart on the original and 12 on a countdown run at the race's rate.
    That is what this catches, and the ear is what caught it first.

    `App` cannot be driven into a race without a cartridge, so this is the two
    cadences and the hold driven exactly as `App._race` drives them. What comes
    out: the four tones on frames 98, 124, 151 and 178 against the original's
    95, 122, 150 and 177, and the green on 211 against its 211.
    """
    import main
    from game.engine.rules import Cue
    from game.engine.run import Run

    from tests.test_engine_bike import _floor, _solid_from

    run = Run(_solid_from(_floor(0), 15))
    countdown = Cadence(main.COUNTDOWN_STEPS, DISPLAY_FPS)
    racing = Cadence(main.ENGINE_STEPS, DISPLAY_FPS)
    tones, green = [], None
    for frame in range(main.START_HOLD + 300):
        if frame < main.START_HOLD:
            continue
        for _ in range((countdown if run.countdown else racing).tick()):
            run.step(0)
            if Cue.COUNT in run.cues or Cue.GO in run.cues:
                tones.append(frame)
            if not run.countdown and green is None:
                green = frame

    assert len(tones) == 4, "three beeps and a go"
    gaps = [b - a for a, b in zip(tones, tones[1:])]
    assert all(26 <= gap <= 28 for gap in gaps), gaps
    assert 205 <= green <= 220, "the original takes 211 frames from the 48 to the green"


@pytest.mark.parametrize("steps, frames", [(0, 60), (30, 0), (-1, 60)])
def test_a_cadence_needs_a_positive_rate(steps, frames):
    """A zero rate would never step, and would do it silently: the race frozen."""
    with pytest.raises(ValueError):
        Cadence(steps, frames)
