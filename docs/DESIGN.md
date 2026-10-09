# bmx-80 — Design

**This document is the design contract.** It is what to check first when in doubt about intended
behaviour: the map model, the engine, the menu and the art. `AGENTS.md` is the shape of the repo;
this is the shape of the game.

Two things it is not. It is not a tutorial — `README.md` runs the game and says how a course is
written. And it is not a record of how any of this was arrived at: every claim below is in the
present tense and is true of the code as it stands, so a statement here that the code contradicts is
a bug in one of the two.

---

## 1. The screen

| Parameter | Value |
|---|---|
| Resolution | 160x144 |
| Display | 60 fps (`DISPLAY_FPS`) |
| Colours | 4 shades, in palette slots 0-3 |
| Terrain grid | 8px tiles (`TILE`) |
| Glyph grid | 16px cells (`CELL`) |

The window and an engine run at different rates. The window draws at `DISPLAY_FPS`; an engine steps
at its own rate, and `game/cadence.py` says which displayed frames step, so the original game's rate
— about 41 steps for every 60 frames — can be reproduced rather than rounded.

### Controls

**The Game Boy's pad, laid on a keyboard the way two hands held it**: the left hand on the cross,
the right on the buttons.

| Game Boy | Key | In a run |
|---|---|---|
| ↑ ← ↓ → | W A S D | Up picks a jump's class; Left and Right turn the bike in the air, Left starts a wheelie |
| A | K | the throttle |
| B | J | a nitro |
| Start | Enter | start, pause |
| Select | Space | on the title, the next way to play; on the menu, SOLO or VS COMPUTER |
| | Esc | out of a race; from the menu back to the title; from the title out of the game |

On the front end the arrows (or the cross) walk the title's rows, the eight courses and the three
levels, and Start or A settles each. On the menu: ↑↓ and ←→ move whichever of the course and the
level is in hand, Tab hands them over, Enter rides.

### A run (`game/engine/run.py`, `game/render/ride_draw.py`)

The engine steps **41 times for every 60 frames** (`Cadence(41, 60)`), the original's own rate.
Each step is an iteration of the original's main loop: the pad is read as held, and a button is
new when it was not held on the iteration before -- so a tap shorter than an iteration can be
missed, as in the original. The bike waits 48 iterations on the grid (x 32, y 232), idling;
the throttle held through the countdown leaves at once. The run is over at the line (x 8064).

**The countdown's iterations are slower**: the original's loop runs **18 for every 60 frames**
(`Cadence(18, 60)`) before the green against 41 after it, and holds the first for **54 frames**.
Nothing physical happens in those iterations -- the clocks are stopped and the bike idles -- so
the rate is the whole of what the start sounds like: the three beeps and the go 27 frames apart
rather than 12.

**Two clocks**, in hundredths of a second: the race's time counts up and the time left counts
down, **two hundredths a tick** -- about 41 ticks a second, so the original's second is a little
slower than a real one. Both stop in the countdown and once the game takes the bike over past the
line. The time left starts at the course's qualifying time for the level -- read from the
cartridge, or from a course file's `limits`; a course with none has ten minutes -- and at nothing
the race is lost.

**The things on the course** (`items.py`): S (the cap to 111), T (ten seconds), N (four nitros),
R (no slope term), J (a nitro anywhere in a flight, nose up), and mini-maniacs (up to three). The
J and the mini-maniacs are secrets, not in the map and only picked up upside down. A thing is
picked up within 15 px of its metatile's corner either way, the bike's x taken within the lap; a
crate taken is gone from the map. A crash loses the S, the R, the J and the mini-maniacs.

**A secret taken leaves a flourish**, and it is the only thing that says one was there: a sign of
four tiles above the bike -- the letter `J`, or a little bike for a mini-maniac -- which **rises a
pixel an iteration** for sixteen of them and is gone. Without it the jet arrives out of a clear
sky, a secret being invisible and taken upside down, which is why the original draws it.

**The mini-maniacs ride behind the player**, one to three of them, and **each is the player a few
iterations ago**: the bike keeps a trail of the last sixteen places it has been -- x, y and the
pose it was in -- and they sit five, seven and nine back on it. So they follow the line the player
took rather than chase the bike, and they bunch up where the player slowed down. **Nothing goes on
the trail while the bike is standing still**, which is what stops the three of them piling up on
it. Only the player keeps one; the computer's bike never has any. Their tiles are the cartridge's
own little-bike alphabet, one per direction with a mirror bit for the far half of the circle --
and they are **sprite tiles below 128**, which the bank cannot name, so they are drawn out of a
small image beside it (`rom_art.sprites`).

**The lines**, on x to the 16 px: at 4016 the one lap left is counted off, every crate comes
back and the sign over the finish goes up; at 8064 the game holds the throttle; at 8112 it takes the bike over, riding or flying, for 64
ticks -- in the air nosing it up and through the rider's flourishes -- and from 8192 on the ground
the bike celebrates, a wheelie at 45 degrees, until the race is over. A finish is offered to the
board with the race's time.

**The computer's bike** (`rival.py`), when the menu's Select picked VS COMPUTER: the same bike and
the same tick, stepped right after the player's, driven by rules rather than a pad. It holds the
throttle and Up, and Left in the air heading left with the nose not level. Just ahead of the player
-- within 64, 128 or 240 px by level -- it is at its best: cap 119, the R, and it lands however it
comes down; further ahead it is held back to cap 79, no R, its landings checked and no Up. 48 px or
more behind, it is put back just off the left of the screen on a stretch of the course's own table
(read from the cartridge), never further back than it is. It picks nothing up and loses nothing
when it crashes, and it starts with 255 nitros.

