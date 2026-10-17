import builtins
import sys
import unittest
from pathlib import Path
from typing import ClassVar

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import quotes  # noqa: E402


class CitationTest(unittest.TestCase):
    def test_every_manufacturer_quote_names_a_page(self) -> None:
        # Arrange
        records = quotes.loaded()

        # Act
        found = quotes.unpaged(records)

        # Assert
        self.assertEqual(found, [])

    def test_a_record_that_quotes_without_a_page_is_reported(self) -> None:
        # Arrange
        given = [("made-up.json", {"facts": {"one": {"quote": "hello"}}})]

        # Act
        found = quotes.unpaged(given)

        # Assert
        self.assertEqual(found, ["made-up.json.facts.one.quote"])

    def test_but_not_when_the_quote_is_the_recording_speaking(self) -> None:
        # Arrange
        given = [("made-up.json", {"referenceDoes": {"quote": "hello"}})]

        # Act
        found = quotes.unpaged(given)

        # Assert
        self.assertEqual(found, [])

    def test_the_records_beside_this_file_are_the_ones_read(self) -> None:
        # Arrange
        expected = "hardware.json"

        # Act
        records = quotes.loaded()

        # Assert
        self.assertIn(expected, [name for name, _ in records])

    def test_a_page_key_says_where_the_quote_is(self) -> None:
        # Arrange
        given = {"page": 7}

        # Act
        found = quotes.pointed(given)

        # Assert
        self.assertTrue(found)

    def test_a_document_naming_a_section_says_it_too(self) -> None:
        # Arrange
        given = {"document": "W65C816S Data Sheet, 8.11.2"}

        # Act
        found = quotes.pointed(given)

        # Assert
        self.assertTrue(found)

    def test_but_naming_only_the_document_does_not(self) -> None:
        # Arrange
        given = {"document": "W65C816S Data Sheet"}

        # Act
        found = quotes.pointed(given)

        # Assert
        self.assertFalse(found)

    def test_a_quote_with_no_page_anywhere_above_it_is_reported(self) -> None:
        # Arrange
        given = {"quote": "hello"}

        # Act
        found = quotes.uncited(given)

        # Assert
        self.assertEqual(found, ["quote"])

    def test_a_page_beside_it_is_enough(self) -> None:
        # Arrange
        given = {"quote": "hello", "page": 7}

        # Act
        found = quotes.uncited(given)

        # Assert
        self.assertEqual(found, [])

    def test_and_a_page_on_the_object_above_counts_for_the_quotes_below(self) -> None:
        # Arrange
        given = {"page": 7, "inner": {"quote": "hello"}}

        # Act
        found = quotes.uncited(given)

        # Assert
        self.assertEqual(found, [])

    def test_a_quote_inside_a_list_is_reached(self) -> None:
        # Arrange
        given = [{"quote": "hello"}]

        # Act
        found = quotes.uncited(given)

        # Assert
        self.assertEqual(found, ["[0].quote"])

    def test_and_a_key_that_merely_ends_in_quote_is_held_to_the_same_rule(self) -> None:
        # Arrange
        given = {"vectorQuote": "hello"}

        # Act
        found = quotes.uncited(given)

        # Assert
        self.assertEqual(found, ["vectorQuote"])


