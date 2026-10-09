"""The engine is written as rules, and the cartridge reader never copies a table.

The original looks most of its numbers up: a speed curve, a quarter sine, a
landing window per direction. This repository reproduces what those tables do
and does not carry them -- every one is re-expressed as the rule that generates
it, and a rule is also the thing a reader can check.

So this is a claim about the **text**, the way
`test_no_test_reads_a_map_the_repo_does_not_ship` is: no literal list, tuple or
set of more than a handful of integers anywhere in `game/engine/` -- or in
`game/rom/`, which reads the original's tables out of the player's cartridge and
must never carry one of its own. The two tables a course hands the engine about
the bike -- its probes and the throw -- are content, in `maps/tables.json`, and
reach the engine through the `Ground` it rides like the rest of a course. A table that
slipped in would pass every behavioural test -- it would *be* the original's
behaviour -- which is exactly why only the text can refuse it.
"""

import ast
import pathlib

GAME = pathlib.Path(__file__).resolve().parent.parent / "game"
PACKAGES = (GAME / "engine", GAME / "rom")

#: The most integers a literal may carry: enough for a short rule's constants,
#: far too few for any table the original has.
MOST = 8


def _integers(node):
    return sum(1 for element in node.elts
               if isinstance(element, ast.Constant) and type(element.value) is int)


def test_the_engine_carries_no_table():
    sources = sorted(source for package in PACKAGES for source in package.glob("*.py"))
    assert all(any(p.glob("*.py")) for p in PACKAGES), "a package to check is missing"
    tables = []
    for source in sources:
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, (ast.List, ast.Tuple, ast.Set)) and _integers(node) > MOST:
                tables.append("%s:%d" % (source.name, node.lineno))
    assert not tables, "a table in the engine, where a rule should be: %s" % tables


def test_the_check_would_see_one():
    """The guard, pointed at a table, has to fire -- or it is guarding nothing."""
    table = ast.parse("CURVE = (0, 8, 16, 16, 32, 32, 48, 48, 52, 54)").body[0].value
    assert _integers(table) > MOST


def _numbers_outside_original():
    """Every integer literal past two in `game/engine/` but `original.py` --
    leaving out an index into a sequence (`probes[3]`) and the members of an
    enum, which number a state rather than tune one."""
    found = []
    for source in sorted((GAME / "engine").glob("*.py")):
        if source.name == "original.py":
            continue
        tree = ast.parse(source.read_text())
        exempt = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                    getattr(base, "id", "") in ("Enum", "IntEnum") for base in node.bases):
                exempt.update(id(inner) for inner in ast.walk(node))
            if isinstance(node, ast.Subscript):
                exempt.update(id(inner) for inner in ast.walk(node.slice))
        found += ["%s:%d" % (source.name, node.lineno) for node in ast.walk(tree)
                  if isinstance(node, ast.Constant) and type(node.value) is int
                  and abs(node.value) > 2 and id(node) not in exempt]
    return found


def test_every_number_the_engine_runs_on_is_in_one_file():
    """Why this test: the engine is two things -- rules an engine written from
    scratch would have, and the numbers that make those rules Motocross
    Maniacs -- and for a long time the numbers were spread through a dozen
    modules, a 57-tick crash written as `elif t >= 29` and a speed curve as
    `68 + 2 * ...`. They are all in `game/engine/original.py` now, named and
    grouped, and this keeps them there: a number in a rule is a number a reader
    cannot find, and a mode cannot move.

    A two is left alone: halving, doubling and the two tiles of a metatile are
    arithmetic, not tuning."""
    assert not _numbers_outside_original(), \
        "a number of the original's outside original.py: %s" % _numbers_outside_original()
