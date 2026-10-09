"""A course of this game's own: the ring, the pieces, and the merge that stamps them.

Against courses this test writes, the way `tests/test_rom.py` checks the
cartridge's reader against cartridge-shaped files it writes itself. What is
under test is the rules -- how a piece lands, what happens where two overlap,
what an author's names become -- on maps of a few cells each, so that every rule
is one case a reader can see.

The shape is the port's on purpose (`game/course.py`), so several of these are
the same claims `tests/test_rom.py` makes about the cartridge. That they are
made twice is the point: the engine reaches a course of ours by the same road.
"""

import pytest

from game.course import (
    ATTITUDES,
    COLS,
    EMPTY,
    GOAL,
    GOAL_COL,
    GOAL_ROW,
    ROWS,
    THROW_STEPS,
    RESERVED,
    Course,
    Tables,
    Tileset,
    vocabulary,
)
from game.engine.terrain import ICE, NORMAL, SKY, Hit
from maps import read

#: The probes and the throw every course of the vocabulary is ridden with --
#: walked out of `maps/`, as the vocabulary is, and never written here.
RIDDEN = read.tables()

#: A vocabulary small enough to read: a floor, a slope whose top left lets
#: through, and a rock.
TILES = {
    "floor": {"solid": True, "dir": 0},
    "sand": {"solid": True, "soft": True},
    "ramp": {"solid": True, "dir": 4},
    "stone": {"solid": True, "rock": True},
}
METATILES = {
    "flat": ["sky", "sky", "floor", "floor"],
    "solid": ["floor", "floor", "floor", "floor"],
    "slope": ["-", "ramp", "ramp", "floor"],
    "beach": ["sky", "sky", "sand", "sand"],
    "boulder": ["sky", "sky", "stone", "stone"],
}


def _course(pieces=None, **kw):
    return Course(Tileset(TILES, METATILES), pieces or {}, RIDDEN, **kw)


def test_a_piece_is_stamped_cell_by_cell_where_its_record_says():
    pieces = {"ledge": [["flat", "flat"], ["solid", "solid"]]}
    course = _course(pieces, stampings=[(3, 7, "ledge")])
    flat, solid = course.tiles_of.metatile_id["flat"], course.tiles_of.metatile_id["solid"]
    assert [course.metatile(3, c) for c in (7, 8)] == [flat, flat]
    assert [course.metatile(4, c) for c in (7, 8)] == [solid, solid]
    assert course.metatile(2, 7) == EMPTY and course.metatile(3, 9) == EMPTY


def test_a_column_past_the_last_wraps_and_a_row_past_the_last_clips():
    """Why this test: a course is a ring in one axis and not in the other, and
    the asymmetry is the original's. A piece laid over the seam has to come out
    the other side; a piece laid at the bottom has to stop rather than appear at
    the top, which would be a wall falling out of the sky.
    """
    pieces = {"pair": [["flat", "flat"]], "tall": [["flat"], ["flat"]]}
    course = _course(pieces, stampings=[(5, COLS - 1, "pair"), (ROWS - 1, 3, "tall")])
    flat = course.tiles_of.metatile_id["flat"]
    assert course.metatile(5, COLS - 1) == flat
    assert course.metatile(5, 0) == flat, "the column came round"
    assert course.metatile(ROWS - 1, 3) == flat
    assert course.metatile(0, 3) == EMPTY, "and the row did not"


def test_two_pieces_on_one_cell_are_merged_tile_by_tile_and_minted_once():
    """Why this test: **the merge is the vocabulary**. There is no piece for
    every shape -- the original draws eight courses out of 82 small ones -- and
    what makes that work is that a piece put down on an occupied cell mixes with
    it rather than replacing it, a transparent tile keeping what was underneath.
    A metatile the set does not have is minted, and minted **once**: the same
    overlap twice is one new metatile, or a long course would run out of ids.
    """
    pieces = {"flat": [["flat"]], "slope": [["slope"]]}
    course = _course(pieces, stampings=[(3, 0, "flat"), (3, 1, "flat"),
                                        (3, 0, "slope"), (3, 1, "slope")])
    made = course.metatile(3, 0)
    assert made == course.metatile(3, 1)
    assert made not in course.tiles_of.metatile_id.values(), "it is a new one"
    sky, floor, ramp = (course.tiles_of.tile_id[n] for n in ("sky", "floor", "ramp"))
    assert course.tiles(made) == (sky, ramp, ramp, floor), \
        "the slope's transparent corner kept the floor's sky"


