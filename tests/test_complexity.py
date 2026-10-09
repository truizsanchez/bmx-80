"""No function of ours has more than a dozen ways through it.

Why this test: the code grew by sediment -- a branch added for each thing a
screen, a state or a tool learned to do -- and the longest functions were the
ones nobody could hold in their head: the front end's update at 28 paths, the
race's step at 22, the editor's key handler at 24. They were broken up into
steps with names, and this keeps them that way. A function that needs a
thirteenth path needs a second function.

The count is McCabe's, measured on the syntax tree: one, plus one for every
`if`, loop, conditional expression, `except`, comprehension, `assert` and
extra operand of `and`/`or`. The vendored widgets are Pyxel's and not counted.

**Three are let through, each for a reason of its own**, and the list is held
to being true: every one of them has to exist and still be over the limit.
"""

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

LIMIT = 12

#: What is let through, and why.
ALLOWED = {
    # The Game Boy's sound chip, a sample at a time: every channel's state is
    # read into locals above one loop, because this loop is where the whole of
    # a sound bank's rendering time goes, and a clip must come out byte for byte
    # what it was. Split into calls, it is several times slower.
    "game/rom/apu.py:render",
    # The chip's register map: one write, decided by which of its twenty-odd
    # registers it lands on -- the hardware's own table, as a chain.
    "game/rom/apu.py:write",
    # The original's sound driver's opcodes E7-EF and their arguments: an
    # interpreter's switch, one arm an opcode.
    "game/rom/sound.py:_command",
}


def _sources():
    sources = sorted([*(ROOT / "game").rglob("*.py"), *(ROOT / "tools").rglob("*.py"),
                      ROOT / "main.py", ROOT / "maps" / "read.py"])
    return [s for s in sources if "widgets" not in s.parts]


def _complexity(function):
    paths = 1
    for node in ast.walk(function):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.IfExp, ast.ExceptHandler,
                             ast.comprehension, ast.Assert)):
            paths += 1
        elif isinstance(node, ast.BoolOp):
            paths += len(node.values) - 1
        elif isinstance(node, ast.Match):
            paths += len(node.cases)
    return paths


def _measured():
    for source in _sources():
        name = source.relative_to(ROOT).as_posix()
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield "%s:%s" % (name, node.name), _complexity(node)


def test_no_function_has_more_than_a_dozen_paths():
    over = sorted("%s (%d)" % (name, paths) for name, paths in _measured()
                  if paths > LIMIT and name not in ALLOWED)
    assert not over, "split these into steps with names: %s" % over


def test_what_is_let_through_is_still_there_and_still_needs_it():
    """A function let through and then simplified, renamed or deleted would
    leave its name here allowing the next one of that name through unseen."""
    measured = dict(_measured())
    assert ALLOWED, "nothing is let through, and this proved nothing"
    for name in ALLOWED:
        assert name in measured, "%s is let through and no longer exists" % name
        assert measured[name] > LIMIT, "%s is back under the limit: take it off" % name


def test_the_count_sees_a_branch():
    """The measure, pointed at a function with two ifs, has to count three."""
    function = ast.parse("def f(a):\n if a: pass\n if not a: pass\n").body[0]
    assert _complexity(function) == 3
