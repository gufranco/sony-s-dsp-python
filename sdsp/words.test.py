import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdsp import words


class ClampTest(unittest.TestCase):
    def test_clamping_holds_a_word_that_already_fits(self) -> None:
        # Arrange
        value = 1234

        # Act
        found = words.clamp16(value)

        # Assert
        self.assertEqual(found, 1234)

    def test_clamping_stops_at_the_top_of_the_range(self) -> None:
        # Arrange
        value = 0x9000

        # Act
        found = words.clamp16(value)

        # Assert
        self.assertEqual(found, 0x7FFF)

    def test_clamping_stops_at_the_bottom_of_the_range(self) -> None:
        # Arrange
        value = -0x9000

        # Act
        found = words.clamp16(value)

        # Assert
        self.assertEqual(found, -0x8000)


class SignedTest(unittest.TestCase):
    def test_a_byte_reads_as_signed(self) -> None:
        # Arrange
        values = (0x7F, 0x80)

        # Act
        found = [words.signed8(value) for value in values]

        # Assert
        self.assertEqual(found, [127, -128])

    def test_a_word_reads_as_signed(self) -> None:
        # Arrange
        values = (0x7FFF, 0x8000)

        # Act
        found = [words.signed16(value) for value in values]

        # Assert
        self.assertEqual(found, [32767, -32768])


if __name__ == "__main__":
    unittest.main()
