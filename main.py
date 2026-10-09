"""Pyxel entry point. The only place that owns the window and the frame loop.

    pyxel run main.py              # the game, on the eight courses in maps/courses/
    python main.py --rom <file.gb> # ...the same eight, from your cartridge, in its art
    python main.py --selftest      # load it all, draw a frame, exit -- for the build
    python main.py --palette green # the four shades in the original screen's green
    python main.py --mode excessive # FREE RIDE starts on it: the display's rate
    python main.py --edit <name>   # the course editor: a course by name, or a new draft
    python main.py --ride <file>   # straight onto one course file, as the editor rides one

**The engine rides both kinds of course.** With `--rom` the eight are read out of
the player's own cartridge and drawn in its own art behind its own panel; without
it they are this game's copies, written in `maps/read.py`'s shape and drawn out of
the tiles `maps/tiles.json` names. Either one is a `Ground`, which is why the
engine cannot tell them apart.

**The game opens on the original's front end** (`game/front.py`) either way. The
menu (`game/menu.py`) is FREE RIDE -- the eight and the author's drafts, in any
mode -- and the title opens it from a fourth row. A race goes back to where it
was started from.

**The pad is the Game Boy's, laid on a keyboard the way two hands held it**: the
left hand has the cross on WASD, the right hand has B on J and A on K -- A is the
throttle, B the nitro. Start is Enter (start, pause) and Select is Space. ESC
leaves a race, goes from the menu back to the title, and from the title out of
the game.
"""

import functools
import zlib
import os
import sys
from collections.abc import Sequence

import pyxel

from game import paths
from game.cadence import Cadence
from game.constants import DISPLAY_FPS, DISPLAY_SCALE, SCREEN_H, SCREEN_W
from game.engine.original import DOWN, LEFT, NITRO, RIGHT, THROTTLE, UP
from game.course import Course as OwnCourse
from game.engine.run import FINISHED, Run
from game.engine.original import NO_LIMIT
from game.engine.terrain import Ground
from game.front import (
    CARD, COURSE, ELSEWHERE, GAMEOVER, RESULTS, SPLASH, TIMEUP, TITLE, Front, Listed)
from game.menu import Menu
from game.mode import CLASSIC, MODES, Mode
from game.render import (
    assets,
    front_draw,
    menu_draw,
    palette,
    ride_draw,
    rom_art,
)
from game.render.audio import Audio, OwnAudio, Voice
from game.rom.cartridge import Cartridge, NotTheCartridge
from game.rom import apu, graphics
from game.rom import mixer as sound
from game.rom.mixer import Clips, Mixer
from game.rom.course import COUNT, Course
from maps import DRAFTS, LISTED, read

# The four things the window can be showing. The front end is several screens
# and `game/front.py` says which -- the window only has to know it is in it.
MENU, FRONT, RACING, PAUSED = "menu", "front", "racing", "paused"

#: The pad, as the original's bits: the cross on WASD, B on J, A on K.
PAD = ((pyxel.KEY_W, UP), (pyxel.KEY_A, LEFT), (pyxel.KEY_S, DOWN), (pyxel.KEY_D, RIGHT),
       (pyxel.KEY_J, NITRO), (pyxel.KEY_K, THROTTLE))
START, SELECT = pyxel.KEY_RETURN, pyxel.KEY_SPACE
#: The original settles a choice on **Start or A**, so both do here.
CONFIRM = pyxel.KEY_K

#: Where the sound's clips are kept between runs, beside everything else the
#: game writes. A player's own cartridge rendered, so it is theirs and it is
#: never committed -- `.gitignore` says so out loud.
SOUND_BANK = "sound.bank"

#: The driver's word for silence: every sound stopped.
SILENCE = 0
#: What the original asks for as each of its screens goes up: whether it
#: silences everything first, and then the sounds in the order it asks for them.
#: The title is silent and **the tune belongs to the screen a course is chosen
#: on**; the card cuts it off with the sound that settled the level; and the end
#: of a race the clock ran out on has a tune of its own, asked for once and
#: playing across both of its waits.
SCREEN_SOUNDS = {
    COURSE: (False, (sound.CONFIRM, sound.SELECT_MUSIC)),
    CARD: (True, (sound.CONFIRM,)),
    RESULTS: (True, ()),
    TIMEUP: (True, (sound.GAMEOVER_MUSIC,)),
}
#: ...and the results' own, which the table above cannot name: the screen has
#: two tunes and picks one on whether the record fell, so the step alone does
#: not decide it. The ordinary one first, the record's second.
RESULTS_TUNES = (sound.RESULTS_MUSIC, sound.RECORD_MUSIC)