**The camera** (`camera.py`) is the original's: once an iteration, before the physics, it moves by
the player's velocity of the iteration before -- sideways always, up or down only from the half of
the screen the bike is leaving -- and its y stays within 0..128 px. It follows a snap onto a
right-hand wall, and stops once the bike celebrates past the line. Its x is exact; its y is exact
but on the odd tick where the original drew the bike a frame late.

**What the screen shows of the course is the background, not the map** (`background.py`). The
original fills its 256 px of background a tile column at a time as the view scrolls, and reads the
map for a column only then; a column on the screen keeps what it had until the view has gone a
whole background on. A crate taken is written through -- it is blanked on the screen as its cell is
emptied -- and nothing else is: the crates put back and **the sign over the finish, written at the
lap line just past it, are not seen until the player comes round to them.**

A course from a cartridge is drawn **in the cartridge's own art**: its background tiles are read
the way the game loads them at race start (`game/rom/graphics.py`) -- **three lists of loads**,
each entry a copy, an inversion, a mirror top to bottom, left to right or both, or a one-bit shape
expanded into the shades its count names -- and put in an image bank of their own. Three, because
a race is drawn out of whatever is in tile memory when it starts and the game has been through the
lettering and the title on its way there: each list writes over what it needs and leaves the rest
of the one before it standing, and one tile of scenery a course draws comes from the title's list
and nowhere else. Without art, a course
is drawn **as its collision**: sky, level ground, slopes and sand in the four shades. The bike's 16x16 picture has its
top-left corner at the bike's position, measured on the original; the view is 128 px tall and the
band below is the HUD's.

---

## 2. The engine

**The engine is a reimplementation of the original game's**: integer arithmetic, the original's
tick order, and terrain read as tiles. It rides the original's courses, read out of the player's
cartridge, and this game's own maps, which are built in the same shape.

It lives in `game/engine/`, and it is **rules, not tables**: where the original looks a number up,
the engine computes it, and no literal table is allowed in the package.

**The rules and the numbers are apart.** Every number the engine runs on is the original's, and
every one is in `game/engine/original.py`, named and grouped: the machine's word sizes, the map's
geometry, the speed curve, the jump classes, the crash's 57-tick script, the lines, the clocks, the
rival's handicap, the camera. The other modules are the rules -- how a bike rides, flies, crashes
and races -- as an engine written from scratch would have them, and
`tests/test_engine_is_rules.py` refuses a number past two anywhere but that file. A mode moves a
few of them through a `Ruleset` (`rules.py`). `tests/test_engine_golden.py` holds the engine to a
record of six races, iteration by iteration, so moving code cannot move a ride.

### Units

A **position** is 8.8 fixed point in y and 16.8 in x, in pixels, y growing downward. A **velocity**
is in 1/256 px per tick. A **direction** is one of 32, counter-clockwise from the right: 0 is right,
8 up, 16 left, 24 down.

### Speed (`speed.py`, `vector.py`)

Speed is an **index**, 0 to 144, turned each tick into a **magnitude** and then into a velocity.

- **The index.** The throttle walks it up two a tick to the **cap** (79; 111 with an S), releasing it
  walks it down two a tick to 0. It never goes below 0, so **the bike never rolls back**. A **nitro**
  -- on a press, with one in hand -- sets it to 144 and holds it there sixteen ticks; then it comes
  down two a tick, throttle or not, to the cap. A press with none in hand spends the tick on nothing.
  The state picks the rule first: the celebration after the line sets 32, a crash tumble 8, a bike
  down 0, and in the air the index is the flight's.
- **The curve.** `curve(index)` is 8 per step to 2, 16 per two steps to 7, `36 + 2i` to 15, then two
  every four indices to 112; from 112 up the index is its own value. 98 at the cap, 112 with an S.
- **The slope term**, set while riding and spent by the next tick's magnitude. Soft ground sets it
  to -56. Then, unless the R is held, the direction walks an accumulator: level empties it; climbing
  (1-7) takes it down two a tick, resting at -34; descending (24-31) takes it up two a tick to 32;
  walls and ceilings (8-23) leave it -- **there is no gravity on a wall**. Steepness never enters.
- **The magnitude** is `curve(index) + term`, held to 0..144.
- **The velocity**: `((magnitude >> 1) * sine(i)) >> 4` and the same with `sine(63 - i)`, `i` the
  angle inside the quadrant, swapped and signed by the quadrant. The quarter sine is
  `min(255, round(256 sin))`. Level ground at full speed is 780, with an S 892, with an S on sand
  446 -- the original's own three measured values, to the integer.

### The ground (`terrain.py`, `probes.py`, `bike.py`)

The engine sees the ground as **tiles, never as geometry**. A course answers the engine's questions
(`Ground`): chiefly the metatile at a cell of its map, the four tiles of a metatile, the collision of
a tile -- solid, soft, no wheelie, and **the direction of travel on it** -- and which cells of the
window around the bike are probed for each direction; and besides those, its rocks, its crates, its
teleports, the thrown rider's arc, and a cell changed when a crate is taken.

- **The window** is the 3x3 metatiles around the bike as 6x6 tiles: from one metatile row above
  the bike's, and from its own column on.
- **The probes**: three floor cells for the direction of travel, so they rotate with it -- under
  the wheels on the level, to the right up a wall, above on a ceiling -- the cell beside the third,
  two for the attitude, and four fixed cells. A cell moves one row down when the bike is in the
  lower half of its metatile and one column left in the left half. Which three cells per direction
  is the ground's to say: the original's are a hand-made table, and a course read from a cartridge
  hands over the cartridge's.