def test_stamping_nothing_erases_the_cell():
    """The original's third case, and an author uses it to cut a hole in a floor
    already laid: a piece of `"."` clears whatever is there rather than merging
    with it."""
    pieces = {"floor": [["flat", "flat", "flat"]], "hole": [[".", "."]]}
    course = _course(pieces, stampings=[(9, 0, "floor"), (9, 1, "hole")])
    flat = course.tiles_of.metatile_id["flat"]
    assert [course.metatile(9, c) for c in range(3)] == [flat, EMPTY, EMPTY]


def test_a_crate_is_stamped_as_the_kind_the_engine_counts_it_in():
    """Why this test: `Run` puts a crate back by its *kind* -- it hands `put`
    the number 2 to 5 -- so those ids are the crates whatever a course calls
    them, and a course that numbered its own metatiles from zero would have a
    race stamping floor tiles where a crate was. The J and the mini-maniacs are
    in the list and **not** in the map: they are picked up and never drawn.
    """
    course = _course(items=[("n", 4, 4), ("s", 4, 6), ("j", 4, 8), ("mini", 4, 9)])
    assert course.metatile(4, 4) == 4 and course.metatile(4, 6) == 2
    assert course.metatile(4, 8) == EMPTY and course.metatile(4, 9) == EMPTY
    assert course.items() == [(4, 4, 4), (2, 4, 6), (6, 4, 8), (7, 4, 9)]


def test_a_tile_says_what_it_collides_as_and_sky_touches_nothing():
    course = _course()
    hit = lambda name: course.collision(course.tiles_of.tile_id[name])  # noqa: E731
    assert hit("floor") == Hit(True, False, False, 0)
    assert hit("ramp") == Hit(True, False, False, 4)
    assert hit("sand") == Hit(True, True, False, 0)
    assert hit("sky") == SKY
    assert course.is_rock(course.tiles_of.tile_id["stone"])
    assert not course.is_rock(course.tiles_of.tile_id["floor"])


def test_an_empty_cell_and_the_row_above_the_map_are_sky():
    """Why this test: the engine copies a window of tiles from one metatile row
    **above** the bike's, so a bike on the top row asks for row -1 every tick.
    The original reads whatever bytes lie before its map; there is nothing here
    to read, and answering sky is the one place this differs on purpose. An
    answer it did not have would be an IndexError mid-race.
    """
    course = _course()
    assert course.metatile(-1, 0) == EMPTY
    assert course.tiles(EMPTY) == (0, 0, 0, 0)
    assert course.collision(0) == SKY


def test_the_sign_over_the_finish_goes_up_where_the_lap_line_puts_it():
    course = _course()
    assert course.metatile(GOAL_ROW, GOAL_COL) == EMPTY and not course.signed
    course.goal()
    assert [course.metatile(GOAL_ROW, GOAL_COL + n) for n in range(len(GOAL))] == list(GOAL)
    assert course.signed


def test_a_crate_taken_is_put_back_over_whatever_was_under_it():
    """The original writes a cell outright here rather than merging, so taking a
    crate takes the ground it was merged into with it. Kept, because it is
    visible in the original and an author draws around it."""
    pieces = {"floor": [["flat"]]}
    course = _course(pieces, stampings=[(4, 4, "floor")], items=[("n", 4, 4)])
    merged = course.metatile(4, 4)
    assert merged not in (EMPTY, 4), "the crate merged into the floor"
    course.put(4, 4, EMPTY)
    assert course.metatile(4, 4) == EMPTY
    course.put(4, 4, 4)
    assert course.metatile(4, 4) == 4, "and the bare crate came back, floor and all"


