"""The screens between one race and the next, as a model.

**This is the front end, and the menu is not.** The original chooses a course
on a screen of its own and then a level on the same one, names both on a card,
races, and ends on the results -- so that is the order here, with a cartridge's
eight courses or, without one, the same eight out of `maps/courses/`.
The front end rides them the original's way, in classic. `game/menu.py` is
FREE RIDE: the same eight and the author's drafts, in any mode. **The title has
a fourth row that opens it**, which the original's title has not -- with a
cartridge it is written in the cartridge's own lettering, under its three.

The game opens on a screen of its own -- the logo and whose game it is -- which
ends by itself and is the one screen Start gets past.

The title is where the way to play is chosen -- solo, against the computer, or
two players -- with the cursor walking the three and Start settling it. What
settling writes is not the cursor's number but a **word of bits**: a race is set
up, there is a second bike, and that bike is a person on the other end of a link
cable. Every screen after the title reads the word and not the cursor.

**Two players asks for the cable and gets no answer**, which is a state the
original has rather than one this game invented: it settles the choice, drives
the serial clock, sends a byte and waits, and when what comes back is its own it
puts the word to nothing and **goes back to the screen it opens on** -- measured,
not read. There is nothing to connect a cable to here, so that is what happens
every time.

Then one screen, two steps. The eight numbers and the three letters are both on the
screen from the start; left and right move whichever is in hand, wrapping at
either end as the original's do, and Start or A settles it. **Nothing goes
back**, which is the original's behaviour and not an omission.

The card is a wait and not a screen to do anything on: `tick` counts it down and
says when the race starts. Measured on the original, it is the same length at
every level and no button shortens it.

A race the clock runs out on ends in two more waits of the same kind: the box
blinking over the stopped race, and then `GAME OVER`. The original comes out of
them **at the screen it opens on**, not at the course, so this does too.

The scoreboard is here for the same reason it is in the menu: a race started
from here has to be offered to it, and the record on the card is read back out
of it. Both halves are `game/records.py`, and the two share one set of records
so that neither can go stale behind the other.

Pyxel-free, like the menu it stands in for.
"""

from collections.abc import Callable, Sequence

from game import records as scoreboard
from game.engine.terrain import Ground

#: Where the game is: on the screen it opens with, on the title, choosing a
#: course, choosing a level, on the card, in the race, on the results -- or in
#: the two the clock running out leads to.
SPLASH, TITLE, COURSE, LEVEL, CARD, RACE, RESULTS = (
    "splash", "title", "course", "level", "card", "race", "results")
TIMEUP, GAMEOVER = "timeup", "gameover"
#: ...or somewhere else: the title's fourth row settled, and the menu is up.
#: Not a screen of this model's, so the window takes it from here.
ELSEWHERE = "elsewhere"

#: The three ways to play, as the title offers them.
MODES = ("SOLO", "VS COMPUTER", "VS 2-PLAYER")
SOLO, VS_COMPUTER, VS_TWO = 0, 1, 2
#: The fourth row a title without a cartridge has: the menu of everything else.
MORE = "FREE RIDE"

#: What the original settles a choice of mode into, which is a word of bits and
#: not the cursor's number: a race is set up, there is a second bike, and that
#: bike is a person on the other end of a link cable. The three the title offers
#: are `1`, `1|2` and `1|2|4`.
SETUP, SECOND_BIKE, LINKED = 1, 2, 4
MODE_WORDS = (SETUP, SETUP | SECOND_BIKE, SETUP | SECOND_BIKE | LINKED)
#: ...and no race at all, which is what the word goes back to when one ends and
#: when the link is asked for and nobody answers.
NO_RACE = 0

#: The levels, as the original has them: A, B and C.
LEVELS = 3

#: Displayed frames the card is up. Measured on the original: 126 at every
#: level, and **no button shortens it** -- Start pressed on the card changes
#: nothing, so nothing here reads one.
CARD_HOLD = 126

#: ...and the screen the game opens with, which lasts longer and **does** give
#: way to Start: 261 frames on the original, and gone the frame after a press.
SPLASH_HOLD = 261