#: The original steps its physics about 41 times for every 60 frames. A mode
#: says its own (`game/mode.py`); this is classic's.
ENGINE_STEPS = CLASSIC.steps
#: ...and about 18 times while the countdown is on the screen. Its main loop is
#: slower before the green than after it: measured on the original at 3.340
#: displayed frames an iteration against 1.44 racing, the same to three decimals
#: on every course and every level. Nothing physical happens in the countdown --
#: the clocks are stopped and the bike idles -- so this is what the start sounds
#: like and nothing else: the beeps land 27 frames apart rather than 12.
COUNTDOWN_STEPS = 18
#: Displayed frames the original holds the countdown at 48 before it starts
#: down: 53 or 54, whichever level. Nothing steps in them.
START_HOLD = 54

# The menu's arrows repeat when held: half a second before they start and then a
# move every eight displayed frames. Written in displayed frames because `btnp`
# counts them.
MENU_HOLD = DISPLAY_FPS // 2
MENU_REPEAT = 8


class App:
    """The window, showing the menu.

    Two flags and both exist for `tests/test_app.py`, which drives the real
    `update` and `draw` with the real keys. `run=False` builds it without
    entering Pyxel's loop; `window=False` takes the one that is already open,
    because **Pyxel can only be initialised once per process** and the test suite
    opens its own headless one in `tests/conftest.py`.
    """

    def __init__(self, run: bool = True, window: bool = True,
                 cartridge: Sequence[Listed] = (), rom: Cartridge | None = None,
                 clips: Clips | None = None, look: str = palette.DEFAULT_LOOK,
                 ride: Listed | None = None, mode: Mode = CLASSIC) -> None:
        if window:
            self._open_window(look)
        # FREE RIDE: the eight -- the cartridge's, when there is one -- and the
        # author's drafts, in whichever mode; `--mode` says which it starts on.
        self.menu = Menu(list(cartridge) or list(LISTED), drafts=list(DRAFTS),
                         mode=mode.name)
        if ride is not None:
            # One course and straight onto it: what the editor opens to ride
            # the course it is drawing. The menu it comes back to lists that
            # course alone, so leaving the race is leaving the ride.
            self.menu = Menu([ride], records=self.menu.records, path=self.menu.path,
                             mode=mode.name)
        #: **The original's screens are the front end**, on the cartridge's
        #: courses or, without one, on the same eight out of `maps/courses/`;
        #: the menu is the door to the rest, which a title without a cartridge
        #: offers as a fourth row. The two share one set of records so that
        #: neither goes stale behind the other. `--ride` is one course and no
        #: front end at all.
        courses = list(cartridge) or (list(LISTED) if ride is None else [])
        self.front = (Front(courses, records=self.menu.records, path=self.menu.path,
                            more=True)
                      if courses else None)
        self.mode = FRONT if self.front is not None else MENU
        #: Where the race in hand was started from, which is where it goes back
        #: to: the front end's results, or the menu.
        self.origin = self.mode
        self.ride: Run | None = None
        #: The time to qualify the race in hand starts with, which is what the
        #: card says and what the clock is set to.
        self.limit = 0
        self.recorded = False
        #: How the race in hand is played: by which rules and at what rate. The
        #: front end's are always the original's; FREE RIDE's are the menu's.
        self.play = CLASSIC
        self.cadence = Cadence(CLASSIC.steps, DISPLAY_FPS)
        #: The countdown's own, slower, and the frames held before it starts down.
        self.countdown_cadence = Cadence(COUNTDOWN_STEPS, DISPLAY_FPS)
        self.start_hold = 0
        #: A course out of a cartridge sounds as the original does; the sound's
        #: driver keeps its own time, 64 ticks a second. The bank of clips it
        #: plays is rendered before the window opens and serves every race.
        self.clips = clips
        #: The cartridge those courses came out of, for everything drawn out of
        #: it. A test hands over courses without one, which is the run with no
        #: cartridge: every screen is then drawn from nothing. **Handed over
        #: here and not when a race starts**, because the screens before the
        #: first race are drawn out of it too.
        self.rom = rom
        rom_art.install_cartridge(rom)
        if rom is not None:
            # A course of this game's own ridden with a cartridge in hand -- a
            # draft on FREE RIDE, or the editor's `R` with its `--rom` -- is drawn
            # in the cartridge's own art: every tile of the vocabulary is named
            # for the original's tile it is.
            rom_art.paint_terrain(rom)
        self.audio: Voice | None = None
        self.sound_cadence = Cadence(apu.TICKS, DISPLAY_FPS)
        #: The screens between races have a voice of their own, and it outlives
        #: a race where the race's does not: it is built once, primed on the
        #: handful of clips a screen can ask for, and kept. Without a cartridge
        #: it is this game's own, which has no music.
        self.screens = self._screen_voice()
        self.screen_cadence = Cadence(apu.TICKS, DISPLAY_FPS)
        self.screen_step: str | None = None
        #: Displayed frames the screen in hand has been up, counted from zero
        #: each time one gives way to another. It is what the results blink on:
        #: they are not one of the screens that end by themselves, so they have
        #: no counter of their own to read.
        self.screen_frames = 0
        if ride is not None:
            self._ride()
        if run:
            pyxel.run(self.update, self.draw)

    @staticmethod
    def _open_window(look: str) -> None:
        """The window, its palette and its art.

        `quit_key=KEY_NONE` because this file has its own use for ESC, and
        anything this file binds has to be named here as well: the quit key is
        read inside `pyxel.run`, where no test can see it.
        """
        pyxel.init(SCREEN_W, SCREEN_H, title="bmx-80", fps=DISPLAY_FPS,
                   display_scale=DISPLAY_SCALE, quit_key=pyxel.KEY_NONE)
        palette.apply()
        assets.load_all()
        palette.show(look)

    def _screen_voice(self) -> Voice:
        """The cartridge's sound for the screens, primed on the handful of clips
        a screen can ask for -- or, without one, this game's own."""
        if self.rom is None or self.clips is None:
            return OwnAudio()
        voice = Audio(Mixer(self.rom, clips=self.clips))
        voice.prime(self.clips.screen_keys())
        return voice

    def _quit(self) -> None:
        """Close the game. A method so that a test can watch it being asked for:
        `pyxel.quit()` does not return, so a test that pressed the key would end
        the run rather than assert anything about it."""
        pyxel.quit()

    def update(self) -> None:
        if self.mode is MENU:
            self._update_menu()
        elif self.mode is FRONT:
            self._update_front()
        else:
            self._update_ride()

    def _update_front(self) -> None:
        """The original's screens: choose a course, choose a level, wait, race.

        **The cursor is the pad's**, as on the original: up and down on the
        title, left and right on the two rows of the screen after it, Start or A
        to settle either -- and the arrows do the same thing for a hand that is
        on them. Select walks the three ways to play, which is what it does on
        the original. Nothing goes back, which is the original's behaviour; ESC
        leaves the game, as it does on the menu.

        The card reads no button at all: none shortens it on the original, and
        the screen it opens on is the one that does give way to Start.
        """
        front = self.front
        assert front is not None
        self._screen_sound(front)
        for _ in range(self.screen_cadence.tick()):
            self.screens.tick()
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self._quit()
        elif front.step is SPLASH:
            front.tick()
            if self._settled():
                front.confirm()
        elif front.step is CARD:
            if front.tick():
                self._green()
        elif front.step in (TIMEUP, GAMEOVER):
            # The end of a race the clock ran out on: two waits, and no button
            # shortens either, as none shortens the card.
            front.tick()
        elif front.step is RESULTS:
            if self._settled():
                self._silence()
                front.confirm()
        else:
            self._choose(front)

    @staticmethod
    def _settled() -> bool:
        """Start or A, this frame."""
        return pyxel.btnp(START) or pyxel.btnp(CONFIRM)

    def _choose(self, front: Front) -> None:
        """The title, or the course and the level: the cursor walked, and the
        choice settled."""
        onwards, backwards = ((pyxel.KEY_DOWN, pyxel.KEY_S), (pyxel.KEY_UP, pyxel.KEY_W)) \
            if front.step is TITLE else \
            ((pyxel.KEY_RIGHT, pyxel.KEY_D), (pyxel.KEY_LEFT, pyxel.KEY_A))
        step = sum(pyxel.btnp(key, hold=MENU_HOLD, repeat=MENU_REPEAT) for key in onwards) \
            - sum(pyxel.btnp(key, hold=MENU_HOLD, repeat=MENU_REPEAT) for key in backwards)
        if pyxel.btnp(SELECT) and front.step is TITLE:
            step += 1
        for _ in range(abs(step)):
            front.move(1 if step > 0 else -1)
            self._cursor(front)
        if self._settled():
            self._settle(front)

    def _settle(self, front: Front) -> None:
        """Start or A on a choice.

        The settling beep comes first and comes whatever the choice was: the
        original asks for it before it looks at what was settled, so the two
        players nobody answers for still make the noise. The screens that follow
        ask for it again as they go up, which is the original asking twice as
        well.
        """
        settled = front.step
        front.confirm()
        if front.step is ELSEWHERE:
            self._open_menu(front)
            return
        if settled is TITLE and front.step is TITLE:
            self.screens.play(sound.CONFIRM)
        if front.step is CARD:
            self._build()

    def _open_menu(self, front: Front) -> None:
        """The menu, opened past the eight the front end already has."""
        self.mode = MENU
        front.back()

    def _cursor(self, front: Front) -> None:
        """The noise the cursor makes, which **only the title's makes**: the two
        rows of the screen after it move in silence on the original."""
        if front.step is TITLE:
            self.screens.play(sound.CURSOR)

    def _screen_sound(self, front: Front) -> None:
        """What a screen asks for as it goes up, asked for once and not a frame.

        The step it is on is what says so, so nothing has to be remembered about
        how the game got here -- and the two waits a clock that ran out leads to
        are one tune between them, asked for at the first of them. **The results
        are the one screen the step does not settle**: they have a tune for a
        record beaten and another for a race that beat nothing.
        """
        step = front.step
        if step == self.screen_step:
            self.screen_frames += 1
            return
        self.screen_step, self.screen_frames = step, 0
        silence, sounds = SCREEN_SOUNDS.get(step, (False, ()))
        if step is RESULTS:
            sounds = (RESULTS_TUNES[front.record_set],)
        if silence:
            self.screens.play(SILENCE)
        for wanted in sounds:
            self.screens.play(wanted)

    def _beat_the_record(self, elapsed: int) -> bool:
        """Whether this time is under the record the card put on the screen.

        The card shows the board's best where there is one and the cartridge's
        own table where there is not (`front_draw.draw_card`), so the same two
        in the same order are what is beaten here. With no cartridge and an
        empty board there is no record to beat and nothing is claimed.
        """
        front = self.front
        if front is None or self.origin is not FRONT:
            return False
        shown = front.record
        if shown is None and self.rom is not None:
            shown = self.rom.record(front.course)
        return shown is not None and elapsed < shown

    def _green(self) -> None:
        """Take the card away and let the race have the window.

        The sound starts here and not when the race was built: the original is
        silent behind its card.
        """
        self.mode = RACING
        if self.audio:
            self.audio.start()

    def _update_ride(self) -> None:
        """A run on the screen: Start pauses, ESC leaves, and -- racing -- the
        engine steps on its own cadence, reading the pad as held each step. The
        countdown has a cadence of its own, and the sound's is neither."""
        if pyxel.btnp(pyxel.KEY_ESCAPE) or self._leaving_results():
            self.mode = self.origin
            self._silence()
            return
        if pyxel.btnp(START):
            self.mode = RACING if self.mode is PAUSED else PAUSED
            if self.audio:
                self.audio.pause(self.mode is PAUSED)
        if self.mode is RACING and self.ride is not None:
            self._race(self.ride)
        if self.audio:
            for _ in range(self.sound_cadence.tick()):
                self.audio.tick()

    def _leaving_results(self) -> bool:
        """A race off the menu ends on its own results, drawn over it, and Start
        is what leaves them."""
        return (self.origin is MENU and self.ride is not None and self.ride.over is not None
                and pyxel.btnp(START))

    def _race(self, ride: Run) -> None:
        if self.start_hold:
            # The original holds the start a while before anything steps.
            self.start_hold -= 1
        else:
            self._step(ride)
        if not ride.over or self.recorded:
            return
        # Once, the iteration the race is over.
        self.recorded = True
        if ride.over == FINISHED:
            self._finished(ride)
        else:
            self._ran_out()

    def _racing_front(self) -> Front | None:
        """The front end, when the race in hand was started from it."""
        return self.front if self.origin is FRONT else None

    def _finished(self, ride: Run) -> None:
        """The time taken, in seconds, to the course's board at the level ridden.
        And the window is the front end's again -- the results are a screen of
        its own.

        Whether it beat the record **the card showed** is the original's
        question and not "did the board take it": an empty board would take any
        time at all, and the card was showing the cartridge's own table. Asked
        before the board is offered anything, because offering it is what moves
        the number.
        """
        front = self._racing_front()
        record = self.play.keeps_records and self._beat_the_record(ride.elapsed)
        if self.play.keeps_records:
            (front or self.menu).finished(ride.elapsed / 100.0)
        if front is not None:
            front.over(record)
            self.mode = FRONT

    def _ran_out(self) -> None:
        """The clock ran out. The race stops where it is and the box goes over
        it, and **the board is not offered anything**: a run that ran out of
        clock was not completed. The original stops the sound here too, before
        the screen it goes on to."""
        front = self._racing_front()
        if front is not None:
            self._silence()
            front.ran_out()
            self.mode = FRONT

    def _step(self, ride: Run) -> None:
        """The frame's engine steps, the pad read as held for each.

        **On the cadence the race is in**: the original's main loop is slower
        counting down than racing. The sound's is neither -- its driver is on
        the timer at 64 ticks a second whatever the loop does -- so the engine
        idles audibly through the hold and the countdown alike.
        """
        held = 0
        for key, bit in PAD:
            if pyxel.btn(key):
                held |= bit
        cadence = self.countdown_cadence if ride.countdown else self.cadence
        for _ in range(cadence.tick()):
            ride.step(held)
            if self.audio:
                self.audio.cue(ride.cues, ride.revs, ride.hurrying)

    def _silence(self) -> None:
        if self.audio:
            self.audio.close()
            self.audio = None

    def _ride(self) -> None:
        """Start what FREE RIDE is pointing at, in the mode it is set to.

        No card and no results screen of the original's: the race starts at
        once, sound and all, and ends on its results drawn over it.
        """
        menu = self.menu
        self._start(menu.build(), menu.name, menu.level, menu.rival, menu.play, MENU)
        if self.audio:
            self.audio.start()
        self.mode = RACING

    def _build(self) -> None:
        """Build the race the card is about to sit in front of.

        Everything is in place before the card goes up -- the art in the bank,
        the clips primed, the run made -- so that the two seconds of card are
        where the work goes and the green is immediate. **The sound does not
        start here**: the original is silent behind its card, so `_green` starts
        it. The front end is the original's, so its races are too: classic.
        """
        front = self.front
        assert front is not None
        self._start(front.build(), front.name, front.level, front.rival, CLASSIC, FRONT)

    def _start(self, built: Ground, name: str, level: int, rival: bool, play: Mode,
               origin: str) -> None:
        """A race on `built`: its art, its clock, its sound, its rate.

        A course out of a cartridge brings its own art and clock and sounds with
        its own tune. A course of this game's own is drawn out of the terrain
        bank -- repainted in the cartridge's pictures when there is one -- and
        with a cartridge it still has the cartridge's bike, panel and sound,
        its tune one of the eight chosen by its name (`tune_of`); without one,
        it has this game's.
        """
        self._silence()
        self.origin, self.play = origin, play
        self.cadence = Cadence(play.steps, DISPLAY_FPS)
        cartridge = built.cartridge if isinstance(built, Course) else self.rom
        if cartridge is not None:
            art = graphics.video(cartridge)
            rom_art.install_art(functools.partial(graphics.pixels, art), art)
        else:
            rom_art.install_art(None)
        rom_art.install_cartridge(cartridge)
        if isinstance(built, Course):
            self.limit = built.cartridge.limit(built.number, level)
        else:
            self.limit = own_limit(built, level)
        self.ride = Run(built, self.limit, rival=rival, level=level, rules=play.rules)
        if cartridge is None:
            self.audio = OwnAudio()
        else:
            tune = built.number if isinstance(built, Course) else tune_of(name)
            self.audio = Audio(Mixer(cartridge, tune, clips=self.clips))
            self.audio.prime()
        self.recorded = False
        self.cadence.reset()
        self.countdown_cadence.reset()
        self.sound_cadence.reset()
        self.start_hold = START_HOLD

    def _update_menu(self) -> None:
        # Up and down move whatever the menu says is in hand -- the course or the
        # level -- and `Menu.move` is where that is decided, so the window does
        # not have to know there are two things on the screen.
        if pyxel.btnp(pyxel.KEY_DOWN, hold=MENU_HOLD, repeat=MENU_REPEAT):
            self.menu.move(1)
        if pyxel.btnp(pyxel.KEY_UP, hold=MENU_HOLD, repeat=MENU_REPEAT):
            self.menu.move(-1)
        if pyxel.btnp(pyxel.KEY_TAB):
            # Hand the arrows to the other one. Nothing walks it backwards, there
            # being two of them.
            self.menu.move_focus()
        if pyxel.btnp(pyxel.KEY_RIGHT):
            self.menu.move_across(1)
        if pyxel.btnp(pyxel.KEY_LEFT):
            self.menu.move_across(-1)
        if pyxel.btnp(START) and self.menu.tracks:
            # An empty drafts tab says how to fill it, and has nothing to ride.
            self._ride()
        if pyxel.btnp(SELECT):
            self.menu.toggle_rival()
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            # Back to the title that opened it, or -- with no front end, which
            # is `--ride` -- out of the game.
            if self.front is not None:
                self.mode = FRONT
            else:
                self._quit()

    def draw(self) -> None:
        if self.mode is MENU:
            menu_draw.draw_menu(self.menu)
            return
        if self.mode is FRONT and self.front is not None:
            self._draw_front(self.front)
            return
        if self.ride is None:
            menu_draw.draw_menu(self.menu)
            return
        ride_draw.draw_run(self.ride, paused=self.mode is PAUSED)

    def _draw_front(self, front: Front) -> None:
        """Whichever of the original's screens is up."""
        if front.step is SPLASH:
            front_draw.draw_splash()
        elif front.step is TITLE:
            front_draw.draw_title(front)
        elif front.step is CARD:
            front_draw.draw_card(front, self.limit)
        elif front.step is RESULTS and self.ride is not None:
            front_draw.draw_results(self.ride, front.record_set, self.screen_frames)
        elif front.step is TIMEUP and self.ride is not None:
            # The race is still what is on the screen: the box goes over it, and
            # blinks on what the wait has left.
            ride_draw.draw_run(self.ride, held=front.held)
        elif front.step is GAMEOVER:
            front_draw.draw_gameover()
        else:
            front_draw.draw_select(front)


