"""A log of what was asked and what was decided, one event to a line.

Written for a specific failure in the editor and worth keeping for the next one
anywhere: an author clicks, nothing is placed, and the status bar has one line in
which to say why. The interesting part is never the refusal itself -- it is the
*list* behind it: which ways of joining the open end existed, how far away they
were, and which shapes could have joined at all. That does not fit in a status
bar and does fit in a file that can be pasted into a conversation.

**It lives here because the game will want the same thing.** A rider can do
something the engine did not expect and have no way to say what it was, and a
screenshot cannot carry a flight.

Free of pyxel, like the rest of the model: the frame number arrives as a callable,
so a test can drive it with no window and `tests/test_model_is_window_free` keeps
it honest.

The format is one event per line, `key=value` after a kind, because the reader
is as likely to be `grep` as a person.
"""

import datetime
import os
from typing import Any, Callable, Iterable, TextIO


def _value(value: Any) -> str:
    """One line, and one field: quoted where it would otherwise be two."""
    text = repr(value) if isinstance(value, (list, tuple, dict)) else str(value)
    text = text.replace("\n", " ")
    return '"%s"' % text if " " in text else text


class Trace:
    """Append-only, flushed per line, and silent when there is nowhere to write.

    Silent rather than optional at every call site: the editor should not grow
    an `if self.trace` around every decision it makes, because the ones that get
    skipped will be the ones nobody thought were interesting.

    **Across sessions, not per session.** Opened with `"w"`, a bug report arrives
    with three lines in it -- the author had opened the editor
    again to check something and the run that mattered was gone. A log that is
    thrown away by the act of looking is the opt-in default's mistake in another
    costume: it is empty exactly when it is wanted. The `----` rule and the
    `start` line are what separate one run from the next, and `pid` is what
    tells two windows apart.

    It grows, and nothing here trims it yet: a session is a few hundred lines
    and the file is gitignored, so the day that matters is a long way off and
    guessing at a policy now would be guessing.
    """

    def __init__(self, path: str | None = None,
                 frame: Callable[[], int] | None = None, keep: int = 400) -> None:
        self.path = path
        self.frame = frame or (lambda: 0)
        self.keep = keep
        self.lines: list[str] = []
        self._handle: TextIO | None = None
        if path:
            fresh = not os.path.exists(path) or os.path.getsize(path) == 0
            self._handle = open(path, "a")
            if not fresh:
                self._handle.write("\n" + "-" * 72 + "\n")
            self.note("start", at=datetime.datetime.now().isoformat(timespec="seconds"),
                      pid=os.getpid())

    def note(self, kind: str, **fields: Any) -> str:
        line = "%6d %-8s %s" % (
            self.frame(), kind,
            " ".join("%s=%s" % (key, _value(value)) for key, value in fields.items()))
        self.lines.append(line)
        del self.lines[:-self.keep]
        if self._handle:
            self._handle.write(line + "\n")
            self._handle.flush()
        return line

    def close(self) -> None:
        if self._handle:
            self._handle.close()
            self._handle = None


def log_wanted(argv: Iterable[str],
               default: str | None) -> tuple[str | None, list[str]]:
    """Where a log goes, and the argv with the words that said so taken out.

    `--no-log` turns it off and `--log <path>` moves it; anything else leaves
    `default`. **On unless refused**, which is the rule both callers wanted for
    the same reason: a log that has to be asked for in advance is empty exactly
    on the run that needed it, because nobody knows they are about to hit the
    bug.

    Returns `(path or None, remaining argv)`. The game reads only the first
    half; the editor reads both, because what is left after these words is the
    name of the map to open. One function because a grammar written twice is a
    grammar that will disagree with itself -- these two already did, over
    whether `--log --debug` means a path called `--debug`. It does not.
    """
    rest = list(argv)
    log = default
    if "--no-log" in rest:
        rest.remove("--no-log")
        log = None
    if "--log" in rest:
        at = rest.index("--log")
        rest.pop(at)
        if at < len(rest) and not rest[at].startswith("--"):
            log = rest.pop(at)
    return log, rest
