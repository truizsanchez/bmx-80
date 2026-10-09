# Contributing

This is a small project with a long memory. Most of what follows is not house style: it is
a handful of rules that each exist because breaking one of them once cost real work.

**If you came here to draw**, improving the art needs no Python at all. A terrain tile is a
drawing in `art/terrain/`: redraw it in place. The bike, the rider, the glyphs and the logo
are generated, and a PNG in `art/hand/` wins over the generated picture of the same name.
`python tools/art_sheet.py` puts every picture the game loads on one PNG under its name --
the tiles alone, then assembled into metatiles and pieces -- and `python tools/art_check.py`
says whether a drawing is one the game can load.

## Getting set up

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest tests/ -q -n auto
```

`requirements.txt` is what a player installs, and it is Pyxel alone; `requirements-dev.txt`
pulls that in and adds the test runner and the checkers.

`-n auto` puts the suite on every core you have: a few seconds, against a quarter of a
minute without it. Drop it when you are chasing one failure and want the output in order.
The suite runs with no window -- Pyxel's `init(headless=True)` lets the real game loop be
driven and screenshotted from a test -- and it has to come back green on a fresh clone; if
it does not, that is a bug worth an issue on its own.

## The checks

Every command is in [`AGENTS.md`](AGENTS.md#commands), and CI runs the same gate on every
pull request. Two of them are worth knowing before you read a failure:

- **`python -m pyflakes game maps tools tests main.py`** catches the unused import and the
  name that is not there. A name imported only to be handed on goes in the module's
  `__all__`, the one spelling of a re-export pyflakes honours.
- **`python -m mypy`** reads `mypy.ini` and makes two claims. Over the whole of `game/`,
  `maps/`, `tools/` and `main.py` it checks the bodies of functions with no annotations.
  Over the modules in its strict list -- every one in scope but the vendored
  `tools/editor/widgets/` -- it is the full strict set. A new module arrives annotated and
  goes on the list in the same commit. `tests/` is checked by running.

**Coverage takes three steps** -- `coverage run`, `coverage combine`, `coverage report` --
because anything that wants a window of its own is driven in a subprocess, and so are the
`-n auto` workers; uncombined, a module the suite drives thoroughly reads as barely touched.
Nothing enforces a threshold. What the report leaves uncovered is mostly what needs a
cartridge, which the suite never has.

## The rules

The five rules a change is judged against, and the four checks that hold the code's shape,
are in [`AGENTS.md`](AGENTS.md#the-five-rules). All of them are enforced by tests, so they
fail for you before anybody sees them. The two that surprise people:

- **A test never names a map.** A map is content: the suite walks all of them and asks only
  that they load, parse, read back as themselves and draw. A test that needs a map builds
  its own, in a few lines of JSON.
- **The engine's numbers live in `game/engine/original.py`**, and every other module of the
  engine is rules. A number written into a rule fails the suite.

## What a change looks like

**One change, one branch, one pull request.** It closes with the checks green, a headless
screenshot of the thing working, and somebody looking at it. A pull request that does one
coherent thing and says what it measured is easy to take; one that does four things is four
reviews.

Two habits the project leans on:

- **Measure before you argue.** Nearly every decision here that changed somebody's mind did
  it with a number. If you are about to write "this would be expensive", spend ten minutes
  finding out.
- **Render it before committing to it.** A naming or shape decision gets dragged through
  `game/render/assets.py`, `art/` and every map and test that names one, so look at the
  picture first. `python tools/rom_shot.py` draws a course as the collision sees it.

## Tests

A new test is welcome; a new test with a docstring saying *why it exists* is worth more.
When a test fails in three years, the docstring is what tells somebody whether the test or
the code is wrong.

- **The Pyxel session is shared across the whole suite.** A test that writes into the image
  bank or leaves another style installed changes what every later test measures. Put it back.
- **No skips and no xfail.** Where a test has to leave something out, it excludes it from a
  loop rather than skipping, and asserts that what remains is not empty.
- **The engine is held to a record.** A change that means to change how a race rides says
  so in its pull request and records again with `python tests/test_engine_golden.py`.

## Courses, as files

A course is JSON, drawn in the editor or written by hand. It is built the way the original
builds its own: a ring of 16 by 256 **metatiles** of 16x16 pixels, and a course is a list of
**pieces** stamped onto it. Where two pieces land on the same cell they are merged tile by
tile, so the shape where one thing meets another never has to be a piece of its own.

- `art/terrain/<name>.png` -- a tile, 8x8, in the four shades. A drawing.
- `maps/tiles.json` -- what each tile **collides as**: solid, soft, no wheelie, a rock, and
  which of the engine's 32 directions it runs in. Declared, never read off the picture.
- `maps/metatiles.json` -- four tile names each, top left to bottom right. `-` lets whatever
  is underneath through.
- `maps/pieces.json` -- a grid of metatile names: what a course puts down. `.` stamps nothing.
- `maps/labels.json` -- a name you can read and a kind (ground, slope up, curve, sign...)
  for every metatile and piece. The editor's palette is grouped by kind, and the name shows
  on the status line under the pointer.
- `maps/courses/<name>.json` -- the pieces at `[row, col, name]`, the crates at
  `[kind, row, col]`, the three levels' time limits, and the stretches where the computer's
  bike is put back.

The tiles, metatiles and pieces are the original's, under its own numbers in hex (`t45` is its
tile 0x45, `p57` its piece 0x57), and the eight courses are the original's eight written in
them. `python tools/vocab_from_rom.py --rom <file.gb> --check` builds every course out of
`maps/` and compares it, cell by cell and ride by ride, with the one your cartridge builds.
`maps/read.py` describes the files at more length.

**Which directory a course is in is what kind of course it is**; nothing in the file says:

- `maps/courses/` holds the courses the project ships: committed, and on the front end.
- `maps/drafts/` is yours: gitignored, and the `custom` tab of FREE RIDE -- with a cartridge
  or without one, drawn in the cartridge's art and sounding with one of its tunes when there is
  one.
- `maps/enhanced/` is the **enhanced** vocabulary: the original's with this game's own tiles,
  metatiles and pieces added over it. Its `drafts/` are yours and on FREE RIDE with the rest;
  in the editor its own pieces are the `extra` tab.

A name may live in one directory only; a name in two is refused at startup rather than
resolved, so a copy has to be renamed. **No test measures what a course is like**: the suite
asks that every course loads, that its schema is clean, that it reads back as itself and
that it draws. So a course can be retuned for how it plays without a test in the way.

## Licensing

Everything you contribute is committed under this repository's MIT licence, so it has to be
yours to give. A cartridge, or anything rendered out of one -- `sound.bank`, a screenshot of
its screens -- never goes in the repository.

## Filing something instead

A bug report that says what you did, what you expected and what happened is enough. If it is
about a map, attach the JSON: it is the whole reproduction. If it is about the editor, attach
`./editor.log`, which records every click. If it is about a race, say which course and level,
and whether you had a cartridge: the two reach the engine by different roads, and the road is
usually where the fault is.