def tune_of(name: str) -> int:
    """Which of the cartridge's eight course tunes a course of this game's own
    plays: one chosen by its name, so the same course always sounds the same."""
    return zlib.crc32(name.encode()) % COUNT + 1


def own_limit(built: Ground, level: int) -> int:
    """The clock a course of this game's own starts at the level ridden, in
    hundredths: the qualifying time its file gives, as the cartridge's courses
    have theirs. A course with none -- a draft, a rig -- rides with no clock to
    speak of."""
    limits = built.limits if isinstance(built, OwnCourse) else ()
    if not limits or limits[level] <= 0:
        return NO_LIMIT
    return round(limits[level] * 100)


def palette_wanted(argv: Sequence[str]) -> str:
    """The look after `--palette`, or the default one. A name there is no look
    for is refused saying which there are, rather than quietly shown in grey."""
    if "--palette" not in argv:
        return palette.DEFAULT_LOOK
    rest = argv[argv.index("--palette") + 1:]
    if not rest or rest[0] not in palette.LOOKS:
        raise SystemExit("--palette takes one of: %s" % ", ".join(palette.LOOKS))
    return rest[0]


def mode_wanted(argv: Sequence[str]) -> Mode:
    """The mode after `--mode`, or classic. A name there is no mode for is
    refused saying which there are."""
    if "--mode" not in argv:
        return CLASSIC
    rest = argv[argv.index("--mode") + 1:]
    if not rest or rest[0] not in MODES:
        raise SystemExit("--mode takes one of: %s" % ", ".join(MODES))
    return MODES[rest[0]]


