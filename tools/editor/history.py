"""Undo: every state the document has been in, and which one it is in now.

**Whole states, and not inverses of edits.** A stack of `(kind, thing)` to be
popped works exactly as long as every edit is an append, and they are not:
deleting piece 40 of 700 has no inverse you can pop. So the owner hands in the
whole of itself after each edit, and going back is handing one of those back.

**It knows nothing of a document.** A state is whatever `Document._snapshot`
makes, and this never looks inside one -- which is why it is typed in full and
the document it serves is not, and why the three rules below can be read here
without a map in sight. No pyxel.
"""

from typing import Generic, TypeVar

State = TypeVar("State")


class History(Generic[State]):
    """A line of states and a place on it. The first is the file as opened."""

    def __init__(self, first: State) -> None:
        self._states = [first]
        self._at = 0

    def __len__(self) -> int:
        return len(self._states)

    def record(self, state: State) -> None:
        """Keep this edit, and drop any future that was undone past.

        The usual rule, and the one an author expects: undo three times, draw
        something, and the three you took back are gone rather than waiting to
        come back over the top of what you just did.
        """
        del self._states[self._at + 1:]
        self._states.append(state)
        self._at = len(self._states) - 1

    def amend(self, state: State) -> bool:
        """Fold this change into the edit before it. False where there is none.

        A drag is one edit however many calls it takes -- undo that took a
        stroke back one cell at a time would not be undo, it would be erasing.
        The first state is not an edit but the file as it was opened, so there
        is nothing to fold into there, and the caller records instead.
        """
        if self._at == 0:
            return False
        self._states[self._at] = state
        return True

    def back(self) -> State | None:
        """The state one edit back, or None at the start."""
        if self._at == 0:
            return None
        self._at -= 1
        return self._states[self._at]

    def forward(self) -> State | None:
        """The state one undo forward, or None where nothing was undone."""
        if self._at + 1 >= len(self._states):
            return None
        self._at += 1
        return self._states[self._at]
