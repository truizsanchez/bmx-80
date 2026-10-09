"""Every number the engine runs on, and each is the original's.

The rest of `game/engine/` is the rules -- how a bike rides, flies, crashes and
races -- written the way an engine would be written from scratch; **this file is
what makes those rules Motocross Maniacs**. Change a number here and the engine
still works, and rides a different game. `tests/test_engine_is_rules.py` holds
the split: no other file of the engine writes a number bigger than two.

The numbers were measured on the original or read out of its code, and a few are
its tables re-expressed as the rule that generates them (the speed curve, the
jump classes, the crash's script) -- the engine carries no table of the
cartridge's. The two it does need as tables, the floor probes and the thrown
rider's arc, are content and come with a course (`maps/tables.json`).

**A mode that plays differently** moves a handful of these through a `Ruleset`
(`rules.py`); `rules.CLASSIC` is these numbers exactly.

Grouped by what they are about, in the order a tick meets them.
"""

# -- the machine ------------------------------------------------------------------
#
# The Game Boy's arithmetic, which the original's behaviour depends on: a
# position wraps where its bytes run out, and a snap keeps the fraction.

#: The fraction of a fixed-point coordinate, in bits: 8.8 for y, 16.8 for x.
PIXEL = 8
#: A byte, and the words the original keeps a coordinate in.
BYTE, WORD, X_WORD = 0xFF, 0xFFFF, 0xFFFFFF
#: The tile grid a snap lands on, as a pixel mask...
GRID = 0xF8
#: ...and as the mask for a whole 8.8 y: the pixel on the grid, the fraction kept.
Y_ON_GRID = GRID << PIXEL | BYTE
#: The camera's x snaps to the tile grid over a whole word of pixels.
X_ON_GRID = 0xFFF8
#: The buttons as the original's pad byte holds them: the cross...
RIGHT, LEFT, UP, DOWN = 0x01, 0x02, 0x04, 0x08
#: ...and A, the throttle, and B, the nitro.
THROTTLE, NITRO = 0x10, 0x20

# -- the map ----------------------------------------------------------------------

#: A tile, and a metatile, in pixels.
TILE, METATILE = 8, 16
#: The map, in metatiles: 16 rows of a ring of 256 columns.
ROWS, COLS = 16, 256
#: The lap, as a mask on x in pixels: 4096 px round.
LAP_MASK = 0x0FFF
#: The screen, in pixels across, and the background's width in tile columns.
VIEW_W, SLOTS = 160, 32
#: Above this row of pixels the world has a ceiling.
WORLD_TOP = 16

# -- directions -------------------------------------------------------------------

#: Directions in a full turn. 0 is right, and they run counter-clockwise.
DIRECTIONS = 32
#: Directions in a quarter turn.
QUADRANT = DIRECTIONS // 4
#: The 45 up: the one slope with probes of its own.
UP_45 = QUADRANT // 2
#: Half a turn: straight left.
HALF_TURN = 2 * QUADRANT
#: Straight down.
STRAIGHT_DOWN = 3 * QUADRANT
#: A tile direction `&` this is 0 when the tile is level or the top of a slope.
NOT_LEVEL = 0x1E

#: The quarter sine the velocity is read from: its steps, and its scale.
SINE_STEPS, SINE_SCALE = 64, 255
#: The velocity is the magnitude halved, times the sine, shifted down this much.
SINE_SHIFT = 4

# -- the probes -------------------------------------------------------------------

#: The window of tiles around the bike, and in metatiles.
WINDOW, WINDOW_METATILES = 6, 3
#: The fixed cells, in the order the original stores them.
FIXED = (26, 27, 15, 21)
#: The first floor probe at the 45 up, riding.
RIDING_UP_45 = 22
#: The position bit that says which half of its metatile the bike is in.
HALF_METATILE = 0x08
#: How many steps a thrown rider's path has (the path is a course's table).
THROW_STEPS = 9

# -- speed ------------------------------------------------------------------------

#: The top of the speed index with nothing picked up...
CAP = 79
#: ...and with an S.
CAP_S = 111
#: How far the index moves in one tick, on the throttle or off it.
INDEX_STEP = 2
#: Where the speed curve stops: from here up, the index *is* the value.
CURVE_TOP = 112
#: The largest magnitude there is: the index a nitro sets, and the ceiling the
#: slope term cannot push a magnitude past.
MAGNITUDE_MAX = 144

