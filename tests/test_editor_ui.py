"""The editor's window, driven through the mouse and the keys with nobody watching.

`tests/editor_session.py` does the driving in a subprocess -- a process gets one
Pyxel window and `conftest.py` has this one's -- and reports what the document
held after each gesture. One session, several claims, because starting a window
is the expensive part.
"""

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    scratch = tmp_path_factory.mktemp("editor")
    done = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "editor_session.py"),
                           str(scratch)], cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_the_palette_puts_what_was_clicked_in_hand(session):
    assert session["hand"] == ["pieces", "two"]


def test_a_drag_along_a_row_repeats_the_piece_a_width_at_a_time_as_one_undo(session):
    """Why this test: a road is the same piece many times, and one drag has to put
    them down edge to edge -- and take them back with one undo, or undo is
    erasing a cell at a time."""
    assert session["run"] == [[10, col, "two"] for col in (2, 4, 6, 8)]
    assert session["run_undone"] == []


def test_a_stamping_goes_on_top_and_the_right_button_takes_the_top_one(session):
    assert session["stacked"] == [0, 1]
    assert session["after_right"] == [[10, 2, "top"]]


def test_alt_and_a_click_picks_up_what_is_on_top(session):
    assert session["eyedropped"] == ["metatiles", "top"]


def test_z_zooms_and_ctrl_s_writes_the_one_way_a_course_is_written(session):
    assert session["zoom"] == 2
    assert session["saved"]["pieces"] == [[10, 2, "full"], [10, 2, "top"]]
    assert session["saved"]["items"] == [["n", 9, 20]]
    assert not session["dirty"]


def test_tab_walks_the_stack_from_the_top_and_a_bracket_moves_the_chosen_one(session):
    """Why this test: the order of the stampings is the merge, so an author has
    to be able to see which one is which under the pointer and move it."""
    assert session["chosen"] == 0, "two TABs from the top of a stack of two"
    assert session["raised"] == ["full", "top"]


def test_a_crate_and_a_respawn_stretch_are_put_down_and_taken_away(session):
    assert session["items"] == [["n", 9, 20]]
    start, end, y = session["teleports"][0]
    assert start < end and y == 10 * 16 + 8 - 16, "standing on the middle of the row"
    assert session["teleports_after_right"] == []


def test_the_clocks_views_and_ride_answer_from_the_window(session):
    """R rides what is drawn, saved or not: a copy written aside and another
    process on it, because Pyxel has one window a process."""
    assert session["clock_a"] == 601.0
    assert session["views"] == [True, True, True]
    assert session["ride"][0] == "--ride"
    assert session["ride_file"]["limits"][0] == 601.0


def test_every_tab_answers_a_click_on_its_label(session):
    assert session["tabs"] == ["pieces", "metatiles", "things"]


def test_the_scrollbar_is_where_the_view_is(session):
    """Why this test: the view kept its own scroll and copied it into the bar
    every frame, and a view that wrapped round the ring handed the bar values
    past its end -- the thumb jumped and dragging it fought the copy. The bar
    is the one place the view is now: its arrow steps it and its thumb drags it."""
    assert session["arrow"] == 1
    assert session["thumb"] > 10
    assert session["home"] == 0


def test_each_scrollbar_is_where_the_layout_puts_it(session):
    from tools.editor.view import PALETTE_BAR, SCROLL, VSCROLL

    assert session["bars"] == [list(rect) for rect in (SCROLL, VSCROLL, PALETTE_BAR)]
