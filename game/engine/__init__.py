"""The engine: Motocross Maniacs' physics, reimplemented rule by rule.

What the original does, as its own arithmetic does it -- not a model tuned to
look like it. Every rule here is one the original applies, in the order it
applies them, and a test beside it says so.

The package keeps five rules of its own:

- **Integers only.** The original works in bytes and words, and rounding is part
  of what it does: a speed computed in floats is a different speed. No `float`
  in a tick; the one rule that needs one -- the sine -- is computed once, at
  import, into integers.
- **Its units.** A position is 8.8 fixed point in y and 16.8 in x, in pixels; a
  velocity is in 1/256 px per tick; y grows downward. A **direction** is one of
  32, counter-clockwise from the right: 0 is right, 8 up, 16 left, 24 down.
- **Numbers are rules, not tables.** Nothing here is a table read out of a
  cartridge: where the original looks a value up, this computes it, and
  `tests/test_engine_is_rules.py` refuses a long literal list of integers.
- **Its numbers are in one file.** Every number the rules run on is the
  original's, and every one is in `original.py` -- the rest of the package is
  the rules, as an engine written from scratch would have them. The same test
  refuses a number past two anywhere else.
- **No Pyxel**, like the rest of the model.
"""
