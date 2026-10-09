# bmx-80

A 2D side-scrolling motocross game, built with [Pyxel](https://github.com/kitao/pyxel).
160x144, an 8-pixel terrain grid, and four shades of grey.

**The engine is a reimplementation of Motocross Maniacs' own**, rule for rule: integer
arithmetic, the original's tick order, terrain read as tiles. It rides the original's eight
courses, and it is playable from start to finish **without the cartridge**: the courses
are written out in `maps/`, and the screens between races, the band under the view and the
sound effects are this game's own. Given your own copy of the cartridge, it reads the
original's courses, art, screens, music and sound out of it instead.

## Playing it

The releases carry a zip per system with **one file in it**: unzip it anywhere and run
`bmx-80` (Windows: `bmx-80.exe`). No Python, no install, nothing to uninstall.

Windows will warn that the publisher is unknown: the binary is not code-signed. "More
info" then "Run anyway", or build it yourself from the source below.

Your times and your drafts go in a **`bmx-80-data/` folder beside the executable**, so you
can find them, back them up or delete them. Move the executable and it makes a new one;
move the folder with it and you keep your records.

### The keys

The Game Boy's pad is laid on the keyboard the way two hands held it:

| Game Boy | Keyboard | In a race |
|---|---|---|
| the cross | **W A S D** (or the arrows on the screens) | **A** leans back -- a wheelie on the level -- and **D** forward; **W** held at a take-off makes a longer jump |
| A | **K** | the throttle |
| B | **J** | a nitro |
| Start | **Enter** | start, pause |
| Select | **Space** | on the title, the next way to play |

**Esc** leaves a race, goes from the menu back to the title, and from the title quits.

### The screens

The game opens on the original's front end: a title where you choose **SOLO** or **VS
COMPUTER**, then a course (1 to 8) and a level (eAsy, Bumpy, Crazy), a card with the course
record and the time to qualify, the race, and the results, or **TIME UP** and **GAME OVER**
when the clock runs out first. VS 2-PLAYER is on the title as it is on the original, and
asks for a link cable nobody answers, as the original does with none attached.

The title has a fourth row, **FREE RIDE**: any of the eight courses or your own drafts, at
any level, in either **mode** -- *classic*, the original's, or *excessive*, the same race at
sixty steps a second (experimental; its times are not kept as records). There the arrows
belong to whichever of the three things you are choosing -- the course, the level, the mode --
and **Tab** hands them over; **Space** puts the computer's bike in the race or takes it out,
**Enter** starts, **Esc** goes back. The front end itself always plays the original's way.

## Your cartridge

The game reads **only the European release** of Motocross Maniacs for the Game Boy:

| | |
|---|---|
| Title in the header | `MOTOCROSSMANIACS` |
| Size | 32,768 bytes |
| SHA-1 | `956a12a65a1c39948c312303719895bd6f141a61` |

Check yours before you use it:

```bash
sha1sum "Motocross Maniacs (Europe).gb"                            # Linux
shasum -a 1 "Motocross Maniacs (Europe).gb"                        # macOS
certutil -hashfile "Motocross Maniacs (Europe).gb" SHA1           # Windows
```

Then hand it to the game with `--rom` (the file name does not matter; the hash does):

```bash
bmx-80 --rom "Motocross Maniacs (Europe).gb"        # the release
python main.py --rom "Motocross Maniacs (Europe).gb" # from the source
```

With it, the eight courses are read out of the cartridge rather than out of `maps/`, and
drawn in its own art; the title, the course select, the card and the results are its own
screens; the bike is its own sprites; and the race sounds with the original's sound driver,
music included. The first run renders the cartridge's sound once, about fifteen seconds, and
keeps it in a file called `sound.bank` beside your records so that every run after starts at
once. That file is derived from your copy and is yours: it is never shipped, and deleting it
only means it is rendered again.

**Anything else is refused**, with a line on the terminal saying why -- the wrong size, not
Motocross Maniacs, or Motocross Maniacs but another release -- and the game runs as it does
without a cartridge. The cartridge is not in this repository, and this project does not tell
you where to get one: dump your own.

## Other options

```bash
bmx-80 --palette green          # the four shades in the original screen's green
bmx-80 --mode excessive         # FREE RIDE starts on the experimental excessive mode
bmx-80 --ride <course.json>     # straight onto one course file, as the editor rides one
```

**What it has not got:** a second player, and music without a cartridge -- the sound effects
are this game's, the tunes are the cartridge's.

## Running it from the source

Python 3.10 or newer (Pyxel's own floor) and one dependency, which is Pyxel.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

pyxel run main.py
```

To build the release zip yourself, on the system you are on:

```bash
pip install -r requirements-dev.txt
python tools/build_exe.py           # -> dist/bmx-80-<version>-<system>-x64.zip
```

Linux and Windows. macOS is not built, and a Windows executable cannot be built from
Linux: the repository's `release` workflow builds that one on a Windows machine.

## Making a course

The game comes with an editor. It opens a course by name, or starts a new one if the name
is not taken:

```bash
bmx-80 --edit <name>                          # the release
python main.py --edit <name>                  # from the source
python main.py --edit <name> --rom <file.gb>  # ...drawn in your cartridge's own art
python main.py --edit <name> --enhanced       # ...a new draft with this game's extra pieces
```

**The editor has not been tested as thoroughly as the game.** It works for drawing and riding
a course, but expect rough edges, and save often. A bug report with the editor's log (see
below) is very welcome.

A course is built the way the original builds its own: **pieces** -- a stretch of road, a
ramp, a loop -- put down on a grid. Where two pieces overlap they are merged, so what you see
under the pointer is exactly what the game will build.

- **Draw**: pick a piece (or a single block) from the palette on the right and click to put
  it down on top. Drag along a row to repeat it. Right-click takes away what is on top;
  ALT-click picks it up.
- **Order**: `TAB` walks what is stacked under the pointer, and `[` `]` move it down or up.
- **Things**: the `things` tab puts down the crates. A drag along a surface marks a stretch
  where the computer's bike is put back when it falls behind (the orange lines). The three
  levels' clocks are on the toolbar.
- **Look**: `Z` zooms, `C` shows what the bike collides with, `G` the game's own view from the
  pointer, `O` the whole lap. The status line names whatever is under the pointer.
- **Ride it**: `R` rides what is drawn, in a window of its own.
- `CTRL-S` saves, `CTRL-Z` / `CTRL-Y` undo and redo, `H` lists every key.

What you draw is a **draft**: it goes in `maps/drafts/` (in `bmx-80-data/` beside the
executable, for the release), and you ride it from **FREE RIDE**, on the `custom` tab -- with
a cartridge or without one. Every click in the editor is written to `editor.log`, which is
what to attach to a bug report.

A course is a JSON file underneath; [`CONTRIBUTING.md`](CONTRIBUTING.md#courses-as-files)
describes the files, for anyone who wants to write one by hand or change the pieces.

## Working on it

[`CONTRIBUTING.md`](CONTRIBUTING.md) is how to set up, run the checks and send a change.
You do not need Python to improve the art: a terrain tile is a drawing in `art/terrain/`,
redrawn in place, and a PNG in `art/hand/` wins over the generated picture of the same name.

## Licence

MIT. See [`LICENSE`](LICENSE).

Motocross Maniacs is Konami's. This project is not affiliated with or endorsed by Konami, and
the eight courses in `maps/courses/` and the vocabulary they are written in are the original
game's, not this project's to license.

**Part of `tools/editor/` is somebody else's, and it is MIT too.**
[`tools/editor/widgets/`](tools/editor/widgets/) is Pyxel's own editor toolkit, vendored for
the map editor's mouse capture, and [`tools/editor/palette.py`](tools/editor/palette.py) is
adapted from Pyxel's editor as well. Copyright (c) 2018-2026 Takashi Kitao; the licence text
is [`tools/editor/widgets/LICENSE-pyxel`](tools/editor/widgets/LICENSE-pyxel) and every file
says at the top where it came from and what was edited.
