"""That the tables carried in source are the ones that were pinned.

A fetched document is refused when its digest does not match. Data that was never
published as a file cannot be fetched, so nothing was checking it, and an edit
that preserved the invariants in `sdsp/tables.py` changed what the model emits
with nothing to notice. The kernel is the sharpest case: it shapes every sample,
and no check that reads the manual can reach it.

The digest is of the values rather than of the source, so reformatting the module
leaves it alone and changing a number does not.
"""

import hashlib
import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sdsp import tables  # noqa: E402

HELD: dict[str, Any] = json.loads((ROOT / "conformance" / "carried.json").read_text())


def digest_of(values: Any) -> str:
    return hashlib.sha256(json.dumps(list(values), separators=(",", ":")).encode()).hexdigest()


class CarriedTableTest(unittest.TestCase):
    @property
    def entries(self) -> list[dict[str, Any]]:
        held: list[dict[str, Any]] = HELD["tables"]
        return held

    def test_every_pinned_table_is_the_table_that_was_pinned(self) -> None:
        wrong = [
            entry["name"]
            for entry in self.entries
            if digest_of(getattr(tables, entry["name"])) != entry["sha256"]
        ]

        self.assertEqual(wrong, [])

    def test_every_pinned_table_is_the_length_that_was_pinned(self) -> None:
        wrong = [
            entry["name"]
            for entry in self.entries
            if len(getattr(tables, entry["name"])) != entry["entries"]
        ]

        self.assertEqual(wrong, [])

    def test_a_changed_entry_is_caught(self) -> None:
        """The check nobody has seen fail, driven against a table that should fail it.

        The change is a sentinel rather than an arithmetic nudge, because these
        tables hold numbers in one member and rows of numbers in another and the
        check has to be the same in both.
        """
        first = self.entries[0]["name"]
        held = getattr(tables, first)
        bent = list(held)
        bent[0] = "changed"

        self.assertNotEqual(digest_of(bent), digest_of(held))

    def test_a_reordering_that_keeps_the_same_values_is_caught(self) -> None:
        """Symmetry and the sum survive a swap. The digest does not."""
        first = self.entries[0]["name"]
        held = getattr(tables, first)
        swapped = list(held)
        swapped[0], swapped[-1] = swapped[-1], swapped[0]

        self.assertNotEqual(digest_of(swapped), digest_of(held))

    def test_every_table_the_module_carries_is_pinned(self) -> None:
        """So a table added later is pinned rather than joining the unpinned quietly."""
        carried = {
            name
            for name in dir(tables)
            if name.isupper()
            and not name.startswith("_")
            and isinstance(getattr(tables, name), tuple)
        }
        pinned = {entry["name"] for entry in self.entries}

        self.assertEqual(carried - pinned, set())

    def test_the_record_says_what_a_digest_here_does_not_claim(self) -> None:
        """It pins what this package holds, never that the table is the part's."""
        self.assertIn("a claim that the table is correct", HELD["whatThisIsNot"].lower())

    def test_the_record_says_why_no_publisher_digest_exists(self) -> None:
        self.assertIn("publisher", HELD["notStated"])

    def test_the_kernel_names_the_open_question_it_belongs_to(self) -> None:
        kernel = next(entry for entry in self.entries if entry["name"] == "GAUSSIAN")

        self.assertEqual(kernel["openQuestion"], "gaussian-kernel-is-undocumented")


if __name__ == "__main__":
    unittest.main()