- **Following the ground** (riding): when the third floor probe is solid, its direction becomes
  the bike's direction and attitude. **That is the whole of how the bike follows terrain**, and why
  a loop is a rail: its tiles carry wall and ceiling directions, and there is no gravity on a wall.
  On the level the bike is put back on the 8 px grid with no vertical velocity; up a right-hand
  wall on it with no horizontal one; on a ceiling up to the next line. Climbing a wall, a tile that
  would lay it back on the level is not taken.
- **Taking off**: with nothing solid under the wheels -- on the level, the second probe; up a 45,
  the cell beside the third; otherwise the first two -- the bike takes off. The jump's class is two
  for a fast index (112 and up) plus one for Up held, or four in the automatic modes; it hangs twice
  its class in ticks.
- **The states that stand still**: stopped, a wall or ceiling direction is a crash; in the
  countdown the bike shivers one pixel up and down. Riding on the level, Left starts a wheelie if
  the cell above is clear and the tile allows it, and sand is read only on the level.
- **A rock** is a tile the ground names (`Ground.is_rock`): under the rider on the level, a crash; under the computer's bike, a hop.

A tick is: the index, the world ceiling, the magnitude and velocity (not falling, not in the
countdown), the state's step, the window and probes, the collision response, and the move.

### The air (`flight.py`, `bike.py`)

**There is no gravity.** A bike leaves the ground in a straight line and its direction of travel
turns towards straight down a step or two at a time; it falls in a straight line.

- **The jump's class**, fixed at take-off: 2 for a fast index (112 and up: a nitro's, or an S's) plus
  1 for Up held; 4 in the automatic modes. It **hangs** twice its class in ticks, speed and direction
  frozen. Then each tick the index drops -- 8 a tick for the slow jump, 4 for the others, 2 for the
  automatic one, lifted to 34 first if it is under 32 -- and on every tick (slow), every other
  (the others) or every fourth (automatic) of the main loop's counter the direction turns: heading
  left up to straight down (24); heading right the other way round, to 25 or 26 and no further.
- **The rider turns the bike, not the flight**: Right noses it down a step a tick, else Left noses
  it up. The direction of travel goes its own way.
- **A nitro in the air**: on the tick after the take-off, or with the J and the nose up (attitude
  0-6). It re-aims the flight along the nose and hangs it eight ticks.
- **The landing**: a solid cell above the bike that is level or the top of a slope is a head-first
  crash. Otherwise the first of the second attitude probe, the first, and the third floor probe to
  touch solid is the surface, and **the bike lands if its attitude is from 5 steps behind the
  surface's direction to 7 in front** -- the same window for every surface -- taking its direction,
  snapped to the grid, riding again. Outside the window it crashes. The computer's bike in its fast
  setup, and any bike in the automatic modes, lands whatever its attitude.
- **A crash starts by what is under the bike**: with nothing under it, a straight fall; level
  ground (or the top of a slope), down on the ground for 57 ticks; a slope, a tumble heading the way
  it slopes -- a climb as its direction plus 32, which is how the tumble tells the two apart.
### A crash, and coming back (`bike.py`)

- **Falling**, the bike keeps the velocity the crash gave it -- straight down -- until a cell under
  it touches ground, and there it tumbles.
- **Tumbling**, it turns end over end, two steps a tick, following the ground under it: a climb's
  tumble travels with its direction plus 32, which moves as half a turn back -- down the slope the
  wrong way round. A rock's tumble spends eight ticks in the air first. When both cells under it
  are level and its direction is level, it is **down**.