class SectionTest(unittest.TestCase):
    def a_record(self, page: object, span: object = None) -> tuple[str, object]:
        document: dict[str, object] = {"title": "a book"}
        if span is not None:
            document["sectionPages"] = span
        fact: dict[str, object] = {"document": "book", "quote": "words"}
        if page is not None:
            fact["filePage"] = page
        return ("held.json", {"book": document, "facts": {"a": fact}})

    def test_a_page_inside_the_section_is_accepted(self) -> None:
        # Arrange
        given = [self.a_record(82, {"from": 76, "to": 99})]

        # Act
        found = quotes.sections(given)

        # Assert
        self.assertEqual(found, [])

    def test_a_page_outside_it_is_reported(self) -> None:
        # Arrange
        given = [self.a_record(105, {"from": 76, "to": 99})]

        # Act
        found = quotes.sections(given)

        # Assert
        self.assertEqual(len(found), 1)
        self.assertIn("outside the 76-99", found[0])

    def test_a_page_below_it_is_reported_too(self) -> None:
        # Arrange
        given = [self.a_record(12, {"from": 76, "to": 99})]

        # Act
        found = quotes.sections(given)

        # Assert
        self.assertIn("outside the 76-99", found[0])

    def test_the_first_and_last_pages_are_inside(self) -> None:
        # Arrange
        given = [self.a_record(page, {"from": 76, "to": 99}) for page in (76, 99)]

        # Act
        found = quotes.sections(given)

        # Assert
        self.assertEqual(found, [])

    def test_a_fact_naming_no_page_is_reported(self) -> None:
        # Arrange
        given = [self.a_record(None, {"from": 76, "to": 99})]

        # Act
        found = quotes.sections(given)

        # Assert
        self.assertIn("names no filePage", found[0])

    def test_a_document_declaring_no_range_is_single_part_and_exempt(self) -> None:
        # Arrange
        given = [self.a_record(None)]

        # Act
        found = quotes.sections(given)

        # Assert
        self.assertEqual(found, [])

    def test_several_ranges_are_accepted_for_a_part_the_book_returns_to(self) -> None:
        # Arrange
        spans = [{"from": 416, "to": 419}, {"from": 424, "to": 424}]
        given = [self.a_record(page, spans) for page in (417, 424)]

        # Act
        found = quotes.sections(given)

        # Assert
        self.assertEqual(found, [])

    def test_and_a_page_between_them_belongs_to_another_part(self) -> None:
        # Arrange
        spans = [{"from": 416, "to": 419}, {"from": 424, "to": 424}]

        # Act
        found = quotes.sections([self.a_record(421, spans)])

        # Assert
        self.assertIn("outside the 416-419, 424-424", found[0])

    def test_a_range_in_a_list_that_is_not_a_mapping_declares_nothing(self) -> None:
        # Arrange
        given = [self.a_record(None, ["416-419"])]

        # Act
        found = quotes.sections(given)

        # Assert
        self.assertEqual(found, [])

    def test_a_range_that_is_not_two_numbers_declares_nothing(self) -> None:
        # Arrange
        given = [self.a_record(None, {"from": "76", "to": 99})]

        # Act
        found = quotes.sections(given)

        # Assert
        self.assertEqual(found, [])

    def test_a_fact_citing_a_document_with_no_range_is_left_alone(self) -> None:
        # Arrange
        held = {
            "book": {"sectionPages": {"from": 76, "to": 99}},
            "other": {"title": "single part"},
            "facts": {"a": {"document": "other", "quote": "words"}},
        }

        # Act
        found = quotes.sections([("held.json", held)])

        # Assert
        self.assertEqual(found, [])

    def test_a_record_carrying_no_ranges_at_all_is_skipped(self) -> None:
        # Arrange
        held = {"facts": {"a": {"document": "book", "quote": "words"}}}

        # Act
        found = quotes.sections([("held.json", held)])

        # Assert
        self.assertEqual(found, [])

    def test_a_row_table_counts_as_a_fact_even_with_no_quote(self) -> None:
        # Arrange
        held = {
            "book": {"sectionPages": {"from": 76, "to": 99}},
            "facts": {"a": {"document": "book", "rows": [], "filePage": 105}},
        }

        # Act
        found = quotes.sections([("held.json", held)])

        # Assert
        self.assertIn("outside", found[0])

    def test_ranges_are_found_inside_a_list(self) -> None:
        # Arrange
        held = {
            "parts": [{"book": {"sectionPages": {"from": 1, "to": 2}}}],
            "facts": {"a": {"document": "book", "quote": "w", "filePage": 9}},
        }

        # Act
        found = quotes.sections([("held.json", held)])

        # Assert
        self.assertIn("outside the 1-2", found[0])

    def test_the_records_on_disk_all_land_in_their_own_section(self) -> None:
        # Arrange
        records = quotes.loaded()

        # Act
        found = quotes.sections(records)

        # Assert
        self.assertEqual(found, [])

    def test_a_fact_in_the_wrong_section_fails_the_run(self) -> None:
        # Arrange
        misplaced = ["a.json.facts.x: names file page 105, outside 76-99"]

        # Act
        code = quotes.main({}, [], misplaced)

        # Assert
        self.assertEqual(code, 1)

    def test_and_the_run_says_which_fact_it_was(self) -> None:
        # Arrange
        said: list[str] = []
        original = builtins.print
        builtins.print = lambda *args, **kwargs: said.append(" ".join(str(one) for one in args))

        # Act
        try:
            quotes.main({}, [], ["a.json.facts.x: names file page 105"])
        finally:
            builtins.print = original

        # Assert
        self.assertTrue(any("names file page 105" in line for line in said))


