"""The editor's model: the course in hand, every edit to it, and its file.

On a vocabulary this file writes, a few tiles and pieces, so that each rule is a
case a reader can see -- and without a window, because none of this needs one.
"""

import json
import os

import pytest

from game.course import COLS, ROWS, Tileset
from maps import HERE, read
from tools.editor.document import Document, empty
from tools.editor.map_file import MapFile

TILES = {"floor": {"dir": 0}, "ramp": {"dir": 4}}
METATILES = {
    "flat": ["sky", "sky", "floor", "floor"],
    "solid": ["floor", "floor", "floor", "floor"],
    "slope": ["-", "ramp", "ramp", "floor"],
}
PIECES = {"road2": [["flat", "flat"]], "hill": [[".", "slope"], ["slope", "solid"]]}


def _document(data=None):
    return Document(Tileset(TILES, METATILES), PIECES, read.tables(), data)


def test_a_stamping_goes_on_top_and_a_right_click_takes_the_top_one_away():
    """Why this test: a course is a list in which each stamping merges into what
    came before, so "the one on top of this cell" is the last in the list that
    covers it -- which is what an author sees and so what a right-click must
    take, and a new stamping always goes on top."""
    doc = _document()
    doc.stamp(5, 10, "road2")
    doc.stamp(5, 11, "solid")
    assert doc.stack(5, 11) == [0, 1]
    assert doc.stack(5, 10) == [0]
    assert doc.remove_top(5, 11)
    assert doc.stampings == [[5, 10, "road2"]]
    assert not doc.remove_top(0, 0), "nothing there, nothing taken"


def test_every_metatile_can_be_put_down_on_its_own():
    doc = _document()
    doc.stamp(3, 3, "slope")
    course = doc.built()
    shown = [course.tile_name(t) for t in course.tiles(course.metatile(3, 3))]
    assert shown == [None, "ramp", "ramp", "floor"], "the transparent corner is sky"
    with pytest.raises(ValueError):
        doc.stamp(3, 3, "nothing_called_this")


def test_raising_a_stamping_changes_the_merge_and_skips_what_it_does_not_touch():
    """Why this test: the order is what decides the merge, so reordering is an
    edit with a visible result -- and moving a stamping past one it shares no
    cell with changes nothing, so a raise goes past the next one it does
    touch."""
    doc = _document()
    doc.stamp(2, 2, "flat")         # 0
    doc.stamp(9, 9, "solid")        # 1 -- elsewhere
    doc.stamp(2, 2, "slope")        # 2
    merged_before = doc.built().metatile(2, 2)
    assert doc.raise_(0) == 2
    assert [name for _, _, name in doc.stampings] == ["solid", "slope", "flat"]
    assert doc.built().metatile(2, 2) != merged_before
    assert doc.lower(2) == 1, "back under the one it overlaps"


def test_a_drag_is_one_undo_however_many_it_put_down_and_redo_brings_it_back():
    doc = _document()
    doc.stamp(4, 0, "road2")
    for col in (2, 4, 6):
        doc.stamp(4, col, "road2", amend=True)
    assert len(doc.stampings) == 4
    assert doc.undo()
    assert doc.stampings == []
    assert not doc.undo(), "the file as opened is as far back as it goes"
    assert doc.redo()
    assert len(doc.stampings) == 4


def test_a_stamping_wraps_round_the_ring_and_stops_at_the_last_row():
    doc = _document()
    assert doc.cells(ROWS - 1, COLS - 1, "hill") == [(ROWS - 1, COLS - 1), (ROWS - 1, 0)]
    doc.stamp(0, COLS - 1, "road2")
    assert doc.stack(0, 0) == [0]


def test_a_crate_replaces_the_crate_on_its_cell_and_goes_before_the_ground():
    doc = _document()
    doc.stamp(6, 6, "solid")
    doc.put_item("n", 6, 6)
    doc.put_item("t", 6, 6)
    assert doc.items == [["t", 6, 6]]
    assert doc.remove_top(6, 6)
    assert doc.items == [] and doc.stampings == [[6, 6, "solid"]]
    with pytest.raises(ValueError):
        doc.put_item("x", 1, 1)


def test_a_clock_is_not_something_undo_takes_back():
    doc = _document()
    doc.set_limit(1, 90)
    assert doc.data["limits"][1] == 90.0
    assert not doc.undo()


def test_the_file_is_one_entry_a_line_and_reads_back_as_itself(tmp_path):
    """Why this test: "is there anything to save" is a comparison of text, which
    holds only if a course has exactly one way to be written."""
    doc = _document(empty())
    doc.stamp(15, 0, "road2")
    doc.put_item("s", 14, 3)
    text = doc.text()
    assert '  [15, 0, "road2"],' not in text and '  [15, 0, "road2"]\n' in text
    assert read.dump(json.loads(text)) == text
    target = MapFile("draft", str(tmp_path / "maps" / "drafts" / "draft.json"))
    assert target.dirty(text)
    target.write(text)
    assert not target.dirty(text)
    assert target.read() == json.loads(text)


def test_every_committed_course_is_written_the_one_way():
    """A course file edited by hand in another layout would read as a change the
    moment the editor opened it, so the committed ones are held to `dump`."""
    checked = 0
    for directory in ("courses", os.path.join("enhanced", "courses")):
        where = os.path.join(HERE, directory)
        for name in sorted(os.listdir(where)) if os.path.isdir(where) else ():
            if name.endswith(".json"):
                with open(os.path.join(where, name)) as handle:
                    text = handle.read()
                assert read.dump(json.loads(text)) == text, name
                checked += 1
    assert checked, "no committed course to hold to it"


def test_a_teleport_stretch_is_kept_from_the_finish_back_and_found_by_its_line():
    """The rival walks the stretches in order from the finish back to the start
    and takes the first behind it, so the order is the file's and not the
    author's; and a stretch is found by the line the bike would stand on."""
    doc = _document()
    doc.add_teleport(100, 300, 232)
    doc.add_teleport(2000, 1500, 200)
    assert doc.teleports == [[1500, 2000, 200], [100, 300, 232]]
    assert doc.teleport_at(200, 248) == 1
    assert doc.teleport_at(200, 100) is None
    doc.remove_teleport(0)
    assert doc.undo() and len(doc.teleports) == 2


def test_a_new_enhanced_course_is_a_draft_in_the_enhanced_vocabulary(tmp_path, monkeypatch):
    """Why this test: `--edit <name> --enhanced` is the one way to start a course
    in this game's own pieces, and what makes it enhanced is only where it is
    written -- so the place a new one goes is the whole of the claim."""
    from game import paths

    monkeypatch.setattr(paths, "user_path", lambda *parts: os.path.join(str(tmp_path), *parts))
    classic, enhanced = MapFile.named("new-one"), MapFile.named("new-one", enhanced=True)
    assert classic.vocabulary == read.CLASSIC
    assert enhanced.vocabulary == read.ENHANCED_VOCABULARY
    assert enhanced.path == os.path.join(str(tmp_path), "maps", "enhanced", "drafts", "new-one.json")