- **Down** is 57 ticks of the rider's story, told with the position: the items are lost (the S's
  cap, the R, the J) and the place is remembered; the rider is thrown along an arc the ground hands
  over (the original's is hand-made, read from the cartridge), lies, gets up and walks back; the
  place is restored; and the bike is stopped there, on the 8 px grid. **The bike comes back where it
  came to rest** -- which in the original is always on ground, because a crash only goes down once
  it is on the ground and the original has ground everywhere. The attitude carries the rider's
  pictures meanwhile, which is why it passes 31.
- **A hole** is not the original's problem, and the engine does not handle one: the original has
  ground everywhere, and a map with a hole in it is this game's own.

- **A wheelie** starts riding on the level with Left held, if the cell above is clear and the tile
  allows it. Held, the nose comes up a step every other tick, on the level only; at 90 degrees it
  is a tumble -- on level ground, down on the same tick. Released, the nose comes down a step a
  tick to the direction of travel and the bike rides again. Sand still costs 56; the slope is not
  read.
- **A wheelie's ground check runs on the tick riding starts one**: with the third probe on solid,
  it ends there -- which on the level is the lower half of a metatile.

### Modes (`game/mode.py`, `rules.Ruleset`)

The engine's numbers are the original's and fixed. **A mode is a value handed to a race, never an
edit to the engine**: a `Ruleset` -- the few numbers another way of playing may move: the two caps,
the index step, the nitros at the start and the landing window -- and the rate the engine steps at.

- **classic** is the original: `rules.CLASSIC`, about 41 steps for every 60 frames.
- **excessive** is the same race sooner: classic's rules, stepped at the display's rate, 60 for 60.
  Every course is ridden iteration for iteration as in classic, so anything that can be finished
  there can be finished here; what it asks for is a thumb good to 17 ms rather than 24. The clocks
  count iterations, so a qualifying time means the same race in both, and the board keeps
  classic's records only.

It is chosen on FREE RIDE (§4), and `python main.py --mode excessive` starts the menu on it; the
front end always plays classic. Whether a course can be finished under a ruleset, and
how exactly it has to be ridden, is measured by searching the pad -- `tools/solve.py`.

### The original's courses (`game/rom/`)

The engine rides tiles, and a course can come from two places: this game's own maps, or the
original's, read out of **the player's own cartridge file**. `game/rom/` carries nothing out of
the cartridge: it knows where the original keeps a course and how to read it, and reads the
European release only -- identified by its SHA-1, and anything else refused with a sentence saying
which check failed.

- **A course** is a map of 16 rows by 256 columns of 16x16 **metatiles**: 4096 px, one lap, and a
  race is two laps of it. A metatile is four tile ids, 2x2.
- It is **built the way the original builds it at race start**: a list of prefab pieces stamped in
  order, then the crates as metatiles of their own. Where two overlap they are merged tile by tile,
  and a merge that is new becomes a metatile of its own -- looked up the way the original looks it
  up, reading past its table into the map, because that is what the original reads.
- **Each tile id has a collision byte**: solid, soft, and the direction of travel on it, which is
  what the engine reads (`game/engine/terrain.Hit`).
- **The sign over the finish is the one thing a race changes about a course.** Crossing the lap
  line puts every crate back and puts `GOAL` up, in the hollow at the top of the mound the finish
  sits on -- so it is not there the first time round, and seeing it is how a player knows this lap
  is the last. Two metatiles written straight in, and **neither has any collision**: it is scenery
  and cannot be ridden into. The engine knows only that the lap line was crossed; what the sign is,
  and whether a course has one, is the course's own (`Ground.goal`).

What the reader does is tested here on cartridge-shaped files of a few dozen bytes. That it rebuilds
the original's eight courses byte for byte is checked against the real cartridge, where one exists.

### The original's panel and its start (`game/rom/panel.py`)

The bottom sixteen pixels are the Game Boy's **window**: two rows of twenty tiles, held in
memory and copied to its map every frame. A course out of a cartridge gets that panel, composed
the way the original composes it and drawn in the cartridge's art. **Without a cartridge the same
panel is drawn from nothing** (`ride_draw._write_band`): the same things in the same places, a
rising row of bars for the speedometer, `TIME` and its bar, `TIRE`, `JET`, `NTR` and a canister a
nitro; the start's `3 2 1 GO!` in this game's lettering where the three sprites would be; and the
computer's bike a shade lighter, which is what the second palette does to it.

- **The speedometer** is most of it: a needle of two tiles by the speed's magnitude, six tiles
  of bar read from the cartridge's own two tables -- stepped every four magnitudes below 48 and
  every eight above -- and two more where the cap is, so **an S crate is read off the panel as
  the bar growing longer**.
- **TIRE** and **JET** show while an R or a J is held, and nothing where they are not.
- **TIME** is a bar and not a clock: the seconds left, eight levels to a tile, capped at
  fifty-five -- so a race that starts with minutes on it starts with the bar full and standing
  still. It is written eight tiles into a row with seven left, and the last is off the screen.
- **NTR** is a canister a nitro, up to eight.

**There is no clock and no lap counter on it**, because the original has neither. The labels
and the ground they sit on are painted out of the cartridge as well, by the same little program
the original paints them with.

**The clock running out** stops the race and ends it, and the end is two waits and no button.
First a box over the view: nine tiles by three of one of the cartridge's own, with `TIME UP` in
its middle row a tile in from each side, over the race left standing where it stopped. The words
**blink on the frames the wait has left** -- eight on and eight off -- and not on the race's own
counter, which has stopped with the race. Then the screen goes and `GAME OVER` is written in the
middle of nothing, in the lettering every screen between races is written in. Then **the game is
back at the screen it opens on**, which is where the original goes and not anywhere nearer. The
waits are `front.TIMEUP_HOLD` and `front.GAMEOVER_HOLD`, and neither reads a button, as the card
does not. **Nothing is offered to the scoreboard**: a run that ran out of clock was not
completed. The fade the original puts between the two is not drawn.

**A pause draws nothing at all**: the original stops, and the sound is what tells you.

**The start** is three sprites in the middle of the view: nothing, then three, two, one, then
`GO!`. They change on the iterations the countdown beeps on (`run.BEEPS_AT`, `run.GO_AT`) and
not on a clock of their own, so the digit and the tone land together. Their tiles come out of
**the game's lettering**, which is loaded before a race is set up and left standing by it --
`graphics.video` runs both lists, because the digits are in the lettering. A sprite
counts its tiles from `$8000`, so its 128 to 255 are the background's ids of the same number,
which is why these three need no reading of their own.

**The barrier** stands on the grid with them, sixteen pixels along from where the bike starts and
eight down, and it is **the one sprite anchored to the course rather than to the screen**: it
stays where it stood while the bike rides away from it, and the original drops it the moment the
camera has carried it off the left. It **falls rather than lifts**, and it falls at the very end:
one tile of three, standing until the countdown has an iteration left, half down on that one, and
flat on the ground from the go onwards. A course of this game's own maps gets a bar of the same
three heights instead.

### The original's screens (`game/rom/screen.py`)

Between races the original shows screens, and **each is a little program in the cartridge**: an
address in its tile map and then the tiles to write there, `$FE` for another address and `$FF`
for the end. So a screen is cloned by running its program, and there is no lettering to decode
and no table to carry -- the words are tile numbers where the cartridge keeps them. The same
interpreter paints the panel's labels, at an address in memory rather than in the map, and
**running a program with its flag clear writes the blank tile instead**, which is how the
original takes a screen away again.

The cursor walks the row it is in and comes back to that row's start rather than running into
the next.

**With a cartridge the original's screens are the front end and the menu is not**: `--rom` starts
the game on the screen a course is chosen on, and a race ends on the results and goes back round
to it. The menu stays what it was, the door to this game's own maps, for a run with no cartridge.
`game/front.py` is the model of that -- which screen is up, what it chose, and the board behind
it -- and it is Pyxel-free like the menu it stands in for.

**The screen the game opens on** is the publisher's, and it is the one screen a press gets past:
it lasts 261 frames, measured, and Start takes it away the frame after it is pressed. Its drawing
is kept in the cartridge as bytes rather than as a list of loads, which is why the art it is
written in is its own. Without a cartridge this game says the same kind of thing about itself.

**The title** is the next of those screens: the drawing, whose game it is, and the three ways to
play -- SOLO, VS COMPUTER, VS 2-PLAYER -- with a cursor the pad walks and Select cycles, as the
original's does. Settling one writes **a word of bits** and not the cursor's number: a race is set
up, there is a second bike, and that bike is a person on the other end of a link cable -- so the
three rows are `1`, `1|2` and `1|2|4`, and every screen after the title reads the word. The
computer's bike is the second bit without the third, which is the original's own test.

**The third row asks for the cable and nobody answers.** It is not a missing screen: the original settles the choice, drives the serial clock, sends a byte and waits, and when
what comes back is its own it puts the word to nothing and **goes back to the screen it opens
on**. Measured on the original with no cable attached: SOLO and VS COMPUTER leave the mode word 1
and 3 and the game on the screen a course is chosen on; VS 2-PLAYER leaves it 0 and the game back
at the beginning, for the opening screen's own 261 frames and then the title. There is nothing to
connect a cable to here, so that is what happens every time -- the beep that settles a choice, and
then round to the start with no race set up behind it.

**A fourth row is this game's**: FREE RIDE (§4), written under the three in the cartridge's own
lettering and at its pitch (`screen.free_ride`), the cursor a row further down. Its letters are
tiles the title's lettering already holds; the F is the one no word of the original's title uses.
Settling it writes no mode word: it leaves the original's screens for the menu.

The title is painted by **the cartridge's other painter** (`paint_runs`): counts rather than
tiles, where a count with its top bit clear is one tile that many times, the count `$80` alone is
a tile and a length with the tile going up by one as it goes -- which is how a whole logo is a
handful of bytes -- and any other count is that many tiles each its own. **Its cursor runs on into
the row below** where the first painter's comes back to its own row's start, which is the whole
difference between a drawing and a row of words.

**One screen and two steps** chooses the course and then the level: the eight numbers and the
three letters are both on it from the start, left and right move whichever is in hand and wrap at
either end, and Start or A settles it. Choosing the course takes the other seven numbers away --
the original blanks that row and writes the chosen one back where it stood. Nothing goes back,
which is the original's behaviour and not an omission.

**The card and the results** are the other two screens. With the computer's bike in the race the
results carry its line under the player's, and **its clock is its own**: the two bikes reach the
line at different moments, and the race ends when the player does -- so the usual end of a race
against it is its line saying `LOST`, which is the cartridge's own word for a bike that never got
there. The card comes before a race, for the
two seconds the original shows it and no less -- no button shortens it: the course's number and
the level's letter are a tile each written into a program that leaves room for them, and under
them the course record and the time to qualify. The results end a race, the band and the course
gone: the banner and the words are the program's, and the time is written in.

**A record beaten puts a line on them.** The record is the one the card showed -- the board's
best where there is one and the cartridge's own table where there is not -- and only a race that
reached the line is compared against it at all. The line is the cartridge's own, `IT'S A RECORD!`,
and it **blinks**, on the same count of displayed frames and the same bit of it the `TIME UP` box
blinks on.

Either time is five digits of the cartridge's own written along a row, **stepping over the two
colons the program has painted already**.

**`GAME OVER` is the screen a race the clock ran out on ends on**, and it is the one screen with
nothing written into it: two words in the middle of an empty screen, and no time, no course and
no banner. The results are where a race that finished goes; this is where the other kind goes,
and it goes on to the screen the game opens with rather than back to the course.

The record on the card is the player's own where there is one. Where there is not, the original
has one anyway: it keeps no times between one switch-on and the next, so it ships a table of them
and shows those until a race beats one, and this reads that table rather than inventing a blank.

A race of this game's own maps gets the same card written in this game's own lettering, with the
course's name where the original has a number and a dash for a record nobody has set.

The lettering a screen is written in and a course's art **cannot both be in the bank**: the
race's list of loads writes over most of the lettering, and Pyxel has three image banks and this
game uses all three. A course's art is not wanted once its race is over, so the results take the
bank and the next race takes it back.

### The original's sound (`game/rom/sound.py`, `apu.py`, `mixer.py`)

A course out of a cartridge sounds as the original does, and the sound is the cartridge's own:

- **The race says when** (`rules.Cue`): the countdown's three beeps and its go; a nitro, or B
  with none; a thing picked up; riding sand, every third iteration; every eighth tick of a
  tumble; a crash that falls or goes down; and the take-over line, which silences everything
  for its fanfare. Only the player's bike is heard. **The engine** is a sound that never ends,
  pitched every iteration by `Speed.revs`: the curve's value, or the index where no magnitude
  is taken (so it revs in the countdown).
- **The original's driver decides what**: run live at its own 64 ticks a second, on the
  cartridge's streams, with its priorities and its seven slots over the chip's four channels.
  An effect on a pulse channel silences what the music or the engine had there, and gives it
  back when it ends.
- **The chip turns it into sound** (`apu.py`): two pulse channels, a wave and a noise channel,
  with their envelopes, sweep and lengths. What plays is a clip per sound and channel, rendered
  once through it; the engine, a two-tick loop for each speed it reaches.
- **The panning is the cartridge's too, and mono is a fold.** The driver throws notes to one
  side or the other, and **the cartridge uses that as an arrangement**: the music the screen a
  course is chosen on plays is centred for five sixths of itself and then throws the whole of
  itself left and right, a phrase at a time, every seven seconds. The register that says which
  is in no channel's window, so the mixer hands it to all four -- but **summing the
  two sides is the wrong answer**: that is the arithmetic a Game Boy's own speaker does, and it
  turns the bounce into a dip to three fifths of the volume, which is what nobody hears, because
  nobody listens to this through one speaker. So a channel sent to **either** side is folded
  down at its own level and one sent to **neither** is not heard, which is the part a render
  blind to the register got wrong. On this cartridge the fold comes out sample for sample as the
  blind render did -- nothing it plays is ever sent nowhere -- and what it buys is that the
  register is read at all. The chip can keep the sides apart instead, each through a filter of
  its own, and **nothing plays that**: Pyxel mixes its four channels to mono at 22050 Hz and its
  channels have a gain and no balance, so hearing the bounce means giving the game an output of
  its own, which is a job on its own.
- **The music** is the tune a course starts when the last beep of the start ends: four tunes
  over the eight courses, each on pulse 2 and the wave, so pulse 1 is left to the engine and the
  noise to the effects. **A tune has no end**, so it is two clips -- an entrance played once and
  a loop played for ever after -- and where one gives way to the other is found by playing the
  tune and watching for the moment it comes back to, never written down. What a looped clip
  loses is the original's drift: its beat is eight bits, the phase moves each time round, and
  the waits land a 64th of a second differently until it comes back true half an hour later.
- **A tune keeps one clock and its voices share it.** All of them start on one tick, and an
  effect on top of one hides that voice without stopping it: the original hands it back wherever
  the tune has reached, which is what keeps the parts together. So the place in a tune is counted
  from the tick the *tune* began, never from the tick a channel of it first became audible — and
  the screen a course is chosen on is where that matters, because the button that settles the
  title and the tune it starts are asked for in the same breath, so a voice is under an effect
  every single time.
- **The tempo is the race's and not the tune's.** A course's tune asks for a tempo of its own
  with a command in its stream, and **that is not the rate the original plays it at**: the game
  rewrites the tempo every iteration out of a table, and out of a second table **while there are
  under ten seconds left**. So a race hurries near the end -- by between an eighth and a quarter,
  by tune, measured, and not the double it sounds like. A clip cannot be played faster, there
  being no rate to turn on a WAV or on Pyxel, so **a course's tune is two pairs of clips** and
  the clock chooses the pair. Where the two meet the tune is carried across as a fraction of its
  loop rather than restarted: the original does not jump, it reads the same stream faster. The
  music the screens play is outside the tables and keeps its stream's own tempo, which is what
  the original's routine does with a tune it does not cover.
- **The clips are a bank**, rendered when the cartridge is opened and kept for every race after.
  A clip costs tens of milliseconds and a tune costs seconds, so one first wanted mid-race is
  frames dropped where the player hears them. A key is a sound and the channel it is heard on
  -- found by asking the driver which slots hold it, never tabulated -- the engine at a pitch,
  or a tune's entrance or loop. **The course is not in a key**: what a course chooses is which
  tune it starts.
- **The bank outlives the run**: rendering it is about fifteen seconds and the file is 41 MB --
  the eight tune renderings are most of both -- so it is written to `sound.bank` beside the game
  and read back in a tenth of a second. It is accepted only when
  it names this cartridge and this code -- the modules that decide a sample, by their compiled
  form, since a built executable keeps no source on disk. Anything else about the file being
  wrong has the same answer: there is no bank, and one is rendered. It is never shipped: it is
  the player's own cartridge, and deleting it costs one run.

- **The screens between races have a voice of their own**, and it outlives a race where the
  race's does not: one `Audio`, built when the cartridge is opened and primed on the handful of
  clips a screen can ask for rather than the whole bank. What each screen asks for is the
  original's own: **the title is silent** -- only its cursor makes a noise -- and **the tune
  belongs to the screen a course is chosen on**; settling the level stops everything and the
  card is silent behind it; and a race the clock ran out on gets a tune of its own, asked for
  as the box goes up and playing across both of that end's waits. A tune that ends rather than
  going round is played once, which is the other shape a tune comes in and is asked for rather
  than guessed from an entrance of nothing.
- **A four-slot tune's drums are not the tune.** The slot that carries them plays no note: each
  hit is a separate sound requested on the noise channel as the tune goes, on a channel the
  tune itself never holds. So the drums are keys of their own, and which hits a tune uses is
  found by playing it, like the channels: the cartridge's table has seven and a tune uses two
  or three.

**The results play one of two jingles**, and which one is whether the record fell: the ordinary
one for a race that beat nothing, the other for a race that beat the time the card had just
shown. Both are rendered before the window opens, because the screen cannot wait to find out
which it wants.

**Without a cartridge the sound is this game's own** (`game/sfx.py`): an effect for every cue the
race makes, the screens' cursor and confirm, a jingle for the results, the record and GAME OVER, and
an engine note pitched by the revs -- data for Pyxel's synthesizer, played by `audio.OwnAudio` behind
the same calls as the cartridge's clips. The moments are the original's, because they are the same
cues; the sounds are this game's. There is no music.

---

## 3. The map model

A map is a course, and a course is what the engine can read: tiles, and ten questions (`Ground`,
§2). There is one format, and it is the original's own shape.

`game/course.py` is the model and `maps/read.py` is the six files it is written in.

It is the original's own. A course is a **ring of 16 rows by 256 columns of
16-pixel metatiles** — 4096 pixels is one lap, and a race is two of them — where a metatile is four
8-pixel tiles and a tile carries a **collision byte**: solid, soft, no-wheelie, and a direction of
travel out of 32. A tile of the enhanced layer may also declare a **surface** (`"surface"` in its
`tiles.json`: `ice`, `spring` or `rush`); the original has only the plain one, and the engine reads
`Hit.surface`. No rule of the engine rides a surface differently: what each one does is an
experiment, not the contract. `game/rom/course.py` builds one from a cartridge and the same shape is what the
courses in `maps/` are written in.

**The vocabulary is the original's.** `maps/tiles.json`, `metatiles.json` and `pieces.json` are its
tiles, its 168 metatiles and the 82 pieces its courses use, under its own numbers in hex, and
`maps/courses/course1` to `course8` are its eight courses as lists of them.
`tools/vocab_from_rom.py` writes them out of a cartridge, and with `--check` builds each course from
`maps/` and compares it with the cartridge's, cell by cell; the one difference it allows is a
transparent tile stamped on an empty cell, which is sky here and the original's tile 0x7F there,
and 0x7F collides as nothing.

**A course is stamped, not drawn.** A prefab **piece** is a small grid of metatile ids — mostly 1x3,
2x2, 3x3, up to 4x4 — and a course is a list of `(row, col, piece)`, stamped in order. Where a piece
lands on an occupied cell the two are **merged tile by tile**, a transparent tile keeping whatever
was underneath, and a metatile the table does not already have is **minted**. That merge is the
whole vocabulary: the original draws eight courses out of 82 pieces because pieces overlap and the
game makes what it needs. A column past the last wraps within its row; a row past the last clips.

**The tiles are drawings.** One 8x8 PNG per name in `art/terrain/`, four shades, loaded by name —
`art/hand/` wins over it exactly as it does for a glyph — and the collision each one carries is
declared beside it in `maps/tiles.json` rather than derived from the picture: a drawing can be any
surface the collision byte can describe, which is the whole of what the engine can ride.

**A level is one number and nothing else**: a time limit. The three are authored rather than derived
from one another, because what makes a level hard on a given course is whether its clock falls above
or below the lines that course can be ridden on — a fact about the map, not a ratio. `DEFAULT_LEVEL`
is the reference clock, what a limit is typed against; moving it re-balances every course without
touching a map. The menu opens on `START_LEVEL`, which is deliberately not the same constant.

**Two things a course tells the engine about the bike**, and both are the original's tables, in
`maps/tables.json` (`game/course.Tables`). Which three cells of the engine's window the floor probes
read, one row per attitude -- the 32 directions, then the thrown rider's poses and the flourishes,
56 rows in all, because the engine reads the probes by attitude as well as by direction. And the path
a crash throws the rider along, nine `(dy, dx)` steps. **They are tables because no rule is them**:
the nearest rotation there is agrees with the probes on 73 of 96 cells and parts from the original
within a hundred iterations, and with the tables every course rides frame for frame as the
original's does -- `tools/vocab_from_rom.py --check` rides each both ways and compares them. The
engine itself still carries no table (`tests/test_engine_is_rules.py`): these are the course's.

**Classic and enhanced.** A vocabulary is layers (`maps/read.py`). The classic one is `maps/` alone,
the original's, and a classic course -- `maps/courses/` -- is held to what the original's are held
to: its vocabulary, and a metatile id that is a byte, 255 of them with the empty cell among them. The
enhanced one is `maps/enhanced/` over it: tiles, metatiles and pieces of this game's own, which
**add and never redefine** -- a course written against the base means the same in both -- and no
cap on ids, since the engine never masks one. An enhanced course is in `maps/enhanced/courses/`, and
nothing in its file says so: the directory is the statement, as it is for every other kind of map.
A course **mints into its own copy** of the vocabulary (`Tileset.fork`), as the original's race does
into a block it fills afresh, so how many metatiles one course makes is that course's alone.

---

## 4. The menu and the scoreboard

**The front end is `game/front.py`, and it is the original's**: the eight courses chosen on its
screens, with a cartridge or without one, always in classic. **The menu is FREE RIDE**, behind the
title's fourth row: the eight -- the cartridge's own when there is one -- and the author's drafts,
at any level, in any mode (`game/mode.py`), SOLO or against the computer. A race off it starts at
once, steps at its mode's rate, offers its time to the board only in classic, and ends on its
results drawn over it, which Start leaves. ESC on the menu is back to the title. With a cartridge,
a course of this game's own is drawn in the cartridge's art (`rom_art.paint_terrain`), with its
bike, panel and sound, and plays one of its eight course tunes chosen by the course's name
(`main.tune_of`).

**Two tabs**: `courses` and `custom` (`maps/drafts/` and `maps/enhanced/drafts/`), each keeping its
own cursor. **The drafts' tab is there even when it is empty**, because that is where the screen
says how to make one; only `--ride`, which is one course, has none. `Menu.move_section` is a modulo
over however many sections there are, so with one it is a no-op and the renderer never has to ask.

**One set of arrows and three things to choose with it** -- the course, the level, the mode.
`Menu.focus` is which of them has it and Tab hands over — **all four keys, not half of them**. A course is a list with another list across from
it; a level is a row of three, walked across, and up and down walk it too. `Menu.move` and
`Menu.move_across` are the only two calls `main` makes.

**It is the only mode this screen has, and it is an honest one**: both halves are on screen at once
and the selection is **filled** where the arrows will land and **outlined** where they will not, in
the same box either way. `test_the_screen_says_which_of_the_two_the_arrows_are_on` measures the
pixels rather than trusting the source.

**The list has a window** of six rows, `menu.WINDOW`, beside the model because the cursor has to be
kept inside it. **The offset is state and not a formula off the cursor**, and it moves as little as it
can, which is what makes a list you are walking down feel still.

**The menu has no logo**: it is headed with its own name, because with a cartridge in it lists the
cartridge's courses and a BMX-80 banner over them said the wrong thing. **The logo is art**, drawn
on this game's own opening screen and title: sixteen 16x16 cells, `logo_00` to `logo_71`, authored as one 128x32 ASCII
picture in `tools/tile_gen.BANNERS`, because the letters cross cell boundaries.

**The scoreboard is a file beside the checkout.** `game/records.py` writes `records.json`, gitignored,
keyed by **course and level**, and each of **time and score keeps its own best**: they are two races
over the same ground. A course nobody has finished draws `--:--` and one nobody has scored on draws
`0`. `M:SS.t` rather than whole seconds, because two runs of one course land in the same second often
enough to make a whole-second record useless.

**Reading a scoreboard is forgiving and reading a map is not**, and the asymmetry is deliberate. A
corrupt `records.json` should cost the player their times, not the ability to start the game.

---

## 5. Assets & palette

The art uses exactly four colours, whichever look `art/STYLE` names. `Image.load()` maps each source
pixel to the *nearest* palette entry, so those four values sit verbatim in slots 0-3 and the mapping
is exact (distance 0 always wins), whatever the other twelve slots hold.

### One collection, and it is ours

`art/terrain/` (8x8) is a map's tileset, **drawn**; `art/tiles/` (16x16) holds the glyphs and the
title, written out as text; `art/moto/` holds 32 rotations of the bike and the crash poses,
**generated from the model in `tools/sprite_gen.py`**. All committed and all required: **a missing
tile raises**; there is no optional group and no silent skip.

**A drawing wins by name.** `art/hand/<name>.png` wins over the generated tile of the same name, by
name and nothing else, and the game neither knows nor cares which it got. Deleting the drawing puts
the derived one back.
`tools/art_check.py` is what a drawing answers to: a name something loads, at its size, in the four
colours. **Where the contour goes is the designer's.**

### What no curve describes

The **glyphs** — a crate with a letter in it, a nitro, a rock — and the **banner** are written out in
`tools/tile_gen.py` rather than computed, because there is no geometry they could be a function of.
Both are ASCII in the four shades' own characters. The banner is spelled at its own size, 128x32,
and `slice_banner` cuts it into the sixteen `logo_*` cells. `assets.GLYPH_TILES` and
`assets.SCREEN_TILES` are the two lists, kept apart because they answer *which kind of tile is this*
for `tools/art_check.py`.

### A map's terrain

One 8x8 PNG per name in `art/terrain/`, and the name is the whole of the addressing: `maps/tiles.json`
says which names exist and what each one collides as, and `assets._load_terrain` walks that list and
loads a file per name into a bank of its own. Nothing is derived and nothing is rastered.

**The collision is declared, not read off the picture.** A tile says whether it is solid, whether it
is soft, whether a wheelie can start on it, and which of the engine's 32 directions is the direction
of travel on it. The original keeps exactly that, one byte a tile. Reading it off a drawing works for
a slope with an unambiguous face and cannot answer at all for a plain block, which has no way to say
which side the sky is on. So it is written down beside the drawing, where an author can see it and
change it.

**The terrain is drawn and the bike is generated**, and that split is on purpose: a geometry that
could raster the terrain would speak only a few of the engine's 32 directions, and a drawing can be
any surface the collision byte can describe. The bike has no such limit, so it stays a function of
its model.

**A tile's sky is transparent.** Every blit uses the sky index as a colkey, and only the columns on
screen are drawn.

**The crates, the rock and the sign over the finish are terrain too.** Each is a metatile, so each
is drawn as the tiles it is cut into -- `tc9` to `td7` for the crates, `tef` and `tdc` for the rock,
`tdd` to `te0` for the sign, which fills the lower half of its two cells -- and declared in
`maps/tiles.json` like any other: a crate and the sign as not solid, since one is reached and the
other is scenery. The four crates are one box with a different letter in it, the same box as the
glyphs above; the R shares its lower left quarter with the N, as the original's does.

**Every other tile is drawn by `tools/vocab_from_rom.py`**, painted by what it collides as: ground
dark with light flecks, sand light with dark dots, scenery plain light grey, each outlined in black
where it meets the sky inside the tile. A drawing is never written over once it is there.

**The signs by the track are drawn by hand.** A board on two posts with grass at its feet, cut into
tiles the boards share -- the plain board, its right and lower edges, the post -- and a symbol of this
game's own over a few tiles of its own: a loop, GO! and a rider, a way down, a jump. Each says what
the original's sign in that place says. What is left plain is three bars and the scenery no course
puts down.

**The bike**: with a cartridge, the bike and the rider are its sprites; without one, they are
`art/moto/`'s, generated from the bike's model.

---

## 6. What is deliberately not here

**Compositions.** `main.py --edit` draws a whole course -- pieces, metatiles, crates, clocks and the
computer's respawn stretches -- but a group of stampings kept to reuse, a loop or a ramp up and down,
is not there: an author repeats one by hand.

**A second player.** The original's third row asks for a link cable and gives up when nothing
answers, which is what this does too — see §2. Two players sharing one screen is a design question
the original never had to answer.

**Music without a cartridge.** The sound effects are this game's own; the tunes are the
cartridge's, and without one there are none.