#: The clock running out is two waits and not a screen to do anything on: the
#: box blinks over the stopped race for this long, and then `GAME OVER` is up
#: for this long. Neither reads a button, as the card does not.
TIMEUP_HOLD, GAMEOVER_HOLD = 192, 128

#: The waits, in the order one leads to the next, and what each gives way to.
#: `RACE` is the odd one: it is not a screen, so `tick` says so rather than
#: going there quietly.
_HOLDS = {SPLASH: (TITLE, SPLASH_HOLD), CARD: (RACE, 0),
          TIMEUP: (GAMEOVER, GAMEOVER_HOLD), GAMEOVER: (SPLASH, SPLASH_HOLD)}

#: A course to ride: the name it is kept under and how to build it, which is
#: what `main.cartridge_courses` hands over.
Listed = tuple[str, Callable[[], Ground]]


class Front:
    """Which screen is up, what is chosen on it, and the scoreboard behind it."""

    def __init__(self, courses: Sequence[Listed], levels: int = LEVELS,
                 records: scoreboard.Records | None = None,
                 path: str | None = None, more: bool = False) -> None:
        self.courses = list(courses)
        #: What the title offers: the three ways to play, and the door to the
        #: menu when `more` asks for it.
        self.rows = MODES + (MORE,) if more else MODES
        self.levels = levels
        self.step = SPLASH
        #: The course as the original counts them, from one.
        self.course = 1
        self.level = 0
        #: Which of the three ways to play the title's cursor is on.
        self.mode = SOLO
        #: ...and what settling it wrote: the original's mode word, which is
        #: what every screen after the title actually reads.
        self.mode_word = NO_RACE
        #: Whether the race just ridden beat the course's record, which is what
        #: the results say and what they play. Cleared as each race is set up,
        #: as the original clears it before it composes the screen.
        self.record_set = False
        #: Frames the screen in hand has left, where it is one that ends by
        #: itself: the opening screen, the card, and the two waits a clock that
        #: ran out leads to.
        self.held = SPLASH_HOLD
        # A path a test can point elsewhere, as the menu takes one: a test that
        # wrote the real scoreboard would be scribbling on the player's times.
        self.path = scoreboard.PATH if path is None else path
        self.records = scoreboard.load(self.path) if records is None else records

    @property
    def rival(self) -> bool:
        """Whether the computer's bike is in the race.

        A second bike that is **not** somebody else's, which is the original's
        own test and not a number: two of the three modes put a bike beside
        yours and only one of them drives it.
        """
        return self.mode_word & (SECOND_BIKE | LINKED) == SECOND_BIKE

    def linked(self) -> bool:
        """Whether a second Game Boy answered on the link cable, which is no.

        The original does not treat two players as unreachable: it settles the
        choice, writes the mode word, drives the serial clock and sends a byte,
        and only when what comes back is its own does it give up -- putting the
        mode back to nothing and **the game back to the screen it opens on**.
        So nobody at the other end is a state the original has, and this is
        that state rather than a screen this game has not written.

        Measured on the original with no cable attached: settling SOLO leaves
        the mode word 1 and the game on the screen a course is chosen on,
        VS COMPUTER leaves it 3 and the same screen, and VS 2-PLAYER leaves it
        0 and the game back on the opening screen, 263 frames of it before the
        title comes round again -- which is the opening screen's own length and
        not a wait of its own.

        There is nothing to connect a cable to here, so this is the answer
        every time. It is a method and not a constant because what it stands
        for is a question asked of the outside, not a fact about this game.
        """
        return False

    @property
    def numbers(self) -> list[int]:
        """The courses, by the number the original knows each by."""
        return list(range(1, len(self.courses) + 1))

    @property
    def name(self) -> str:
        """What the scoreboard keeps this course's times under."""
        return self.courses[self.course - 1][0]

    @property
    def best(self) -> float | None:
        """The time to beat on the course and level chosen, in seconds."""
        return scoreboard.best(self.records, self.name, self.level)

    @property
    def record(self) -> int | None:
        """...and in hundredths, which is what a screen writes."""
        best = self.best
        return None if best is None else int(best * 100)

    def move(self, step: int) -> None:
        """Along whatever is in hand, wrapping at either end.

        Wrapping because the original wraps: eight back to one, C back to A, and
        the three ways to play round as well.
        """
        if self.step is TITLE:
            self.mode = (self.mode + step) % len(self.rows)
        elif self.step is COURSE:
            self.course = (self.course - 1 + step) % len(self.courses) + 1
        elif self.step is LEVEL:
            self.level = (self.level + step) % self.levels

    def confirm(self) -> None:
        """Start or A: settle what is in hand and go on to the next thing.

        From the results it starts the round again, at the course -- which is
        where the original goes back to.
        """
        if self.step is SPLASH:
            # The one screen a press gets past: the original lets Start through
            # it and holds every other screen for as long as it holds it.
            self.step = TITLE
        elif self.step is TITLE and self.rows[self.mode] is MORE:
            self.step = ELSEWHERE
        elif self.step is TITLE:
            # The mode is settled into the word every screen after this one
            # reads -- and where it asks for the cable, the cable is asked. The
            # original waits for a byte from the other end and, getting its own
            # back, puts the word to nothing and stays on the title. So does
            # this: the third row is not a dead end, it is a call nobody picks
            # up.
            self.mode_word = MODE_WORDS[self.mode]
            if self.mode_word & LINKED and not self.linked():
                self.mode_word = NO_RACE
                self.step, self.held = SPLASH, SPLASH_HOLD
                return
            self.step = COURSE
        elif self.step is COURSE:
            self.step = LEVEL
        elif self.step is LEVEL:
            self.step = CARD
            self.held = CARD_HOLD
            self.record_set = False
        elif self.step is RESULTS:
            self.step = COURSE
            # ...and the race is done with: the original puts the mode word
            # back to nothing as it leaves this screen.
            self.mode_word = NO_RACE

    def tick(self) -> bool:
        """A frame of a screen that ends by itself. True the frame a race starts.

        Four of them do -- the opening screen, the card, and the two the clock
        running out leads to -- and only the card's end is a race, which is why
        one of the four is the answer and the other three are not.
        """
        if self.step not in _HOLDS:
            return False
        self.held -= 1
        if self.held > 0:
            return False
        self.step, self.held = _HOLDS[self.step]
        return self.step is RACE

    def over(self, record: bool = False) -> None:
        """The race is done: the results are what is on the screen now.

        `record` is whether the time just ridden beat the record **that the card
        showed**, which is the original's own question: it compares against the
        table the card was written from, and only a bike that reached the line
        is compared at all. It decides two things and they are the same thing --
        a line on the screen, and which of the two tunes the screen plays.
        """
        self.step = RESULTS
        self.record_set = record

    def back(self) -> None:
        """Back from the menu the fourth row opened, to the title it left."""
        self.step = TITLE

    def ran_out(self) -> None:
        """The clock ran out: the box goes over the race it stopped.

        The original makes one thing of the two that follow -- the blinking box
        and then `GAME OVER` -- and comes out of them at the screen it opens on
        rather than anywhere nearer, so that is where `tick` walks from here.
        **Nothing is offered to the scoreboard**, which is the rule `finished`
        states: a run that ran out of clock was not completed.
        """
        self.step, self.held = TIMEUP, TIMEUP_HOLD
        self.mode_word = NO_RACE

    def build(self) -> Ground:
        """The chosen course, built when it is asked for."""
        return self.courses[self.course - 1][1]()

    def finished(self, elapsed: float, score: int = 0) -> bool:
        """Offer a finished race to the scoreboard, and write it through.

        The same two halves and the same rule as the menu's: **only a finish is
        offered**, because a run that ran out of clock has no business on a board
        of things that were completed.
        """
        if not scoreboard.put(self.records, self.name, self.level, elapsed, score):
            return False
        scoreboard.save(self.records, self.path)
        return True