def ride_wanted(argv: Sequence[str]) -> Listed | None:
    """The course file after `--ride`, as a listing of one, or none.

    Built in the vocabulary its place says (`read.vocabulary_of`), or the
    enhanced one when `--enhanced` says so -- which is how the editor hands over
    the copy it writes aside, whose place says nothing.
    """
    if "--ride" not in argv:
        return None
    rest = argv[argv.index("--ride") + 1:]
    if not rest:
        raise SystemExit("--ride takes a course file")
    path = rest[0]
    name = os.path.splitext(os.path.basename(path))[0]
    where = read.ENHANCED_VOCABULARY if "--enhanced" in argv else read.vocabulary_of(path)
    return name, lambda: read.course(path, where=where)


def rom_wanted(argv: Sequence[str]) -> str | None:
    """The file after `--rom`, if there is one."""
    if "--rom" not in argv:
        return None
    rest = argv[argv.index("--rom") + 1:]
    return rest[0] if rest else None


def open_cartridge(path: str | None) -> Cartridge | None:
    """The cartridge at `path`: none without one, and none -- said on the
    terminal -- if the file is not it.

    Apart from `cartridge_courses` because the cartridge is two things to the
    game, the courses and the sound, and it is opened once for both.
    """
    if path is None:
        return None
    try:
        return Cartridge.from_file(path)
    except (OSError, NotTheCartridge) as refused:
        print("cannot read %s: %s" % (path, refused))
        return None


