"""A run on the screen: the course, the bike, and a line of text.

**The course is drawn in the original's own art** when it came from a cartridge:
its 256 background tiles are installed in a bank of their own (`install_art`)
and the map is blitted out of it, a tile at a time. **Without art** a tile is a
square in one of the four shades by what the bike makes of it -- sky, level
ground, a slope, sand: the picture of what is ridden.

**The bike is drawn where the original draws it**: its 16x16 picture with the
top-left corner at the bike's position, in the pose its attitude names. With a
cartridge every pose is the cartridge's own, read from its table of sprites.
Without one it is this game's picture: past the line in the air the rider's
flourishes are the bike rearing up on its back wheel, drawn as the nose-up angle
nearest each. Either way, while the rider is off it the wreck lies where the
crash stopped and the rider is drawn in the pose the attitude carries.

**The camera** is the original's (`game/engine/camera.py`), riding with the bike's
velocity; the view is 128 px tall and the band below it is the HUD's. With the
computer's bike in the race it is drawn too, behind the player's.

**A course out of a cartridge draws the original's own furniture**: its panel in
the band (`game/rom/panel.py`), the three sprites of its start, the pin over the
player's bike, and the box the clock running out puts over the view. A course of
this game's own maps gets the same things drawn from nothing: the same panel,
the same three two one GO!, a pin of the same shape and a box of the same size.

**A pause says nothing** on a course of the cartridge's, because the original
says nothing: it stops, and the sound is what tells you.

**A race that is over is a screen**, not something over the race: the clock
running out is a box, and the finish takes the window -- the course and the band
go, and what is left is the original's results (`game/rom/screen.py`).
"""

from collections.abc import Sequence

import pyxel

from game.constants import CELL, SCREEN_H, SCREEN_W, TILE
from game.course import Course as OurCourse
from game.engine.bike import Bike
from game.engine.original import FLOURISHES, PIXEL
from game.engine.original import J
from game.engine.original import MINIS_BEHIND
from game.engine.run import FINISHED, TIME_UP, Run
from game.engine.original import START_X, START_Y
from game.render import assets, front_draw, rom_art
from game.rom import panel
from game.rom.cartridge import SECOND_PALETTE, X_FLIP, Y_FLIP
from game.render.lettering import label
from game.render.style import BULK, EDGE, RIM, SKY

#: Where a mini-maniac sits against the place the player was: four pixels along
#: and four down, which is the original's own offset.
MINI_OFFSET = 4
#: The view above the HUD's band.
VIEW_H = 128
#: The course is this tall; the camera never shows below it.
COURSE_H = 256
#: A pose past 31 is the rider's own. Two runs of the same seven pictures, one
#: facing each way: thrown back, and thrown forward.
BACK_POSES, FORWARD_POSES = 0x29, 0x33
#: The flourishes, as the angle of the bike rearing up in each: 34, 45, 56 degrees.
_FLOURISH_ANGLES = dict(zip(FLOURISHES, (3, 4, 5)))
_POSES = ("rider_lying", "rider_lying", "rider_rising", "rider_walk_a", "rider_walk_b",
          "rider_lifting", "rider_lifting")