#: The speed curve, below `CURVE_TOP`, as four pieces: up to each index, the
#: magnitude is `base + per * (index // every)`. Steps of eight at the very
#: bottom, of sixteen to 7, a line of slope two to 15, then two every four
#: indices -- counted from 16 -- up to the top.
CURVE = ((2, 0, 8, 1), (7, 0, 16, 2), (15, 36, 2, 1))
#: ...and the last piece, from `CURVE_FROM`.
CURVE_FROM, CURVE_BASE, CURVE_PER, CURVE_EVERY = 16, 68, 2, 4

#: A nitro sets the index to the top and holds it there this many ticks.
NITRO_INDEX = MAGNITUDE_MAX
NITRO_TICKS = 16
#: Nitros in hand at the start.
NITROS_START = 4

#: The index a crash tumble forces, and the one the celebration after the line does.
INDEX_CRASHING = 8
INDEX_FINISHED = 32

#: How far the slope accumulator moves in one tick on a slope.
SLOPE_STEP = 2
#: Downhill it stops at this...
SLOPE_TOP = 32
#: ...and uphill it is not lowered once it is below this -- so it comes to rest
#: one step further, at -34. The original compares before it subtracts.
SLOPE_FLOOR = -32
#: The term on soft ground.
SOFT_TERM = -56

# -- on the ground ------------------------------------------------------------------

#: Directions whose snap is on y (level, and one step up) ...
SNAP_LEVEL = 2
#: ... the right-hand wall, whose snap is on x, and the ceiling.
WALL_RIGHT, CEILING = QUADRANT, HALF_TURN
#: On the ceiling the snap is taken this far lower.
CEILING_LIFT = 8
#: A wheelie's nose this far up or more, and the first attitude probe decides.
WHEELIE_GROUND = 3
#: A wheelie's nose at this is over: 90 degrees.
WHEELIE_OVER = 8

# -- the air ------------------------------------------------------------------------

#: The speed index from which a take-off is a fast one.
FAST = CURVE_TOP
#: A take-off's class: slow or fast, and one more with Up held...
FAST_CLASS, UP_CLASS = 2, 1
#: ...and a take-off in the automatic modes is this class, whatever the speed.
AUTO_CLASS = 4
#: A take-off hangs this many ticks for each step of its class.
HANG_PER_CLASS = 2
#: The jump classes that fall their own way: the slow one, and the automatic one.
SLOW, AUTOMATIC = 0, AUTO_CLASS
#: How each class falls: the index lost a tick once the hang is over, the
#: period the direction turns on (the loop counter `& period` is 0), and the
#: steps it turns by. The slow jump falls fast; every other falls slower; the
#: automatic one, slowest.
FALL_SLOW, FALL_AUTOMATIC, FALL_OTHER = (8, 0, 2), (2, 3, 1), (4, 1, 1)
#: The index a falling bike is lifted to before its drop, when it is below the floor.
INDEX_FLOOR, INDEX_LIFT = 32, 34
#: A climb, heading right, stops turning one or two steps short of straight down.
RIGHT_DOWN_STOPS = (STRAIGHT_DOWN + 1, STRAIGHT_DOWN + 2)
#: A nitro fired in the air hangs the bike this many ticks.
AIR_NITRO_HANG = 8
#: Without the J, a nitro in the air needs the nose this far up or less: 0-6.
AIR_NITRO_ATTITUDE = 7
#: The landing window: attitude minus surface, in steps, behind and ahead.
LAND_BEHIND, LAND_AHEAD = 5, 7
#: In the air, a solid cell above whose direction is one of these is a crash:
#: the rider's head in level ground, or in the top of a slope.
HEAD_FIRST = (0, 28)

# -- the crash ----------------------------------------------------------------------

#: A bike falling straight down moves this fast, in 1/256 px a tick.
FALL_SPEED = 0x400
#: A rock's tumble spends this many ticks in the air before it looks for the ground.
ROCK_TUMBLE_AIR = 8
#: A tumble whose tile says "level" or "at the top of a slope" takes this for a
#: direction instead.
TUMBLE_LEVEL = 32
#: A tumble spins the bike this many steps a tick, and thumps on ticks where
#: the loop counter `&` `TUMBLE_BEAT` is 0: every eighth.
TUMBLE_SPIN, TUMBLE_BEAT = 2, 7

