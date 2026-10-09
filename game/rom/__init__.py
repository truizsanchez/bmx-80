"""The original game's own data, read out of the player's cartridge file.

**This package carries nothing out of the cartridge.** It knows *where* the
original keeps a course and *how* to read it -- the way a program that opens a
file format knows the format -- and reads it from a copy of the ROM the player
supplies. Without one, the game runs on the courses in `maps/`; with one, the
same engine rides the original's courses as the cartridge builds them.

No table, map or picture is written into this package, and
`tests/test_engine_is_rules.py` refuses a literal table here just as it does in
the engine.

Only the European release is read, and anything else is refused by name
(`cartridge.py`). No Pyxel.
"""