def draw_course(run: Run, cam_x: int, cam_y: int) -> None:
    """Every tile in view, in whichever of the three pictures a course has.

    **A course of this game's own out of the terrain bank**, where its tiles
    are loaded by name -- and repainted in the cartridge's pictures when there
    is one; a cartridge's course in the cartridge's art; and, for a course that is neither -- a test's, a rig with no art yet
    -- the collision itself, shaded, which is the one picture that can always be
    drawn because the engine has to be able to read it.

    **The two pictures are of the screen's background, not of the map**
    (`game/engine/background.py`): where the map changes in view, as it does at
    the lap line, the screen goes on showing what scrolled in. The collision is
    the map's, because that is what it pictures.
    """
    ground = run.bike.ground
    pyxel.cls(SKY)
    if isinstance(ground, OurCourse):
        _draw_drawn(run, ground, cam_x, cam_y)
        return
    if rom_art.has_art():
        _draw_art(run, cam_x, cam_y)
        return
    first_col, first_row = cam_x // TILE, cam_y // TILE
    for row in range(first_row, first_row + VIEW_H // TILE + 1):
        if not 0 <= row < COURSE_H // TILE:
            continue
        for col in range(first_col, first_col + SCREEN_W // TILE + 1):
            metatile = ground.metatile(row // 2, col // 2)
            hit = ground.collision(ground.tiles(metatile)[(row % 2) * 2 + col % 2])
            if not hit.solid:
                continue
            shade = BULK if hit.soft else EDGE if hit.direction == 0 else RIM
            pyxel.rect(col * TILE - cam_x, row * TILE - cam_y, TILE, TILE, shade)


def _draw_drawn(run: Run, ground: OurCourse, cam_x: int, cam_y: int) -> None:
    """A course of this game's own: one blit per tile out of the terrain bank,
    which `assets` loaded a PNG into for every name `maps/tiles.json` declares."""
    first_col, first_row = cam_x // TILE, cam_y // TILE
    for row in range(first_row, first_row + VIEW_H // TILE + 1):
        if not 0 <= row < COURSE_H // TILE:
            continue
        for col in range(first_col, first_col + SCREEN_W // TILE + 1):
            name = ground.tile_name(run.background.tile(row, col))
            if name is None:
                continue
            u, v = assets.terrain_uv(name)
            pyxel.blt(col * TILE - cam_x, row * TILE - cam_y, assets.TERRAIN_BANK,
                      u, v, TILE, TILE, SKY)


def _draw_art(run: Run, cam_x: int, cam_y: int) -> None:
    first_col, first_row = cam_x // TILE, cam_y // TILE
    for row in range(first_row, first_row + VIEW_H // TILE + 1):
        if not 0 <= row < COURSE_H // TILE:
            continue
        for col in range(first_col, first_col + SCREEN_W // TILE + 1):
            tile = run.background.tile(row, col)
            pyxel.blt(col * TILE - cam_x, row * TILE - cam_y, rom_art.ART_BANK,
                      (tile % rom_art.COLS) * TILE, (tile // rom_art.COLS) * TILE,
                      TILE, TILE)


def _sprite(name: str, x: int, y: int, mirror: bool = False) -> None:
    u, v = assets.uv(name)
    pyxel.blt(x, y, assets.BANK, u, v, -CELL if mirror else CELL, CELL, SKY)


def bike_picture(attitude: int) -> str | None:
    """The bike's picture for an attitude, or None when the rider is off it."""
    attitude = _FLOURISH_ANGLES.get(attitude, attitude)
    return "bike%02d" % attitude if attitude < 32 else None


def draw_bike(bike: Bike, cam_x: int, cam_y: int) -> None:
    if rom_art.rom() is not None:
        _draw_rom_bike(bike, cam_x, cam_y)
        return
    if not bike.player:
        # The computer's bike, a shade lighter all over: what the cartridge's
        # second palette does to its sprites.
        pyxel.pal(EDGE, BULK)
        pyxel.pal(BULK, RIM)
    _draw_own_bike(bike, cam_x, cam_y)
    pyxel.pal()


def _draw_own_bike(bike: Bike, cam_x: int, cam_y: int) -> None:
    x, y = bike.px
    picture = bike_picture(bike.attitude)
    if picture is not None:
        _sprite(picture, x - cam_x, y - cam_y)
        return
    if bike.rider_off:
        sy, sx = (bike.saved[0] >> PIXEL) & 0xFF, bike.saved[1]
        _sprite("wreck", sx - cam_x, sy - cam_y)
    back = bike.attitude < FORWARD_POSES
    pose = bike.attitude - (BACK_POSES if back else FORWARD_POSES)
    _sprite(_POSES[max(0, min(len(_POSES) - 1, pose))], x - cam_x, y - cam_y, mirror=back)


def _draw_rom_bike(bike: Bike, cam_x: int, cam_y: int) -> None:
    """The bike in the cartridge's own sprites: the pose its attitude names,
    every attitude there is, flourishes and the rider's own included.

    **The wreck is what the rider coming off drew and nothing drew over.** The
    pose the bike is left in writes the rider and the bike lying on the ground;
    the thrown rider's poses write fewer slots and leave the bike's standing, so
    it stays where the crash stopped while the rider flies -- and the original
    moves those slots with the camera, which is drawing them at the place saved.
    The computer's bike is drawn through the second palette.
    """
    cartridge = rom_art.rom()
    assert cartridge is not None
    rival = 0 if bike.player else SECOND_PALETTE
    x, y = bike.px[0] - cam_x, bike.px[1] - cam_y
    cells = [(x + dx, y + dy, tile, flags | rival)
             for dx, dy, tile, flags in _slots(cartridge.pose(bike.attitude))]
    if bike.rider_off:
        thrown = BACK_POSES if bike.thrown_back else FORWARD_POSES
        lying = cartridge.pose(thrown + 1)[len(cartridge.pose(thrown)):]
        sy, sx = (bike.saved[0] >> PIXEL) & 0xFF, bike.saved[1]
        cells += [(sx - cam_x + dx, sy - cam_y + dy, tile, flags | rival)
                  for dx, dy, tile, flags in _slots(lying)]
    rom_art.sprites(cells, SKY)


def _slots(pose: Sequence[tuple[int, int, int, int] | None]) -> list[tuple[int, int, int, int]]:
    """A pose's sprites as `(dx, dy, tile, flags)`, without the slots it empties."""
    return [(dx, dy, tile, flags) for dy, dx, tile, flags in (s for s in pose if s is not None)]


def clock(hundredths: int, fraction: bool = False) -> str:
    """`M:SS`, or `M:SS.hh` with the fraction."""
    seconds, rest = divmod(max(0, hundredths), 100)
    text = "%d:%02d" % divmod(seconds, 60)
    return text + (".%02d" % rest if fraction else "")


def draw_band(run: Run, paused: bool) -> None:
    """The band below the view: the course's own panel, or this game's.

    A course out of a cartridge has one (`game/rom/panel.py`) and it is drawn in
    the cartridge's art, tile for tile. Without a cartridge the same panel is
    drawn from nothing (`_write_band`).

    The original says nothing for a pause; without a cartridge there is no
    sound to say it either, so this game writes the word.
    """
    if rom_art.rom() is not None:
        _draw_panel(run)
        return
    _write_band(run)
    if paused:
        label(SCREEN_W - 4 * 6 - 6, VIEW_H - 12, 4 * 6 + 4, "PAUSED")


def _draw_panel(run: Run) -> None:
    """The course's own panel: two rows of twenty tiles out of the bank."""
    cartridge = rom_art.rom()
    assert cartridge is not None
    for row, tiles in enumerate(panel.rows(cartridge, run)):
        rom_art.tiles([(col * TILE, VIEW_H + row * TILE, tile)
                       for col, tile in enumerate(tiles)])


def _draw_marker(bike: Bike, cam_x: int, cam_y: int) -> None:
    """The pin over the player's bike, so that the two are told apart.

    The cartridge's is two tiles, a block and the point under it. Without one it
    is the same shape drawn from nothing, which is what every part of this game
    does where the cartridge is not there to be read. The computer's bike never
    gets one either way.
    """
    x, y = bike.px[0] - cam_x, bike.px[1] - cam_y
    if rom_art.rom() is not None:
        rom_art.tiles(panel.marker(x, y), SKY)
        return
    x, y = x + panel.MARKER_X, y + panel.MARKER_Y
    pyxel.rect(x, y, TILE, TILE, EDGE)
    for row in range(TILE // 2):
        pyxel.rect(x + row + 1, y + TILE + row, TILE - 2 * row - 2, 1, EDGE)


def _draw_barrier(run: Run, cam_x: int, cam_y: int) -> None:
    """The barrier on the grid, which falls as the countdown runs out.

    **Anchored to the course and not to the screen**, unlike the start's three
    sprites: it stands where the bike started, and once the bike has ridden past
    it the course carries it off the left and it does not come back.

    Without a cartridge it is a bar of the same three heights, standing on the
    ground and shortening as it goes down -- the same shape the cartridge's
    three tiles draw, told the only way four shades can tell it.
    """
    x, y = START_X + panel.BARRIER_X - cam_x, START_Y + panel.BARRIER_Y - cam_y
    cells = panel.barrier(run.countdown, x, y)
    if rom_art.rom() is not None:
        rom_art.tiles(cells, SKY)
        return
    for at_x, at_y, tile in cells:
        high = TILE >> panel.BARRIER.index(tile)
        pyxel.rect(at_x, at_y + TILE - high, 2, high, EDGE)


def _draw_minis(run: Run, cam_x: int, cam_y: int) -> None:
    """The mini-maniacs riding behind the player: one each, in a row.

    **Each one is the player a few iterations ago**, read off the trail the bike
    keeps -- so they follow the line the player took rather than chase the bike,
    and they bunch up where the player slowed down. The pose is the player's own
    of that moment, in the cartridge's own little-bike alphabet.

    Their tiles are sprite tiles below 128, which the bank cannot reach, so they
    go through `rom_art.sprites`. Drawn before the bike, which is where the
    original has them: behind it.
    """
    bike = run.bike
    if not bike.minis:
        return
    cartridge = rom_art.rom()
    cells = []
    for back in MINIS_BEHIND[:bike.minis]:
        was = bike.behind(back)
        if was is None:
            continue
        x, y = was[0] - cam_x + MINI_OFFSET, was[1] - cam_y + MINI_OFFSET
        if x < 0:
            continue
        if cartridge is None:
            _mini(x, y)
            continue
        tile, mirrored = cartridge.mini(was[2])
        cells.append((x, y, tile, X_FLIP | Y_FLIP if mirrored else 0))
    rom_art.sprites(cells, SKY)


def _mini(x: int, y: int) -> None:
    """A mini-maniac with no cartridge to draw it: this game's little bike, eight
    pixels square at `(x, y)`, as the cartridge's own tile is."""
    u, v = assets.uv("mini")
    pyxel.blt(x, y, assets.BANK, u, v, TILE, TILE, SKY)


def _draw_secret(run: Run, cam_x: int, cam_y: int) -> None:
    """The flourish a secret taken has left, while it lasts.

    Anchored to the course, not to the screen, and rising: `Flash` moves it, so
    this only subtracts the camera. Without a cartridge it is this game's crate
    of the same size with the J in it, or a mini-maniac.
    """
    flash = run.flash
    if flash is None:
        return
    x, y = flash.x - cam_x, flash.y - cam_y
    if rom_art.rom() is not None:
        rom_art.tiles(panel.secret(flash.kind, x, y), SKY)
        return
    if x >= 0:
        _sprite("item_jet" if flash.kind == J else "item_mini", x, y)


def _draw_timeup(held: int) -> None:
    """The box the clock running out puts over the view, and its blinking words.

    The cartridge's is nine tiles by three of its own, filled and lettered; this
    game's own maps get the same box and the same blink drawn from nothing.

    **Both blink on the frames the wait has left** and not on the race's
    iteration counter: the race has stopped by the time this is on the screen,
    so its counter has stopped with it, and the original counts this one down a
    displayed frame at a time (`game/front.py`, `TIMEUP_HOLD`).
    """
    if rom_art.rom() is not None:
        rom_art.tiles(panel.timeup(held))
        return
    pyxel.rect(panel.BOX_X, panel.BOX_Y, panel.BOX_W * TILE, panel.BOX_H * TILE, RIM)
    if not held & panel.BLINK:
        words = "TIME UP"
        width = 4 * len(words) + 4
        label(panel.BOX_X + (panel.BOX_W * TILE - width) // 2,
              panel.BOX_Y + TILE, width, words)


def _draw_start(run: Run) -> None:
    """The start's three sprites, over the view: nothing, then three, two, one,
    then `GO!` -- or, with no cartridge, the same words in this game's lettering,
    where the three sprites would be."""
    if rom_art.rom() is not None:
        rom_art.tiles(panel.start(run.countdown), SKY)
        return
    word = panel.start_word(run.countdown)
    if word:
        wide = 4 * len(word) + 4
        label(panel.START_X + (3 * panel.START_STEP - wide) // 2, panel.START_Y, wide, word)


def _write_band(run: Run) -> None:
    """This game's own band, for a course with no cartridge to draw the panel
    out of: **the original's panel, drawn from nothing** -- the same things in
    the same places (`game/rom/panel.py`), so a player who knows one reads the
    other.

    The top row is the speedometer, a rising row of bars filled to the speed,
    with a notch where an S has moved the cap; then `TIME` and its bar, the
    seconds left up to fifty-five. The bottom row is `TIRE` and `JET` while an
    R or a J is held, and `NTR` with a canister for each nitro, up to eight.
    No clock and no lap, because the original's panel has neither.
    """
    bike = run.bike
    pyxel.rect(0, VIEW_H, SCREEN_W, SCREEN_H - VIEW_H, SKY)
    top, low = VIEW_H, VIEW_H + TILE
    _speedometer(top, bike.magnitude, bike.speed.cap > bike.rules.cap)
    label(panel.TIME_BAR * TILE - 4 * TILE // 2 - 6, top, 4 * 4 + 4, "TIME")
    _time_bar(panel.TIME_BAR * TILE, top + 1, run.left)
    # The bottom row a pixel lower, so the speedometer's bars keep two pixels of
    # sky between them and the words under them.
    low += 1
    if bike.no_slope:
        label(panel.RIDER_TIRE % panel.WIDE * TILE, low, 4 * 4 + 4, "TIRE")
    if bike.jet:
        label(panel.RIDER_JET % panel.WIDE * TILE, low, 4 * 3 + 4, "JET")
    label(panel.TIME_BAR * TILE - 4 * TILE // 2 - 6, low, 4 * 3 + 4, "NTR")
    for n in range(min(bike.speed.nitros, panel.BARS)):
        _canister(panel.NITROS % panel.WIDE * TILE + n * TILE + 4, low + 1)


#: The speedometer's bars: how many, and the pixels each takes across; how tall
#: the last one is, and the row of the band their feet stand on.
SPEED_BARS, SPEED_PITCH = 16, 3
SPEED_HIGH, SPEED_FOOT = 5, 6


def _speedometer(y: int, magnitude: int, raised: bool) -> None:
    """A row of bars, each a pixel taller than the last, filled up to the speed
    and dotted past it -- the shape the original's needle and bar draw -- with
    a notch at the end while the cap is raised."""
    lit = min(magnitude, panel.TOP) * SPEED_BARS // panel.TOP
    for bar in range(SPEED_BARS):
        high = 1 + bar * SPEED_HIGH // SPEED_BARS
        x = 2 + bar * SPEED_PITCH
        if bar < lit:
            pyxel.rect(x, y + SPEED_FOOT - high, 2, high, EDGE)
        else:
            pyxel.pset(x, y + SPEED_FOOT - 1, RIM)
    if raised:
        x = 2 + SPEED_BARS * SPEED_PITCH + 1
        pyxel.tri(x, y + 1, x + 4, y + 1, x + 2, y + 5, EDGE)


def _time_bar(x: int, y: int, left: int) -> None:
    """The seconds left as a bar, capped at `panel.LONGEST`, as the original's
    is: a race with more than that starts full and standing still."""
    wide = SCREEN_W - x - 2
    pyxel.rectb(x, y, wide, TILE - 3, EDGE)
    full = min(left // 100, panel.LONGEST) * (wide - 2) // panel.LONGEST
    pyxel.rect(x + 1, y + 1, full, TILE - 5, EDGE)


def _canister(x: int, y: int) -> None:
    """A nitro: a bottle with a cap."""
    pyxel.rect(x + 1, y, 2, 1, EDGE)
    pyxel.rect(x, y + 1, 4, TILE - 3, EDGE)
    pyxel.pset(x + 1, y + 2, SKY)


def draw_run(run: Run, paused: bool = False, held: int = 0) -> None:
    """A frame of a run. `held` is what the wait over a stopped race has left,
    which is what the box the clock running out puts over the view blinks on."""
    if run.over == FINISHED:
        front_draw.draw_results(run)
        return
    # The card and the results borrow the bank for their lettering, so the
    # course's art is asked for here rather than once when the race was built.
    rom_art.course()
    cam_x, cam_y = run.camera.px
    draw_course(run, cam_x, cam_y)
    if run.rival is not None:
        draw_bike(run.rival, cam_x, cam_y)
    _draw_barrier(run, cam_x, cam_y)
    _draw_minis(run, cam_x, cam_y)
    draw_bike(run.bike, cam_x, cam_y)
    _draw_secret(run, cam_x, cam_y)
    _draw_marker(run.bike, cam_x, cam_y)
    _draw_start(run)
    if run.over == TIME_UP:
        _draw_timeup(held)
    draw_band(run, paused)