def test_a_course_mints_into_its_own_copy_of_the_vocabulary():
    """Why this test: the editor builds a course from one set each time the
    pointer moves a cell with a piece in hand. When a merge's new metatile went
    into the set itself, every one of those builds spent an id nobody gave back,
    and an original course ran out of ids within a hundred moves of the pointer.
    A course's mints are its own, as the original's are its race's."""
    tiles = Tileset(TILES, METATILES)
    before = dict(tiles.quads)
    first = Course(tiles, {}, RIDDEN, stampings=[(3, 3, "solid"), (3, 3, "slope")])
    second = Course(tiles, {}, RIDDEN, stampings=[(3, 3, "solid"), (3, 3, "slope")])
    assert tiles.quads == before, "the set handed in minted nothing"
    made = first.metatile(3, 3)
    assert made not in before, "the merge did mint, or this proved nothing"
    assert second.metatile(3, 3) == made, "and every course mints from the same place"


def test_a_course_is_ridden_with_the_tables_it_is_handed():
    """Why this test: which cells the floor probes read and where a crash throws
    the rider are what a course tells the engine about the bike, and they are
    data (`maps/tables.json`) -- so a course has to answer with exactly what it
    was handed, and nothing of its own."""
    probes = [(27, 26, 21)] * ATTITUDES
    throw = [(step, -1) for step in range(THROW_STEPS)]
    course = Course(Tileset(TILES, METATILES), {}, Tables.of(probes, throw))
    assert [course.probes(a) for a in range(ATTITUDES)] == probes
    assert [course.throw(step) for step in range(THROW_STEPS)] == throw


@pytest.mark.parametrize("probes, throw", [
    ([(27, 26, 21)] * 32, [(0, -1)] * THROW_STEPS),                # the directions only
    ([(27, 26)] * ATTITUDES, [(0, -1)] * THROW_STEPS),             # two probes, not three
    ([(27, 26, 36)] * ATTITUDES, [(0, -1)] * THROW_STEPS),         # outside the window
    ([(27, 26, 21)] * ATTITUDES, [(0, -1)] * (THROW_STEPS - 1)),   # a step short
])
def test_tables_of_the_wrong_shape_are_refused(probes, throw):
    """Why this test: the engine indexes both by number, so a table a row short
    would not fail where it is read -- it would fail in a race, at the one
    attitude nobody had ridden yet. The probes are read by attitude as well as
    by direction, so thirty-two rows is exactly the short table this found."""
    with pytest.raises(ValueError):
        Tables.of(probes, throw)


