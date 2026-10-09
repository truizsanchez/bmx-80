"""Every map this game has of its own, in one list per directory.

**The directory is the statement.** `maps/courses/` is a course, on the menu;
`maps/drafts/` is the author's, gitignored and answerable to none of them.
`maps/enhanced/courses/` and `maps/enhanced/drafts/` are the same two again in
the **enhanced** vocabulary -- the original's with this game's own pieces over
it, and no cap on metatile ids. Which directory a file is in is the whole of
what kind of map it is -- nothing in the file says.

The format they are written in is `maps/read.py`, and what the engine reads is
`game/course.py`.
"""

import os
from collections.abc import Callable, Sequence

from game.engine.terrain import Ground
from maps import read

HERE = os.path.dirname(os.path.abspath(__file__))

#: One row of a listing: the name a map is shown by, and how to build it. The
#: same shape the cartridge's courses are listed in (`main.cartridge_courses`),
#: because the engine asks the same thing of either -- a `Ground`, and a
#: `Course` of ours is one.
Listed = tuple[str, Callable[[], Ground]]
Listing = Sequence[Listed]

# ...and the courses, which is the menu's first tab. Read at import, because
# the listing is a fact about the disk and every screen wants the same one.
LISTED: Listing = read.listed()
# ...the enhanced courses, a tab of their own.
ENHANCED: Listing = read.listed(read.ENHANCED_COURSE_DIR, vocabulary=read.ENHANCED_VOCABULARY)
# ...and the author's drafts, which are gitignored: classic and enhanced in one
# tab, each built in its own vocabulary.
DRAFTS: Listing = [*read.listed(os.path.join(HERE, "drafts"), vocabulary=read.CLASSIC),
                   *read.listed(os.path.join(read.ENHANCED, "drafts"),
                                vocabulary=read.ENHANCED_VOCABULARY)]

# Every map there is: the project's courses, then the author's drafts.
TRACKS: Listing = [*LISTED, *ENHANCED, *DRAFTS]
# ...and the project's alone, which is what the course rules in `tests/` walk.
COMMITTED: Listing = [*LISTED, *ENHANCED]

BY_NAME: dict[str, Callable[[], Ground]] = dict(TRACKS)
