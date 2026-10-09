"""The look: what the four shades are shown as, and how it is asked for."""

import pytest


def test_a_look_changes_what_the_shades_are_shown_as_and_not_the_pictures(pyxel_headless):
    """Why this test: the art is loaded against the style's own four colours by
    nearest match, so a look can only ever be a change to what the screen shows
    the four indices as -- **after** the load. A look that re-read the art, or
    that reached a bank, would put every grey of a PNG on whichever green was
    nearest. So: the colours change, the pictures' indices do not, and the greys
    come back exactly.
    """
    from game.render import assets, palette
    from game.render.style import active

    u, v = assets.uv("bike00")
    bank = pyxel_headless.images[assets.BANK]
    before = [bank.pget(u + x, v + y) for y in range(16) for x in range(16)]
    try:
        palette.show("green")
        assert pyxel_headless.colors[:4] == list(palette.LOOKS["green"] or ())
        assert [bank.pget(u + x, v + y) for y in range(16) for x in range(16)] == before
    finally:
        palette.show(palette.DEFAULT_LOOK)
    assert pyxel_headless.colors[:4] == list(active().shades)


def test_the_look_is_asked_for_by_name_and_a_wrong_one_says_which_there_are():
    """A look nobody has is refused rather than shown in grey, which would look
    like the flag had been read and ignored."""
    from main import palette_wanted

    assert palette_wanted(["main.py"]) == "grey"
    assert palette_wanted(["main.py", "--palette", "green"]) == "green"
    with pytest.raises(SystemExit, match="green"):
        palette_wanted(["main.py", "--palette", "pink"])
    with pytest.raises(SystemExit):
        palette_wanted(["main.py", "--palette"])


def test_every_look_keeps_its_four_shades_apart():
    """Why this test: the green the game first shipped had its two light shades
    5% of the range apart in brightness, and the sky and the lightest fill read
    as one colour -- the look was right by its own numbers and wrong on the
    screen. Four shades are the whole of the picture, so each has to be
    visibly brighter than the one before it: a tenth of the range at least, by
    the Rec. 601 luma a screen is judged by."""
    from game.render import palette
    from game.render.style import active

    def luma(colour):
        r, g, b = colour >> 16, (colour >> 8) & 0xFF, colour & 0xFF
        return 0.299 * r + 0.587 * g + 0.114 * b

    for name, shades in palette.LOOKS.items():
        four = shades or active().shades
        steps = [luma(lighter) - luma(darker) for darker, lighter in zip(four, four[1:])]
        assert min(steps) >= 25.5, "%s: two of its shades are %.1f apart" % (name, min(steps))
