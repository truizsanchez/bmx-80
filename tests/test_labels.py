"""Every metatile and piece has a name a person can read (`maps/labels.json`).

Why this test: the vocabulary is the original's, under its own hex numbers --
`m1a`, `p57` -- and an editor palette of a hundred and sixty `mXX` is a palette
nobody can use. The labels are the layer that says what each one is, and the
editor groups by their kinds; a metatile or piece added without one would be the
one the author cannot find. Walked, never named, as every map rule is.
"""

from maps import read
from tools import label_vocab
from tools.label_vocab import METATILE_KINDS, PIECE_KINDS


def test_every_metatile_and_piece_has_a_label_of_a_known_kind():
    labels = read.labels()
    metatiles, pieces = read.metatiles(), read.pieces()
    assert metatiles and pieces, "nothing to walk, and this proved nothing"
    assert not label_vocab.missing(labels), label_vocab.missing(labels)
    for name in metatiles:
        label = labels["metatiles"][name]
        assert label["name"] and label["kind"] in METATILE_KINDS, (name, label)
    for name in pieces:
        label = labels["pieces"][name]
        assert label["name"] and label["kind"] in PIECE_KINDS, (name, label)


def test_a_metatile_is_drafted_from_what_its_tiles_collide_as():
    tiles = {"floor": {"dir": 0}, "up": {"dir": 4}, "down": {"dir": 28},
             "wall": {"dir": 8}, "dune": {"soft": True}, "post": {"solid": False}}
    draft = label_vocab.metatile_label
    assert draft("a", ["sky", "sky", "floor", "floor"], tiles) == \
        {"kind": "ground", "name": "ground bottom"}
    assert draft("b", ["up"] * 4, tiles)["kind"] == "slope up"
    assert draft("c", ["down"] * 4, tiles)["name"] == "down 45 full"
    assert draft("d", ["wall"] * 4, tiles)["kind"] == "curve"
    assert draft("e", ["sky", "sky", "dune", "dune"], tiles)["kind"] == "sand"
    assert draft("f", ["post"] * 4, tiles)["kind"] == "scenery"
    assert draft("crate_s", ["post"] * 4, tiles)["kind"] == "special"


def test_a_piece_is_drafted_from_the_surface_a_bike_rides():
    tiles = {"floor": {"dir": 0}, "up": {"dir": 4}, "down": {"dir": 28},
             "post": {"solid": False}}
    metatiles = {"road": ["sky", "sky", "floor", "floor"], "rise": ["up"] * 4,
                 "fall": ["down"] * 4, "sign": ["post"] * 4}
    draft = label_vocab.piece_label
    assert draft("a", [["road", "road", "road"]], metatiles, tiles)["kind"] == "road"
    assert draft("b", [["rise", "rise"]], metatiles, tiles)["kind"] == "ramp up"
    assert draft("c", [["rise", "fall"]], metatiles, tiles)["kind"] == "hill"
    assert draft("d", [["fall", "rise"]], metatiles, tiles)["kind"] == "dip"
    assert draft("e", [["sign", "sign"], ["sign", "sign"], ["road", "road"]],
                 metatiles, tiles)["kind"] == "sign"


def test_a_label_a_person_wrote_is_never_overwritten():
    """The file is a first draft and then content: filling it in again adds
    what is missing and leaves every name somebody chose."""
    mine = {"metatiles": {"m1": {"kind": "ground", "name": "my road"}}, "pieces": {}}
    draft = {"metatiles": {"m1": {"kind": "ground", "name": "ground full"},
                           "m2": {"kind": "rock", "name": "rock"}},
             "pieces": {"p1": {"kind": "road", "name": "road 1x1"}}}
    filled = label_vocab.filled(mine, draft)
    assert filled["metatiles"]["m1"]["name"] == "my road"
    assert filled["metatiles"]["m2"]["name"] == "rock"
    assert filled["pieces"]["p1"]["kind"] == "road"
