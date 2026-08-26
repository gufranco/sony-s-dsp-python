"""Everything this package raises, in one place.

One module so a caller can see the whole set at once, and so `except` has
somewhere to import from. It imports nothing from the rest of the package, which
is what keeps it from ever closing a cycle: everything here raises, so everything
here imports this, and an import running the other way would make the order
modules happen to load in decide whether the package works at all.
"""

from __future__ import annotations


class UnknownModelError(Exception):
    """No part goes by that name.

    The message names the parts that would have worked, because a refusal that
    does not costs the caller a search through the source. There is one.
    """


class NotAKernel(Exception):
    """A supplied interpolation kernel cannot be the one on the die.

    The kernel is the one table here that no digest can settle, because nobody
    has dumped the interpolation ROM as a file: it circulates as a printed table
    of numbers. So a copy handed in is checked against what the part's own
    behaviour requires instead, and the message names the property that failed
    and what was seen, because "rejected" leaves a caller no way forward.
    """
