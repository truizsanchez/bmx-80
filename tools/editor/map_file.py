"""Where the course in hand lives, and what was last written there.

A name, a path, and the file's text as the editor last wrote or opened it:
`dirty` is the question leaving asks -- is there anything a save would write --
and it is a question about the disk, not the window. **Compared as text**, and
the text is `read.dump`'s: one way to write a course, so two are equal exactly
when their files are.

No pyxel.
"""

import json
import os
from typing import Any

from game import paths
from maps import HERE, read

#: Where a course is looked for by name, in the order a name is found: the
#: project's courses, its enhanced ones, then the author's drafts.
DIRECTORIES = ("courses", os.path.join("enhanced", "courses"), "drafts",
               os.path.join("enhanced", "drafts"))


def drafts_dir(enhanced: bool = False) -> str:
    """Where a new course is written: the author's own, gitignored -- in the
    enhanced vocabulary's drafts when it is to be an enhanced course."""
    return (paths.user_path("maps", "enhanced", "drafts") if enhanced
            else paths.user_path("maps", "drafts"))


class MapFile:
    """One course's place on the disk: its name, its path, and what is there."""

    def __init__(self, name: str, path: str) -> None:
        self.name = name
        self.path = path
        #: The file as this editor last wrote or opened it; None until then.
        self._saved: str | None = None

    @classmethod
    def named(cls, name: str, enhanced: bool = False) -> "MapFile":
        """Wherever a course of that name lives; nowhere yet is a new draft,
        classic or `enhanced`."""
        for directory in DIRECTORIES:
            path = os.path.join(HERE, directory, name + ".json")
            if os.path.exists(path):
                return cls(name, path)
        return cls(name, os.path.join(drafts_dir(enhanced), name + ".json"))

    @property
    def vocabulary(self) -> tuple[str, ...]:
        """The vocabulary this course is written in, which its place says."""
        return read.vocabulary_of(self.path)

    def read(self) -> "dict[str, Any] | None":
        """The course on the disk, or None for one not there yet."""
        if not os.path.exists(self.path):
            return None
        with open(self.path) as handle:
            data: dict[str, Any] = json.load(handle)
        self._saved = read.dump(data)
        return data

    def dirty(self, text: str) -> bool:
        """Whether writing `text` would change anything the file has."""
        return text != self._saved

    def write(self, text: str) -> str:
        """Write `text` here, making the directory if it is a new one."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as handle:
            handle.write(text)
        self._saved = text
        return self.path
