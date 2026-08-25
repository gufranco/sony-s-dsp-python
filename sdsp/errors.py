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