def cartridge_courses(cartridge: Cartridge | None) -> list[Listed]:
    """The original's eight courses, for its own front end to choose from; none
    without a cartridge, and then the front end rides maps/courses/ instead."""
    if cartridge is None:
        return []

    # Mode 1: the one a single player's race starts in.
    return [("course %d" % n, functools.partial(_course, cartridge, n))
            for n in range(1, COUNT + 1)]


def _course(cartridge: Cartridge, number: int) -> Ground:
    return Course(cartridge, number, 1)


def selftest_wanted(argv: Sequence[str]) -> bool:
    """Whether `--selftest` was asked for. Same shape and the same reason."""
    return "--selftest" in argv


def selftest() -> int:
    """Load everything a player can reach, draw one frame, and say so.

    **This exists for the build.** A packaged executable that is missing a data
    file does not fail at startup -- it fails on the screen that first needs the
    file. Everything the bundle has to carry is named here instead: the palette,
    every tile (`assets.load_all` treats a missing one as fatal, which is the
    assertion this borrows), and every map on disk loaded. `tools/build_exe.py`
    runs it against the binary it just built.

    Headless, because the machine that asks the question may have no display.
    Returns a process exit code.

    """
    from game.render import headless

    headless.boot(chdir_to=__file__)
    import maps

    tracks = dict(maps.TRACKS)
    if not tracks:
        print("selftest: no maps in the bundle")
        return 1
    built = {name: build() for name, build in tracks.items()}
    pyxel.cls(0)
    print("selftest: ok -- %d maps, %d tiles" % (len(built), len(assets.names())))
    return 0


