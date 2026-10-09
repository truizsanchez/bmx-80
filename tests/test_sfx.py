"""This game's own sound, for a race with no cartridge (`game/sfx.py`).

The model is what plays when; `game/render/audio.OwnAudio` is what hears it.
Neither is listened to here -- a test cannot -- so what is held is that every
moment the race makes a sound for has one, that Pyxel takes each as written,
and that the engine rises with the revs and is not restarted for nothing.
"""

import pytest

from game import sfx
from game.engine.rules import Cue


def test_every_cue_the_race_makes_has_a_sound():
    """Why this test: a cue added to the engine with no sound here would be a
    moment the original makes a noise for and this game passes in silence."""
    assert set(sfx.CUES) == set(Cue)


@pytest.mark.parametrize("effect", list(sfx.CUES.values()) + list(sfx.SCREENS.values())
                         + [sfx.engine(sfx.IDLE), sfx.engine(sfx.HIGHEST)])
def test_pyxel_takes_every_sound_as_written(pyxel_headless, effect):
    """A note string Pyxel cannot read raises when it is set, which in a race
    would be the first time that sound was wanted."""
    import pyxel

    sound = pyxel.Sound()
    sound.set(effect.notes, effect.tones, effect.volumes, effect.effects, effect.speed)
    assert len(sound.notes) >= 1


def test_the_engine_rises_with_the_revs_and_stops_at_the_top():
    pitches = [sfx.engine_pitch(revs) for revs in range(0, 400)]
    assert pitches == sorted(pitches), "the engine went down as it wound up"
    assert pitches[0] == sfx.IDLE and pitches[-1] == sfx.HIGHEST
    assert sfx.note(0) == "c0" and sfx.note(13) == "c#1"


def test_the_engine_is_replayed_only_when_its_pitch_moves(pyxel_headless, monkeypatch):
    """Why this test: a loop restarted every iteration is a buzz of its own, so
    the engine goes back on its channel only when the revs move its note."""
    import pyxel

    from game.render.audio import OwnAudio

    played = []
    monkeypatch.setattr(pyxel, "play", lambda channel, *a, **kw: played.append(channel))
    audio = OwnAudio()
    audio.start()
    audio.cue([], 0)
    audio.cue([], 1)
    assert played.count(sfx.ENGINE_CHANNEL) == 1
    audio.cue([], 200)
    assert played.count(sfx.ENGINE_CHANNEL) == 2


def test_the_finish_takes_the_engine_away(pyxel_headless, monkeypatch):
    import pyxel

    from game.render.audio import OwnAudio

    stopped = []
    monkeypatch.setattr(pyxel, "stop", lambda *a: stopped.append(a))
    audio = OwnAudio()
    audio.start()
    audio.cue([Cue.FINISH], 50)
    assert not audio.running and (sfx.ENGINE_CHANNEL,) in stopped
    audio.cue([], 120)
    assert not audio.running, "and nothing after the line starts it again"


def test_a_race_without_a_cartridge_is_heard(pyxel_headless, tmp_path):
    """Why this test: a race on this game's own courses was silent, and said so
    in a docstring as a thing to fix."""
    import main
    from game.render.audio import OwnAudio

    app = main.App(run=False, window=False)
    app.front.records, app.front.path = {}, str(tmp_path / "r.json")
    app.front.confirm()
    app.front.confirm()
    app.front.confirm()
    app.front.confirm()
    app._build()
    assert isinstance(app.audio, OwnAudio)
    assert isinstance(app.screens, OwnAudio)
