import hashlib
import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sdsp  # noqa: E402

HELD: dict[str, Any] = json.loads((ROOT / "conformance" / "carried.json").read_text())


def digest_of(values: Any) -> str:
    return hashlib.sha256(json.dumps(list(values), separators=(",", ":")).encode()).hexdigest()


class CarriedTableTest(unittest.TestCase):
    @property
    def entries(self) -> list[dict[str, Any]]:
        held: list[dict[str, Any]] = HELD["tables"]
        return held

    def test_every_pinned_table_is_the_table_that_was_pinned(self) -> None:
        # Arrange
        entries = self.entries

        # Act
        wrong = [
            entry["name"]
            for entry in entries
            if digest_of(getattr(sdsp, entry["name"])) != entry["sha256"]
        ]

        # Assert
        self.assertEqual(wrong, [])

    def test_every_pinned_table_is_the_length_that_was_pinned(self) -> None:
        # Arrange
        entries = self.entries

        # Act
        wrong = [
            entry["name"]
            for entry in entries
            if len(getattr(sdsp, entry["name"])) != entry["entries"]
        ]

        # Assert
        self.assertEqual(wrong, [])

    def test_a_changed_entry_is_caught(self) -> None:
        # Arrange
        held = getattr(sdsp, self.entries[0]["name"])
        bent = [*held]
        bent[0] = "changed"

        # Act
        found = digest_of(bent)

        # Assert
        self.assertNotEqual(found, digest_of(held))

    def test_a_reordering_that_keeps_the_same_values_is_caught(self) -> None:
        # Arrange
        held = getattr(sdsp, self.entries[0]["name"])
        swapped = [held[-1], *held[1:-1], held[0]]

        # Act
        found = digest_of(swapped)

        # Assert
        self.assertNotEqual(found, digest_of(held))

    def test_every_table_the_package_exports_is_pinned(self) -> None:
        # Arrange
        pinned = {entry["name"] for entry in self.entries}

        # Act
        carried = {
            name
            for name in sdsp.__all__
            if name.isupper() and isinstance(getattr(sdsp, name), tuple)
        }

        # Assert
        self.assertEqual(carried - pinned, set())

    def test_the_record_says_what_a_digest_here_does_not_claim(self) -> None:
        # Arrange
        said = HELD["whatThisIsNot"]

        # Act
        found = said.lower()

        # Assert
        self.assertIn("a claim that the table is correct", found)

    def test_the_record_says_why_no_publisher_digest_exists(self) -> None:
        # Arrange
        said = HELD["notStated"]

        # Act
        found = "publisher" in said

        # Assert
        self.assertEqual(found, True)

    def test_the_kernel_names_the_open_question_it_belongs_to(self) -> None:
        # Arrange
        entries = self.entries

        # Act
        kernel = next(entry for entry in entries if entry["name"] == "GAUSSIAN")

        # Assert
        self.assertEqual(kernel["openQuestion"], "gaussian-kernel-is-undocumented")


if __name__ == "__main__":
    unittest.main()