def test_the_vocabularys_probes_stay_inside_the_windows_middle():
    """Why this test: the engine moves a probed cell a row down or a column left
    by where the bike sits in its metatile, so a probe on the window's edge
    would read past it. Walked over whatever `maps/tables.json` holds."""
    for direction, cells in enumerate(RIDDEN.probes):
        assert all(1 <= cell // 6 <= 4 and 1 <= cell % 6 <= 4 for cell in cells), direction


#: A 45 up and a 45 down with a table between, on a road along the bottom row:
#: the shape of every jump a course of ours has, in a vocabulary of its own.
RAMP_TILES = {"floor": {"dir": 0}, "fill": {"dir": 0}, "up": {"dir": 4}, "down": {"dir": 28}}
RAMP_METATILES = {
    "road": ["sky", "sky", "floor", "floor"], "under": ["fill"] * 4,
    "up_fill": ["up", "fill", "fill", "fill"], "up_tip": ["-", "-", "-", "up"],
    "down_fill": ["fill", "down", "fill", "fill"], "down_tip": ["-", "-", "down", "-"],
}
RAMP_PIECES = {
    "ramp_up": [[".", ".", "up_tip"], [".", "up_tip", "up_fill"],
                ["up_tip", "up_fill", "under"], ["up_fill", "under", "under"]],
    "ramp_down": [["down_tip", ".", "."], ["down_fill", "down_tip", "."],
                  ["under", "down_fill", "down_tip"], ["under", "under", "down_fill"]],
    "table": [["under"] * 3] * 3,
}


def _jump():
    stampings = [(ROWS - 1, col, "road") for col in range(COLS)]
    stampings += [(12, 40, "ramp_up"), (12, 46, "ramp_down"), (13, 43, "table")]
    stampings += [(12, col, "road") for col in (43, 44, 45)]
    return Course(Tileset(RAMP_TILES, RAMP_METATILES), RAMP_PIECES, RIDDEN, stampings=stampings)


def test_a_bike_lands_on_the_road_and_not_in_it():
    """Why this test: turned about the middle of the window, the third probe
    stayed in the bike's own bottom row nose down, so a landing found the road
    only once it was inside the bike and `_snap` rounded it down a whole tile.
    The bike then rode the rest of the lap 8 px into the road -- which the
    suite never saw, and a screenshot did.

    Measured on the pixels the bike stands on, not on a number: whenever it
    rides level on the road, the row under it is solid and its own bottom row
    is not."""
    from game.engine.rules import State
    from game.engine.original import THROTTLE
    from game.engine.run import Run

    course = _jump()

    def solid(x, y):
        tiles = course.tiles(course.metatile((y >> 4) % ROWS, (x >> 4) % COLS))
        return course.collision(tiles[((y >> 3) & 1) * 2 + ((x >> 3) & 1)]).solid

    run, landed = Run(course, limit=60000), 0
    for _ in range(1500):
        run.step(THROTTLE)
        bike = run.bike
        x, y = bike.px
        if bike.state is State.RIDING and bike.direction == 0 and x > 800:
            landed += 1
            assert solid(x + 8, y + 16) and not solid(x + 8, y + 15), (x, y)
    assert landed, "the bike never came down past the jump and this proved nothing"


def test_a_tumble_at_the_foot_of_a_ramp_comes_to_rest():
    """Why this test: leaning forward down the 45, the bike tumbles at its foot.
    With the third probe a row short of the ground it followed the slope past
    the end of it, found nothing under it, and fell through the bottom of the
    course for ever -- a race that could not go on. It has to come to rest and
    ride again."""
    from game.engine.rules import State
    from game.engine.original import RIGHT, THROTTLE
    from game.engine.run import Run

    run, states = Run(_jump(), limit=60000), set()
    for _ in range(1500):
        run.step(THROTTLE | RIGHT)
        states.add(run.bike.state)
    assert State.CRASHING in states, "nothing tumbled and this proved nothing"
    assert run.bike.px[0] > 1000, "the bike is still at x=%d" % run.bike.px[0]


def test_a_metatile_that_is_not_four_tiles_is_refused():
    with pytest.raises(ValueError):
        Tileset(TILES, {"wrong": ["sky", "sky", "floor"]})


def test_a_tile_a_metatile_names_and_nothing_declares_is_refused():
    with pytest.raises(KeyError):
        Tileset(TILES, {"wrong": ["sky", "sky", "gravel", "floor"]})


def test_the_lap_is_the_one_the_engines_lines_are_written_in():
    """Why this test: `Run` has the lap line, the finish and the take-over at
    4016, 8064 and 8112 pixels, and the bike's `y` is one byte. A course of
    another size would need an engine of another size, so the ring's dimensions
    are not an author's to choose and this says so out loud.
    """
    from game.course import LAP_PX, METATILE_PX
    from game.engine.original import FINISH_LINE, LAP_LINE, TAKEOVER_LINE

    assert (ROWS, COLS, METATILE_PX) == (16, 256, 16)
    assert LAP_PX == 4096
    assert LAP_LINE < LAP_PX, "the lap line is on the first time round"
    assert LAP_PX <= FINISH_LINE < TAKEOVER_LINE < 2 * LAP_PX, "and the finish on the second"
    assert ROWS * METATILE_PX == 256, "and y is a byte"


def test_every_direction_a_tile_can_declare_is_one_the_engine_counts_in():
    tiles = {"steep": {"dir": 40}}
    set_ = Tileset(tiles, {})
    assert set_.hits[set_.tile_id["steep"]].direction == 8, "40 is 8, once round"
    assert len(set_.hits) == 3, "the sky, the one tile declared, and the transparent id"


def test_every_metatile_can_be_stamped_on_its_own_and_a_piece_wins_its_name():
    """Why this test: an author puts pieces down, and a detail that is one
    metatile should not have to be declared as a piece before it can be placed
    -- so every metatile is a piece of one cell by its own name. Where a piece
    has the same name the piece is what the author meant. The goal and the
    crates are the engine's own and are placed as items, never as ground.
    """
    tiles = Tileset(TILES, METATILES)
    offered = vocabulary({"slope": [["flat", "solid"]]}, tiles)
    assert offered["beach"] == [["beach"]]
    assert offered["slope"] == [["flat", "solid"]], "the piece, not the metatile"
    assert not set(RESERVED) & set(offered)
    course = _course(stampings=[(2, 3, "beach")])
    assert course.metatile(2, 3) == course.tiles_of.metatile_id["beach"]


def test_a_transparent_tile_stamped_on_nothing_lets_the_sky_through():
    """Why this test: `-` in a metatile means "keep what is underneath", and on
    an empty cell what is underneath is sky. Kept as it was, the transparent id
    reached the engine, whose collision has no entry for it -- a crash the first
    time the bike's probes read that cell."""
    course = _course(stampings=[(4, 4, "slope")])
    top_left = course.tiles(course.metatile(4, 4))[0]
    assert course.collision(top_left) == SKY
    assert course.tile_name(top_left) is None


def test_the_sign_put_up_whole_lets_the_sky_through_where_it_is_transparent():
    """Why this test: the sign over the finish is written into the map whole --
    `put`, no merge, as the original does -- and its top half is `-`. The
    transparent id reached the engine that way, and a bike crashed or jumping
    by the finish probed it: an IndexError, found by `tools/solve.py`. The
    original's transparent tile collides as nothing, and so does ours."""
    metatiles = dict(METATILES, goal_left=["-", "-", "floor", "floor"])
    course = Course(Tileset(TILES, metatiles), {}, RIDDEN)
    course.goal()
    top_left = course.tiles(course.metatile(GOAL_ROW, GOAL_COL))[0]
    assert course.collision(top_left) == SKY
    assert course.tile_name(top_left) is None


def test_a_tile_declares_its_surface_by_name_and_a_name_there_is_none_of_is_refused():
    """Why this test: a surface is what an enhanced tile does beyond the
    original's four facts, and it is declared by a name an author types -- so a
    misspelt one has to be refused where it is read, not ridden as plain ground."""
    tiles = Tileset({"glaze": {"surface": "ice"}, "road": {}}, {})
    assert tiles.hits[tiles.tile_id["glaze"]].surface == ICE
    assert tiles.hits[tiles.tile_id["road"]].surface == NORMAL
    with pytest.raises(ValueError, match="slush"):
        Tileset({"bad": {"surface": "slush"}}, {})


def test_the_originals_vocabulary_has_one_kind_of_surface():
    """The base vocabulary is the cartridge's, and the cartridge has no surface
    but the plain one: a surface belongs to the enhanced layer."""
    base = read.tileset(read.CLASSIC)
    assert all(hit.surface == NORMAL for hit in base.hits)


def test_a_classic_set_is_held_to_the_originals_ids_and_an_enhanced_one_is_not():
    """Why this test: a metatile id is a byte in the original, 255 of them with
    `EMPTY` among them, and a classic course is held to that. An enhanced one is
    not -- the engine never masks an id -- so its ids go on past 254, stepping
    over `EMPTY`, which has to stay the empty cell whatever else is minted."""
    many = {"t%d" % n: {"dir": 0} for n in range(40)}
    quads = [("t%d" % a, "t%d" % b, "t%d" % c, "t%d" % d)
             for a in range(40) for b in range(2) for c in range(2) for d in range(2)]
    capped, open_ended = Tileset(many, {}), Tileset(many, {}, capped=False)
    with pytest.raises(ValueError):
        for quad in quads:
            capped.find_or_mint(capped.tiles_of(quad))
    ids = [open_ended.find_or_mint(open_ended.tiles_of(quad)) for quad in quads]
    assert max(ids) > EMPTY, "the open set went past the byte"
    assert EMPTY not in ids, "and never handed out the empty cell"
