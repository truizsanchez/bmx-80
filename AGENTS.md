# bmx-80 — working notes for an agent

A 2D side-scrolling motocross game in [Pyxel](https://github.com/kitao/pyxel). 160x144,
an 8-pixel terrain grid, four shades of grey.

**The engine is a reimplementation of Motocross Maniacs' own**: integer arithmetic, the
original's tick order, terrain read as tiles. It rides the original's eight courses. Without a
cartridge they come out of `maps/`, written in the original's own vocabulary (`maps/read.py`),
and the whole game -- front end, band, sound effects -- is this game's own. With the player's
own cartridge (`--rom`, the European release only) the courses, art, screens and sound are read
out of it.

This file is the repo as it is now. Two companions, and they answer different questions:

| | |
|---|---|
| [`docs/DESIGN.md`](docs/DESIGN.md) | the contract: the engine, the original's screens and sound, the map model, the menu, the art. **Check it first when in doubt about intended behaviour.** |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | setting up, the checks, and sending a change -- for a human. The rules are here. |

## Layout

```
main.py              # the window and the frame loop: App, the front end's and the
                     #   menu's keys, a race's cadence, --selftest and the flags
game/
  constants.py       # the screen, the grids (CELL=16 for glyphs, TILE=8 for the
                     #   terrain) and the window's rates
  engine/            # the engine: Motocross Maniacs' own, rule by rule, in integers.
                     #   No Pyxel, and no table out of a cartridge
    original.py      #   every number the engine runs on, and each is the original's:
                     #   the machine, the map, speed, the air, the crash, the race,
                     #   the rival, the camera. The rest of engine/ is the rules
    rules.py         #   the engine's vocabulary: the states (numbered as the
                     #   original's), the sound cues, and `Ruleset`, the few numbers
                     #   a mode may move. `CLASSIC` is the original's
    speed.py         #   the index, the curve, the nitro, the slope term, the magnitude
    vector.py        #   a magnitude along one of 32 directions, as (vx, vy)
    terrain.py       #   `Hit`, a tile as the collision sees it, and `Ground`, what a
                     #   course answers the engine
    probes.py        #   the 6x6 window of tiles around the bike, and the cells probed
    flight.py        #   the air: a jump's class and fall, the turn towards the ground,
                     #   the rider turning the bike, the landing window
    items.py         #   the six things to pick up -- S, T, N, R, J, mini-maniacs --
                     #   when the bike is on one, and what each does
    camera.py        #   the original's camera, which rides with the player's velocity
    background.py    #   the course as the screen has it: each column as it was when
                     #   it scrolled in, so a sign put up at the lap line is seen only
                     #   the next time round
    rival.py         #   the computer's bike: its buttons, its handicap by the gap to
                     #   the player, its teleport when it falls behind
    run.py           #   a race: the countdown, the two bikes, the lines, the things
                     #   picked up, the clocks, and the sound cues
    bike.py          #   one bike and one tick, in the original's order, a method per
                     #   state: stopped, riding, a wheelie, the air, a crash, down
  rom/               # the player's own cartridge, read. Knows where the original keeps
                     #   each thing and carries nothing out of it
    cartridge.py     #   the file, identified by SHA-1 and refused otherwise with the
                     #   reason; reads of it by address
    course.py        #   a course built as the original builds it at the start of a
                     #   race: pieces stamped and merged, then the crates
    graphics.py      #   the original's tile art, loaded as the game loads it
    screen.py        #   the original's screens -- the logo, the title, the course
                     #   select, the card, the results, GAME OVER -- painted by running
                     #   the little program the cartridge keeps each one as
    panel.py         #   the band under the view (speedometer, TIRE, JET, the time bar,
                     #   the nitros), the start's 3 2 1 GO!, the pin over the player's
                     #   bike, and the TIME UP box -- which tiles each is, per moment
    sound.py         #   the original's sound driver, run on the cartridge's data
    apu.py           #   the Game Boy's sound chip: register writes in, samples out
    mixer.py         #   what a race sounds like, as clips rendered once and kept in
                     #   ./sound.bank
  course.py          # a course of this game's own, in the original's shape: the ring
                     #   of metatiles, the merge, the collision each tile declares.
                     #   `Tileset` is where an author's names become the engine's ids.
                     #   Also the three levels, and `Tables` (maps/tables.json)
  front.py           # the front end as a model: which screen is up -- the logo, the
                     #   title, the course, the level, the card, the race, the results,
                     #   TIME UP and GAME OVER -- what was chosen, and the records.
                     #   The game opens on it, with or without a cartridge
  menu.py            # FREE RIDE, behind the title's fourth row: the eight courses
                     #   and the drafts, a level, a mode (classic or excessive)
  sfx.py             # the sound effects with no cartridge, as data for Pyxel's
                     #   synthesizer: one per sound cue, the screens', the engine note
  mode.py            # a way to play: a `Ruleset` and the rate the engine steps at.
                     #   classic is the original's; excessive (experimental) is the
                     #   same race at 60 steps a second
  cadence.py         # which displayed frames step an engine
  records.py         # best times and scores by course and level, in ./records.json
  trace.py           # an append-only event log, silent with no path
  paths.py           # where the game writes: the repo in a checkout, bmx-80-data/
                     #   beside the executable in a build
  render/            # everything drawn, and the sound played -- the only Pyxel in game/
    headless.py      #   a window nobody looks at, for the tools and the suite
    style.py         #   a look as data: four colours and two thresholds
    palette.py       #   the four shades, and the looks (grey, green)
    assets.py        #   the art in Pyxel's banks by name; `art/hand/` wins by name
    lettering.py     #   a line of text centred, and a word in reverse video
    rom_art.py       #   the cartridge's tiles in Pyxel's bank: a course's art or the
                     #   screens' lettering, never both at once
    front_draw.py    #   the screens between races, the cartridge's and this game's
    menu_draw.py     #   the menu
    ride_draw.py     #   a race: the course, the bikes, the band, the start, TIME UP
    audio.py         #   the sound played: the cartridge's clips (`Audio`) or this
                     #   game's own effects (`OwnAudio`), behind the same calls
art/                 # the art
  STYLE              #   which look art/ was generated in
  tiles/             #   16x16 glyphs and the logo, generated by tile_gen.py
  terrain/           #   8x8 terrain tiles, one PNG a name: drawings. maps/tiles.json
                     #     names them and says what each collides as
  moto/              #   the bike's 32 rotations and the crash, generated by sprite_gen.py
  hand/              #   a PNG here wins over the generated one of the same name
docs/                # DESIGN.md, the contract
maps/                # the courses, and the vocabulary they are drawn in: the
                     #   original's, under its own numbers in hex (`t45`, `m1a`, `p57`),
                     #   written by tools/vocab_from_rom.py. Which directory a file is
                     #   in is what kind of map it is -- nothing in the file says
  tiles.json         #   every terrain tile and what it collides as: solid, soft, no
                     #     wheelie, a rock, one of the engine's 32 directions
  metatiles.json     #   four tile names each, TL TR BL BR; `-` lets the tile under through
  pieces.json        #   a grid of metatile names: what an author puts down; `.` erases
  tables.json        #   which window cells the floor probes read, one row an attitude,
                     #     and the thrown rider's arc: the original's, as content
  labels.json        #   a readable name and a kind for every metatile and piece --
                     #     the ids are the original's numbers. The editor's palette
                     #     is grouped by kind; the engine never reads it
  courses/           #   the eight courses: pieces at (row, col), crates, the three
                     #     clocks, the teleports. On the front end
  drafts/            #   yours: gitignored, on the menu, held to none of the rules
  enhanced/          #   the enhanced vocabulary: tiles, metatiles and pieces added over
                     #     the original's (never redefining one), and its own courses/
                     #     and drafts/. No cap on metatile ids
  read.py            #   the files, read. What refuses a bad one is game/course.py
tools/
  tile_gen.py        # writes art/tiles/; --check proves it fresh
  sprite_gen.py      # writes art/moto/; --check proves it fresh
  art_check.py       # whether a drawing is one the game can load; --list is every
                     #   tile, what draws it and where it appears
  art_sheet.py       # every tile, metatile, piece, glyph and pose on one PNG
  label_vocab.py     # drafts maps/labels.json from the collision; never overwrites a
                     #   label that is there; --check lists what has none
  menu_shot.py       # the menu, windowless
  rom_shot.py        # a course of your cartridge, drawn as the collision sees it
  vocab_from_rom.py  # maps/ written out of your cartridge; --check builds every course
                     #   both ways and compares them, cell by cell and ride by ride
  solve.py           # can a course be finished under a ruleset, and how fast: a beam
                     #   search over the pad, a portfolio of configurations, and
                     #   `fragility`, how exactly the line found must be ridden. Slow
  build_exe.py       # the game frozen into one executable and zipped (PyInstaller);
                     #   runs `main.py --selftest` against the binary
  pixels.py          # what the generators share: a raster, a PNG by hand, --check
  editor/            # the course editor: `main.py --edit <name>`
    ui.py            #   the window: map, palette, toolbar, status, editor.log
    view.py          #   where everything in it is, as arithmetic
    document.py      #   the course in hand and every edit to it
    map_file.py      #   where it lives, and whether a save would change it
    history.py       #   undo: every state a document has been in
    palette.py       #   the chrome's colours and the game's four shades (from Pyxel's
                     #   editor, MIT)
    widgets/         #   Pyxel's editor toolkit, vendored unchanged (MIT)
tests/               # the suite. tests/golden/ holds the engine's recorded races
```

## The five rules

Enforced by tests, not by review, so they fail for you before anybody sees them.

1. **Pyxel stays at the edges.** Only `main.py`, `game/render/` and `tools/` may import it;
   the model stays window-free so a test can drive it. `tests/test_model_is_window_free.py`.
2. **`game/` never names `tests/`, and `tests/` never names a map.** `maps/` is content,
   drawn and meant to be retuned: the tests walk every map and choose none by name
   (`test_no_test_reads_a_map_the_repo_does_not_ship`). A test that needs a map builds one
   in a few lines of JSON.
3. **Generated art is a cache with a proof.** `art/moto/` and `art/tiles/` are what
   `sprite_gen.py` and `tile_gen.py` write, and `--check` says so byte for byte; never
   hand-edit them. The terrain is not generated: a tile is a drawing in `art/terrain/`,
   and its collision is declared in `maps/tiles.json`.
4. **World and screen coordinates never share a variable.** Every draw takes the camera
   offset `(cam_x, cam_y)` and draws at `world - cam`.
5. **One way to make a map, and it is the one that rides.** A course is what the engine
   reads -- the `Ground` protocol in `game/engine/terrain.py`. A course of this game's own
   is in the original's shape: a ring of 16x256 metatiles, pieces stamped with a
   tile-by-tile merge, a collision each tile declares. **The merge is the vocabulary**: a
   shape that is two pieces overlapping is not a piece of its own.

Four more checks hold the code's shape:

- **The engine's numbers are in one file.** Every integer past two in `game/engine/` is
  in `original.py`, and no module of the engine or of `game/rom/` carries a table of the
  cartridge's (`tests/test_engine_is_rules.py`).
- **The engine rides as it rode.** `tests/test_engine_golden.py` holds six races,
  iteration by iteration. A change that means to change how the engine rides says so and
  records again: `python tests/test_engine_golden.py`.
- **No function has more than a dozen paths** (`tests/test_complexity.py`), with three
  hardware emulators let through, each for a stated reason.
- **The build ships what the game reads.** A new data directory goes in
  `tools/build_exe.py`'s `DATA`, which `tests/test_build_manifest.py` checks; a single new
  file is caught only by building, which runs `--selftest` on the binary.

## Commands

```bash
source .venv/bin/activate           # pip install -r requirements-dev.txt, once
python -m pytest tests/ -q -n auto  # the suite: no window, no skips, no xfail
python -m mypy                      # reads mypy.ini: a floor over the whole repo,
                                    #   and a strict list annotated in full
python -m pyflakes game maps tools tests main.py
python -m coverage run -m pytest tests/ -q -n auto && python -m coverage combine \
  && python -m coverage report      # three steps: the -n auto workers are subprocesses
python tools/tile_gen.py --check    # the glyphs and the logo are what the text says
python tools/sprite_gen.py --check  # the bike art is what the model says
python tools/art_check.py           # ...and any hand-drawn tile is a tile
python main.py --selftest           # every tile and every course loaded, no window
python tools/build_exe.py           # one executable in a zip: what a player is handed

pyxel run main.py                   # the game, without a cartridge
python main.py --rom <file.gb>      # ...with one: WASD, K (A), J (B), Enter, Space, Esc
python main.py --palette green      # ...in the original screen's green
python main.py --mode excessive     # ...at 60 steps a second (experimental)
python main.py --ride <file.json>   # ...straight onto one course file
python main.py --edit <name>        # the editor: a course by name, or a new draft
python main.py --edit <name> --enhanced       # ...a draft in the enhanced vocabulary
python main.py --edit course1 --rom <file.gb> # ...its tiles in the cartridge's art;
                                              #   `R` rides it in the same art

python tools/art_check.py --list    # every tile, what draws it, where it appears
python tools/art_sheet.py           # every picture the game loads, on one sheet
python tools/menu_shot.py           # the menu, windowless
python tools/rom_shot.py --rom <file.gb> 1          # a course of yours, as collision
python tools/vocab_from_rom.py --rom <file.gb> --check  # maps/ against the cartridge
python tools/solve.py 1 2 --levels free,crazy       # can it be finished, how fast
python tools/solve.py 1 --cap 111 --step 4          # ...under another ruleset
```

A course out of `maps/` rides with the original's own probe table and throw
(`maps/tables.json`), so it rides frame for frame as the cartridge's does, and
`vocab_from_rom --check` rides every course both ways to prove it.

## Working here

**One change, one branch, one pull request**, closed with three things: the checks green,
a headless screenshot of the thing working, and somebody looking at it.

Two habits the project runs on:

- **Measure before you argue.** Several decisions stated confidently in prose were
  reversed by ten minutes of measurement. A number in a doc is re-measured before it is
  repeated.
- **Render it before committing to it.** A naming or shape decision gets dragged through
  `game/render/assets.py`, `art/` and every map and test that names one, so look at the
  picture first. `tools/rom_shot.py` draws a course as the collision sees it, which is the
  view that catches a map that measures well and rides badly.

When adding a test, a docstring saying *why it exists* is worth more than the test: when
one fails in three years, it is what says whether the test or the code is wrong. **No
skips and no xfail**: where a test must leave something out it excludes it from a loop and
asserts that what remains is not empty.