class DeclaredDocumentTest(unittest.TestCase):
    def a_record(self, cited: str, declared: object = None) -> tuple[str, object]:
        held: dict[str, object] = {"facts": {"a": {"document": cited, "quote": "words"}}}
        if declared is not None:
            held["documents"] = declared
        return ("held.json", held)

    def test_a_declared_key_is_accepted(self) -> None:
        # Arrange
        given = [self.a_record("book", {"book": {}})]

        # Act
        found = quotes.undeclared(given)

        # Assert
        self.assertEqual(found, [])

    def test_a_prose_title_is_reported(self) -> None:
        # Arrange
        given = [self.a_record("Some Data Sheet, 8.2", {"book": {}})]

        # Act
        found = quotes.undeclared(given)

        # Assert
        self.assertEqual(len(found), 1)
        self.assertIn("not a declared document", found[0])

    def test_a_bare_file_name_is_reported(self) -> None:
        # Arrange
        given = [self.a_record("manual.pdf", {"book": {}})]

        # Act
        found = quotes.undeclared(given)

        # Assert
        self.assertIn("not a declared document", found[0])

    def test_a_record_declaring_nothing_is_left_alone(self) -> None:
        # Arrange
        given = [self.a_record("anything at all")]

        # Act
        found = quotes.undeclared(given)

        # Assert
        self.assertEqual(found, [])

    def test_a_documents_block_nested_in_a_part_is_found(self) -> None:
        # Arrange
        held = {
            "parts": [{"documents": {"book": {}}}],
            "facts": {"a": {"document": "elsewhere", "quote": "w"}},
        }

        # Act
        found = quotes.undeclared([("held.json", held)])

        # Assert
        self.assertIn("not a declared document", found[0])

    def test_a_documents_block_that_is_not_a_mapping_declares_nothing(self) -> None:
        # Arrange
        given = [self.a_record("anything", ["book"])]

        # Act
        found = quotes.undeclared(given)

        # Assert
        self.assertEqual(found, [])

    def test_the_records_on_disk_all_cite_declared_documents(self) -> None:
        # Arrange
        records = quotes.loaded()

        # Act
        found = quotes.undeclared(records)

        # Assert
        self.assertEqual(found, [])


class AttributionTest(unittest.TestCase):
    def a_record(self, cited: str, quote: str) -> tuple[str, object]:
        return (
            "held.json",
            {
                "documents": {
                    "right": {"file": "right.pdf"},
                    "wrong": {"file": "wrong.pdf"},
                },
                "facts": {"a": {"document": cited, "quote": quote}},
            },
        )

    BOOKS: ClassVar[dict[str, str]] = {
        "right.pdf": quotes.flatten(
            "the quick brown fox jumps over the lazy dog and keeps running"
        ),
        "wrong.pdf": quotes.flatten("nothing here resembles the sentence above in any way at all"),
    }

    def test_a_quote_in_the_document_it_names_is_accepted(self) -> None:
        # Arrange
        given = [self.a_record("right", "the quick brown fox jumps over the lazy dog")]

        # Act
        found = quotes.misattributed(given, self.BOOKS)

        # Assert
        self.assertEqual(found, [])

    def test_a_quote_that_lives_in_another_document_is_reported(self) -> None:
        # Arrange
        given = [self.a_record("wrong", "the quick brown fox jumps over the lazy dog")]

        # Act
        found = quotes.misattributed(given, self.BOOKS)

        # Assert
        self.assertEqual(len(found), 1)
        self.assertIn("right.pdf", found[0])

    def test_a_quote_in_no_document_at_all_is_left_to_the_other_check(self) -> None:
        # Arrange
        given = [self.a_record("right", "a sentence that appears in neither of them anywhere")]

        # Act
        found = quotes.misattributed(given, self.BOOKS)

        # Assert
        self.assertEqual(found, [])

    def test_a_document_with_no_file_on_this_machine_is_skipped(self) -> None:
        # Arrange
        held = (
            "held.json",
            {
                "documents": {"right": {"file": "absent.pdf"}},
                "facts": {"a": {"document": "right", "quote": "the quick brown fox jumps"}},
            },
        )

        # Act
        found = quotes.misattributed([held], self.BOOKS)

        # Assert
        self.assertEqual(found, [])

    def test_a_record_declaring_no_files_is_left_alone(self) -> None:
        # Arrange
        held = ("held.json", {"facts": {"a": {"document": "x", "quote": "the quick brown fox"}}})

        # Act
        found = quotes.misattributed([held], self.BOOKS)

        # Assert
        self.assertEqual(found, [])

    def test_an_entry_saying_nothing_has_no_quote_to_place(self) -> None:
        # Arrange
        held = (
            "held.json",
            {
                "documents": {"right": {"file": "right.pdf"}},
                "facts": {
                    "a": {"document": "right", "quote": "nothing at all", "saysNothing": True}
                },
            },
        )

        # Act
        found = quotes.misattributed([held], self.BOOKS)

        # Assert
        self.assertEqual(found, [])

    def test_a_declared_document_naming_no_file_cannot_be_checked(self) -> None:
        # Arrange
        held = (
            "held.json",
            {
                "documents": {"right": {"file": "right.pdf"}, "paperOnly": {"title": "no file"}},
                "facts": {"a": {"document": "paperOnly", "quote": "the quick brown fox jumps"}},
            },
        )

        # Act
        found = quotes.misattributed([held], self.BOOKS)

        # Assert
        self.assertEqual(found, [])

    def test_the_records_on_disk_are_all_where_they_say_they_are(self) -> None:
        # Arrange
        records = quotes.loaded()

        # Act
        found = quotes.misattributed(records)

        # Assert
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