#: A bike down stays down this many ticks, and they run as a script, counted
#: down: the rider comes off for the first `THROWN_OFF`, flies `THROW_STEPS`
#: along the course's arc, lies until `LANDED_FROM`, sits up until `CRAWL_FROM`,
#: crawls back to the bike until `REMOUNT_FROM`, gets on until `READY_FROM`,
#: and is ready for the rest.
DOWN_TICKS = 57
THROWN_OFF = 3
LANDED_FROM, CRAWL_FROM, REMOUNT_FROM, READY_FROM = 29, 26, 9, 6
STANDING_FROM = 3
#: The crawl changes pose while the timer `&` this is set.
CRAWL_BLINK = 4
#: The rider's poses in the script, thrown back and thrown forward: coming off,
#: flying and lying, sitting up, and crawling (two poses from here).
POSE_OFF = (0x2A, 0x34)
POSE_FLYING = (0x29, 0x33)
POSE_SITTING = (0x2B, 0x35)
POSE_CRAWLING = (0x2C, 0x36)
#: ...and the two either way: getting on, and ready.
POSE_REMOUNT, POSE_READY = 0x2E, 0x2F

# -- the finish ---------------------------------------------------------------------

#: Riding, the finish's celebration starts this low on the screen...
FINISH_Y = 0xE0
#: ...on a column of the lap where x `>> FINISH_SHIFT & FINISH_MASK` is 0.
FINISH_SHIFT, FINISH_MASK = 16, 0x0F
#: The celebration past the line is a wheelie at this attitude: 45 degrees.
CELEBRATION_ATTITUDE = 4
#: Past the line in the air, the nose goes up to this, then through the rider's
#: flourishes -- poses past 31, pictures rather than angles -- one every
#: `FLOURISH_BEAT + 1` iterations of the loop counter.
FLOURISH_FROM = 3
FLOURISHES = (0x30, 0x31, 0x32)
FLOURISH_BEAT = 3

# -- the race -----------------------------------------------------------------------

#: Iterations of the countdown.
COUNTDOWN = 48
#: The countdown beeps with this many iterations left, and says go at `GO_AT`.
BEEPS_AT, GO_AT = (34, 26, 18), 10
#: Where the original puts the bike on the grid: pixels.
START_X, START_Y = 32, 232
#: The lines, on x rounded down to 16 px.
LAP_LINE, FINISH_LINE, TAKEOVER_LINE = 4016, 8064, 8112
LINE_GRID = 0xFFF0
#: Laps left at the start: one, which the lap line counts off.
LAPS = 1
#: Ticks the celebration lasts, from the take-over.
CELEBRATION = 0x40
#: Both clocks move by this much a tick, in hundredths of a second.
CLOCK_STEP = 2
#: The clock is pressing under this much, in hundredths: ten seconds.
HURRY = 1000
#: Without a qualifying time to start from, this long -- ten minutes.
NO_LIMIT = 60000
#: Riding sand sounds every this many iterations.
SAND_BEAT = 3
#: A cell with nothing in it.
EMPTY = 0xFF

# -- the things to pick up ------------------------------------------------------------

#: The kinds, as the original numbers them.
S, T, N, R, J, MINI = 2, 3, 4, 5, 6, 7
#: A secret is taken upside down: at this attitude.
UPSIDE_DOWN = 16
#: A thing is reached from 15 px before its corner to 14 past it.
REACH, SPAN = 15, 30
#: What the T adds to the time left: ten seconds, in hundredths.
TEN_SECONDS = 1000
#: Nitros an N adds, and the most mini-maniacs there are.
NITRO_PACK, MAX_MINIS = 4, 3
#: The flourish a secret taken leaves: how many iterations it is up, and how far
#: above the bike it starts.
FLASH, FLASH_Y = 16, -8
#: How many iterations of the player's own track are remembered, and how far
#: behind each mini-maniac rides on it. Three of them, and the oldest of the
#: three is nine iterations back -- so the trail is kept a little longer than
#: the furthest one needs.
TRAIL = 16
MINIS_BEHIND = (5, 7, 9)

# -- the computer's bike ----------------------------------------------------------------

#: How far ahead the computer's bike is let run at its best, by level.
RIVAL_REACH = (0x40, 0x80, 0xF0)
#: Its best cap, and how far behind it is teleported.
BEST_CAP, BEHIND = 0x77, 0x30
#: The teleport puts it this far left of the view's edge.
OFF_SCREEN = 16

# -- the camera -------------------------------------------------------------------------

#: The camera's y, in 8.8, starts at and never passes this: 128 px.
Y_LIMIT = 128 << PIXEL
#: The picture's y is counted from 16 above the screen, as the hardware counts it.
SPRITE_Y_OFFSET = 16
#: The screen's half, in those units: below it the camera follows the bike down,
#: above it up.
SCREEN_HALF = 0x40