# Guarded, so that importing this file does not start a game.
#
# Safe for both ways in: `pyxel run main.py` goes through
# `runpy.run_path(..., run_name="__main__")`, and `python main.py` is a script.
if __name__ == "__main__":
    # First run out of a built executable: the parts the repo ships have to
    # reach the folder the player can write in. A no-op in a checkout, and a
    # no-op every run after the first. See `game/paths.seed`.
    paths.seed()
    if "--edit" in sys.argv:
        # The editor owns its own window, its own size and its own frame loop,
        # so it is handed the rest of the line and the game never starts.
        from tools.editor import ui
        sys.exit(ui.main(sys.argv[sys.argv.index("--edit") + 1:]))
    if selftest_wanted(sys.argv):
        sys.exit(selftest())
    # The sound's clips, in hand before the window opens rather than on a frame
    # the player is watching. Rendering them is about fifteen seconds -- the
    # eight tune renderings most of it -- so they are kept beside the game and
    # that is paid on a first run only. Said on the terminal, because fifteen
    # seconds with nothing on the screen looks like nothing happening.
    # Read before the sound is rendered, so a look there is none of says so
    # at once rather than after it.
    look = palette_wanted(sys.argv)
    rom = open_cartridge(rom_wanted(sys.argv))
    bank = Clips(rom, paths.user_path(SOUND_BANK)) if rom is not None else None
    if bank is not None:
        if not bank.kept():
            print("rendering the cartridge's sound; this is done once")
        bank.prime()
    ride = ride_wanted(sys.argv)
    App(cartridge=cartridge_courses(rom) if ride is None else (),
        rom=rom, clips=bank, look=look, ride=ride, mode=mode_wanted(sys.argv))
